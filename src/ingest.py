"""
PDF Ingest Pipeline: PDF → Text → Chunks → BGE-m3 Embeddings → FAISS Index

Usage:
    from src.ingest import ingest_pdf, load_vectorstore

    # Ingest a single PDF
    ingest_pdf("path/to/paper.pdf", store_dir="vectorstore")

    # Load existing index
    vectorstore = load_vectorstore("vectorstore")
"""

import json
import logging
import os
import re
import time
from collections.abc import Callable
from pathlib import Path

from langchain_community.document_loaders import PyMuPDFLoader
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

logger = logging.getLogger(__name__)

# ---------- Configuration ----------

EMBEDDING_MODEL = "BAAI/bge-m3"
DEFAULT_CHUNK_SIZE = 768
DEFAULT_CHUNK_OVERLAP = 50
DEFAULT_STORE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "vectorstore")
INGEST_METADATA_FILE = "ingest_metadata.json"

# Academic section header patterns (for semantic chunking)
SECTION_PATTERNS = [
    # English academic sections (most common first)
    r"(?i)^(?:#{1,3}\s*)?(?:abstract)\s*$",
    r"(?i)^(?:#{1,3}\s*)?(?:introduction)\s*$",
    r"(?i)^(?:#{1,3}\s*)?(?:background|background\s*(?:and|&)\s*related\s*work)\s*$",
    r"(?i)^(?:#{1,3}\s*)?(?:related\s*work|related\s*(?:works|studies|research))\s*$",
    r"(?i)^(?:#{1,3}\s*)?(?:methodology|method|approach|proposed\s*(?:method|approach|framework|model|system))\s*$",
    r"(?i)^(?:#{1,3}\s*)?(?:simulation\s*setup|experimental\s*setup|experimental\s*(?:details|procedure|design))\s*$",
    r"(?i)^(?:#{1,3}\s*)?(?:results?|experimental\s*results?|simulation\s*results?|results?\s*(?:and|&)\s*discussion)\s*$",
    r"(?i)^(?:#{1,3}\s*)?(?:discussion|analysis)\s*$",
    r"(?i)^(?:#{1,3}\s*)?(?:conclusion|conclusions|summary|concluding\s*remarks)\s*$",
    r"(?i)^(?:#{1,3}\s*)?(?:references|bibliography)\s*$",
    r"(?i)^(?:#{1,3}\s*)?(?:acknowledgments?|acknowledgements?)\s*$",
    # Korean academic sections
    r"(?i)^(?:#{1,3}\s*)?(?:초록|개요)\s*$",
    r"(?i)^(?:#{1,3}\s*)?(?:서론|서\s*론|소개)\s*$",
    r"(?i)^(?:#{1,3}\s*)?(?:배경|이론적\s*배경|관련\s*연구|관련\s*이론)\s*$",
    r"(?i)^(?:#{1,3}\s*)?(?:방법론|연구\s*방법|실험\s*방법|제안\s*방법)\s*$",
    r"(?i)^(?:#{1,3}\s*)?(?:실험|실험\s*결과|시뮬레이션\s*결과)\s*$",
    r"(?i)^(?:#{1,3}\s*)?(?:결과\s*(?:및\s*)?토론|토론|분석)\s*$",
    r"(?i)^(?:#{1,3}\s*)?(?:결론|요약)\s*$",
    r"(?i)^(?:#{1,3}\s*)?(?:참고\s*문헌|참고문헌|인용\s*문헌)\s*$",
]

# ---------- Embedding Model ----------

_embedding_model = None


def get_embedding_model():
    """Get or initialize the BGE-m3 embedding model (singleton)."""
    global _embedding_model
    if _embedding_model is None:
        logger.info(f"Loading embedding model: {EMBEDDING_MODEL}")
        _embedding_model = HuggingFaceEmbeddings(
            model_name=EMBEDDING_MODEL,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},  # for cosine similarity
        )
    return _embedding_model


# ---------- Ingest Metadata Persistence ----------

# Schema of ingest_metadata.json:
# {
#   "files": {
#     "filename.pdf": {
#       "ingested_at": 1234567890.0,   # Unix timestamp
#       "chunks": 42,                  # Number of chunks for this file
#       "pages": 10,                   # Number of pages
#       "path": "data/papers/filename.pdf"
#     },
#     ...
#   }
# }


