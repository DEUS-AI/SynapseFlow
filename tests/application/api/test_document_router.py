"""Tests for document_router with storage abstraction.

Verifies upload and content endpoints use DocumentStorage + DocumentRepository
when configured.
"""

import pytest
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from io import BytesIO


@pytest.fixture
def mock_storage():
    """In-memory DocumentStorage mock."""
    store = {}

    async def upload(container, key, data, content_type):
        store[f"{container}/{key}"] = data
        return key

    async def download(container, key):
        k = f"{container}/{key}"
        if k not in store:
            raise FileNotFoundError(f"Not found: {container}/{key}")
        return store[k]

    async def exists(container, key):
        return f"{container}/{key}" in store

    async def delete(container, key):
        store.pop(f"{container}/{key}", None)

    async def list_keys(container, prefix=""):
        return [k.split("/", 1)[1] for k in store if k.startswith(f"{container}/{prefix}")]

    storage = MagicMock()
    storage.upload = AsyncMock(side_effect=upload)
    storage.download = AsyncMock(side_effect=download)
    storage.exists = AsyncMock(side_effect=exists)
    storage.delete = AsyncMock(side_effect=delete)
    storage.list_keys = AsyncMock(side_effect=list_keys)
    storage._store = store
    return storage


@pytest.fixture
def mock_db_session():
    """Mock DB session factory."""
    session = MagicMock()
    session.added = []
    session.add = lambda obj: session.added.append(obj)
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.delete = AsyncMock()

    @asynccontextmanager
    async def factory():
        yield session

    return factory, session


@pytest.fixture
def configured_client(mock_storage, mock_db_session):
    """TestClient with storage and DB configured."""
    import application.api.document_router as doc_mod

    factory, session = mock_db_session

    # Save originals
    orig_storage = doc_mod._document_storage
    orig_db = doc_mod._db_session_factory

    doc_mod._document_storage = mock_storage
    doc_mod._db_session_factory = factory

    from application.api.main import app
    client = TestClient(app, raise_server_exceptions=False)

    yield client, mock_storage, session

    # Restore
    doc_mod._document_storage = orig_storage
    doc_mod._db_session_factory = orig_db


class TestUpload:
    def test_upload_stores_in_storage_and_postgres(self, configured_client):
        client, storage, session = configured_client

        mock_doc = MagicMock()
        mock_doc.external_id = "test123"
        mock_doc.id = "uuid-1"
        mock_doc.filename = "paper.pdf"

        with patch(
            "infrastructure.database.repositories.DocumentRepository.register_document",
            new_callable=AsyncMock,
            return_value=mock_doc,
        ):
            response = client.post(
                "/api/admin/documents/upload?category=medical",
                files=[("files", ("paper.pdf", b"%PDF-content", "application/pdf"))],
            )

        assert response.status_code == 200
        data = response.json()
        assert len(data["uploaded"]) == 1
        assert data["uploaded"][0]["id"] == "test123"
        assert data["uploaded"][0]["filename"] == "paper.pdf"

        # Verify storage was called
        storage.upload.assert_called_once()
        call_args = storage.upload.call_args
        assert call_args[0][0] == "documents"
        # Key includes doc_id: medical/{external_id}/paper.pdf
        key = call_args[0][1]
        assert key.startswith("medical/") and key.endswith("/paper.pdf")

    def test_upload_rejects_non_pdf(self, configured_client):
        client, storage, session = configured_client

        response = client.post(
            "/api/admin/documents/upload",
            files=[("files", ("notes.txt", b"hello", "text/plain"))],
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["uploaded"]) == 0
        assert len(data["failed"]) == 1
        assert "Not a PDF" in data["failed"][0]["error"]


class TestContent:
    def test_get_content_from_storage(self, configured_client):
        client, storage, session = configured_client

        # Put markdown in storage
        storage._store["markdown/paper.md"] = b"# Title\n\nContent here"

        mock_doc = MagicMock()
        mock_doc.external_id = "doc1"
        mock_doc.markdown_path = "paper.md"
        mock_doc.filename = "paper.pdf"

        with patch(
            "infrastructure.database.repositories.DocumentRepository.get_by_external_id",
            new_callable=AsyncMock,
            return_value=mock_doc,
        ):
            response = client.get("/api/admin/documents/doc1/content")

        assert response.status_code == 200
        data = response.json()
        assert data["content"] == "# Title\n\nContent here"
        assert data["content_type"] == "text/markdown"
        assert data["word_count"] == 4  # "#", "Title", "Content", "here"

    def test_get_content_not_found(self, configured_client):
        client, storage, session = configured_client

        with patch(
            "infrastructure.database.repositories.DocumentRepository.get_by_external_id",
            new_callable=AsyncMock,
            return_value=None,
        ):
            response = client.get("/api/admin/documents/missing/content")

        assert response.status_code == 404
