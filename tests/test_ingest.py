"""Tests for the PDF ingest pipeline."""

import json
import os
from pathlib import Path

import pytest

from src.ingest import (
    INGEST_METADATA_FILE,
    _metadata_path,
    get_ingested_files,
    load_ingest_metadata,
    remove_ingest_metadata,
    reset_vectorstore,
    save_ingest_metadata,
)


class TestIngestMetadata:
    """Persistent ingest metadata (JSON alongside FAISS index)."""

    def test_metadata_path_ends_with_json(self, tmp_path):
        path = _metadata_path(str(tmp_path))
        assert path.endswith(INGEST_METADATA_FILE)

    def test_save_and_load_metadata(self, tmp_path):
        store_dir = str(tmp_path)
        save_ingest_metadata(store_dir, "paper1.pdf", chunk_count=10, page_count=5)
        meta = load_ingest_metadata(store_dir)
        files = meta.get("files", {})
        assert "paper1.pdf" in files
        assert files["paper1.pdf"]["chunks"] == 10
        assert files["paper1.pdf"]["pages"] == 5

    def test_get_ingested_files(self, tmp_path):
        store_dir = str(tmp_path)
        save_ingest_metadata(store_dir, "a.pdf", chunk_count=1)
        save_ingest_metadata(store_dir, "b.pdf", chunk_count=2)
        files = get_ingested_files(store_dir)
        assert files == ["a.pdf", "b.pdf"]

    def test_remove_metadata(self, tmp_path):
        store_dir = str(tmp_path)
        save_ingest_metadata(store_dir, "keep.pdf", chunk_count=1)
        save_ingest_metadata(store_dir, "remove.pdf", chunk_count=2)
        assert remove_ingest_metadata(store_dir, "remove.pdf") is True
        assert get_ingested_files(store_dir) == ["keep.pdf"]

    def test_remove_nonexistent_returns_false(self, tmp_path):
        assert remove_ingest_metadata(str(tmp_path), "ghost.pdf") is False

    def test_empty_store_returns_empty(self, tmp_path):
        meta = load_ingest_metadata(str(tmp_path))
        assert meta == {"files": {}}

    def test_load_empty_store_no_exception(self, tmp_path):
        files = get_ingested_files(str(tmp_path))
        assert files == []


class TestIngestMetadataSmoke:
    """Quick smoke tests against the real (non-destructive) vectorstore."""

    def test_real_vectorstore_metadata_loads(self):
        """Verify the real vectorstore metadata loads without error."""
        meta = load_ingest_metadata("vectorstore")
        assert "files" in meta


class TestLayoutAwareExtraction:
    """Integration tests for pymupdf4llm layout-aware PDF extraction."""

    PDF_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "PDF")

    def _pdf_path(self, name: str) -> str:
        return os.path.join(self.PDF_DIR, name)

    def test_load_real_pdf_returns_documents(self):
        """Load a real PDF and verify Document structure."""
        path = self._pdf_path("s41598-026-48536-w.pdf")
        if not os.path.exists(path):
            pytest.skip(f"Test PDF not found: {path}")

        from src.ingest import load_pdf

        docs = load_pdf(path)
        assert len(docs) > 0, "Expected at least one page"
        for doc in docs:
            assert doc.page_content, "Expected non-empty page content"
            assert "source" in doc.metadata
            assert "page" in doc.metadata
            assert "source_filename" in doc.metadata
            assert doc.metadata["page"] >= 0

    def test_metadata_includes_tables(self):
        """Verify table_count and has_tables metadata are present."""
        path = self._pdf_path("s41598-026-48536-w.pdf")
        if not os.path.exists(path):
            pytest.skip(f"Test PDF not found: {path}")

        from src.ingest import load_pdf

        docs = load_pdf(path)
        for doc in docs:
            assert "table_count" in doc.metadata
            assert "has_tables" in doc.metadata
            assert isinstance(doc.metadata["table_count"], int)
            assert isinstance(doc.metadata["has_tables"], bool)
            assert doc.metadata["table_count"] >= 0
            assert doc.metadata["has_tables"] == (doc.metadata["table_count"] > 0)

    def test_load_nonexistent_raises_error(self):
        """Verify FileNotFoundError for bad paths."""
        from src.ingest import load_pdf

        with pytest.raises(FileNotFoundError):
            load_pdf("nonexistent_file_xyz.pdf")

    def test_section_chunker_works_with_markdown(self):
        """Verify section-aware chunking produces section_name metadata from markdown."""
        path = self._pdf_path("s41598-026-48536-w.pdf")
        if not os.path.exists(path):
            pytest.skip(f"Test PDF not found: {path}")

        from src.ingest import load_pdf, split_documents

        docs = load_pdf(path)
        chunks = split_documents(docs)
        assert len(chunks) > 0, "Expected at least one chunk"

        # Verify section_name metadata
        section_names = {c.metadata.get("section_name") for c in chunks}
        assert len(section_names) > 0, "Expected at least one section name"
        # At least some sections should be detected (common sections like abstract, introduction)
        assert all(isinstance(s, str) for s in section_names if s is not None), (
            "Section names must be strings"
        )

    def test_metadata_schema_unchanged(self):
        """Verify split documents still have all expected metadata keys."""
        path = self._pdf_path("s41598-026-48536-w.pdf")
        if not os.path.exists(path):
            pytest.skip(f"Test PDF not found: {path}")

        from src.ingest import load_pdf, split_documents

        docs = load_pdf(path)
        chunks = split_documents(docs)

        for chunk in chunks:
            # Core metadata must be preserved
            assert "source" in chunk.metadata
            assert "page" in chunk.metadata
            assert "source_filename" in chunk.metadata
            assert "section_name" in chunk.metadata
            # New table metadata must also be present
            assert "table_count" in chunk.metadata
            assert "has_tables" in chunk.metadata

    def test_paper_title_in_metadata(self):
        """Verify paper_title is auto-detected from real PDF."""
        path = self._pdf_path("s41598-026-48536-w.pdf")
        if not os.path.exists(path):
            pytest.skip(f"Test PDF not found: {path}")

        from src.ingest import load_pdf

        docs = load_pdf(path)
        for doc in docs:
            assert "paper_title" in doc.metadata
            title = doc.metadata["paper_title"]
            assert isinstance(title, str) and len(title) > 0, (
                f"Expected non-empty paper_title, got {title!r}"
            )
            # Title should not be the filename stem
            assert title != "s41598-026-48536-w", (
                f"Expected detected title, not filename: {title!r}"
            )

    def test_paper_title_consistency_across_pages(self):
        """Verify all pages share the same detected paper_title."""
        path = self._pdf_path("s41598-026-48536-w.pdf")
        if not os.path.exists(path):
            pytest.skip(f"Test PDF not found: {path}")

        from src.ingest import load_pdf

        docs = load_pdf(path)
        titles = {doc.metadata["paper_title"] for doc in docs}
        assert len(titles) == 1, f"Expected same paper_title across all pages, got: {titles}"

    def test_extract_paper_title_returns_string(self):
        """Verify _extract_paper_title returns a non-empty string."""
        path = self._pdf_path("s41598-026-48536-w.pdf")
        if not os.path.exists(path):
            pytest.skip(f"Test PDF not found: {path}")

        from src.ingest import _extract_paper_title

        title = _extract_paper_title(path)
        assert isinstance(title, str) and len(title) > 0

    def test_extract_paper_title_fallback_to_filename(self):
        """Verify _extract_paper_title falls back to filename for bad paths."""
        from src.ingest import _extract_paper_title

        title = _extract_paper_title("nonexistent.pdf")
        assert title == "nonexistent"