def _metadata_path(store_dir: str) -> str:
    """Get the full path to the ingest metadata JSON file."""
    return os.path.join(store_dir, INGEST_METADATA_FILE)


def save_ingest_metadata(
    store_dir: str,
    filename: str,
    chunk_count: int = 0,
    page_count: int = 0,
    file_path: str = "",
):
    """
    Record that a PDF has been ingested into the vector store.

    Creates/updates a JSON metadata file alongside the FAISS index so the
    UI can display which papers are available without re-uploading.
    """
    metadata = {}
    meta_path = _metadata_path(store_dir)
    if os.path.exists(meta_path):
        try:
            with open(meta_path, encoding="utf-8") as f:
                metadata = json.load(f)
        except (OSError, json.JSONDecodeError):
            logger.warning(f"Corrupt metadata file, starting fresh: {meta_path}")

    if "files" not in metadata:
        metadata["files"] = {}

    metadata["files"][filename] = {
        "ingested_at": time.time(),
        "chunks": chunk_count,
        "pages": page_count,
        "path": file_path,
    }

    os.makedirs(store_dir, exist_ok=True)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    logger.info(f"Updated ingest metadata: {filename} ({chunk_count} chunks)")


def load_ingest_metadata(store_dir: str) -> dict:
    """
    Load the ingest metadata for all previously ingested papers.

    Returns:
        Dict with {"files": {"filename.pdf": {...}, ...}} or empty dict if none.
    """
    meta_path = _metadata_path(store_dir)
    if not os.path.exists(meta_path):
        return {"files": {}}
    try:
        with open(meta_path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        logger.warning(f"Failed to load ingest metadata: {e}")
        return {"files": {}}


def get_ingested_files(store_dir: str) -> list[str]:
    """
    Get the sorted list of filenames that have been ingested.

    Returns:
        List of filenames (e.g., ["paper1.pdf", "paper2.pdf"]).
    """
    metadata = load_ingest_metadata(store_dir)
    return sorted(metadata.get("files", {}).keys())


def remove_ingest_metadata(store_dir: str, filename: str) -> bool:
    """
    Remove a file from the ingest metadata (does NOT touch the FAISS index).

    Returns:
        True if the file was found and removed, False otherwise.
    """
    metadata = load_ingest_metadata(store_dir)
    if filename in metadata.get("files", {}):
        del metadata["files"][filename]
        meta_path = _metadata_path(store_dir)
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        logger.info(f"Removed from ingest metadata: {filename}")
        return True
    return False


# ---------- PDF Loading ----------


def load_pdf(file_path: str) -> list[Document]:
    """
    Load a PDF file and return a list of Document objects (one per page).

    Args:
        file_path: Absolute or relative path to the PDF file.

    Returns:
        List of Document objects with page_content and metadata (source, page).
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"PDF not found: {file_path}")

    logger.info(f"Loading PDF: {file_path}")
    loader = PyMuPDFLoader(file_path)
    documents = loader.load()

    # Add filename to metadata
    filename = Path(file_path).name
    for doc in documents:
        doc.metadata["source_filename"] = filename

    logger.info(f"Loaded {len(documents)} pages from {filename}")
    return documents


# ---------- Text Splitting ----------


def _detect_section(text: str) -> str | None:
    """Detect which academic section a line of text belongs to.

    Checks against known section header patterns, stripping common
    numbering prefixes (e.g. "2.1", "II.", "A.") first.
    """
    text_stripped = text.strip()
    if not text_stripped:
        return None

    # Strip markdown heading markers
    cleaned = text_stripped.lstrip("#").strip()
    # Strip numbering prefixes: "2.1", "II.", "A.", "(1)", "1)"
    cleaned = re.sub(r"^[\dIVXLCDM]+[\.\)]\s*", "", cleaned)
    cleaned = re.sub(r"^\([\dIVXLCDM]+\)\s*", "", cleaned)
    cleaned = re.sub(r"^[A-Z][\.\)]\s*", "", cleaned)

    for pattern in SECTION_PATTERNS:
        if re.match(pattern, cleaned):
            return cleaned.strip().lower()
    return None


def _split_by_sections(text: str) -> list[tuple[str, str]]:
    """
    Split text into (section_name, content) segments at section boundaries.

    Returns a list of (section_name, text_block) tuples. The first segment
    that appears before any detected section header gets section_name = None
    (defaults to "background" for leading content).
    """
    lines = text.split("\n")
    segments: list[tuple[str, str]] = []
    current_section: str | None = None
    current_lines: list[str] = []

    for line in lines:
        detected = _detect_section(line)
        if detected is not None:
            # Flush previous section content
            if current_lines:
                block = "\n".join(current_lines).strip()
                if block:
                    segments.append((current_section or "background", block))
                current_lines = []
            current_section = detected
        else:
            current_lines.append(line)

    # Flush remaining
    if current_lines:
        block = "\n".join(current_lines).strip()
        if block:
            segments.append((current_section or "background", block))

    return segments


def split_documents(
    documents: list[Document],
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[Document]:
    """
    Split documents into overlapping chunks with section awareness.

    Academic section headers (Introduction, Methodology, Results, etc.) are
    detected and used as natural chunk boundaries. Each chunk inherits a
    ``section_name`` metadata field indicating which section it belongs to.

    For technical TCAD papers, RecursiveCharacterTextSplitter with
    separators prioritizes paragraph → sentence → phrase boundaries
    within each section.

    Args:
        documents: List of Document objects with page-level metadata.
        chunk_size: Target chunk size in characters.
        chunk_overlap: Overlap between consecutive chunks.

    Returns:
        List of chunked Document objects with section_name in metadata.
    """
    text_splitter = RecursiveCharacterTextSplitter(
        separators=["\n\n", "\n", ". ", " ", ""],
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        is_separator_regex=False,
    )

    all_chunks: list[Document] = []

    for doc in documents:
        page_text = doc.page_content
        page_meta = dict(doc.metadata)  # copy base metadata (source, page, source_filename)

        # Split page into sections
        sections = _split_by_sections(page_text)

        for section_name, section_text in sections:
            if not section_text.strip():
                continue

            # Create a temporary document for this section to split further
            section_doc = Document(page_content=section_text, metadata={})
            section_chunks = text_splitter.split_documents([section_doc])

            for chunk in section_chunks:
                chunk.metadata.update(page_meta)
                chunk.metadata["section_name"] = section_name
                all_chunks.append(chunk)

    if not all_chunks:
        # Fallback: split without section awareness (original behavior)
        logger.warning("No section-aware chunks created — falling back to flat split")
        all_chunks = text_splitter.split_documents(documents)

    logger.info(
        "Split %d pages into %d chunks (size=%s, overlap=%s)",
        len(documents),
        len(all_chunks),
        chunk_size,
        chunk_overlap,
    )
    return all_chunks


# ---------- Vector Store ----------


def build_vectorstore(
    chunks: list[Document],
    store_dir: str = DEFAULT_STORE_DIR,
    progress_callback: Callable[[str, int], None] | None = None,
) -> FAISS:
    """
    Embed chunks and build a FAISS vector store, then save to disk.

    Uses batch embedding (via mini-batches) for ~2x speedup over sequential.

    Args:
        chunks: List of chunked Document objects.
        store_dir: Directory to save the FAISS index.
        progress_callback: Optional fn(message, percent_0_100) for UI progress.

    Returns:
        FAISS vector store object.
    """
    embedding_model = get_embedding_model()
    n = len(chunks)

    logger.info(f"Building FAISS index with {n} chunks...")

    # Batch embed with progress reporting (mini-batches of 10)
    texts = [c.page_content for c in chunks]
    metadatas = [c.metadata for c in chunks]
    all_embeddings: list[list[float]] = []

    batch_size = 10
    for start in range(0, n, batch_size):
        end = min(start + batch_size, n)
        batch_texts = texts[start:end]
        batch_embs = embedding_model.embed_documents(batch_texts)
        all_embeddings.extend(batch_embs)

        if progress_callback:
            pct = int(10 + 80 * end / n)
            progress_callback(f"Embedding {end}/{n} chunks...", pct)

    # Build FAISS index from pre-computed embeddings (batch)
    text_embedding_pairs = list(zip(texts, all_embeddings, strict=False))
    vectorstore = FAISS.from_embeddings(
        text_embeddings=text_embedding_pairs,
        embedding=embedding_model,
        metadatas=metadatas,
    )

    # Save to disk
    if progress_callback:
        progress_callback("Saving vector store...", 95)
    os.makedirs(store_dir, exist_ok=True)
    vectorstore.save_local(store_dir)
    logger.info(f"FAISS index saved to {store_dir}")

    if progress_callback:
        progress_callback("Done!", 100)

    return vectorstore


# ---------- High-Level API ----------


def ingest_pdf(
    file_path: str,
    store_dir: str = DEFAULT_STORE_DIR,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    progress_callback: Callable[[str, int], None] | None = None,
) -> FAISS:
    """
    Full ingestion pipeline: PDF → chunks → batch embeddings → FAISS.

    Also persists ingest metadata so the UI knows which files are available
    across sessions without re-uploading.

    Args:
        file_path: Path to the PDF file.
        store_dir: Directory to save/update the FAISS index.
        chunk_size: Character chunk size.
        chunk_overlap: Chunk overlap.
        progress_callback: Optional fn(message, percent_0_100) for UI progress.

    Returns:
        FAISS vector store with the ingested content.
    """
    # 1. Load PDF
    if progress_callback:
        progress_callback("Loading PDF...", 5)
    documents = load_pdf(file_path)

    # 2. Split into chunks
    if progress_callback:
        progress_callback("Splitting text into chunks...", 8)
    chunks = split_documents(documents, chunk_size, chunk_overlap)

    # 3. Extract page count from documents
    page_count = len(documents)

    # 4. Build or update vector store
    if os.path.exists(os.path.join(store_dir, "index.faiss")):
        logger.info("Existing index found, merging new chunks...")
        if progress_callback:
            progress_callback("Loading existing index...", 10)
        embedding_model = get_embedding_model()

        texts = [c.page_content for c in chunks]
        metadatas = [c.metadata for c in chunks]
        all_embeddings: list[list[float]] = []

        n = len(texts)
        batch_size = 10
        for start in range(0, n, batch_size):
            end = min(start + batch_size, n)
            batch_texts = texts[start:end]
            batch_embs = embedding_model.embed_documents(batch_texts)
            all_embeddings.extend(batch_embs)
            if progress_callback:
                pct = int(10 + 80 * end / n)
                progress_callback(f"Merging {end}/{n} chunks...", pct)

        text_embedding_pairs = list(zip(texts, all_embeddings, strict=False))
        existing = FAISS.load_local(
            store_dir, embedding_model, allow_dangerous_deserialization=True
        )
        existing.add_embeddings(
            text_embeddings=text_embedding_pairs,
            metadatas=metadatas,
        )

        if progress_callback:
            progress_callback("Saving merged index...", 95)
        existing.save_local(store_dir)
        logger.info(f"Merged and saved to {store_dir}")
        vectorstore = existing
    else:
        vectorstore = build_vectorstore(chunks, store_dir, progress_callback)

    # 5. Record ingest metadata (filename, chunk count, page count)
    filename = Path(file_path).name
    save_ingest_metadata(
        store_dir=store_dir,
        filename=filename,
        chunk_count=len(chunks),
        page_count=page_count,
        file_path=file_path,
    )

    if progress_callback:
        progress_callback("Done!", 100)

    return vectorstore


def load_vectorstore(store_dir: str = DEFAULT_STORE_DIR) -> FAISS | None:
    """
    Load a previously saved FAISS index from disk.

    Args:
        store_dir: Directory containing the FAISS index files.

    Returns:
        FAISS vector store, or None if not found.
    """
    index_path = os.path.join(store_dir, "index.faiss")
    if not os.path.exists(index_path):
        logger.warning(f"No FAISS index found at {store_dir}")
        return None

    embedding_model = get_embedding_model()
    vectorstore = FAISS.load_local(store_dir, embedding_model, allow_dangerous_deserialization=True)
    logger.info(f"Loaded FAISS index from {store_dir} ({vectorstore.index.ntotal} vectors)")
    return vectorstore


def get_store_info(store_dir: str = DEFAULT_STORE_DIR) -> dict:
    """
    Get information about the current vector store.

    Returns:
        Dict with store status information.
    """
    index_path = os.path.join(store_dir, "index.faiss")
    if not os.path.exists(index_path):
        return {"exists": False, "path": store_dir, "vector_count": 0}

    vs = load_vectorstore(store_dir)
    return {
        "exists": True,
        "path": store_dir,
        "vector_count": vs.index.ntotal if vs else 0,
        "embedding_model": EMBEDDING_MODEL,
    }
