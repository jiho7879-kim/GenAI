"""Tests for the Query Rewriter Agent (no LLM / API dependencies)."""

from src.agents.query_rewriter import (
    QuestionType,
    RewrittenQuery,
    _expand_abbreviations,
    _extract_keywords,
    _parse_llm_response,
    rewrite_query,
)


class TestExpandAbbreviations:
    """_expand_abbreviations — domain abbreviation expansion."""

    def test_expands_tcad(self):
        result = _expand_abbreviations("TCAD calibration method")
        assert "technology computer-aided design" in result
        assert "technology cad" in result

    def test_expands_gaa(self):
        result = _expand_abbreviations("GAA FET structure")
        assert "gate-all-around" in result
        assert "gaafet" in result

    def test_returns_empty_for_unknown(self):
        result = _expand_abbreviations("hello world")
        assert result == []

    def test_case_insensitive(self):
        result_lower = _expand_abbreviations("tcad simulation")
        result_upper = _expand_abbreviations("TCAD simulation")
        assert result_lower == result_upper

    def test_expands_multiple_abbreviations(self):
        result = _expand_abbreviations("ML for TCAD")
        assert "machine learning" in result
        assert "technology computer-aided design" in result

    def test_does_not_expand_partial_match(self):
        # "cat" should not match "tcad"
        result = _expand_abbreviations("catalyst")
        assert "technology computer-aided design" not in result

    def test_empty_string(self):
        assert _expand_abbreviations("") == []


class TestExtractKeywords:
    """_extract_keywords — noise word removal without LLM."""

    def test_removes_english_noise(self):
        result = _extract_keywords("what is the TCAD calibration method")
        assert "tcad" in result
        assert "calibration" in result
        assert "method" in result
        assert "what" not in result
        assert "is" not in result
        assert "the" not in result

    def test_removes_korean_noise(self):
        result = _extract_keywords("TCAD 캘리브레이션 방법 설명해줘")
        assert "tcad" in result
        assert "캘리브레이션" in result
        assert "방법" in result
        assert "설명" not in result  # noise word removed

    def test_preserves_technical_terms(self):
        result = _extract_keywords("GAA FET threshold voltage")
        assert "gaa" in result
        assert "fet" in result
        assert "threshold" in result
        assert "voltage" in result

    def test_limits_to_10_keywords(self):
        result = _extract_keywords("A B C D E F G H I J K L M N O P Q R S T U V W X Y Z")
        assert len(result) <= 10

    def test_handles_empty_string(self):
        assert _extract_keywords("") == []

    def test_handles_only_noise(self):
        result = _extract_keywords("what is the of and for")
        assert result == []


class TestParseLLMResponse:
    """_parse_llm_response — JSON extraction from LLM output."""

    def test_plain_json(self):
        raw = '{"question_type": "methodology", "keywords": ["TCAD"]}'
        result = _parse_llm_response(raw)
        assert result == {"question_type": "methodology", "keywords": ["TCAD"]}

    def test_json_in_markdown_fence(self):
        raw = '```json\n{"question_type": "result", "keywords": ["mobility"]}\n```'
        result = _parse_llm_response(raw)
        assert result == {"question_type": "result", "keywords": ["mobility"]}

    def test_json_with_extra_text(self):
        raw = 'Here is my response:\n{"question_type": "theory", "keywords": ["physics"]}\nDone.'
        result = _parse_llm_response(raw)
        assert result == {"question_type": "theory", "keywords": ["physics"]}

    def test_invalid_json_returns_none(self):
        assert _parse_llm_response("not json") is None

    def test_empty_string_returns_none(self):
        assert _parse_llm_response("") is None

    def test_malformed_json_returns_none(self):
        assert _parse_llm_response("{broken json}") is None


class TestRewriteQuery:
    """rewrite_query — fallback behavior (no LLM dependency)."""

    def test_empty_query_returns_empty(self):
        result = rewrite_query("")
        assert result.is_fallback

    def test_whitespace_query_returns_empty(self):
        result = rewrite_query("   ")
        assert result.is_fallback

    def test_none_query_returns_empty(self):
        result = rewrite_query(None)  # type: ignore[arg-type]
        assert result.original == ""

    def test_fallback_extracts_keywords(self):
        # When Ollama is not running, rewrite_query falls back to _extract_keywords.
        # Keywords are still extracted — is_fallback checks for empty content,
        # not whether LLM was used.
        result = rewrite_query("what is the TCAD calibration method for GAA FET?")
        assert "tcad" in result.keywords
        assert "calibration" in result.keywords
        assert "gaa" in result.keywords
        assert "what" not in result.keywords

    def test_fallback_expands_abbreviations(self):
        result = rewrite_query("explain TCAD simulation setup")
        assert "technology computer-aided design" in result.expanded_terms

    def test_fallback_sets_general_type(self):
        result = rewrite_query("tell me about the paper")
        assert result.question_type == QuestionType.GENERAL


class TestRewrittenQuery:
    """RewrittenQuery dataclass behavior."""

    def test_default_values(self):
        q = RewrittenQuery(original="test")
        assert q.question_type == QuestionType.GENERAL
        assert q.keywords == []
        assert q.sub_queries == []
        assert q.expanded_terms == []
        assert q.hyde_snippet == ""

    def test_is_fallback_true_when_empty(self):
        q = RewrittenQuery(original="hello")
        assert q.is_fallback is True

    def test_is_fallback_false_with_keywords(self):
        q = RewrittenQuery(original="hello", keywords=["tcad"])
        assert q.is_fallback is False

    def test_is_fallback_false_with_sub_queries(self):
        q = RewrittenQuery(original="hello", sub_queries=["tcad calibration"])
        assert q.is_fallback is False

    def test_is_fallback_false_with_both(self):
        q = RewrittenQuery(
            original="hello",
            keywords=["tcad"],
            sub_queries=["tcad calibration"],
        )
        assert q.is_fallback is False