class TestResetVectorstore:
    """Dangerous vector store reset function."""

    def test_reset_requires_confirm(self):
        """Verify reset_vectorstore raises ValueError without confirm=True."""
        with pytest.raises(ValueError, match="DANGEROUS"):
            reset_vectorstore(confirm=False)

    def test_reset_clears_index_and_metadata(self, tmp_path):
        """Verify reset deletes FAISS files and metadata."""
        store_dir = str(tmp_path)

        os.makedirs(store_dir, exist_ok=True)
        Path(os.path.join(store_dir, "index.faiss")).write_text("fake")
        Path(os.path.join(store_dir, "index.pkl")).write_text("fake")
        with open(os.path.join(store_dir, "ingest_metadata.json"), "w") as f:
            json.dump({"files": {"test.pdf": {"title": "test"}}}, f)

        assert reset_vectorstore(store_dir, confirm=True) is True
        assert not os.path.exists(os.path.join(store_dir, "index.faiss"))
        assert not os.path.exists(os.path.join(store_dir, "index.pkl"))
        assert not os.path.exists(os.path.join(store_dir, "ingest_metadata.json"))

    def test_reset_empty_store_returns_false(self, tmp_path):
        """Verify reset on empty store returns False."""
        assert reset_vectorstore(str(tmp_path), confirm=True) is False

    def test_reset_preserves_non_index_files(self, tmp_path):
        """Verify reset only deletes vector store files, not other files."""
        store_dir = str(tmp_path)
        os.makedirs(store_dir, exist_ok=True)
        Path(os.path.join(store_dir, "other_file.txt")).write_text("keep me")

        reset_vectorstore(store_dir, confirm=True)
        assert os.path.exists(os.path.join(store_dir, "other_file.txt"))


class TestIngestMetadataWithTitle:
    """Ingest metadata persistence with auto-detected title."""

    def test_save_metadata_with_title(self, tmp_path):
        """Verify title is stored in ingest metadata."""
        store_dir = str(tmp_path)
        save_ingest_metadata(
            store_dir,
            "paper1.pdf",
            chunk_count=10,
            page_count=5,
            title="Test Paper Title",
        )
        meta = load_ingest_metadata(store_dir)
        assert meta["files"]["paper1.pdf"]["title"] == "Test Paper Title"

    def test_save_metadata_without_title_falls_back_to_filename(self, tmp_path):
        """Verify missing title falls back to filename."""
        store_dir = str(tmp_path)
        save_ingest_metadata(store_dir, "paper1.pdf", chunk_count=1)
        meta = load_ingest_metadata(store_dir)
        assert meta["files"]["paper1.pdf"]["title"] == "paper1.pdf"
