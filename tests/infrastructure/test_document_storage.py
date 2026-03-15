"""Tests for LocalDocumentStorage."""

import pytest
from pathlib import Path

from infrastructure.document_storage import LocalDocumentStorage


@pytest.fixture
def storage(tmp_path):
    return LocalDocumentStorage(base_dir=str(tmp_path))


@pytest.mark.asyncio
async def test_upload_and_download(storage):
    data = b"hello world"
    key = await storage.upload("docs", "test.txt", data, "text/plain")
    assert key == "test.txt"
    result = await storage.download("docs", "test.txt")
    assert result == data


@pytest.mark.asyncio
async def test_exists(storage):
    assert not await storage.exists("docs", "missing.txt")
    await storage.upload("docs", "found.txt", b"data", "text/plain")
    assert await storage.exists("docs", "found.txt")


@pytest.mark.asyncio
async def test_delete(storage):
    await storage.upload("docs", "to_delete.txt", b"data", "text/plain")
    assert await storage.exists("docs", "to_delete.txt")
    await storage.delete("docs", "to_delete.txt")
    assert not await storage.exists("docs", "to_delete.txt")


@pytest.mark.asyncio
async def test_delete_nonexistent(storage):
    # Should not raise
    await storage.delete("docs", "nonexistent.txt")


@pytest.mark.asyncio
async def test_download_not_found(storage):
    with pytest.raises(FileNotFoundError):
        await storage.download("docs", "missing.txt")


@pytest.mark.asyncio
async def test_list_keys(storage):
    await storage.upload("docs", "a.txt", b"1", "text/plain")
    await storage.upload("docs", "b.txt", b"2", "text/plain")
    await storage.upload("docs", "sub/c.txt", b"3", "text/plain")

    keys = await storage.list_keys("docs")
    assert sorted(keys) == ["a.txt", "b.txt", "sub/c.txt"]


@pytest.mark.asyncio
async def test_list_keys_with_prefix(storage):
    await storage.upload("docs", "reports/jan.txt", b"1", "text/plain")
    await storage.upload("docs", "reports/feb.txt", b"2", "text/plain")
    await storage.upload("docs", "other.txt", b"3", "text/plain")

    keys = await storage.list_keys("docs", prefix="reports/")
    assert sorted(keys) == ["reports/feb.txt", "reports/jan.txt"]


@pytest.mark.asyncio
async def test_list_keys_empty_container(storage):
    keys = await storage.list_keys("nonexistent")
    assert keys == []


@pytest.mark.asyncio
async def test_upload_overwrites(storage):
    await storage.upload("docs", "file.txt", b"old", "text/plain")
    await storage.upload("docs", "file.txt", b"new", "text/plain")
    result = await storage.download("docs", "file.txt")
    assert result == b"new"


@pytest.mark.asyncio
async def test_nested_key(storage):
    await storage.upload("docs", "a/b/c/deep.txt", b"deep", "text/plain")
    assert await storage.exists("docs", "a/b/c/deep.txt")
    result = await storage.download("docs", "a/b/c/deep.txt")
    assert result == b"deep"
