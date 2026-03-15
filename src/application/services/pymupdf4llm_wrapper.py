"""pymupdf4llm PDF→Markdown converter adapter."""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import pymupdf4llm
    PYMUPDF4LLM_AVAILABLE = True
except ImportError:
    PYMUPDF4LLM_AVAILABLE = False


class PyMuPDF4LLMWrapper:
    """Adapter for pymupdf4llm PDF→Markdown conversion.

    Uses PyMuPDF's native PDF parsing for fast conversion with
    good structure preservation (headings, tables, lists).

    Example:
        wrapper = PyMuPDF4LLMWrapper()
        markdown = wrapper.convert_to_markdown("path/to/file.pdf")
    """

    def __init__(self) -> None:
        if not PYMUPDF4LLM_AVAILABLE:
            raise ImportError(
                "pymupdf4llm is not installed. Install with: "
                "uv pip install 'multi_agent_system[pymupdf4llm]'"
            )

    def convert_to_markdown(self, file_path: str) -> Optional[str]:
        """Convert a PDF file to Markdown text using pymupdf4llm.

        Args:
            file_path: Path to the PDF file.

        Returns:
            Markdown string or None if conversion fails.
        """
        try:
            return pymupdf4llm.to_markdown(file_path)
        except Exception as e:
            logger.error(f"pymupdf4llm conversion failed for {file_path}: {e}")
            return None
