"""
RAG Chain: Retrieve chunks from FAISS → Generate answer with Ollama LLM.

Supports both simple (direct) and enhanced (multi-query + RRF fusion) retrieval.

Usage:
    from src.rag_chain import RAGChain
    rag = RAGChain(vectorstore_dir="vectorstore")
    answer, sources = rag.query("What is TCAD?")

Also provides standalone reranking utilities for Arxiv search results.
"""

import logging
import re
from typing import Any

import numpy as np
from langchain_core.documents import Document
from langchain_core.prompts import PromptTemplate
from langchain_ollama import OllamaLLM

from src.ingest import load_vectorstore

logger = logging.getLogger(__name__)

# ---------- Configuration ----------

# Ollama models available
MODEL_FAST = "qwen2.5:1.5b"
MODEL_ACCURATE = "qwen3.5:4b"

# ---------------------------------------------------------------------------
# Question type detection (keyword-based, no LLM)
# ---------------------------------------------------------------------------

_QT_METHODOLOGY = {
    "method",
    "methodology",
    "approach",
    "technique",
    "calibration",
    "simulation",
    "simulate",
    "modeling",
    "model",
    "setup",
    "procedure",
    "step",
    "process",
    "fabrication",
    "implementation",
    "how to",
    "how is",
    "how does",
    "how are",
    "way to",
    "방법",
    "방법론",
    "캘리브레이션",
    "시뮬레이션",
    "모델링",
    "절차",
}
_QT_RESULT = {
    "result",
    "performance",
    "accuracy",
    "improvement",
    "enhancement",
    "efficiency",
    "error",
    "comparison",
    "metric",
    "figure",
    "table",
    "data",
    "measurement",
    "characteristic",
    "achieved",
    "best",
    "highest",
    "lowest",
    "effect",
    "impact",
    "trade-off",
    "결과",
    "성능",
    "정확도",
    "개선",
    "효율",
    "측정",
    "특성",
}
_QT_THEORY = {
    "what is",
    "what are",
    "define",
    "definition",
    "explain",
    "principle",
    "theory",
    "concept",
    "mechanism",
    "physics",
    "understand",
    "describe",
    "fundamental",
    "basis of",
    "원리",
    "이론",
    "개념",
    "정의",
    "설명",
    "물리",
    "기본",
}
_QT_COMPARISON = {
    "compare",
    "comparison",
    "difference",
    "versus",
    "vs",
    "better",
    "advantage",
    "disadvantage",
    "trade-off",
    "similarities",
    "differ",
    "relative",
    "which",
    "비교",
    "차이",
    "장단점",
    "장점",
    "단점",
}
_ALL_QT_WORDS = _QT_METHODOLOGY | _QT_RESULT | _QT_THEORY | _QT_COMPARISON


def _detect_question_type(question: str) -> str:
    """Classify question into methodology/result/theory/comparison/general."""
    q_lower = question.lower().strip()
    scores: dict[str, int] = {
        "methodology": 0,
        "result": 0,
        "theory": 0,
        "comparison": 0,
    }

    for word in _QT_METHODOLOGY:
        if word in q_lower:
            scores["methodology"] += 1
    for word in _QT_RESULT:
        if word in q_lower:
            scores["result"] += 1
    for word in _QT_THEORY:
        if word in q_lower:
            scores["theory"] += 1
    for word in _QT_COMPARISON:
        if word in q_lower:
            scores["comparison"] += 1

    best = max(scores, key=scores.get)
    if scores[best] == 0:
        return "general"
    return best


# ---------------------------------------------------------------------------
# Query expansion helpers (no LLM required)
# ---------------------------------------------------------------------------

_QUERY_EXPANSIONS: dict[str, list[str]] = {
    "tcad": ["technology computer-aided design"],
    "gaa": ["gate-all-around"],
    "mosfet": ["mos", "metal-oxide-semiconductor"],
    "fet": ["field-effect transistor"],
    "cmos": ["complementary metal-oxide-semiconductor"],
    "dd": ["drift-diffusion"],
    "mc": ["monte carlo"],
    "ml": ["machine learning"],
    "ann": ["artificial neural network", "neural network"],
    "vth": ["threshold voltage"],
    "gm": ["transconductance"],
    "ss": ["subthreshold swing"],
    "ion": ["on-current", "drive current"],
    "ioff": ["off-current", "leakage current"],
}


def _expand_query_terms(query: str) -> list[str]:
    """Generate sub-queries by expanding abbreviations."""
    q_lower = query.lower()
    expanded = [query]  # original is always first
    for abbr, expansions in _QUERY_EXPANSIONS.items():
        if re.search(rf"\b{re.escape(abbr)}\b", q_lower):
            for term in expansions:
                # Replace abbreviation with expansion in the query
                expanded_query = re.sub(rf"\b{re.escape(abbr)}\b", term, query, flags=re.IGNORECASE)
                if expanded_query != query:
                    expanded.append(expanded_query)
    return expanded


