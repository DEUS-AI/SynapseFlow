"""Document Storage Abstraction.

Provides a protocol for document storage with local filesystem
and Azure Blob Storage implementations.
"""

import os
import logging
from pathlib import Path
from typing import List, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


@runtime_checkable
class DocumentStorage(Protocol):
    """Protocol for document storage backends."""

    async def upload(self, container: str, key: str, data: bytes, content_type: str) -> str: ...
    async def download(self, container: str, key: str) -> bytes: ...
    async def exists(self, container: str, key: str) -> bool: ...
    async def delete(self, container: str, key: str) -> None: ...
    async def list_keys(self, container: str, prefix: str = "") -> List[str]: ...


class LocalDocumentStorage:
    """Filesystem-backed document storage for local development."""

    def __init__(self, base_dir: str = "storage"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, container: str, key: str) -> Path:
        return self.base_dir / container / key

    async def upload(self, container: str, key: str, data: bytes, content_type: str) -> str:
        path = self._path(container, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        logger.info(f"Stored locally: {container}/{key} ({len(data)} bytes)")
        return key

    async def download(self, container: str, key: str) -> bytes:
        path = self._path(container, key)
        if not path.exists():
            raise FileNotFoundError(f"Not found: {container}/{key}")
        return path.read_bytes()

    async def exists(self, container: str, key: str) -> bool:
        return self._path(container, key).exists()

    async def delete(self, container: str, key: str) -> None:
        path = self._path(container, key)
        if path.exists():
            path.unlink()

    async def list_keys(self, container: str, prefix: str = "") -> List[str]:
        container_path = self.base_dir / container
        if not container_path.exists():
            return []
        results = []
        for path in container_path.rglob("*"):
            if path.is_file():
                rel = str(path.relative_to(container_path))
                if rel.startswith(prefix):
                    results.append(rel)
        return sorted(results)


class BlobDocumentStorage:
    """Azure Blob Storage-backed document storage."""

    def __init__(self, connection_string: str):
        from azure.storage.blob.aio import BlobServiceClient
        self.client = BlobServiceClient.from_connection_string(connection_string)

    async def upload(self, container: str, key: str, data: bytes, content_type: str) -> str:
        from azure.storage.blob import ContentSettings
        container_client = self.client.get_container_client(container)
        await container_client.upload_blob(
            name=key,
            data=data,
            content_settings=ContentSettings(content_type=content_type),
            overwrite=True,
        )
        logger.info(f"Stored in blob: {container}/{key} ({len(data)} bytes)")
        return key

    async def download(self, container: str, key: str) -> bytes:
        from azure.core.exceptions import ResourceNotFoundError
        try:
            blob_client = self.client.get_blob_client(container, key)
            stream = await blob_client.download_blob()
            return await stream.readall()
        except ResourceNotFoundError:
            raise FileNotFoundError(f"Not found: {container}/{key}")

    async def exists(self, container: str, key: str) -> bool:
        from azure.core.exceptions import ResourceNotFoundError
        try:
            blob_client = self.client.get_blob_client(container, key)
            await blob_client.get_blob_properties()
            return True
        except ResourceNotFoundError:
            return False

    async def delete(self, container: str, key: str) -> None:
        from azure.core.exceptions import ResourceNotFoundError
        try:
            blob_client = self.client.get_blob_client(container, key)
            await blob_client.delete_blob()
        except ResourceNotFoundError:
            pass

    async def list_keys(self, container: str, prefix: str = "") -> List[str]:
        container_client = self.client.get_container_client(container)
        results = []
        async for blob in container_client.list_blobs(name_starts_with=prefix):
            results.append(blob.name)
        return results


def create_document_storage() -> DocumentStorage:
    """Create document storage based on DOCUMENT_STORAGE_BACKEND env var."""
    backend = os.environ.get("DOCUMENT_STORAGE_BACKEND", "local")

    if backend == "blob":
        connection_string = os.environ.get("AZURE_STORAGE_CONNECTION_STRING", "")
        if not connection_string:
            # Try reading from mounted secret
            secret_path = "/mnt/secrets/storage-connection-string"
            if os.path.exists(secret_path):
                connection_string = open(secret_path).read().strip()
        if not connection_string:
            raise ValueError("AZURE_STORAGE_CONNECTION_STRING required for blob backend")
        logger.info("Using Azure Blob Storage backend")
        return BlobDocumentStorage(connection_string)

    logger.info("Using local filesystem storage backend")
    return LocalDocumentStorage()
