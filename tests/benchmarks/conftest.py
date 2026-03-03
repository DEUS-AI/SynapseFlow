"""Pytest fixtures for extraction benchmark tests."""

import os
import pytest
from pathlib import Path


BENCHMARK_DIR = Path(__file__).parent
RESULTS_DIR = BENCHMARK_DIR / "results"


@pytest.fixture
def results_dir() -> Path:
    """Return the results directory, creating it if needed."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    return RESULTS_DIR


@pytest.fixture
def sample_pdf_path() -> Path:
    """Return path to a sample PDF for benchmarking.

    Looks for PDFs in the project's standard locations.
    Override with BENCHMARK_PDF_PATH env var.
    """
    env_path = os.getenv("BENCHMARK_PDF_PATH")
    if env_path:
        p = Path(env_path)
        if p.exists():
            return p

    project_root = Path(__file__).parent.parent.parent
    candidates = [
        project_root / "examples",
        project_root / "data",
        project_root / "markdown_output",
    ]
    for directory in candidates:
        if directory.exists():
            pdfs = list(directory.glob("*.pdf"))
            if pdfs:
                return pdfs[0]
            mds = list(directory.glob("*.md"))
            if mds:
                return mds[0]

    pytest.skip("No benchmark document found. Set BENCHMARK_PDF_PATH env var.")
