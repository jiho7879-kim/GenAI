"""Tests for ArxivSearchAgent — no external API dependencies."""

from src.agents.arxiv_agent import ArxivSearchAgent


class TestParseBatchSummary:
    """_parse_batch_summary — LLM output parser for batch summarization."""

    def test_numbered_list(self):
        raw = (
            "1. This paper proposes a new TCAD calibration method.\n2. A survey of GAA FET devices."
        )
        result = ArxivSearchAgent._parse_batch_summary(raw, 2)
        assert len(result) == 2
        assert "TCAD calibration" in result[0]
        assert "GAA FET" in result[1]

    def test_numbered_with_period_variants(self):
        raw = "1: First summary\n2) Second summary"
        result = ArxivSearchAgent._parse_batch_summary(raw, 2)
        assert "First summary" in result[0]
        assert "Second summary" in result[1]

    def test_continuation_lines(self):
        raw = "1. This is a long\nsummary that continues on the next line.\n2. Second paper."
        result = ArxivSearchAgent._parse_batch_summary(raw, 2)
        assert len(result) == 2
        assert "continues" in result[0]

    def test_fallback_on_no_numbers(self):
        raw = "Just some raw text without any numbering."
        result = ArxivSearchAgent._parse_batch_summary(raw, 1)
        assert len(result) == 1
        assert "raw text" in result[0]

    def test_empty_input(self):
        result = ArxivSearchAgent._parse_batch_summary("", 5)
        assert result == []

    def test_fewer_results_than_expected(self):
        raw = "1. Only one summary."
        result = ArxivSearchAgent._parse_batch_summary(raw, 3)
        assert len(result) == 1
        assert "Only one" in result[0]


class TestRerank:
    """ArxivSearchAgent.rerank — basic behavior without a real vector store."""

    def test_empty_papers_returns_empty(self):
        agent = ArxivSearchAgent()
        result = agent.rerank([], vectorstore=None, top_k=5)
        assert result == []

    def test_rerank_adds_similarity_key(self):
        agent = ArxivSearchAgent()
        papers = [
            {"title": "Paper A", "abstract": "TCAD calibration method"},
            {"title": "Paper B", "abstract": "Machine learning for devices"},
        ]
        # Without a real vectorstore, scores will be 0.0, but similarity key should exist
        result = agent.rerank(papers, vectorstore=None, top_k=5)
        assert len(result) == 2
        for p in result:
            assert "similarity" in p
            assert isinstance(p["similarity"], float)

    def test_rerank_respects_top_k(self):
        agent = ArxivSearchAgent()
        papers = [{"title": f"Paper {i}", "abstract": f"Abstract {i}"} for i in range(10)]
        result = agent.rerank(papers, vectorstore=None, top_k=3)
        assert len(result) == 3


class TestSearchCache:
    """Search cache key generation."""

    def test_cache_key_normalization(self):
        agent = ArxivSearchAgent()
        key1 = agent._get_cache_key("TCAD Machine Learning", 5)
        key2 = agent._get_cache_key("tcad machine learning  ", 5)
        assert key1 == key2

    def test_cache_key_different_max_results(self):
        agent = ArxivSearchAgent()
        key1 = agent._get_cache_key("test query", 5)
        key2 = agent._get_cache_key("test query", 10)
        assert key1 != key2
