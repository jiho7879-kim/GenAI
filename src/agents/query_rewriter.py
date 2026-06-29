"""
Query Rewriter Agent: Rewrites user questions to optimize RAG retrieval quality.

Strategies:
- **Query Decomposition**: Break complex questions into simpler sub-queries.
- **Keyword Extraction**: Remove question words, keep core technical terms.
- **Term Expansion**: Expand abbreviations and add domain synonyms.
- **HyDE**: Generate a hypothetical document snippet for embedding search.
- **Question Type Classification**: Route to retrieval + prompt strategy.

When the LLM is unavailable, falls back to basic keyword cleaning.
"""

import json
import logging
import re
from dataclasses import dataclass, field
from enum import StrEnum
from urllib import request as url_request
from urllib.error import URLError

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "qwen3.5:4b"
REWRITE_TIMEOUT = 15

# ── Question Types ────────────────────────────────────────────────────────


class QuestionType(StrEnum):
    METHODOLOGY = "methodology"
    RESULT = "result"
    THEORY = "theory"
    COMPARISON = "comparison"
    GENERAL = "general"


# ── Rewrite Result ────────────────────────────────────────────────────────


@dataclass
class RewrittenQuery:
    """Result of LLM query rewriting."""

    original: str
    question_type: QuestionType = QuestionType.GENERAL

    # Core keywords for direct retrieval
    keywords: list[str] = field(default_factory=list)

    # Decomposed sub-queries (for complex questions)
    sub_queries: list[str] = field(default_factory=list)

    # Expanded terms for synonym matching
    expanded_terms: list[str] = field(default_factory=list)

    # HyDE: hypothetical document snippet for embedding search
    hyde_snippet: str = ""

    @property
    def is_fallback(self) -> bool:
        return not self.keywords and not self.sub_queries


# ── Domain-specific abbreviation map (fast, no LLM needed) ────────────────

ABBREVIATION_MAP: dict[str, list[str]] = {
    "tcad": ["technology computer-aided design", "technology cad"],
    "gaa": ["gate-all-around", "gaafet", "gaa fet"],
    "fet": ["field-effect transistor"],
    "mosfet": ["metal-oxide-semiconductor field-effect transistor", "mos"],
    "cmos": ["complementary metal-oxide-semiconductor"],
    "bsim": ["berkeley short-channel igfet model"],
    "dd": ["drift-diffusion"],
    "mc": ["monte carlo"],
    "mcli": ["machine learning calibration"],
    "ai": ["artificial intelligence"],
    "ml": ["machine learning"],
    "ann": ["artificial neural network"],
    "dnn": ["deep neural network"],
    "cnn": ["convolutional neural network"],
    "rnn": ["recurrent neural network"],
    "gan": ["generative adversarial network"],
    "gpr": ["gaussian process regression"],
    "svm": ["support vector machine"],
    "pca": ["principal component analysis"],
    "sdevice": ["sdevice", "sentaurus device"],
    "sprocess": ["sprocess", "sentaurus process"],
    "lkl": ["langevin kinetics"],
    "fda": ["frequency domain analysis"],
    "tf": ["thin film", "transfer function"],
    "soi": ["silicon-on-insulator"],
    "finfet": ["fin field-effect transistor"],
    "tfet": ["tunnel field-effect transistor"],
    "hbm": ["hot carrier degradation", "hot carrier injection"],
    "nbti": ["negative bias temperature instability"],
    "pbti": ["positive bias temperature instability"],
    "rtn": ["random telegraph noise"],
    "srams": ["static random-access memory cells"],
    "ic": ["integrated circuit"],
    "vth": ["threshold voltage"],
    "gm": ["transconductance"],
    "gds": ["drain conductance", "output conductance"],
    "ss": ["subthreshold swing"],
    "ion": ["on-current", "drive current"],
    "ioff": ["off-current", "leakage current"],
}


def _expand_abbreviations(text: str) -> list[str]:
    """Expand known abbreviations/synonyms in the text."""
    text_lower = text.lower()
    expanded = set()
    for abbr, expansions in ABBREVIATION_MAP.items():
        if re.search(rf"\b{re.escape(abbr)}\b", text_lower):
            expanded.update(expansions)
    return sorted(expanded)


# ── Ollama helper (reuse from query_optimizer pattern) ────────────────────


