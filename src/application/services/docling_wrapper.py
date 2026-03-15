"""Docling PDF→Markdown converter adapter."""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from docling.document_converter import DocumentConverter
    DOCLING_AVAILABLE = True
except ImportError:
    DOCLING_AVAILABLE = False


class DoclingWrapper:
    """Adapter for IBM Docling PDF→Markdown conversion.

    Uses Docling's ML-based document understanding for high-quality
    table detection, OCR, and structured output.

    Example:
        wrapper = DoclingWrapper()
        markdown = wrapper.convert_to_markdown("path/to/file.pdf")
    """

    def __init__(self) -> None:
        if not DOCLING_AVAILABLE:
            raise ImportError(
                "docling is not installed. Install with: "
                "uv pip install 'multi_agent_system[docling]'"
            )
        self._converter = DocumentConverter()

    def convert_to_markdown(self, file_path: str) -> Optional[str]:
        """Convert a PDF file to Markdown text using Docling.

        Args:
            file_path: Path to the PDF file.

        Returns:
            Markdown string or None if conversion fails.
        """
        try:
            result = self._converter.convert(file_path)
            return result.document.export_to_markdown()
        except Exception as e:
            logger.error(f"Docling conversion failed for {file_path}: {e}")
            return None
