"""Background Quality Scanner Job.

Periodically scans and assesses:
1. Documents that haven't been quality-assessed yet
2. Ontology quality for the knowledge graph

Configuration via environment variables:
- ENABLE_QUALITY_SCANNER: Enable/disable the scanner (default: true)
- QUALITY_SCAN_INTERVAL_SECONDS: Interval between scans (default: 300 = 5 minutes)
- QUALITY_SCAN_BATCH_SIZE: Number of documents to assess per scan (default: 10)
- ONTOLOGY_SCAN_INTERVAL_SECONDS: Interval for ontology scans (default: 3600 = 1 hour)
"""

import asyncio
import os
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class QualityScannerConfig:
    """Configuration for the quality scanner."""
    enabled: bool = True
    document_scan_interval_seconds: int = 300  # 5 minutes
    ontology_scan_interval_seconds: int = 3600  # 1 hour
    batch_size: int = 10
    markdown_directory: Path = field(default_factory=lambda: Path("markdown_output"))

    @classmethod
    def from_env(cls) -> "QualityScannerConfig":
        """Load configuration from environment variables."""
        return cls(
            enabled=os.environ.get("ENABLE_QUALITY_SCANNER", "true").lower() == "true",
            document_scan_interval_seconds=int(
                os.environ.get("QUALITY_SCAN_INTERVAL_SECONDS", "300")
            ),
            ontology_scan_interval_seconds=int(
                os.environ.get("ONTOLOGY_SCAN_INTERVAL_SECONDS", "3600")
            ),
            batch_size=int(os.environ.get("QUALITY_SCAN_BATCH_SIZE", "10")),
            markdown_directory=Path(
                os.environ.get("MARKDOWN_DIRECTORY", "markdown_output")
            ),
        )


@dataclass
class ScanResult:
    """Result of a quality scan."""
    scan_type: str  # "document" or "ontology"
    timestamp: datetime
    documents_scanned: int = 0
    documents_assessed: int = 0
    documents_failed: int = 0
    ontology_assessed: bool = False
    ontology_score: Optional[float] = None
    errors: List[str] = field(default_factory=list)


