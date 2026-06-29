"""
Arxiv Search Agent: Searches Arxiv for papers and returns structured results.

Uses the arxiv Python API (no API key required).
Results are cached to avoid redundant API calls within a session.

Paper summaries use raw abstract text (no LLM) for maximum speed.
Use the `summarize_paper()` method for on-demand LLM summaries.
"""

import json
import logging
import re
import time
from dataclasses import dataclass
from urllib import request as url_request

logger = logging.getLogger(__name__)

ARXIV_CACHE_TTL = 3600  # 1 hour cache

OLLAMA_BASE_URL = "http://localhost:11434"


def _ollama_generate(
    model: str,
    prompt: str,
    *,
    temperature: float = 0.1,
    num_predict: int = 512,
    timeout: int = 30,
) -> str:
    """Call Ollama directly via the /api/generate endpoint (no langchain)."""
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


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class ArxivPaper:
    """Structured representation of an Arxiv paper."""

    title: str
    authors: list[str]
    arxiv_id: str
    arxiv_url: str
    abstract: str
    published: str
    summary: str | None = None  # Will be set to abstract (fast, no LLM)


# Simple in-memory cache
_search_cache = {}


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


class ArxivSearchAgent:
    """Agent for searching and summarizing papers from Arxiv."""

    def __init__(self, max_results: int = 5):
        """
        Initialize the Arxiv search agent.

        Args:
            max_results: Maximum papers to return per search.
        """
        self.max_results = max_results

    def _get_cache_key(self, query: str, max_results: int) -> str:
        return f"{query.lower().strip()}_{max_results}"

    def _is_cache_valid(self, cache_key: str) -> bool:
        if cache_key in _search_cache:
            entry = _search_cache[cache_key]
            if time.time() - entry["timestamp"] < ARXIV_CACHE_TTL:
                return True
            else:
                del _search_cache[cache_key]
        return False

    def batch_summarize(
        self,
        papers: list[dict],
        model: str = "qwen3.5:4b",
    ) -> list[dict]:
        """
        Generate LLM summaries for a batch of papers in a single prompt.

        All papers are sent in one LLM call. If the LLM call fails (timeout,
        server error), each paper retains its original truncated-abstract summary.

        Args:
            papers: List of paper dicts with 'title' and 'abstract' keys.
            model: Ollama model name.

        Returns:
            Same list of dicts with the 'summary' field updated to LLM-generated text.
        """
        if not papers:
            return papers

        lines = [
            "Summarize each paper below in 1-2 sentences. Focus on:",
            "(1) What problem does it solve? (2) What method does it use? (3) Key result?",
            "",
        ]
        for i, p in enumerate(papers, 1):
            title = p.get("title", "Unknown")[:120]
            abstract = p.get("abstract", "")[:300]
            lines.append(f"{i}. Title: {title}")
            lines.append(f"   Abstract: {abstract}")
            lines.append("")

        lines.append(f"Return exactly one summary per paper, numbered 1 to {len(papers)}.")

        prompt = "\n".join(lines)

        try:
            raw = _ollama_generate(model, prompt, num_predict=1024, timeout=30)
            summaries = self._parse_batch_summary(raw, len(papers))

            for i, paper in enumerate(papers):
                if i < len(summaries) and summaries[i]:
                    paper["summary"] = summaries[i]

            logger.info(
                "Batch summary: %d/%d papers updated via LLM",
                sum(1 for s in summaries if s),
                len(papers),
            )
        except Exception as e:
            logger.warning("Batch summarization failed: %s — keeping fallback summaries", e)

        return papers

    @staticmethod
    def _parse_batch_summary(raw: str, expected: int) -> list[str]:
        """
        Parse batch-summary LLM output into a list of per-paper summaries.

        Handles numbered lists (e.g. "1. Summary...", "2. Summary...") and
        plain line-separated output.
        """
        summaries: list[str] = []
        lines = raw.strip().split("\n")

        for line in lines:
            line = line.strip()
            if not line:
                continue
            match = re.match(r"^\d+[\.:\)]\s*(.*)", line)
            if match:
                summaries.append(match.group(1).strip())
            elif summaries:
                # Continuation line — append to last summary
                summaries[-1] += " " + line

        # If parsing failed, return the raw response as a single summary
        if not summaries and raw.strip():
            return [raw.strip()[:300]]

        return summaries

    def search(
        self,
        query: str,
        max_results: int = None,
        *,
        summarize: bool = False,
        model: str = "qwen3.5:4b",
    ) -> list[dict]:
        """
        Search Arxiv for papers matching the query.

        Args:
            query: Search keywords (e.g., "TCAD machine learning GAA FET").
            max_results: Override default max results.
            summarize: If True, generate LLM summaries for all results.
            model: Ollama model for summarization.

        Returns:
            List of dicts with paper metadata and summaries.
        """
        target_max = max_results or self.max_results
        cache_key = self._get_cache_key(query, target_max)

        # Check cache
        if self._is_cache_valid(cache_key):
            logger.info("Arxiv cache hit for: '%s'", query)
            return _search_cache[cache_key]["results"]

        # Fetch from Arxiv API
        try:
            import arxiv

            logger.info("Searching Arxiv for: '%s' (max=%s)", query, target_max)

            client = arxiv.Client()
            search = arxiv.Search(
                query=query,
                max_results=target_max,
                sort_by=arxiv.SortCriterion.Relevance,
            )

            results = []
            for paper in client.results(search):
                paper_data = {
                    "title": paper.title,
                    "authors": ", ".join([a.name for a in paper.authors]),
                    "arxiv_id": paper.get_short_id(),
                    "url": paper.entry_id,
                    "abstract": paper.summary.replace("\n", " "),
                    "published": paper.published.strftime("%Y-%m-%d"),
                    # Use truncated abstract as summary (fast, no LLM)
                    "summary": paper.summary[:300].replace("\n", " ") + "...",
                }
                results.append(paper_data)

            if summarize and results:
                results = self.batch_summarize(results, model=model)

            # Cache results
            _search_cache[cache_key] = {
                "timestamp": time.time(),
                "results": results,
            }

            logger.info("Found %d papers on Arxiv", len(results))
            return results

        except ImportError:
            logger.error("arxiv package not installed. Run: pip install arxiv")
            return [{"error": "arxiv package not installed"}]
        except Exception as e:
            logger.error("Arxiv search failed: %s", e)
            return [{"error": f"Search failed: {str(e)}"}]

    def summarize_paper(
        self,
        title: str,
        abstract: str,
        model: str = "qwen3.5:4b",
    ) -> str:
        """
        Generate an LLM summary for a single paper (on-demand).

        This is NOT called during search — use when the user requests
        deeper analysis of a specific paper.

        Args:
            title: Paper title.
            abstract: Paper abstract.
            model: Ollama model name.

        Returns:
            One-sentence summary, or truncated abstract on failure.
        """
        prompt = f"""Paper title: {title}
Abstract: {abstract[:500]}

Summarize this paper in 1-2 sentences, focusing on what problem it solves and what method it uses."""

        try:
            return _ollama_generate(model, prompt, num_predict=512, timeout=30)
        except Exception as e:
            logger.warning(f"Paper summary generation failed: {e}")
            return abstract[:200] + "..."

    def get_paper_detail(self, arxiv_id: str) -> dict | None:
        """
        Fetch detailed information about a specific paper by Arxiv ID.

        Args:
            arxiv_id: The Arxiv paper ID.

        Returns:
            Paper dict with full details, or None if not found.
        """
        try:
            import arxiv

            client = arxiv.Client()
            search = arxiv.Search(id_list=[arxiv_id])
            paper = next(client.results(search), None)

            if paper is None:
                return None

            return {
                "title": paper.title,
                "authors": ", ".join([a.name for a in paper.authors]),
                "arxiv_id": arxiv_id,
                "url": paper.entry_id,
                "abstract": paper.summary.replace("\n", " "),
                "published": paper.published.strftime("%Y-%m-%d"),
                "pdf_url": paper.pdf_url,
                "summary": paper.summary[:300].replace("\n", " ") + "...",
            }
        except Exception as e:
            logger.error(f"Failed to fetch paper {arxiv_id}: {e}")
            return None

    @staticmethod
    def rerank(
        papers: list[dict],
        vectorstore: object,
        top_k: int = 5,
    ) -> list[dict]:
        """
        Rerank search results by relevance to the user's paper library.

        Each paper's abstract is embedded (BGE-m3) and compared via cosine
        similarity to the centroid of the user's FAISS index. Results are
        sorted by similarity (descending) and limited to top_k.

        If the vector store is empty or unavailable, the original order is
        preserved (up to top_k).

        Args:
            papers: List of paper dicts from search().
            vectorstore: A langchain FAISS vector store (loaded via load_vectorstore).
            top_k: Maximum papers to return after reranking.

        Returns:
            Reranked list of paper dicts, each with a 'similarity' key (0.0 to 1.0).
        """
        if not papers:
            return papers

        # Import lazily to avoid circular dependency at module level
        from src.rag_chain import compute_similarity_scores

        abstracts = [p.get("abstract", "")[:500] for p in papers]
        scores = compute_similarity_scores(abstracts, vectorstore)

        for paper, score in zip(papers, scores, strict=False):
            paper["similarity"] = round(score, 4)

        reranked = sorted(papers, key=lambda p: p.get("similarity", 0), reverse=True)
        return reranked[:top_k]
