"""Marker PDF→Markdown converter adapter."""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from marker.converters.pdf import PdfConverter
    from marker.models import create_model_dict
    MARKER_AVAILABLE = True
except ImportError:
    MARKER_AVAILABLE = False


class MarkerWrapper:
    """Adapter for Marker ML-based PDF→Markdown conversion.

    Uses Marker's deep-learning models for table detection,
    heading identification, and layout analysis.

    Example:
        wrapper = MarkerWrapper()
        markdown = wrapper.convert_to_markdown("path/to/file.pdf")
    """

    def __init__(self) -> None:
        if not MARKER_AVAILABLE:
            raise ImportError(
                "marker-pdf is not installed. Install with: "
                "uv pip install 'multi_agent_system[marker]'"
            )
        self._model_dict = create_model_dict()
        self._converter = PdfConverter(artifact_dict=self._model_dict)

    def convert_to_markdown(self, file_path: str) -> Optional[str]:
        """Convert a PDF file to Markdown text using Marker.

        Args:
            file_path: Path to the PDF file.

        Returns:
            Markdown string or None if conversion fails.
        """
        try:
            rendered = self._converter(file_path)
            return rendered.markdown
        except Exception as e:
            logger.error(f"Marker conversion failed for {file_path}: {e}")
            return None
