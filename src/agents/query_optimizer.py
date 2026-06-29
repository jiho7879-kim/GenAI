"""
Query Optimizer Agent: Rewrites raw user queries into Arxiv-optimized search queries.

Uses a local Ollama LLM to:
- Detect language (Korean → English translation)
- Extract key technical terms and remove noise words
- Build Arxiv query syntax (AND, OR, ti:, cat:, quotes for phrases)
- Infer relevant arXiv categories from context

When the LLM is unavailable or times out, the original query is returned as-is
so the caller always gets a usable query string.
"""

import json
import logging
import re
from enum import StrEnum
from urllib import request as url_request
from urllib.error import URLError

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "qwen3.5:4b"
QUERY_TIMEOUT = 15  # seconds — LLM should respond fast for a short rewrite

# ── arXiv category mappings for TCAD / semiconductor domain ──────────────

DOMAIN_CATEGORIES: dict[str, list[str]] = {
    "TCAD": ["physics.app-ph", "cond-mat.mtrl-sci"],
    "device": ["physics.app-ph", "cond-mat.mes-hall", "cond-mat.mtrl-sci"],
    "machine_learning": ["cs.LG", "cs.AI", "stat.ML"],
    "semiconductor": ["cond-mat.mtrl-sci", "physics.app-ph"],
    "materials": ["cond-mat.mtrl-sci", "cond-mat.mes-hall"],
    "circuits": ["cs.AR", "cs.ET"],
    "physics": ["physics.app-ph", "physics.ins-det"],
}

ALL_TCAD_CATEGORIES = sorted({cat for cats in DOMAIN_CATEGORIES.values() for cat in cats})

# ── Query Rewrite Result ─────────────────────────────────────────────────


class QueryType(StrEnum):
    GENERAL = "general"
    TITLE = "title"
    AUTHOR = "author"
    CATEGORY = "category"
    DATE_RANGE = "date_range"


class OptimizedQuery:
    """Result of LLM query optimization."""

    def __init__(
        self,
        optimized: str,
        original: str,
        query_type: QueryType = QueryType.GENERAL,
        categories: list[str] | None = None,
        language: str = "en",
    ):
        self.optimized = optimized
        self.original = original
        self.query_type = query_type
        self.categories = categories or []
        self.language = language

    @property
    def final_query(self) -> str:
        """Return the final query string to send to the Arxiv API."""
        return self.optimized

    @property
    def is_fallback(self) -> bool:
        """True if the optimizer fell back to the original query."""
        return self.optimized == self.original


# ── Ollama helper (mirrors the pattern in arxiv_agent.py) ────────────────


def _ollama_generate(
    model: str = DEFAULT_MODEL,
    prompt: str = "",
    *,
    temperature: float = 0.1,
    num_predict: int = 512,
    timeout: int = QUERY_TIMEOUT,
) -> str:
    """Call Ollama /api/generate and return the response text."""
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


# ── LLM Prompt ───────────────────────────────────────────────────────────

QUERY_OPTIMIZER_PROMPT = """You are a search query optimizer for arXiv, a scientific paper repository.

Your job: rewrite the user's search request into an arXiv API query string that will return RELEVANT results.

## Rules
1. Translate Korean or other non-English queries to English keywords.
2. Remove filler words like "찾아줘", "검색해", "search for", "find papers about", "latest", "recent", "논문", etc.
3. Keep important technical terms, acronyms, and proper nouns exactly as-is.
4. Use arXiv syntax when helpful:
   - `ti:"exact phrase"` for title-specific terms
   - `AND` between distinct concepts
   - `OR` between synonyms or alternatives
   - `cat:cs.LG` to restrict to a category (use ONLY the categories listed below)
5. For simple 1-2 word queries, just return the cleaned keywords WITHOUT any field prefixes.

## Allowed arXiv categories (TCAD/semiconductor/ML domain)
{category_list}

## Output format
Return ONLY a JSON object with these fields, nothing else:
{{
  "query": "the optimized arXiv query string",
  "categories": ["cat1", "cat2"],
  "language": "ko" or "en",
  "notes": "brief reasoning"
}}

## Examples

Input: "GAA FET 최신 논문 찾아줘"
Output: {{"query": "ti:\\"gate-all-around FET\\" OR ti:\\"GAA FET\\"", "categories": ["cond-mat.mtrl-sci", "physics.app-ph"], "language": "ko", "notes": "Translated Korean query, restricted to device categories"}}

Input: "TCAD machine learning calibration methods"
Output: {{"query": "ti:TCAD AND ti:calibration AND (cat:physics.app-ph OR cat:cs.LG)", "categories": ["physics.app-ph", "cs.LG"], "language": "en", "notes": "Title-specific terms with category restriction"}}

Input: "Transformer attention mechanism"
Output: {{"query": "Transformer attention mechanism", "categories": ["cs.LG", "cs.AI"], "language": "en", "notes": "General search, added ML categories"}}

Input: "What is the latest research on GAA FET?"
Output: {{"query": "ti:\\"GAA FET\\" OR ti:\\"gate-all-around FET\\"", "categories": ["cond-mat.mtrl-sci"], "language": "en", "notes": "Removed question words, focused on technical terms"}}

## Input
User query: {user_query}
"""


