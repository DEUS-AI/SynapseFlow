"""Tests for QualityScannerJob.

Comprehensive unit tests for the background quality scanner.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass

from application.services.quality_scanner_job import (
    QualityScannerConfig,
    ScanResult,
    QualityScannerJob,
    get_quality_scanner,
    initialize_quality_scanner,
)


class TestQualityScannerConfig:
    """Tests for QualityScannerConfig."""

    def test_config_default_values(self):
        """Test default configuration values."""
        config = QualityScannerConfig()

        assert config.enabled is True
        assert config.document_scan_interval_seconds == 300
        assert config.ontology_scan_interval_seconds == 3600
        assert config.batch_size == 10
        assert config.markdown_directory == Path("markdown_output")

    def test_config_custom_values(self):
        """Test custom configuration values."""
        config = QualityScannerConfig(
            enabled=False,
            document_scan_interval_seconds=60,
            ontology_scan_interval_seconds=1800,
            batch_size=5,
            markdown_directory=Path("/custom/path"),
        )

        assert config.enabled is False
        assert config.document_scan_interval_seconds == 60
        assert config.ontology_scan_interval_seconds == 1800
        assert config.batch_size == 5
        assert config.markdown_directory == Path("/custom/path")

    def test_config_from_environment(self):
        """Test loading configuration from environment variables."""
        with patch.dict(
            "os.environ",
            {
                "ENABLE_QUALITY_SCANNER": "false",
                "QUALITY_SCAN_INTERVAL_SECONDS": "120",
                "ONTOLOGY_SCAN_INTERVAL_SECONDS": "600",
                "QUALITY_SCAN_BATCH_SIZE": "20",
                "MARKDOWN_DIRECTORY": "/test/markdown",
            },
        ):
            config = QualityScannerConfig.from_env()

            assert config.enabled is False
            assert config.document_scan_interval_seconds == 120
            assert config.ontology_scan_interval_seconds == 600
            assert config.batch_size == 20
            assert config.markdown_directory == Path("/test/markdown")

    def test_config_from_env_defaults(self):
        """Test loading configuration with default environment values."""
        with patch.dict("os.environ", {}, clear=True):
            config = QualityScannerConfig.from_env()

            assert config.enabled is True
            assert config.document_scan_interval_seconds == 300
            assert config.batch_size == 10


class TestScanResult:
    """Tests for ScanResult dataclass."""

    def test_scan_result_document_defaults(self):
        """Test ScanResult with document scan defaults."""
        result = ScanResult(
            scan_type="document",
            timestamp=datetime.now(),
        )

        assert result.scan_type == "document"
        assert result.documents_scanned == 0
        assert result.documents_assessed == 0
        assert result.documents_failed == 0
        assert result.ontology_assessed is False
        assert result.ontology_score is None
        assert result.errors == []

    def test_scan_result_ontology(self):
        """Test ScanResult with ontology scan data."""
        result = ScanResult(
            scan_type="ontology",
            timestamp=datetime.now(),
            ontology_assessed=True,
            ontology_score=0.85,
        )

        assert result.scan_type == "ontology"
        assert result.ontology_assessed is True
        assert result.ontology_score == 0.85

    def test_scan_result_with_errors(self):
        """Test ScanResult with errors."""
        result = ScanResult(
            scan_type="document",
            timestamp=datetime.now(),
            errors=["Error 1", "Error 2"],
        )

        assert len(result.errors) == 2
        assert "Error 1" in result.errors


class TestQualityScannerJob:
    """Tests for QualityScannerJob."""

    @pytest.fixture
    def mock_document_tracker(self):
        """Mock document tracker."""
        tracker = MagicMock()
        tracker.list_documents = MagicMock(return_value=[])
        tracker.update_document = MagicMock()
        return tracker

    @pytest.fixture
    def mock_kg_backend(self):
        """Mock knowledge graph backend."""
        backend = AsyncMock()
        backend.query_raw = AsyncMock(return_value=[])
        return backend

    @pytest.fixture
    def scanner_config(self):
        """Test scanner configuration."""
        return QualityScannerConfig(
            enabled=True,
            document_scan_interval_seconds=60,
            ontology_scan_interval_seconds=120,
            batch_size=5,
        )

    @pytest.fixture
    def scanner(self, scanner_config, mock_document_tracker, mock_kg_backend):
        """Create a QualityScannerJob with mocked dependencies."""
        return QualityScannerJob(
            config=scanner_config,
            document_tracker=mock_document_tracker,
            kg_backend=mock_kg_backend,
        )

    # --- Initialization Tests ---

    def test_init_default_config(self):
        """Test initialization with default config."""
        scanner = QualityScannerJob()

        assert scanner.config is not None
        assert scanner.config.enabled is True
        assert scanner.document_tracker is None
        assert scanner.kg_backend is None

    def test_init_with_dependencies(self, scanner_config, mock_document_tracker, mock_kg_backend):
        """Test initialization with all dependencies."""
        scanner = QualityScannerJob(
            config=scanner_config,
            document_tracker=mock_document_tracker,
            kg_backend=mock_kg_backend,
        )

        assert scanner.config == scanner_config
        assert scanner.document_tracker == mock_document_tracker
        assert scanner.kg_backend == mock_kg_backend

    def test_init_internal_state(self, scanner):
        """Test initial internal state."""
        assert scanner._running is False
        assert scanner._last_document_scan is None
        assert scanner._last_ontology_scan is None
        assert scanner._scan_history == []

    # --- Property Tests ---

    def test_is_running_property_initial(self, scanner):
        """Test is_running property initial state."""
        assert scanner.is_running is False

    def test_is_running_property_after_change(self, scanner):
        """Test is_running property after state change."""
        scanner._running = True
        assert scanner.is_running is True

    def test_status_property_initial(self, scanner):
        """Test status property initial state."""
        status = scanner.status

        assert status["enabled"] is True
        assert status["running"] is False
        assert status["last_document_scan"] is None
        assert status["last_ontology_scan"] is None
        assert status["document_scan_interval_seconds"] == 60
        assert status["ontology_scan_interval_seconds"] == 120
        assert status["batch_size"] == 5
        assert status["recent_scans"] == []

    def test_status_property_with_history(self, scanner):
        """Test status property with scan history."""
        scan_result = ScanResult(
            scan_type="document",
            timestamp=datetime.now(),
            documents_assessed=5,
        )
        scanner._scan_history.append(scan_result)
        scanner._last_document_scan = scan_result.timestamp

        status = scanner.status

        assert len(status["recent_scans"]) == 1
        assert status["recent_scans"][0]["type"] == "document"
        assert status["recent_scans"][0]["documents_assessed"] == 5
        assert status["last_document_scan"] is not None

    # --- Start/Stop Tests ---

    @pytest.mark.asyncio
    async def test_start_disabled(self, scanner_config, mock_document_tracker, mock_kg_backend):
        """Test start when scanner is disabled."""
        scanner_config.enabled = False
        scanner = QualityScannerJob(
            config=scanner_config,
            document_tracker=mock_document_tracker,
            kg_backend=mock_kg_backend,
        )

        await scanner.start()

        assert scanner.is_running is False

    @pytest.mark.asyncio
    async def test_start_already_running(self, scanner):
        """Test start when already running."""
        scanner._running = True

        await scanner.start()

        # Should remain running without error
        assert scanner.is_running is True

    @pytest.mark.asyncio
    async def test_stop_scanner(self, scanner):
        """Test stopping the scanner."""
        scanner._running = True

        await scanner.stop()

        assert scanner.is_running is False

    @pytest.mark.asyncio
    async def test_stop_not_running(self, scanner):
        """Test stop when not running."""
        await scanner.stop()

        assert scanner.is_running is False

    # --- Document Scanning Tests ---

    @pytest.mark.asyncio
    async def test_scan_documents_no_tracker(self, scanner_config, mock_kg_backend):
        """Test scan_documents with no tracker configured."""
        scanner = QualityScannerJob(
            config=scanner_config,
            document_tracker=None,
            kg_backend=mock_kg_backend,
        )

        result = await scanner.scan_documents()

        assert result.scan_type == "document"
        assert "Document tracker not available" in result.errors

    @pytest.mark.asyncio
    async def test_scan_documents_empty_list(self, scanner, mock_document_tracker):
        """Test scan_documents with no documents."""
        mock_document_tracker.list_documents.return_value = []

        result = await scanner.scan_documents()

        assert result.documents_scanned == 0
        assert result.documents_assessed == 0

    @pytest.mark.asyncio
    async def test_scan_documents_already_assessed(self, scanner, mock_document_tracker, tmp_path):
        """Test scan_documents skips already assessed documents."""

        @dataclass
        class MockDocument:
            id: str
            filename: str
            quality_score: float
            markdown_path: str

        # Document already has quality_score
        mock_document_tracker.list_documents.return_value = [
            MockDocument(id="doc1", filename="test.pdf", quality_score=0.8, markdown_path=str(tmp_path / "test.md")),
        ]

        result = await scanner.scan_documents()

        # Should not scan already assessed documents
        assert result.documents_scanned == 0

    @pytest.mark.asyncio
    async def test_scan_documents_unassessed(self, scanner, mock_document_tracker, tmp_path):
        """Test scan_documents processes unassessed documents."""

        @dataclass
        class MockDocument:
            id: str
            filename: str
            quality_score: float
            markdown_path: str

        # Create a temp markdown file
        markdown_file = tmp_path / "test.md"
        markdown_file.write_text("# Test Document\n\nThis is test content.")

        mock_document_tracker.list_documents.return_value = [
            MockDocument(id="doc1", filename="test.pdf", quality_score=None, markdown_path=str(markdown_file)),
        ]

        # Mock the quality check function at the source module
        with patch(
            "application.services.document_quality_service.quick_quality_check",
            new_callable=AsyncMock,
        ) as mock_check:
            mock_check.return_value = {
                "overall_score": 0.75,
                "quality_level": "GOOD",
            }

            result = await scanner.scan_documents()

        assert result.documents_scanned == 1
        assert result.documents_assessed == 1
        assert result.documents_failed == 0

    @pytest.mark.asyncio
    async def test_scan_documents_respects_batch_size(self, scanner, mock_document_tracker, tmp_path):
        """Test scan_documents respects batch size limit."""

        @dataclass
        class MockDocument:
            id: str
            filename: str
            quality_score: float
            markdown_path: str

        # Create 10 unassessed documents
        documents = []
        for i in range(10):
            md_file = tmp_path / f"test{i}.md"
            md_file.write_text(f"# Document {i}\n\nContent {i}")
            documents.append(
                MockDocument(id=f"doc{i}", filename=f"test{i}.pdf", quality_score=None, markdown_path=str(md_file))
            )

        mock_document_tracker.list_documents.return_value = documents

        with patch(
            "application.services.document_quality_service.quick_quality_check",
            new_callable=AsyncMock,
        ) as mock_check:
            mock_check.return_value = {
                "overall_score": 0.75,
                "quality_level": "GOOD",
            }

            result = await scanner.scan_documents()

        # Batch size is 5 in fixture
        assert result.documents_scanned == 10
        assert result.documents_assessed == 5  # Batch size limit

    @pytest.mark.asyncio
    async def test_scan_documents_missing_file(self, scanner, mock_document_tracker, tmp_path):
        """Test scan_documents handles missing markdown files."""

        @dataclass
        class MockDocument:
            id: str
            filename: str
            quality_score: float
            markdown_path: str

        # Path to non-existent file
        mock_document_tracker.list_documents.return_value = [
            MockDocument(id="doc1", filename="test.pdf", quality_score=None, markdown_path=str(tmp_path / "nonexistent.md")),
        ]

        result = await scanner.scan_documents()

        # Should not assess non-existent files
        assert result.documents_scanned == 1
        assert result.documents_assessed == 0

    @pytest.mark.asyncio
    async def test_scan_documents_error_handling(self, scanner, mock_document_tracker, tmp_path):
        """Test scan_documents handles per-document errors."""

        @dataclass
        class MockDocument:
            id: str
            filename: str
            quality_score: float
            markdown_path: str

        markdown_file = tmp_path / "test.md"
        markdown_file.write_text("# Test Document\n\nContent")

        mock_document_tracker.list_documents.return_value = [
            MockDocument(id="doc1", filename="test.pdf", quality_score=None, markdown_path=str(markdown_file)),
        ]

        with patch(
            "application.services.document_quality_service.quick_quality_check",
            new_callable=AsyncMock,
        ) as mock_check:
            mock_check.side_effect = Exception("Assessment failed")

            result = await scanner.scan_documents()

        assert result.documents_failed == 1
        assert len(result.errors) == 1

    @pytest.mark.asyncio
    async def test_scan_documents_updates_tracker(self, scanner, mock_document_tracker, tmp_path):
        """Test scan_documents updates document tracker."""

        @dataclass
        class MockDocument:
            id: str
            filename: str
            quality_score: float
            markdown_path: str

        markdown_file = tmp_path / "test.md"
        markdown_file.write_text("# Test\n\nContent")

        mock_document_tracker.list_documents.return_value = [
            MockDocument(id="doc1", filename="test.pdf", quality_score=None, markdown_path=str(markdown_file)),
        ]

        with patch(
            "application.services.document_quality_service.quick_quality_check",
            new_callable=AsyncMock,
        ) as mock_check:
            mock_check.return_value = {
                "overall_score": 0.8,
                "quality_level": "GOOD",
            }

            await scanner.scan_documents()

        mock_document_tracker.update_document.assert_called_once()
        call_args = mock_document_tracker.update_document.call_args
        assert call_args[0][0] == "doc1"
        assert call_args[1]["quality_score"] == 0.8
        assert call_args[1]["quality_level"] == "GOOD"

    # --- Ontology Scanning Tests ---

    @pytest.mark.asyncio
    async def test_scan_ontology_no_backend(self, scanner_config, mock_document_tracker):
        """Test scan_ontology with no KG backend configured."""
        scanner = QualityScannerJob(
            config=scanner_config,
            document_tracker=mock_document_tracker,
            kg_backend=None,
        )

        result = await scanner.scan_ontology()

        assert result.scan_type == "ontology"
        assert "Knowledge graph backend not available" in result.errors
        assert result.ontology_assessed is False

    @pytest.mark.asyncio
    async def test_scan_ontology_success(self, scanner, mock_kg_backend):
        """Test successful ontology scan."""
        mock_report = MagicMock()
        mock_report.overall_score = 0.85

        with patch(
            "application.services.ontology_quality_service.OntologyQualityService"
        ) as mock_service_class:
            mock_service = MagicMock()
            mock_service.assess_ontology = AsyncMock(return_value=mock_report)
            mock_service_class.return_value = mock_service

            # Mock the store function to do nothing
            scanner._store_ontology_assessment = AsyncMock()

            result = await scanner.scan_ontology()

        assert result.scan_type == "ontology"
        assert result.ontology_assessed is True
        assert result.ontology_score == 0.85

    @pytest.mark.asyncio
    async def test_scan_ontology_error_handling(self, scanner, mock_kg_backend):
        """Test ontology scan error handling."""
        with patch(
            "application.services.ontology_quality_service.OntologyQualityService"
        ) as mock_service_class:
            mock_service = MagicMock()
            mock_service.assess_ontology = AsyncMock(side_effect=Exception("KG error"))
            mock_service_class.return_value = mock_service

            result = await scanner.scan_ontology()

        assert result.ontology_assessed is False
        assert len(result.errors) == 1
        assert "KG error" in result.errors[0]

    # --- Manual Scan Tests ---

    @pytest.mark.asyncio
    async def test_manual_scan_documents_only(self, scanner, mock_document_tracker):
        """Test manual scan with documents only."""
        mock_document_tracker.list_documents.return_value = []

        results = await scanner.run_manual_scan(scan_type="document")

        assert "document" in results
        assert "ontology" not in results
        assert len(scanner._scan_history) == 1

    @pytest.mark.asyncio
    async def test_manual_scan_ontology_only(self, scanner, mock_kg_backend):
        """Test manual scan with ontology only."""
        results = await scanner.run_manual_scan(scan_type="ontology")

        assert "ontology" in results
        assert "document" not in results
        assert len(scanner._scan_history) == 1

    @pytest.mark.asyncio
    async def test_manual_scan_both(self, scanner, mock_document_tracker, mock_kg_backend):
        """Test manual scan with both types."""
        mock_document_tracker.list_documents.return_value = []

        results = await scanner.run_manual_scan(scan_type="both")

        assert "document" in results
        assert "ontology" in results
        assert len(scanner._scan_history) == 2

    @pytest.mark.asyncio
    async def test_manual_scan_updates_timestamps(self, scanner, mock_document_tracker):
        """Test manual scan updates last scan timestamps."""
        mock_document_tracker.list_documents.return_value = []

        await scanner.run_manual_scan(scan_type="document")

        assert scanner._last_document_scan is not None


class TestModuleFunctions:
    """Tests for module-level functions."""

    def test_get_quality_scanner_singleton(self):
        """Test get_quality_scanner returns same instance."""
        # Reset global instance
        import application.services.quality_scanner_job as module

        module._scanner_instance = None

        scanner1 = get_quality_scanner()
        scanner2 = get_quality_scanner()

        assert scanner1 is scanner2

    def test_initialize_quality_scanner(self):
        """Test initialize_quality_scanner creates new instance."""
        import application.services.quality_scanner_job as module

        mock_tracker = MagicMock()
        mock_backend = AsyncMock()

        scanner = initialize_quality_scanner(
            document_tracker=mock_tracker,
            kg_backend=mock_backend,
        )

        assert scanner.document_tracker == mock_tracker
        assert scanner.kg_backend == mock_backend
        assert module._scanner_instance is scanner

    def test_initialize_quality_scanner_with_config(self):
        """Test initialize_quality_scanner with custom config."""
        config = QualityScannerConfig(enabled=False, batch_size=20)

        scanner = initialize_quality_scanner(config=config)

        assert scanner.config.enabled is False
        assert scanner.config.batch_size == 20


class TestScanResultAggregation:
    """Tests for scan result aggregation and history."""

    @pytest.fixture
    def scanner(self):
        """Create a basic scanner."""
        return QualityScannerJob()

    def test_scan_history_limit(self, scanner):
        """Test that status only shows last 10 scans."""
        # Add 15 results
        for i in range(15):
            scanner._scan_history.append(
                ScanResult(
                    scan_type="document",
                    timestamp=datetime.now(),
                    documents_assessed=i,
                )
            )

        status = scanner.status

        # Should only show last 10
        assert len(status["recent_scans"]) == 10
        # Last one should have documents_assessed=14
        assert status["recent_scans"][-1]["documents_assessed"] == 14

    def test_scan_history_mixed_types(self, scanner):
        """Test history with mixed scan types."""
        scanner._scan_history.append(
            ScanResult(scan_type="document", timestamp=datetime.now(), documents_assessed=5)
        )
        scanner._scan_history.append(
            ScanResult(scan_type="ontology", timestamp=datetime.now(), ontology_score=0.8)
        )

        status = scanner.status

        assert len(status["recent_scans"]) == 2
        assert status["recent_scans"][0]["type"] == "document"
        assert status["recent_scans"][1]["type"] == "ontology"
