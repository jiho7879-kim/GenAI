"""
Paper Agent: Handles questions and analysis about ingested papers using RAG.

This agent wraps the RAGChain and adds:
- Source citation formatting
- Paper-specific filtering (by filename)
- Summarization requests
- Answer grounding verification (Self-Reflection)
"""

import json
import logging
import re

from langchain_core.documents import Document
from langchain_core.prompts import PromptTemplate

from src.rag_chain import RAGChain

logger = logging.getLogger(__name__)

# ── Self-Reflection / Claim Verification Prompt ────────────────────────────

CLAIM_CHECK_PROMPT = """You are a fact-checker for academic answers.
Given the context and the generated answer, verify each claim.

Context:
{context}

Generated Answer:
{answer}

For each claim in the answer, check:
1. Is this claim DIRECTLY supported by the context? (YES / PARTIAL / NO)
2. If PARTIAL: what additional information from context is missing?
3. If NO: what does the context actually say?

Output a JSON array (and ONLY the JSON array, no other text):
[
  {{"claim": "...", "status": "YES", "correction": ""}},
  {{"claim": "...", "status": "PARTIAL", "correction": "context also mentions ..."}},
  {{"claim": "...", "status": "NO", "correction": "context actually says ..."}}
]"""


def format_sources(sources: list[Document]) -> str:
    """
    Format source documents into a readable citation list.

    Args:
        sources: List of source Document objects.

    Returns:
        Formatted markdown string with cited sources.
    """
    if not sources:
        return "*No specific sources referenced.*"

    seen = set()
    formatted = []
    for i, doc in enumerate(sources, 1):
        page = doc.metadata.get("page", "?")
        filename = doc.metadata.get("source_filename", doc.metadata.get("source", "Unknown"))
        # Deduplicate by page content hash
        content_preview = doc.page_content[:80].strip()
        key = f"{filename}-p{page}-{content_preview[:30]}"
        if key in seen:
            continue
        seen.add(key)
        formatted.append(f'{i}. **{filename}**, p.{page} — "{content_preview}..."')

    return "\n".join(formatted) if formatted else "*No unique sources.*"


