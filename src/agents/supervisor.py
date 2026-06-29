"""
Supervisor Agent: Classifies user intent and routes to the appropriate specialist agent.

Intent categories:
- "paper": Questions about already-ingested papers (RAG Q&A, summarization)
- "search": Search for new papers on Arxiv
- "report": Generate a comprehensive report combining multiple sources

Classification uses Ollama LLM for natural language understanding (handles
Korean, English, and mixed queries without keyword maintenance), with
keyword-based fallback if the LLM is unavailable.
"""

import logging
import re
from typing import Literal
from urllib import request as url_request
from urllib.error import URLError

from langchain_ollama import OllamaLLM

from src.agents.query_optimizer import OptimizedQuery, optimize_query
from src.rag_chain import MODEL_FAST

logger = logging.getLogger(__name__)

# Available intents
IntentType = Literal["paper", "search", "report", "unknown"]

# ---------------------------------------------------------------------------
# Keyword-based classification (instant, no LLM dependency)
# ---------------------------------------------------------------------------

_PAPER_KEYWORDS = [
    # Korean
    "요약",
    "summary",
    "작성",
    "설명",
    "분석",
    "해석",
    "내용",
    "논문",
    "챕터",
    "부분",
    "이해",
    "알려줘",
    "뭐라고",
    "무엇",
    "어떻게",
    # English
    "summarize",
    "summary",
    "what does",
    "what is",
    "explain",
    "tell me about",
    "describe",
    "of this paper",
    "in the paper",
    "from the paper",
    "according to",
    "mentioned",
    "section",
    "chapter",
    "page",
    "chunk",
    "document",
    "uploaded",
    "ingestion",
    # Hybrid / common patterns
    "about",
    "meaning",
    "implication",
    "conclusion",
]

_SEARCH_KEYWORDS = [
    # Korean
    "찾아",
    "검색",
    "찾아줘",
    "찾아봐",
    "검색해",
    "찾는",
    "관련 논문",
    "새로운",
    "논문 검색",
    # English
    "search",
    "find",
    "look for",
    "look up",
    "find papers",
    "find articles",
    "search for",
    "search papers",
    "recent",
    "latest",
    "new papers",
    "related work",
]

_REPORT_KEYWORDS = [
    # Korean
    "보고서",
    "레포트",
    "정리",
    "종합",
    "요약서",
    "리포트",
    "문서화",
    "리뷰 작성",
    # English
    "report",
    "literature review",
    "lit review",
    "comprehensive",
    "overview",
    "survey",
    "synthesis",
    "write a",
    "draft",
]

# Patterns that should be word-boundary matched to avoid substring false positives
_ENGLISH_WORDS = {
    "find",
    "about",
    "search",
    "report",
    "summarize",
    "paper",
    "recent",
    "latest",
}


def _word_in_text(word: str, text: str) -> bool:
    """Check if a word appears in text with word boundaries."""
    return bool(re.search(rf"\b{re.escape(word)}\b", text))


def _has_kw(text: str, kw: str) -> bool:
    """Check if keyword appears in text. Uses word boundaries for English words."""
    kw_lower = kw.lower()
    if kw_lower in _ENGLISH_WORDS:
        return _word_in_text(kw_lower, text)
    return kw_lower in text


def _keyword_classify(text: str) -> IntentType:
    """Classify intent by keyword matching. Returns one of paper/search/report/unknown."""
    text_lower = text.lower().strip()

    scores = {"paper": 0, "search": 0, "report": 0}

    # Count keyword hits
    for kw in _PAPER_KEYWORDS:
        if _has_kw(text_lower, kw):
            scores["paper"] += 1
    for kw in _SEARCH_KEYWORDS:
        if _has_kw(text_lower, kw):
            scores["search"] += 1
    for kw in _REPORT_KEYWORDS:
        if _has_kw(text_lower, kw):
            scores["report"] += 1

    # Negative penalties to disambiguate
    for kw in ["찾아", "검색", "search"]:
        if _has_kw(text_lower, kw):
            scores["paper"] = max(0, scores["paper"] - 2)
    for kw in ["요약", "설명해", "분석", "알려줘"]:
        if _has_kw(text_lower, kw):
            scores["search"] = max(0, scores["search"] - 2)

    # Select best intent
    best = max(scores, key=scores.get)
    best_score = scores[best]

    # Require at least 1 hit to classify
    if best_score <= 0:
        return "unknown"

    # If there's a tie, check confidence
    sorted_scores = sorted(scores.values(), reverse=True)
    if len(sorted_scores) >= 2 and sorted_scores[0] == sorted_scores[1]:
        return "unknown"

    return best


# ---------------------------------------------------------------------------
# LLM classification prompt (used before keyword fallback)
# ---------------------------------------------------------------------------

