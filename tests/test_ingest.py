"""Tests for the PDF ingest pipeline."""

from src.ingest import (
    INGEST_METADATA_FILE,
    _metadata_path,
    get_ingested_files,
    load_ingest_metadata,
    remove_ingest_metadata,
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
