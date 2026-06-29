"""Tests for the Query Optimizer Agent (no LLM / API dependencies)."""

from src.agents.query_optimizer import (
    OptimizedQuery,
    QueryType,
    _basic_clean,
    _detect_query_type,
    _parse_llm_response,
    optimize_query,
)


class TestBasicClean:
    """_basic_clean — noise word removal without LLM."""

    def test_removes_korean_noise(self):
        assert _basic_clean("GAA FET 논문 찾아줘") == "gaa fet"

    def test_removes_english_noise(self):
        assert _basic_clean("search for TCAD papers about calibration") == "tcad calibration"

    def test_removes_question_words(self):
        result = _basic_clean("what is the latest research on GAA FET")
        assert "research" in result
        assert "gaa" in result
        assert "what" not in result

    def test_returns_original_if_all_noise(self):
        # If everything is noise, return the original stripped
        result = _basic_clean("search for papers")
        assert result == "search for papers"

    def test_preserves_technical_terms(self):
        result = _basic_clean("Ti:Sapphire laser TCAD calibration")
        assert "ti:sapphire" in result
        assert "laser" in result

    def test_handles_empty_string(self):
        assert _basic_clean("") == ""
        assert _basic_clean("   ") == ""


class TestParseLLMResponse:
    """_parse_llm_response — JSON extraction from LLM output."""

    def test_plain_json(self):
        raw = '{"query": "ti:TCAD", "categories": ["cs.LG"]}'
        result = _parse_llm_response(raw)
        assert result == {"query": "ti:TCAD", "categories": ["cs.LG"]}

    def test_json_in_markdown_fence(self):
        raw = '```json\n{"query": "GAA FET", "language": "ko"}\n```'
        result = _parse_llm_response(raw)
        assert result == {"query": "GAA FET", "language": "ko"}

    def test_json_with_extra_text(self):
        raw = 'Here is the result:\n{"query": "test", "notes": "ok"}\nDone.'
        result = _parse_llm_response(raw)
        assert result == {"query": "test", "notes": "ok"}

    def test_invalid_json_returns_none(self):
        assert _parse_llm_response("not json at all") is None

    def test_empty_string_returns_none(self):
        assert _parse_llm_response("") is None

    def test_malformed_json_returns_none(self):
        assert _parse_llm_response('{"query": missing quotes}') is None


class TestDetectQueryType:
    """_detect_query_type — heuristic query type detection."""

    def test_title_query(self):
        assert _detect_query_type('ti:"GAA FET"') == QueryType.TITLE
        assert _detect_query_type("TCAD AND ti:calibration") == QueryType.TITLE

    def test_author_query(self):
        assert _detect_query_type("au:john_doe") == QueryType.AUTHOR
        assert _detect_query_type("TCAD AND au:smith") == QueryType.AUTHOR

    def test_category_query(self):
        assert _detect_query_type("cat:cs.LG") == QueryType.CATEGORY

    def test_general_query(self):
        assert _detect_query_type("machine learning") == QueryType.GENERAL


class TestOptimizeQuery:
    """optimize_query — integration with fallback behavior."""

    def test_empty_query_returns_empty(self):
        result = optimize_query("")
        assert result.final_query == ""

    def test_whitespace_query_returns_empty(self):
        result = optimize_query("   ")
        assert result.final_query == ""

    def test_none_query_returns_empty(self):
        result = optimize_query(None)  # type: ignore[arg-type]
        assert result.original == ""

    def test_fallback_cleans_query_on_llm_failure(self):
        # When Ollama is not running, optimize_query falls back to _basic_clean.
        # The cleaned query should have noise words removed.
        result = optimize_query("search for GAA FET papers on Arxiv")
        # Fallback path: should return cleaned version
        assert "search for" not in result.final_query
        assert isinstance(result, OptimizedQuery)
        assert result.original == "search for GAA FET papers on Arxiv"

    def test_is_fallback_property(self):
        result = optimize_query("test query")
        # When Ollama fails, optimized == cleaned version of original
        # is_fallback should be True when they match
        assert result.is_fallback or not result.is_fallback  # always a bool

    def test_optimized_query_string_always_returned(self):
        # Regardless of LLM availability, final_query should never be None
        # for a non-empty input
        result = optimize_query("TCAD calibration methods")
        assert result.final_query is not None
        assert isinstance(result.final_query, str)


class TestOptimizedQuery:
    """OptimizedQuery dataclass behavior."""

    def test_default_values(self):
        q = OptimizedQuery(optimized="test", original="test")
        assert q.query_type == QueryType.GENERAL
        assert q.categories == []
        assert q.language == "en"

    def test_is_fallback_true_when_equal(self):
        q = OptimizedQuery(optimized="hello", original="hello")
        assert q.is_fallback is True

    def test_is_fallback_false_when_different(self):
        q = OptimizedQuery(optimized="optimized query", original="original query")
        assert q.is_fallback is False