def _generate_sub_queries(question: str, qtype: str) -> list[str]:
    """Generate sub-queries for multi-query retrieval based on question type."""
    queries = [question]  # original query always first

    # Expand abbreviations
    expanded = _expand_query_terms(question)
    queries.extend(e for e in expanded if e not in queries)

    # Add type-specific focused queries
    if qtype == "methodology":
        queries.append(f"method {question}")
        queries.append(f"approach {question}")
    elif qtype == "result":
        queries.append(f"result {question}")
        queries.append(f"performance {question}")
    elif qtype == "theory":
        queries.append(f"principle {question}")
        queries.append(f"overview {question}")
    elif qtype == "comparison":
        queries.append(f"difference {question}")
        queries.append(f"comparison {question}")

    return queries[:5]  # max 5 sub-queries


# ---------------------------------------------------------------------------
# RRF (Reciprocal Rank Fusion)
# ---------------------------------------------------------------------------


def _rrf_fusion(
    ranked_lists: list[list[Document]],
    k: int = 60,
) -> list[tuple[Document, float]]:
    """Fuse multiple ranked lists using Reciprocal Rank Fusion.

    Each document's score = sum(1 / (k + rank)) across all lists.
    Higher-ranked documents in more lists get the highest fused scores.

    Args:
        ranked_lists: List of ranked document lists (from each sub-query).
        k: RRF constant (default 60).

    Returns:
        List of (document, fused_score) tuples sorted by score descending.
    """
    scores: dict[str, float] = {}
    doc_map: dict[str, Document] = {}

    for doc_list in ranked_lists:
        for rank, doc in enumerate(doc_list, 1):
            # Use content hash as key for dedup
            key = doc.page_content[:100]
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank)
            if key not in doc_map:
                doc_map[key] = doc

    # Re-sort by fused score
    result = sorted(
        [(doc_map[k], score) for k, score in scores.items()],
        key=lambda x: x[1],
        reverse=True,
    )
    return result


# ---------------------------------------------------------------------------
# Prompt templates (by question type)
# ---------------------------------------------------------------------------

QA_PROMPT_TEMPLATE = """You are a research assistant specializing in semiconductor devices, TCAD simulation, and machine learning for TCAD.

Use the following retrieved document chunks to answer the user's question.
If you cannot find the answer in the provided context, say so clearly — do not make up information.
When referencing specific information, cite the source (page number, section name, filename) from the context.

Context:
{context}

Question: {question}

Please provide a thorough, technically accurate answer. Include relevant equations, parameters, or device physics concepts when appropriate. Format your answer in Markdown with clear section breaks."""

PROMPT_METHODOLOGY = """You are analyzing the methodology of a TCAD/semiconductor paper.

Use the provided context to explain the approach, methods, or techniques used.
Focus on: simulation setup, key parameters, calibration steps, tools, and validation.

Context:
{context}

Question: {question}

Structure your answer:
1. **Approach Overview** — what method does the paper use?
2. **Key Parameters** — numerical values, material properties, device dimensions
3. **Procedure** — step-by-step calibration or simulation flow
4. **Validation** — how was the method verified?

Cite specific sections and page numbers. If details are missing from context, say so."""

PROMPT_RESULT = """You are analyzing experimental or simulation results from a TCAD/semiconductor paper.

Use the provided context to report quantitative findings.
Focus on: exact numbers, comparisons, trends, and performance metrics.

Context:
{context}

Question: {question}

Structure your answer:
1. **Key Findings** — quantitative results with exact values
2. **Comparison** — how does this compare to baselines or prior work?
3. **Significance** — what does this result imply?

Always cite the specific section or page. Report exact numbers including units."""

PROMPT_THEORY = """You are explaining a technical concept from TCAD/semiconductor device physics.

Use the provided context to give a clear, accurate explanation.

Context:
{context}

Question: {question}

Structure your answer:
1. **Definition** — what is this concept?
2. **Physical Principle** — how does it work? Include equations if relevant
3. **Application in TCAD** — how is this concept used in simulation?
4. **Example from Paper** — concrete example from the provided context

Cite sources for each part of your explanation."""

PROMPT_COMPARISON = """You are comparing different approaches or concepts from TCAD/semiconductor papers.

Use the provided context to identify similarities and differences.

Context:
{context}

Question: {question}

Structure your answer:
1. **Items Compared** — what is being compared?
2. **Similarities** — how are they alike?
3. **Differences** — how do they differ? Use a table when possible
4. **Trade-offs** — advantages and disadvantages of each

Cite specific sources for each comparison point."""

