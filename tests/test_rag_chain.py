"""Tests for the RAG Chain — retrieval, fusion, and question classification."""

from langchain_core.documents import Document

from src.rag_chain import (
    _TYPE_TO_PROMPT,
    PROMPT_COMPARISON,
    PROMPT_GENERAL,
    PROMPT_METHODOLOGY,
    PROMPT_RESULT,
    PROMPT_THEORY,
    _detect_question_type,
    _expand_query_terms,
    _generate_sub_queries,
    _rrf_fusion,
)


class TestDetectQuestionType:
    """_detect_question_type — keyword-based question classification."""

    def test_methodology_keywords(self):
        assert _detect_question_type("Explain the calibration method") == "methodology"
        assert _detect_question_type("How does the simulation setup work?") == "methodology"
        assert _detect_question_type("What approach was used for TCAD?") == "methodology"

    def test_result_keywords(self):
        assert _detect_question_type("What results were achieved?") == "result"
        assert _detect_question_type("Show the performance metrics") == "result"
        assert _detect_question_type("What accuracy was achieved?") == "result"

    def test_theory_keywords(self):
        assert _detect_question_type("What is the principle behind TCAD?") == "theory"
        assert _detect_question_type("Define threshold voltage") == "theory"
        assert _detect_question_type("Explain the physics of GAA FET") == "theory"

    def test_comparison_keywords(self):
        assert _detect_question_type("Compare DD and MC transport") == "comparison"
        assert _detect_question_type("What is the difference between A and B?") == "comparison"
        assert _detect_question_type("Which approach is better?") == "comparison"

    def test_general_when_no_keywords_match(self):
        assert _detect_question_type("Tell me about the paper") == "general"
        assert _detect_question_type("Hello") == "general"
        assert _detect_question_type("") == "general"

    def test_korean_methodology(self):
        assert _detect_question_type("TCAD 캘리브레이션 방법 설명") == "methodology"

    def test_korean_result(self):
        assert _detect_question_type("실험 결과 알려줘") == "result"

    def test_korean_theory(self):
        assert _detect_question_type("원리를 설명해줘") == "theory"

    def test_korean_comparison(self):
        assert _detect_question_type("두 방법 차이점 비교") == "comparison"


class TestExpandQueryTerms:
    """_expand_query_terms — abbreviation expansion in queries."""

    def test_expands_tcad(self):
        result = _expand_query_terms("TCAD simulation")
        assert any("technology computer-aided" in q for q in result)

    def test_keeps_original_first(self):
        result = _expand_query_terms("GAA FET")
        assert result[0] == "GAA FET"

    def test_expands_multiple_abbreviations(self):
        result = _expand_query_terms("ML for TCAD")
        assert any("machine learning" in q.lower() for q in result)
        assert any("technology computer-aided" in q.lower() for q in result)

    def test_no_expansion_for_unknown(self):
        result = _expand_query_terms("hello world")
        assert len(result) == 1
        assert result[0] == "hello world"

    def test_empty_string(self):
        result = _expand_query_terms("")
        assert result == [""]


class TestGenerateSubQueries:
    """_generate_sub_queries — multi-query generation by question type."""

    def test_original_query_included(self):
        result = _generate_sub_queries("TCAD calibration", "general")
        assert "TCAD calibration" in result

    def test_methodology_adds_focused_queries(self):
        result = _generate_sub_queries("calibration", "methodology")
        assert any("method calibration" in q for q in result)
        assert any("approach calibration" in q for q in result)

    def test_result_adds_focused_queries(self):
        result = _generate_sub_queries("mobility", "result")
        assert any("result mobility" in q for q in result)
        assert any("performance mobility" in q for q in result)

    def test_theory_adds_focused_queries(self):
        result = _generate_sub_queries("TCAD", "theory")
        assert any("principle TCAD" in q for q in result)
        assert any("overview TCAD" in q for q in result)

    def test_comparison_adds_focused_queries(self):
        result = _generate_sub_queries("DD MC", "comparison")
        assert any("difference DD MC" in q for q in result)
        assert any("comparison DD MC" in q for q in result)

    def test_max_five_queries(self):
        result = _generate_sub_queries("test query", "methodology")
        assert len(result) <= 5


class TestRRFFusion:
    """_rrf_fusion — Reciprocal Rank Fusion of multiple ranked lists."""

    def make_doc(self, content: str, page: int = 1) -> Document:
        return Document(
            page_content=content,
            metadata={"page": page, "source": "test.pdf"},
        )

    def test_single_list_returns_one(self):
        docs = [self.make_doc("doc1"), self.make_doc("doc2")]
        result = _rrf_fusion([docs], k=60)
        assert len(result) == 2

    def test_fuses_two_lists(self):
        docs_a = [self.make_doc("doc_a1"), self.make_doc("doc_a2")]
        docs_b = [self.make_doc("doc_b1"), self.make_doc("doc_b2")]
        result = _rrf_fusion([docs_a, docs_b], k=60)
        assert len(result) == 4

    def test_deduplicates_identical_content(self):
        doc = self.make_doc("same content")
        result = _rrf_fusion([[doc], [doc]], k=60)
        assert len(result) == 1

    def test_higher_rank_gets_higher_score(self):
        docs_a = [self.make_doc("doc1"), self.make_doc("doc2")]
        docs_b = [self.make_doc("doc2"), self.make_doc("doc1")]
        result = _rrf_fusion([docs_a, docs_b], k=60)
        # doc1 appears at rank 1 in list A → higher score
        # doc2 appears at rank 1 in list B → higher score
        # Both appear at rank 1 in one list → should be top
        top_score = result[0][1]
        assert top_score > 0.0

    def test_returns_document_score_tuples(self):
        docs = [self.make_doc("unique content")]
        result = _rrf_fusion([docs], k=60)
        assert len(result) == 1
        doc, score = result[0]
        assert isinstance(doc, Document)
        assert isinstance(score, float)
        assert score > 0.0

    def test_empty_input_returns_empty(self):
        assert _rrf_fusion([], k=60) == []

    def test_k_parameter_affects_score(self):
        docs = [self.make_doc("content")]
        result_k10 = _rrf_fusion([docs], k=10)
        result_k100 = _rrf_fusion([docs], k=100)
        assert result_k10[0][1] > result_k100[0][1]


class TestTypeToPrompt:
    """_TYPE_TO_PROMPT — prompt template mapping completeness."""

    def test_all_types_have_prompts(self):
        expected_types = {"methodology", "result", "theory", "comparison", "general"}
        assert set(_TYPE_TO_PROMPT.keys()) == expected_types

    def test_prompts_are_distinct(self):
        assert _TYPE_TO_PROMPT["methodology"] is PROMPT_METHODOLOGY
        assert _TYPE_TO_PROMPT["result"] is PROMPT_RESULT
        assert _TYPE_TO_PROMPT["theory"] is PROMPT_THEORY
        assert _TYPE_TO_PROMPT["comparison"] is PROMPT_COMPARISON
        assert _TYPE_TO_PROMPT["general"] is PROMPT_GENERAL

    def test_prompts_contain_context_variable(self):
        for qtype, template in _TYPE_TO_PROMPT.items():
            assert "{context}" in template, f"{qtype} prompt missing {{context}}"
            assert "{question}" in template, f"{qtype} prompt missing {{question}}"