def _ollama_generate(
    model: str = DEFAULT_MODEL,
    prompt: str = "",
    *,
    temperature: float = 0.1,
    num_predict: int = 512,
    timeout: int = REWRITE_TIMEOUT,
) -> str:
    body = json.dumps(
        {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": num_predict,
            },
        }
    ).encode()
    req = url_request.Request(
        f"{OLLAMA_BASE_URL}/api/generate",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    resp = url_request.urlopen(req, timeout=timeout)
    data = json.loads(resp.read())
    return (data.get("response") or "").strip()


# ── LLM Prompt ─────────────────────────────────────────────────────────────

QUERY_REWRITE_PROMPT = """You are a search query optimizer for a scientific RAG system.
Your task: rewrite the user's question to maximize retrieval accuracy from a paper library.

## Rules
1. Identify the QUESTION TYPE:
   - "methodology": asks about methods, approaches, techniques, calibration
   - "result": asks about experimental/simulation results, performance, metrics
   - "theory": asks for explanations of concepts, definitions, principles
   - "comparison": asks to compare/contrast multiple items or papers
   - "general": everything else

2. Extract CORE KEYWORDS (3-5 technical terms, remove question words).
   Example: "What is the TCAD calibration method for GAA FETs?"
   → ["TCAD calibration", "GAA FET", "methodology"]

3. For COMPLEX questions, DECOMPOSE into simpler sub-queries (max 3).
   Example: "Compare DD and MC transport in TCAD simulation"
   → ["drift-diffusion transport TCAD simulation", "Monte Carlo transport TCAD simulation"]

4. For questions asking about SPECIFIC topics, generate a HYPOTHETICAL DOCUMENT
   snippet (1-2 sentences) that would be the perfect retrieval result.
   This snippet should read like a real paper excerpt containing the answer.

5. Translate Korean questions to English keywords.

## Output format
Return ONLY a JSON object, nothing else:
{{
  "question_type": "methodology|result|theory|comparison|general",
  "keywords": ["keyword1", "keyword2", ...],
  "sub_queries": ["sub-query1", ...],
  "hyde_snippet": "A hypothetical text that would perfectly answer this question...",
  "reasoning": "brief explanation of your choices"
}}

## Examples

Input: "Explain the TCAD calibration method for GAA FET devices"
Output: {{
  "question_type": "methodology",
  "keywords": ["TCAD calibration", "GAA FET", "calibration methodology"],
  "sub_queries": ["TCAD calibration procedure", "GAA FET device simulation calibration"],
  "hyde_snippet": "The TCAD calibration for GAA FET devices involves matching I-V characteristics through iterative adjustment of doping profiles, mobility parameters, and contact resistances using Sentaurus TCAD mixed-mode simulation.",
  "reasoning": "Methodology question about calibration. Extracted core technical terms and generated a realistic calibration description snippet."
}}

## Input
User question: {user_question}
"""


# ── Rewrite function ──────────────────────────────────────────────────────


def rewrite_query(user_question: str) -> RewrittenQuery:
    """Rewrite a user question to optimize RAG retrieval.

    Uses LLM-based rewriting with fallback to keyword cleaning.
    """
    if not user_question or not user_question.strip():
        return RewrittenQuery(original=user_question or "")

    text = user_question.strip()

    # Expand abbreviations first (fast, no LLM)
    expanded_terms = _expand_abbreviations(text)
    logger.info("Expanded terms for '%s': %s", text[:40], expanded_terms)

    # Try LLM-based rewriting
    try:
        prompt = QUERY_REWRITE_PROMPT.format(user_question=text)
        raw = _ollama_generate(prompt=prompt, num_predict=512, timeout=REWRITE_TIMEOUT)
        parsed = _parse_llm_response(raw)

        if parsed and parsed.get("keywords"):
            qtype_str = parsed.get("question_type", "general")
            try:
                qtype = QuestionType(qtype_str)
            except ValueError:
                qtype = QuestionType.GENERAL

            rewritten = RewrittenQuery(
                original=text,
                question_type=qtype,
                keywords=parsed.get("keywords", []),
                sub_queries=parsed.get("sub_queries", []),
                expanded_terms=expanded_terms,
                hyde_snippet=parsed.get("hyde_snippet", ""),
            )
            logger.info(
                "Query rewritten: type=%s, keywords=%s, sub_queries=%d",
                qtype,
                rewritten.keywords[:3],
                len(rewritten.sub_queries),
            )
            return rewritten
    except (URLError, OSError, json.JSONDecodeError, ValueError) as exc:
        logger.warning("LLM query rewrite failed: %s — using fallback", exc)

    # Fallback: basic keyword extraction
    keywords = _extract_keywords(text)
    return RewrittenQuery(
        original=text,
        question_type=QuestionType.GENERAL,
        keywords=keywords,
        expanded_terms=expanded_terms,
    )


# ── Internal helpers ──────────────────────────────────────────────────────


def _parse_llm_response(raw: str) -> dict | None:
    """Extract JSON from LLM response, tolerating markdown fences."""
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    text = text.strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        return None


def _extract_keywords(text: str) -> list[str]:
    """Extract meaningful keywords from text without LLM."""
    noise = {
        "what",
        "is",
        "are",
        "the",
        "does",
        "do",
        "can",
        "how",
        "why",
        "explain",
        "describe",
        "tell",
        "me",
        "about",
        "show",
        "find",
        "search",
        "give",
        "list",
        "compare",
        "contrast",
        "analyze",
        "summarize",
        "please",
        "i",
        "want",
        "to",
        "know",
        "regarding",
        "regards",
        "this",
        "that",
        "these",
        "those",
        "papers",
        "paper",
        "in",
        "of",
        "for",
        "on",
        "with",
        "by",
        "from",
        "between",
        "among",
        "using",
        "based",
        "and",
        "or",
        "but",
        "not",
        "있",
        "없",
        "찾",
        "알려",
        "설명",
        "논문",
        "보고서",
        "분석",
        "비교",
        "요약",
        "정리",
        "것",
        "수",
        "있을까",
        "알고",
        "싶",
        "하는",
        "대해",
        "관련",
        "통해",
    }
    # Tokenize and filter
    text_lower = text.lower()
    tokens = re.findall(r"[a-zA-Z가-힣][a-zA-Z가-힣0-9\-\.]+", text_lower)
    keywords = [t for t in tokens if t not in noise and len(t) > 1]
    # Remove duplicates while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for kw in keywords:
        if kw not in seen:
            seen.add(kw)
            unique.append(kw)
    return unique[:10]
