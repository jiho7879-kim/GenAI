"""
Paper Analyst Agent: Multi-step pipeline for complex paper analysis.

Orchestrates a sequence of sub-tasks:
Retriever → Reader → Comparator → Verifier → Report

Designed for CPU-constrained environments (sequential pipeline,
single LLM call at a time).

Usage:
    analyst = AnalystAgent()
    result = analyst.analyze(
        "Compare the TCAD calibration methods across all ingested papers"
    )
"""

import logging
import time

from src.agents.paper_agent import PaperAgent
from src.agents.report_agent import ReportAgent
from src.rag_chain import _detect_question_type

logger = logging.getLogger(__name__)


class AnalystAgent:
    """Multi-step paper analysis pipeline.

    Pipeline steps:
        1. RETRIEVE — Gather relevant chunks from all papers
        2. READ — Extract per-paper findings via focused sub-queries
        3. COMPARE — Cross-reference findings (for comparison questions)
        4. VERIFY — Check answer grounding against source context
        5. REPORT — Format final structured report
    """

    def __init__(
        self,
        vectorstore_dir: str = None,
        model_name: str = "qwen3.5:4b",
        top_k: int = 5,
    ):
        self.paper = PaperAgent(
            vectorstore_dir=vectorstore_dir,
            model_name=model_name,
            top_k=top_k,
        )
        self.report = ReportAgent()
        self._analysis_log: list[dict] = []

    # ── Public API ──────────────────────────────────────────────────────────

    def analyze(self, question: str) -> dict:
        """Run the full analysis pipeline for a complex question.

        Args:
            question: The user's analysis request (e.g. comparison, survey).

        Returns:
            Dict with keys:
                - answer: Final structured analysis report
                - sources: Formatted source citations
                - trace: Step-by-step pipeline trace
                - verification: Verification summary
        """
        self._analysis_log = []
        self._log("pipeline", f"Starting analysis: {question[:80]}")

        if not self.paper.is_ready():
            return {
                "answer": "No papers ingested yet. Please upload PDFs first.",
                "sources": "",
                "trace": [],
                "verification": {},
            }

        try:
            qtype = _detect_question_type(question)
            needs_comparison = qtype == "comparison"

            # Step 1: Retrieve
            retrieve_start = time.time()
            source_docs = self._step_retrieve(question, qtype)
            self._log(
                "retrieve",
                f"Retrieved {len(source_docs)} chunks ({time.time() - retrieve_start:.1f}s)",
            )

            if not source_docs:
                return {
                    "answer": "No relevant content found in ingested papers.",
                    "sources": "",
                    "trace": self._analysis_log,
                    "verification": {},
                }

            # Step 2: Read — extract paper-specific info
            read_start = time.time()
            per_paper = self._step_read(question, source_docs, needs_comparison)
            self._log(
                "read",
                f"Extracted findings from {len(per_paper)} paper group(s) "
                f"({time.time() - read_start:.1f}s)",
            )

            # Step 3: Compare (only for comparison questions)
            if needs_comparison and len(per_paper) > 1:
                compare_start = time.time()
                comparison = self._step_compare(question, per_paper)
                self._log(
                    "compare",
                    f"Generated comparison analysis ({time.time() - compare_start:.1f}s)",
                )
            else:
                comparison = None

            # Step 4: Generate final answer
            answer, formatted_sources = self._step_answer(
                question,
                per_paper,
                comparison,
                source_docs,
            )

            # Step 5: Verify
            verify_start = time.time()
            verification = self.paper.verify_answer(question, answer, source_docs)
            verification["claims_count"] = len(verification.get("claims", []))
            self._log(
                "verify",
                f"Verification: {verification.get('summary', 'done')} "
                f"({time.time() - verify_start:.1f}s)",
            )

            return {
                "answer": answer,
                "sources": formatted_sources,
                "trace": self._analysis_log,
                "verification": verification,
            }

        except Exception as e:
            logger.error("AnalystAgent.analyze failed: %s", e)
            return {
                "answer": f"Analysis failed: {e}",
                "sources": "",
                "trace": self._analysis_log,
                "verification": {},
            }

    # ── Pipeline Steps ──────────────────────────────────────────────────────

    def _step_retrieve(self, question: str, qtype: str) -> list:
        """Step 1: Retrieve relevant chunks using multi-query expansion."""
        return self.paper.rag.retrieve(question, qtype=qtype)

    def _step_read(
        self,
        question: str,
        source_docs: list,
        needs_comparison: bool,
    ) -> list[dict]:
        """Step 2: Extract per-paper findings via focused sub-queries."""
        # Group chunks by source file
        paper_groups: dict[str, list] = {}
        for doc in source_docs:
            fname = doc.metadata.get("source_filename", doc.metadata.get("source", "unknown"))
            if fname not in paper_groups:
                paper_groups[fname] = []
            paper_groups[fname].append(doc)

        per_paper = []
        for fname, docs in paper_groups.items():
            # Build a per-paper context
            context = "\n\n".join(d.page_content for d in docs)

            # Ask a focused question tailored to this paper
            if needs_comparison:
                focused_q = (
                    f"What approach or method does this paper ({fname}) use "
                    f"regarding: {question[:120]}"
                )
            else:
                focused_q = f"What does this paper ({fname}) say about: {question[:120]}"

            per_paper.append(
                {
                    "filename": fname,
                    "chunks": len(docs),
                    "context": context,
                    "focused_question": focused_q,
                }
            )

        return per_paper

    def _step_compare(self, question: str, per_paper: list[dict]) -> str:
        """Step 3: Generate cross-paper comparison analysis."""
        papers_desc = []
        for p in per_paper:
            papers_desc.append(f"--- {p['filename']} ---\n{p['context'][:1500]}")

        comparison_prompt = (
            "Compare the following papers' approaches regarding:\n"
            f"{question}\n\n"
            f"{chr(10).join(papers_desc)}\n\n"
            "Provide a structured comparison:\n"
            "1. **Summary of each paper's approach**\n"
            "2. **Key similarities**\n"
            "3. **Key differences** (use a table)\n"
            "4. **Trade-offs and advantages**\n"
            "Cite specific sources for each point."
        )

        try:
            return self.paper.rag.llm.invoke(comparison_prompt)
        except Exception as e:
            logger.warning("Comparison step failed: %s", e)
            return ""

    def _step_answer(
        self,
        question: str,
        per_paper: list[dict],
        comparison: str | None,
        source_docs: list,
    ) -> tuple[str, str]:
        """Step 4: Generate the final structured analysis report."""
        # Use ReportAgent to format
        rag_answer, _ = self.paper.rag.query(question)
        formatted_sources = self._format_trace_sources(source_docs)

        if comparison:
            full_answer = (
                f"## Analysis: {question}\n\n"
                f"{rag_answer}\n\n"
                f"---\n"
                f"### Cross-Paper Comparison\n\n"
                f"{comparison}"
            )
        else:
            full_answer = rag_answer

        report = self.report.format_answer(full_answer, formatted_sources)
        return report, formatted_sources

    # ── Helpers ─────────────────────────────────────────────────────────────

    def _format_trace_sources(self, source_docs: list) -> str:
        """Format source documents grouped by filename."""
        from src.agents.paper_agent import format_sources

        return format_sources(source_docs)

    def _log(self, step: str, message: str):
        """Record a pipeline step in the trace log."""
        entry = {"step": step, "message": message}
        self._analysis_log.append(entry)
        logger.debug("[%s] %s", step.upper(), message)