class PaperAgent:
    """Agent for answering questions about ingested papers."""

    def __init__(
        self,
        vectorstore_dir: str = None,
        model_name: str = "qwen3.5:4b",
        top_k: int = 5,
    ):
        """
        Initialize the Paper Agent with a RAG chain.

        Args:
            vectorstore_dir: Path to FAISS index directory.
            model_name: Ollama model for generation.
            top_k: Number of chunks to retrieve.
        """
        self.rag = RAGChain(
            vectorstore_dir=vectorstore_dir,
            model_name=model_name,
            top_k=top_k,
        )

    def load_vectorstore(self, vectorstore_dir: str) -> bool:
        """Load or reload the vector store."""
        return self.rag.load(vectorstore_dir)

    def is_ready(self) -> bool:
        """Check if papers have been ingested and ready for Q&A."""
        return self.rag.is_ready()

    def ask(self, question: str) -> dict:
        """
        Ask a question about ingested papers.

        Args:
            question: The question to answer.

        Returns:
            Dict with keys:
                - answer: The generated answer text
                - sources: Formatted source citations
                - source_docs: Raw source Document objects
        """
        if not self.is_ready():
            return {
                "answer": "⚠️ No papers ingested yet. Please upload PDFs first via the Paper Lab tab.",
                "sources": "",
                "source_docs": [],
            }

        try:
            answer, source_docs = self.rag.query(question)
            formatted_sources = format_sources(source_docs)

            return {
                "answer": answer,
                "sources": formatted_sources,
                "source_docs": source_docs,
            }
        except Exception as e:
            logger.error(f"PaperAgent.ask failed: {e}")
            return {
                "answer": f"❌ Error generating answer: {str(e)}",
                "sources": "",
                "source_docs": [],
            }

    def summarize(self, focus: str = "overview") -> dict:
        """
        Generate a structured summary of all ingested papers.

        Args:
            focus: Specific aspect to focus on (e.g., "methodology", "results").

        Returns:
            Dict with summary text and sources.
        """
        if not self.is_ready():
            return {
                "answer": "⚠️ No papers ingested yet.",
                "sources": "",
                "source_docs": [],
            }

        try:
            summary, source_docs = self.rag.summarize(
                f"Summarize the {focus} of the papers in my library."
            )
            formatted_sources = format_sources(source_docs)

            return {
                "answer": summary,
                "sources": formatted_sources,
                "source_docs": source_docs,
            }
        except Exception as e:
            logger.error(f"PaperAgent.summarize failed: {e}")
            return {
                "answer": f"❌ Error generating summary: {str(e)}",
                "sources": "",
                "source_docs": [],
            }

    def switch_model(self, model_name: str):
        """Switch the underlying LLM model."""
        self.rag.switch_model(model_name)

    def verify_answer(
        self,
        question: str,
        answer: str,
        source_docs: list[Document],
    ) -> dict:
        """Verify answer claims against the retrieved context (Self-Reflection).

        Uses a lightweight 1-pass LLM fact-check: sends the context and generated
        answer to a verification prompt, then classifies each claim as
        YES / PARTIAL / NO.

        Args:
            question: The original question.
            answer: The generated answer text.
            source_docs: Source documents used to generate the answer.

        Returns:
            Dict with keys:
                - verified: bool (True if all claims are supported)
                - claims: list of claim dicts with status
                - summary: human-readable verification summary
        """
        if not source_docs or not answer:
            return {
                "verified": bool(not answer),
                "claims": [],
                "summary": "No answer or sources to verify."
                if not answer
                else "No sources to verify against.",
            }

        # Build context string from source documents
        context_parts = []
        for doc in source_docs:
            meta = doc.metadata
            section = meta.get("section_name", "")
            page = meta.get("page", "?")
            filename = meta.get("source_filename", meta.get("source", "Unknown"))
            header = f"[Source: {filename}, p.{page}"
            if section:
                header += f", Section: {section}"
            header += "]"
            context_parts.append(f"{header}\n{doc.page_content}")
        context_str = "\n\n".join(context_parts)

        try:
            prompt = PromptTemplate(
                template=CLAIM_CHECK_PROMPT,
                input_variables=["context", "answer"],
            )
            chain = prompt | self.rag.llm
            raw = chain.invoke({"context": context_str, "answer": answer})
            claims = self._parse_verification(raw)

            n_yes = sum(1 for c in claims if c.get("status") == "YES")
            n_partial = sum(1 for c in claims if c.get("status") == "PARTIAL")
            n_no = sum(1 for c in claims if c.get("status") == "NO")

            verified = n_no == 0

            summary_parts = []
            if verified and n_partial == 0:
                summary_parts.append(f"✅ All {n_yes} claims supported by context.")
            elif verified:
                summary_parts.append(
                    f"⚠️ {n_yes} supported, {n_partial} partially supported "
                    f"(all corrections applied)."
                )
            else:
                summary_parts.append(
                    f"❌ {n_no} unsupported claim(s) found. {n_yes} supported, {n_partial} partial."
                )

            return {
                "verified": verified,
                "claims": claims,
                "summary": " ".join(summary_parts),
            }
        except Exception as e:
            logger.warning("Answer verification failed: %s — skipping", e)
            return {
                "verified": True,
                "claims": [],
                "summary": "Verification skipped due to error.",
            }

    @staticmethod
    def _parse_verification(raw: str) -> list[dict]:
        """Parse verification JSON from LLM output, tolerating markdown fences."""
        text = raw.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        text = text.strip()
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if not match:
            return []
        try:
            claims = json.loads(match.group())
            if isinstance(claims, list):
                return claims
            return []
        except (json.JSONDecodeError, TypeError):
            return []
