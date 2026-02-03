"""Document Tracking Service.

Tracks PDF document status for ingestion management.
Stores tracking data in a JSON file for simplicity.
"""

import json
import hashlib
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class DocumentRecord:
    """Represents a tracked document."""
    id: str
    filename: str
    path: str
    category: str
    size_bytes: int
    status: str = "not_started"  # not_started, processing, completed, failed
    ingested_at: Optional[str] = None
    entity_count: int = 0
    relationship_count: int = 0
    error_message: Optional[str] = None
    markdown_path: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "DocumentRecord":
        """Create from dictionary."""
        return cls(**data)


class DocumentTracker:
    """Tracks document ingestion status using a JSON file."""

    def __init__(
        self,
        tracking_file: Path = Path("data/document_tracking.json"),
        pdf_directory: Path = Path("PDFs"),
        markdown_directory: Path = Path("markdown_output")
    ):
        self.tracking_file = tracking_file
        self.pdf_directory = pdf_directory
        self.markdown_directory = markdown_directory
        self._ensure_tracking_file()

    def _ensure_tracking_file(self):
        """Ensure tracking file exists."""
        if not self.tracking_file.exists():
            self.tracking_file.parent.mkdir(parents=True, exist_ok=True)
            self._save({})
            logger.info(f"Created tracking file: {self.tracking_file}")

    def _load(self) -> Dict[str, dict]:
        """Load tracking data from file."""
        try:
            with open(self.tracking_file, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}

    def _save(self, data: Dict[str, dict]):
        """Save tracking data to file."""
        with open(self.tracking_file, 'w') as f:
            json.dump(data, f, indent=2, default=str)

    def _generate_id(self, path: Path) -> str:
        """Generate a unique ID for a document based on path."""
        hash_input = str(path.absolute()).encode()
        return f"doc:{hashlib.sha256(hash_input).hexdigest()[:12]}"

    def _get_category(self, path: Path) -> str:
        """Get category from path (parent folder name)."""
        relative = path.relative_to(self.pdf_directory)
        if relative.parent != Path("."):
            return str(relative.parent)
        return "general"

    def _get_markdown_path(self, pdf_path: Path) -> Optional[str]:
        """Get the corresponding markdown file path if it exists."""
        md_path = self.markdown_directory / f"{pdf_path.stem}.md"
        if md_path.exists():
            return str(md_path)
        return None

    def scan_pdf_directory(self) -> List[DocumentRecord]:
        """Scan PDF directory and sync with tracking data."""
        if not self.pdf_directory.exists():
            logger.warning(f"PDF directory not found: {self.pdf_directory}")
            return []

        tracking_data = self._load()
        documents = []
        found_ids = set()

        # Find all PDFs
        for pdf_path in self.pdf_directory.rglob("*.pdf"):
            doc_id = self._generate_id(pdf_path)
            found_ids.add(doc_id)

            if doc_id in tracking_data:
                # Update existing record with current file info
                record = DocumentRecord.from_dict(tracking_data[doc_id])
                record.size_bytes = pdf_path.stat().st_size
                record.markdown_path = self._get_markdown_path(pdf_path)
            else:
                # Create new record
                record = DocumentRecord(
                    id=doc_id,
                    filename=pdf_path.name,
                    path=str(pdf_path),
                    category=self._get_category(pdf_path),
                    size_bytes=pdf_path.stat().st_size,
                    markdown_path=self._get_markdown_path(pdf_path),
                    created_at=datetime.now().isoformat()
                )
                tracking_data[doc_id] = record.to_dict()

            documents.append(record)

        # Remove tracking entries for deleted files
        deleted_ids = set(tracking_data.keys()) - found_ids
        for doc_id in deleted_ids:
            del tracking_data[doc_id]
            logger.info(f"Removed tracking for deleted file: {doc_id}")

        # Save updated tracking data
        self._save(tracking_data)

        return sorted(documents, key=lambda d: d.filename)

    def get_document(self, doc_id: str) -> Optional[DocumentRecord]:
        """Get a specific document by ID."""
        tracking_data = self._load()
        if doc_id in tracking_data:
            return DocumentRecord.from_dict(tracking_data[doc_id])
        return None

    def get_document_by_filename(self, filename: str) -> Optional[DocumentRecord]:
        """Get a document by filename."""
        tracking_data = self._load()
        for record_data in tracking_data.values():
            if record_data.get("filename") == filename:
                return DocumentRecord.from_dict(record_data)
        return None

    def update_document(self, doc_id: str, **updates) -> Optional[DocumentRecord]:
        """Update a document record."""
        tracking_data = self._load()
        if doc_id not in tracking_data:
            return None

        record_data = tracking_data[doc_id]
        record_data.update(updates)
        record_data["updated_at"] = datetime.now().isoformat()
        tracking_data[doc_id] = record_data
        self._save(tracking_data)

        return DocumentRecord.from_dict(record_data)

    def register_document(self, pdf_path: Path, category: str = "general") -> DocumentRecord:
        """Register a new document."""
        doc_id = self._generate_id(pdf_path)
        tracking_data = self._load()

        record = DocumentRecord(
            id=doc_id,
            filename=pdf_path.name,
            path=str(pdf_path),
            category=category,
            size_bytes=pdf_path.stat().st_size,
            markdown_path=self._get_markdown_path(pdf_path),
            created_at=datetime.now().isoformat()
        )

        tracking_data[doc_id] = record.to_dict()
        self._save(tracking_data)

        return record

    def remove_document(self, doc_id: str) -> bool:
        """Remove a document from tracking."""
        tracking_data = self._load()
        if doc_id in tracking_data:
            del tracking_data[doc_id]
            self._save(tracking_data)
            return True
        return False

    def list_documents(
        self,
        status: Optional[str] = None,
        category: Optional[str] = None,
        search: Optional[str] = None
    ) -> List[DocumentRecord]:
        """List documents with optional filters."""
        documents = self.scan_pdf_directory()

        if status:
            documents = [d for d in documents if d.status == status]

        if category:
            documents = [d for d in documents if d.category == category]

        if search:
            search_lower = search.lower()
            documents = [d for d in documents if search_lower in d.filename.lower()]

        return documents

    def get_categories(self) -> List[str]:
        """Get all unique categories."""
        documents = self.scan_pdf_directory()
        categories = set(d.category for d in documents)
        return sorted(categories)

    def get_statistics(self) -> dict:
        """Get overall statistics."""
        documents = self.scan_pdf_directory()

        stats = {
            "total": len(documents),
            "not_started": len([d for d in documents if d.status == "not_started"]),
            "processing": len([d for d in documents if d.status == "processing"]),
            "completed": len([d for d in documents if d.status == "completed"]),
            "failed": len([d for d in documents if d.status == "failed"]),
            "total_entities": sum(d.entity_count for d in documents),
            "total_relationships": sum(d.relationship_count for d in documents),
            "with_markdown": len([d for d in documents if d.markdown_path]),
        }

        return stats