_CLASSIFY_PROMPT = """You are a classifier for a research paper assistant. Categorize the user's request into exactly one of:

paper: User is asking about papers they have already uploaded/ingested — Q&A, summarization, explanation, analysis of their paper library.
search: User wants to find NEW papers on Arxiv or the web — looking for papers/articles they haven't ingested yet.
report: User wants a comprehensive written report, literature review, or synthesis combining multiple sources.
unknown: Greeting, small talk, off-topic, or doesn't clearly fit any category.

Reply with ONLY one word: paper, search, report, or unknown.

Examples:
User: 이 논문의 주요 결과를 설명해줘
Answer: paper
User: Find recent papers on GAA FET simulation
Answer: search
User: 내 논문들에서 TCAD 캘리브레이션 방법론을 비교 분석해줘
Answer: paper
User: Write a literature review on ML methods in TCAD
Answer: report
User: Search for new papers about semiconductor device modeling
Answer: search
User: hello
Answer: unknown
User: 각 paper별 summary를 한글로 작성해줘
Answer: paper
User: GAA 구조에 대해 설명해줘
Answer: paper

Now classify. Reply with ONLY one word.
User: {query}
Answer:"""


# ---------------------------------------------------------------------------
# Supervisor agent
# ---------------------------------------------------------------------------


class SupervisorAgent:
    """Intent classifier and router for the research assistant."""

    @staticmethod
    def check_ollama() -> tuple:
        """
        Check if Ollama server is accessible.

        Returns:
            Tuple of (ok: bool, message: str).
        """
        try:
            req = url_request.Request("http://localhost:11434/api/tags", method="GET")
            url_request.urlopen(req, timeout=3)
            return True, "Ollama connected"
        except URLError:
            return False, (
                "Ollama 서버에 연결할 수 없습니다 (localhost:11434).\n\n"
                "터미널에서 다음 명령어로 Ollama를 실행해주세요:\n"
                "    ollama serve\n\n"
                "또는 Ollama 앱이 설치되어 있다면 바탕화면/시작메뉴에서 실행하세요."
            )

    def __init__(self, model_name: str = None):
        self.model_name = model_name or MODEL_FAST
        self._llm = None

    def _get_llm(self):
        """Lazy-init OllamaLLM for intent classification."""
        if self._llm is None:
            try:
                self._llm = OllamaLLM(
                    model=self.model_name,
                    temperature=0,
                    num_predict=16,
                )
            except Exception as e:
                logger.warning("Failed to init OllamaLLM for classification: %s", e)
        return self._llm

    def _llm_classify(self, text: str) -> IntentType | None:
        """Classify intent via LLM. Returns None if unavailable or fails."""
        llm = self._get_llm()
        if llm is None:
            return None
        try:
            raw = llm.invoke(_CLASSIFY_PROMPT.format(query=text)).strip().lower()
            if raw in ("paper", "search", "report", "unknown"):
                return raw
            logger.warning("LLM returned unrecognized intent: '%s'", raw)
            return None
        except Exception as e:
            logger.warning("LLM classification failed: %s", e)
            return None

    @property
    def llm(self):
        """Kept for compatibility — returns the underlying OllamaLLM instance."""
        return self._get_llm()

    def classify(self, user_input: str) -> IntentType:
        """
        Classify the user's request using LLM, falling back to keywords.

        Args:
            user_input: The user's raw text input.

        Returns:
            One of: "paper", "search", "report", "unknown"
        """
        if not user_input or not user_input.strip():
            return "unknown"

        intent = self._llm_classify(user_input)
        if intent is not None:
            logger.info(f"Intent: '{intent}' (LLM) from: '{user_input[:80]}...'")
            return intent

        intent = _keyword_classify(user_input)
        logger.info(f"Intent: '{intent}' (keyword fallback) from: '{user_input[:80]}...'")
        return intent

    def route(self, user_input: str) -> tuple:
        """
        Classify intent and extract relevant parameters.

        For search intents, the raw query is optimized via LLM for arXiv API syntax.
        For other intents, the query is returned as-is with basic cleaning.

        Args:
            user_input: The user's raw text input.

        Returns:
            Tuple of (intent, cleaned_query).
            - cleaned_query: For "search" intent, the arXiv-optimized query string.
              For other intents, the user input with routing prefixes removed.
        """
        intent = self.classify(user_input)

        if intent == "search":
            optimized: OptimizedQuery = optimize_query(user_input)
            logger.info(
                "Search query optimized: '%s' → '%s' (fallback=%s, cats=%s)",
                optimized.original[:60],
                optimized.final_query[:80],
                optimized.is_fallback,
                optimized.categories,
            )
            return intent, optimized.final_query

        return intent, user_input.strip()