class QualityScannerJob:
    """Background job for periodic quality assessment."""

    def __init__(
        self,
        config: Optional[QualityScannerConfig] = None,
        document_tracker=None,
        kg_backend=None,
    ):
        """Initialize the quality scanner job.

        Args:
            config: Scanner configuration (loaded from env if not provided)
            document_tracker: Document tracker instance
            kg_backend: Knowledge graph backend for ontology assessment
        """
        self.config = config or QualityScannerConfig.from_env()
        self.document_tracker = document_tracker
        self.kg_backend = kg_backend

        self._running = False
        self._last_document_scan: Optional[datetime] = None
        self._last_ontology_scan: Optional[datetime] = None
        self._scan_history: List[ScanResult] = []

    @property
    def is_running(self) -> bool:
        """Check if the scanner is currently running."""
        return self._running

    @property
    def status(self) -> Dict[str, Any]:
        """Get the current scanner status."""
        return {
            "enabled": self.config.enabled,
            "running": self._running,
            "last_document_scan": (
                self._last_document_scan.isoformat() if self._last_document_scan else None
            ),
            "last_ontology_scan": (
                self._last_ontology_scan.isoformat() if self._last_ontology_scan else None
            ),
            "document_scan_interval_seconds": self.config.document_scan_interval_seconds,
            "ontology_scan_interval_seconds": self.config.ontology_scan_interval_seconds,
            "batch_size": self.config.batch_size,
            "recent_scans": [
                {
                    "type": r.scan_type,
                    "timestamp": r.timestamp.isoformat(),
                    "documents_assessed": r.documents_assessed,
                    "ontology_score": r.ontology_score,
                }
                for r in self._scan_history[-10:]
            ],
        }

    async def start(self) -> None:
        """Start the background scanner."""
        if not self.config.enabled:
            logger.info("Quality scanner is disabled")
            return

        if self._running:
            logger.warning("Quality scanner is already running")
            return

        self._running = True
        logger.info(
            f"Starting quality scanner (document interval: {self.config.document_scan_interval_seconds}s, "
            f"ontology interval: {self.config.ontology_scan_interval_seconds}s)"
        )

        # Start both scan loops concurrently
        await asyncio.gather(
            self._document_scan_loop(),
            self._ontology_scan_loop(),
            return_exceptions=True,
        )

    async def stop(self) -> None:
        """Stop the background scanner."""
        self._running = False
        logger.info("Stopping quality scanner")

    async def _document_scan_loop(self) -> None:
        """Main loop for document quality scanning."""
        while self._running:
            try:
                result = await self.scan_documents()
                self._scan_history.append(result)
                self._last_document_scan = result.timestamp

                if result.documents_assessed > 0:
                    logger.info(
                        f"Document scan complete: {result.documents_assessed}/{result.documents_scanned} assessed"
                    )

            except Exception as e:
                logger.error(f"Document scan failed: {e}", exc_info=True)

            # Wait for next scan
            await asyncio.sleep(self.config.document_scan_interval_seconds)

    async def _ontology_scan_loop(self) -> None:
        """Main loop for ontology quality scanning."""
        while self._running:
            try:
                result = await self.scan_ontology()
                self._scan_history.append(result)
                self._last_ontology_scan = result.timestamp

                if result.ontology_assessed:
                    logger.info(f"Ontology scan complete: score={result.ontology_score:.2f}")

            except Exception as e:
                logger.error(f"Ontology scan failed: {e}", exc_info=True)

            # Wait for next scan
            await asyncio.sleep(self.config.ontology_scan_interval_seconds)

    async def scan_documents(self) -> ScanResult:
        """Scan and assess documents that haven't been quality-assessed.

        Returns:
            ScanResult with assessment details
        """
        from application.services.document_quality_service import quick_quality_check

        result = ScanResult(
            scan_type="document",
            timestamp=datetime.now(),
        )

        if not self.document_tracker:
            result.errors.append("Document tracker not available")
            return result

        # Get completed documents without quality assessment
        documents = self.document_tracker.list_documents(status="completed")
        unassessed = [
            d for d in documents
            if d.quality_score is None and d.markdown_path
        ]

        result.documents_scanned = len(unassessed)

        # Assess batch
        for doc in unassessed[: self.config.batch_size]:
            try:
                markdown_path = Path(doc.markdown_path)
                if not markdown_path.exists():
                    continue

                markdown_content = markdown_path.read_text(encoding='utf-8')
                quality_result = await quick_quality_check(markdown_content, doc.filename)

                # Update document tracker
                self.document_tracker.update_document(
                    doc.id,
                    quality_score=quality_result.get("overall_score"),
                    quality_level=quality_result.get("quality_level"),
                    quality_assessed_at=datetime.now().isoformat()
                )

                result.documents_assessed += 1
                logger.debug(f"Assessed {doc.filename}: {quality_result.get('quality_level')}")

            except Exception as e:
                result.documents_failed += 1
                result.errors.append(f"{doc.filename}: {str(e)}")
                logger.warning(f"Failed to assess {doc.filename}: {e}")

        return result

    async def scan_ontology(self) -> ScanResult:
        """Run ontology quality assessment.

        Returns:
            ScanResult with assessment details
        """
        result = ScanResult(
            scan_type="ontology",
            timestamp=datetime.now(),
        )

        if not self.kg_backend:
            result.errors.append("Knowledge graph backend not available")
            return result

        try:
            from application.services.ontology_quality_service import OntologyQualityService

            service = OntologyQualityService(kg_backend=self.kg_backend)
            report = await service.assess_ontology()

            result.ontology_assessed = True
            result.ontology_score = report.overall_score

            # Store in PostgreSQL if available
            await self._store_ontology_assessment(report)

        except Exception as e:
            result.errors.append(str(e))
            logger.error(f"Ontology assessment failed: {e}", exc_info=True)

        return result

    async def _store_ontology_assessment(self, report) -> None:
        """Store ontology assessment in PostgreSQL."""
        try:
            from infrastructure.database.session import db_session
            from infrastructure.database.repositories import OntologyQualityRepository

            async with db_session() as session:
                repo = OntologyQualityRepository(session)
                await repo.save_assessment(
                    assessment_id=f"scan-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                    ontology_name="default",
                    overall_score=report.overall_score,
                    quality_level=report.quality_level.value,
                    coverage_ratio=report.coverage.coverage_ratio,
                    odin_coverage=report.coverage.odin_coverage,
                    schema_org_coverage=report.coverage.schema_org_coverage,
                    compliance_ratio=report.compliance.compliance_ratio,
                    fully_compliant=report.compliance.fully_compliant,
                    non_compliant=report.compliance.non_compliant,
                    coherence_ratio=report.taxonomy.coherence_ratio,
                    orphan_nodes=report.taxonomy.orphan_nodes,
                    consistency_ratio=report.consistency.consistency_ratio,
                    entity_count=report.entity_count,
                    relationship_count=report.relationship_count,
                    critical_issues=report.critical_issues[:10],
                    recommendations=report.recommendations[:10],
                )
                await session.commit()
                logger.debug("Stored ontology assessment in PostgreSQL")

        except Exception as e:
            logger.warning(f"Failed to store ontology assessment: {e}")

    async def run_manual_scan(self, scan_type: str = "both") -> Dict[str, ScanResult]:
        """Run a manual quality scan.

        Args:
            scan_type: "document", "ontology", or "both"

        Returns:
            Dictionary with scan results
        """
        results = {}

        if scan_type in ("document", "both"):
            results["document"] = await self.scan_documents()
            self._scan_history.append(results["document"])
            self._last_document_scan = results["document"].timestamp

        if scan_type in ("ontology", "both"):
            results["ontology"] = await self.scan_ontology()
            self._scan_history.append(results["ontology"])
            self._last_ontology_scan = results["ontology"].timestamp

        return results


# Global scanner instance
_scanner_instance: Optional[QualityScannerJob] = None


def get_quality_scanner() -> QualityScannerJob:
    """Get the global quality scanner instance."""
    global _scanner_instance
    if _scanner_instance is None:
        _scanner_instance = QualityScannerJob()
    return _scanner_instance


def initialize_quality_scanner(
    document_tracker=None,
    kg_backend=None,
    config: Optional[QualityScannerConfig] = None,
) -> QualityScannerJob:
    """Initialize the global quality scanner with dependencies.

    Args:
        document_tracker: Document tracker instance
        kg_backend: Knowledge graph backend
        config: Optional configuration

    Returns:
        Initialized QualityScannerJob instance
    """
    global _scanner_instance
    _scanner_instance = QualityScannerJob(
        config=config,
        document_tracker=document_tracker,
        kg_backend=kg_backend,
    )
    return _scanner_instance


async def start_background_scanner() -> None:
    """Start the background quality scanner."""
    scanner = get_quality_scanner()
    await scanner.start()