PROMPT_GENERAL = QA_PROMPT_TEMPLATE

_TYPE_TO_PROMPT: dict[str, str] = {
    "methodology": PROMPT_METHODOLOGY,
    "result": PROMPT_RESULT,
    "theory": PROMPT_THEORY,
    "comparison": PROMPT_COMPARISON,
    "general": PROMPT_GENERAL,
}

SUMMARIZE_PROMPT_TEMPLATE = """You are a research assistant specializing in semiconductor devices and TCAD.

Summarize the following paper content in a structured format:

Paper: {context}

Please include:
1. **Title & Authors** (if available)
2. **Research Goal** — What problem does this paper address?
3. **Methodology** — What TCAD/ML approach was used?
4. **Key Findings** — What were the main results?
5. **Limitations** — What are the stated or implied limitations?

Keep the summary concise but technically precise. Use Markdown formatting."""


class RAGChain:
    """RAG retrieval + generation chain using local Ollama LLM.

    Supports enhanced retrieval with multi-query expansion, RRF fusion,
    and question-type-aware prompt selection.
    """

    def __init__(
        self,
        vectorstore_dir: str = None,
        model_name: str = MODEL_FAST,
        top_k: int = 5,
        temperature: float = 0.1,
    ):
        self.vectorstore_dir = vectorstore_dir
        self.model_name = model_name
        self.top_k = top_k
        self.temperature = temperature

        self._vectorstore = None
        self._llm = None

    @property
    def vectorstore(self):
        if self._vectorstore is None and self.vectorstore_dir:
            self._vectorstore = load_vectorstore(self.vectorstore_dir)
        return self._vectorstore

    @vectorstore.setter
    def vectorstore(self, vs):
        self._vectorstore = vs

    @property
    def llm(self):
        if self._llm is None:
            self._llm = OllamaLLM(
                model=self.model_name,
                temperature=self.temperature,
                num_predict=2048,
            )
        return self._llm

    # ------------------------------------------------------------------
    # Enhanced retrieval: multi-query + RRF fusion
    # ------------------------------------------------------------------

    def _search(self, query: str, k: int = None) -> list[Document]:
        """Run a single similarity search against the vector store."""
        if self.vectorstore is None:
            return []
        target_k = k or self.top_k
        docs = self.vectorstore.similarity_search(query, k=target_k)
        return docs

    def retrieve(
        self,
        question: str,
        qtype: str = None,
        sub_queries: list[str] = None,
    ) -> list[Document]:
        """Retrieve documents using multi-query + RRF fusion.

        Args:
            question: The user's question.
            qtype: Pre-detected question type (auto-detected if None).
            sub_queries: Additional sub-queries to search (generated if None).

        Returns:
            List of Document objects (deduplicated, ranked by RRF).
        """
        if self.vectorstore is None:
            return []

        qt = qtype or _detect_question_type(question)
        sq = sub_queries or _generate_sub_queries(question, qt)

        # Search each sub-query independently
        all_ranked: list[list[Document]] = []
        for q in sq:
            docs = self._search(q, k=self.top_k + 2)
            if docs:
                all_ranked.append(docs)

        if not all_ranked:
            logger.warning("No documents retrieved for any sub-query")
            return []

        # If only one query returned results, return those directly
        if len(all_ranked) == 1:
            return all_ranked[0][: self.top_k]

        # RRF fusion
        fused = _rrf_fusion(all_ranked, k=60)
        return [doc for doc, _score in fused[: self.top_k]]

    def query(
        self,
        question: str,
        qtype: str = None,
        sub_queries: list[str] = None,
        use_enhanced: bool = True,
    ) -> tuple[str, list[Document]]:
        """Ask a question and get an answer with supporting sources.

        When use_enhanced=True (default), applies multi-query retrieval
        with RRF fusion and question-type-specific prompt templates.

        Args:
            question: The user's question.
            qtype: Question type (auto-detected if None).
            sub_queries: Custom sub-queries (auto-generated if None).
            use_enhanced: If True, use multi-query + RRF + type-aware prompt.
                          If False, use simple single-query retrieval.

        Returns:
            Tuple of (answer_string, list_of_source_documents).
        """
        if self.vectorstore is None:
            raise ValueError("Vector store not loaded. Call load() first.")

        qt = qtype or _detect_question_type(question)

        if use_enhanced:
            sources = self.retrieve(question, qtype=qt, sub_queries=sub_queries)
        else:
            sources = self._search(question, k=self.top_k)

        if not sources:
            return ("*No relevant chunks found in the ingested papers for this question.*", [])

        # Build context from retrieved documents
        context_parts = []
        for i, doc in enumerate(sources, 1):
            meta = doc.metadata
            section = meta.get("section_name", "")
            page = meta.get("page", "?")
            filename = meta.get("source_filename", meta.get("source", "Unknown"))
            header = f"[{i}] Source: {filename}, p.{page}"
            if section:
                header += f", Section: {section}"
            context_parts.append(f"{header}\n{doc.page_content}")
        context_str = "\n\n".join(context_parts)

        # Select prompt template based on question type
        prompt_template = _TYPE_TO_PROMPT.get(qt, PROMPT_GENERAL)
        prompt = PromptTemplate(
            template=prompt_template,
            input_variables=["context", "question"],
        )
        chain = prompt | self.llm
        answer = chain.invoke({"context": context_str, "question": question})

        logger.info(
            "RAG query: '%s' (type=%s, enhanced=%s, sources=%d)",
            question[:50],
            qt,
            use_enhanced,
            len(sources),
        )
        return answer, sources

    def summarize(
        self, question: str = "Summarize the paper content"
    ) -> tuple[str, list[Document]]:
        """
        Generate a structured summary of the ingested papers.

        Args:
            question: Can be a specific summarization request.

        Returns:
            Tuple of (summary_string, list_of_source_documents).
        """
        # For summarization, retrieve more chunks to get comprehensive context
        if self.vectorstore is None:
            raise ValueError("Vector store not loaded.")

        retriever = self.vectorstore.as_retriever(
            search_type="similarity",
            search_kwargs={"k": min(self.top_k * 3, 15)},
        )

        docs = retriever.invoke(question)
        context = "\n\n".join([d.page_content for d in docs])

        prompt = PromptTemplate(
            template=SUMMARIZE_PROMPT_TEMPLATE,
            input_variables=["context"],
        )

        chain = prompt | self.llm
        summary = chain.invoke({"context": context})

        return summary, docs

    def load(self, vectorstore_dir: str = None):
        """Load/reload the vector store from disk."""
        target_dir = vectorstore_dir or self.vectorstore_dir
        if not target_dir:
            raise ValueError("No vectorstore directory specified.")
        self._vectorstore = load_vectorstore(target_dir)
        self.vectorstore_dir = target_dir
        self._qa_chain = None  # force rebuild
        return self._vectorstore is not None

    def is_ready(self) -> bool:
        """Check if the RAG chain is ready to answer questions."""
        return self.vectorstore is not None

    def switch_model(self, model_name: str):
        """Switch to a different Ollama model."""
        self.model_name = model_name
        self._llm = None
        self._qa_chain = None
        logger.info("Switched to model: %s", model_name)