# ── Optimizer ─────────────────────────────────────────────────────────────


def optimize_query(user_query: str) -> OptimizedQuery:
    """
    Rewrite a user's natural-language search request into an Arxiv-optimized query.

    Falls back to the cleaned original query if the LLM call fails or times out,
    ensuring the caller always receives a usable string.
    """
    if not user_query or not user_query.strip():
        return OptimizedQuery(
            optimized="",
            original=user_query or "",
            query_type=QueryType.GENERAL,
        )

    query_stripped = user_query.strip()

    # ── Try LLM-based optimization ────────────────────────────────────
    try:
        category_hint = ", ".join(ALL_TCAD_CATEGORIES)
        prompt = QUERY_OPTIMIZER_PROMPT.format(
            user_query=query_stripped,
            category_list=category_hint,
        )

        raw = _ollama_generate(prompt=prompt, num_predict=512, timeout=QUERY_TIMEOUT)
        parsed = _parse_llm_response(raw)

        if parsed and parsed.get("query"):
            categories = parsed.get("categories", [])
            lang = parsed.get("language", "en")
            logger.info(
                "Query optimized: '%s' -> '%s' (lang=%s, cats=%s)",
                query_stripped[:60],
                parsed["query"][:80],
                lang,
                categories,
            )
            return OptimizedQuery(
                optimized=parsed["query"],
                original=query_stripped,
                query_type=_detect_query_type(parsed["query"]),
                categories=categories,
                language=lang,
            )
    except (URLError, OSError, json.JSONDecodeError, ValueError) as exc:
        logger.warning("LLM query optimization failed: %s — using fallback", exc)

    # ── Fallback: clean the original query ────────────────────────────
    fallback = _basic_clean(query_stripped)
    logger.info("Query optimizer fallback: '%s' -> '%s'", query_stripped[:60], fallback[:80])
    return OptimizedQuery(
        optimized=fallback,
        original=query_stripped,
        query_type=QueryType.GENERAL,
    )


# ── Internal helpers ──────────────────────────────────────────────────────


def _parse_llm_response(raw: str) -> dict | None:
    """Extract JSON from the LLM response, tolerating markdown fences."""
    text = raw.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    text = text.strip()

    # Try to find a JSON object in the response
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        return None


def _basic_clean(query: str) -> str:
    """Clean a query without LLM: remove noise words, extract keywords."""
    # Common noise patterns (Korean + English)
    noise_patterns = [
        r"\b찾아줘\b",
        r"\b찾아봐\b",
        r"\b검색해\b",
        r"\b검색\b",
        r"\b논문\b",
        r"\b알려줘\b",
        r"\b찾는\b",
        r"\b관련\b",
        r"\bsearch\s+for\b",
        r"\bfind\s+papers\b",
        r"\bfind\s+articles\b",
        r"\blook\s+for\b",
        r"\blook\s+up\b",
        r"\bsearch\s+papers\b",
        r"\bsearch\s+for\b",
        r"\bwhat\s+is\b",
        r"\bwhat\s+are\b",
        r"\btell\s+me\b",
        r"\bshow\s+me\b",
        r"\bi\s+want\b",
        r"\bcan\s+you\b",
        r"\bpl(?:e)?a?s?e\b",
        r"\babout\b",
        r"\bpapers\b",
        r"\barticles\b",
        r"\blatest\b",
        r"\brecent\b",
        r"\bnew\b",
        r"\bon\s+arxiv\b",
        r"\bin\s+arxiv\b",
        r"\bthe\b",
        r"\ba\b",
        r"\ban\b",
    ]
    cleaned = query.lower()
    for pat in noise_patterns:
        cleaned = re.sub(pat, "", cleaned)
    # Collapse whitespace
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    # If everything was noise, return original
    if not cleaned:
        return query.strip()
    return cleaned


def _detect_query_type(query: str) -> QueryType:
    """Heuristically detect query type from the optimized query string."""
    if query.startswith("au:") or " au:" in query:
        return QueryType.AUTHOR
    if query.startswith("ti:") or " ti:" in query:
        return QueryType.TITLE
    if "cat:" in query:
        return QueryType.CATEGORY
    if "submittedDate" in query or "[" in query:
        return QueryType.DATE_RANGE
    return QueryType.GENERAL
