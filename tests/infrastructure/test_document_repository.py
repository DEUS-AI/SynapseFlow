"""Tests for DocumentRepository tracking methods.

Uses an in-memory SQLite database. Registers a JSONB→JSON type adapter
since SQLite doesn't support JSONB natively.
"""

import pytest
from uuid import uuid4

from sqlalchemy import JSON
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import sessionmaker

from infrastructure.database.models import Document
from infrastructure.database.repositories import DocumentRepository


@pytest.fixture
async def async_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    # Register JSONB → JSON adapter for SQLite
    from sqlalchemy.ext.compiler import compiles

    @compiles(JSONB, "sqlite")
    def compile_jsonb_sqlite(type_, compiler, **kw):
        return compiler.visit_JSON(JSON(), **kw)

    async with engine.begin() as conn:
        await conn.run_sync(Document.__table__.create)

    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session

    await engine.dispose()


@pytest.mark.asyncio
async def test_register_document(async_session):
    repo = DocumentRepository(async_session)
    doc = await repo.register_document(
        filename="test.pdf",
        category="general",
        size_bytes=1024,
        storage_key="general/test.pdf",
        external_id="abc123",
    )
    assert doc.filename == "test.pdf"
    assert doc.external_id == "abc123"
    assert doc.source_path == "general/test.pdf"
    assert doc.status == "pending"
    assert doc.id is not None


@pytest.mark.asyncio
async def test_register_generates_external_id(async_session):
    repo = DocumentRepository(async_session)
    doc = await repo.register_document(
        filename="auto.pdf",
        category="medical",
        size_bytes=2048,
        storage_key="medical/auto.pdf",
    )
    assert doc.external_id is not None
    assert len(doc.external_id) == 12


@pytest.mark.asyncio
async def test_update_status(async_session):
    repo = DocumentRepository(async_session)
    doc = await repo.register_document(
        filename="status.pdf", category="test", size_bytes=100,
        storage_key="test/status.pdf", external_id="st1",
    )
    updated = await repo.update_status(doc.id, "processing")
    assert updated.status == "processing"

    completed = await repo.update_status(doc.id, "completed")
    assert completed.status == "completed"


@pytest.mark.asyncio
async def test_update_status_with_error(async_session):
    repo = DocumentRepository(async_session)
    doc = await repo.register_document(
        filename="fail.pdf", category="test", size_bytes=100,
        storage_key="test/fail.pdf", external_id="f1",
    )
    updated = await repo.update_status(doc.id, "failed", error_message="boom")
    assert updated.status == "failed"
    assert updated.error_message == "boom"


@pytest.mark.asyncio
async def test_update_status_nonexistent(async_session):
    repo = DocumentRepository(async_session)
    result = await repo.update_status(uuid4(), "processing")
    assert result is None


@pytest.mark.asyncio
async def test_update_ingestion_results(async_session):
    repo = DocumentRepository(async_session)
    doc = await repo.register_document(
        filename="ingest.pdf", category="test", size_bytes=500,
        storage_key="test/ingest.pdf", external_id="ig1",
    )
    updated = await repo.update_ingestion_results(
        doc.id, entity_count=42, relationship_count=15, markdown_key="ingest.md"
    )
    assert updated.entity_count == 42
    assert updated.relationship_count == 15
    assert updated.markdown_path == "ingest.md"


@pytest.mark.asyncio
async def test_update_ingestion_results_no_markdown(async_session):
    repo = DocumentRepository(async_session)
    doc = await repo.register_document(
        filename="no_md.pdf", category="test", size_bytes=500,
        storage_key="test/no_md.pdf", external_id="nm1",
    )
    updated = await repo.update_ingestion_results(
        doc.id, entity_count=10, relationship_count=5
    )
    assert updated.entity_count == 10
    assert updated.markdown_path is None


@pytest.mark.asyncio
async def test_list_by_status(async_session):
    repo = DocumentRepository(async_session)
    await repo.register_document(
        filename="a.pdf", category="test", size_bytes=100,
        storage_key="a.pdf", external_id="a1",
    )
    doc_b = await repo.register_document(
        filename="b.pdf", category="test", size_bytes=200,
        storage_key="b.pdf", external_id="b1",
    )
    await repo.update_status(doc_b.id, "completed")

    pending = await repo.list_by_status("pending")
    assert len(pending) == 1
    assert pending[0].filename == "a.pdf"

    completed = await repo.list_by_status("completed")
    assert len(completed) == 1
    assert completed[0].filename == "b.pdf"