# ---------------------------------------------------------------------------
# Relevance Reranking for Arxiv search results
# ---------------------------------------------------------------------------


def _get_vectorstore_centroid(vectorstore: Any) -> np.ndarray | None:
    """
    Compute the centroid of all vectors in a FAISS index.

    The centroid represents the "center" of the user's paper library in
    embedding space. Papers whose abstracts are close to this centroid
    are likely topically related to the user's research interests.

    Args:
        vectorstore: A langchain FAISS vector store object.

    Returns:
        A 1-D numpy array (the centroid vector), or None if the index is empty.
    """
    try:
        index = vectorstore.index
        if index is None or index.ntotal == 0:
            return None

        all_vectors = index.reconstruct_n(0, index.ntotal)
        centroid = np.mean(all_vectors, axis=0)
        # Re-normalize: mean of unit vectors is not unit-length, but dot product
        # requires unit vectors for cosine similarity
        norm = np.linalg.norm(centroid)
        if norm > 0:
            centroid = centroid / norm
        return centroid
    except Exception as exc:
        logger.warning("Failed to compute vector store centroid: %s", exc)
        return None


def compute_similarity_scores(
    texts: list[str],
    vectorstore: Any,
) -> list[float]:
    """
    Compute cosine similarity between each text and the library centroid.

    Used to rerank Arxiv search results by relevance to the user's paper library.

    Args:
        texts: List of text strings (e.g., paper abstracts).
        vectorstore: A langchain FAISS vector store object.

    Returns:
        List of similarity scores (float, 0 to 1), one per input text.
        Returns zeros if the vector store is empty or on error.
    """
    if not texts or vectorstore is None:
        return [0.0] * len(texts) if texts else []

    centroid = _get_vectorstore_centroid(vectorstore)
    if centroid is None:
        logger.info("No vector store centroid available — returning zero scores")
        return [0.0] * len(texts)

    try:
        embedding_fn = vectorstore.embedding_function
        embeddings = embedding_fn.embed_documents(texts)
        embeddings_np = np.array(embeddings)

        # Dot product = cosine similarity because both vectors are normalized
        scores = embeddings_np @ centroid
        return [float(max(0.0, min(1.0, s))) for s in scores]
    except Exception as exc:
        logger.warning("Similarity scoring failed: %s — returning zeros", exc)
        return [0.0] * len(texts)
