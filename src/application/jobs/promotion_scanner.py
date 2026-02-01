"""Background job for scanning and promoting entities between layers.

This job periodically scans entities in PERCEPTION and SEMANTIC layers,
checking if they meet promotion criteria, and automatically promotes them.

Run standalone: uv run python -m application.jobs.promotion_scanner
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class PromotionScannerJob:
    """
    Background job that periodically scans for promotion candidates.

    Features:
    - Configurable scan interval
    - Layer-specific scanning
    - Statistics tracking
    - Graceful shutdown
    """

    def __init__(
        self,
        transition_service,  # AutomaticLayerTransitionService
        scan_interval_seconds: int = 300,  # 5 minutes
        enable_perception_scan: bool = True,
        enable_semantic_scan: bool = True,
    ):
        """
        Initialize promotion scanner job.

        Args:
            transition_service: AutomaticLayerTransitionService instance
            scan_interval_seconds: Interval between scans
            enable_perception_scan: Whether to scan PERCEPTION layer
            enable_semantic_scan: Whether to scan SEMANTIC layer
        """
        self.transition_service = transition_service
        self.scan_interval = scan_interval_seconds
        self.enable_perception_scan = enable_perception_scan
        self.enable_semantic_scan = enable_semantic_scan

        self._running = False
        self._task: Optional[asyncio.Task] = None

        self.stats = {
            "total_scans": 0,
            "total_promotions": 0,
            "last_scan_at": None,
            "last_scan_duration_ms": 0,
            "errors": 0,
        }

    async def start(self) -> None:
        """Start the background scanner."""
        if self._running:
            logger.warning("Promotion scanner is already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._scan_loop())
        logger.info(
            f"Promotion scanner started (interval: {self.scan_interval}s)"
        )

    async def stop(self) -> None:
        """Stop the background scanner gracefully."""
        if not self._running:
            return

        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Promotion scanner stopped")

    async def _scan_loop(self) -> None:
        """Main scan loop."""
        while self._running:
            try:
                await self._run_scan()
                await asyncio.sleep(self.scan_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.stats["errors"] += 1
                logger.error(f"Error in promotion scan: {e}")
                await asyncio.sleep(min(self.scan_interval, 60))

    async def _run_scan(self) -> Dict[str, Any]:
        """Execute a single scan cycle."""
        start_time = datetime.now()
        self.stats["total_scans"] += 1
        self.stats["last_scan_at"] = start_time.isoformat()

        results = {
            "scan_id": f"scan_{self.stats['total_scans']:06d}",
            "started_at": start_time.isoformat(),
            "perception_candidates": 0,
            "semantic_candidates": 0,
            "promotions": 0,
        }

        logger.debug(f"Starting promotion scan {results['scan_id']}")

        try:
            # Scan PERCEPTION layer
            if self.enable_perception_scan:
                perception_results = await self._scan_layer("PERCEPTION")
                results["perception_candidates"] = perception_results.get("candidates", 0)
                results["promotions"] += perception_results.get("promotions", 0)

            # Scan SEMANTIC layer
            if self.enable_semantic_scan:
                semantic_results = await self._scan_layer("SEMANTIC")
                results["semantic_candidates"] = semantic_results.get("candidates", 0)
                results["promotions"] += semantic_results.get("promotions", 0)

            self.stats["total_promotions"] += results["promotions"]

        except Exception as e:
            results["error"] = str(e)
            logger.error(f"Scan error: {e}")

        # Calculate duration
        end_time = datetime.now()
        duration_ms = (end_time - start_time).total_seconds() * 1000
        self.stats["last_scan_duration_ms"] = duration_ms
        results["duration_ms"] = duration_ms
        results["completed_at"] = end_time.isoformat()

        total_candidates = results.get("perception_candidates", 0) + results.get("semantic_candidates", 0)
        if results["promotions"] == 0:
            if total_candidates == 0:
                logger.info(
                    f"Scan {results['scan_id']} completed in {duration_ms:.0f}ms: "
                    f"No promotion candidates found (entities need higher confidence, validation, or ontology match)"
                )
            else:
                logger.info(
                    f"Scan {results['scan_id']} completed in {duration_ms:.0f}ms: "
                    f"Found {total_candidates} candidates but 0 promotions (may already be promoted or failed criteria)"
                )
        else:
            logger.info(
                f"Scan {results['scan_id']} completed: "
                f"{results['promotions']} promotions from {total_candidates} candidates in {duration_ms:.0f}ms"
            )

        return results

    async def _scan_layer(self, layer: str) -> Dict[str, Any]:
        """
        Scan a specific layer for promotion candidates.

        Args:
            layer: Layer to scan

        Returns:
            Scan results
        """
        result = {"layer": layer, "candidates": 0, "promotions": 0}

        try:
            # Use transition service to scan and promote
            candidates = await self.transition_service.scan_for_promotion_candidates(layer)
            result["candidates"] = len(candidates)

            if len(candidates) == 0:
                logger.debug(
                    f"No promotion candidates found in {layer} layer. "
                    f"Entities need confidence >= threshold, validation_count >= 3, or ontology_codes to qualify."
                )
            else:
                logger.info(f"Found {len(candidates)} promotion candidates in {layer} layer")

            for candidate in candidates:
                # Handle both dict candidates (from Neo4j) and string IDs
                if isinstance(candidate, dict):
                    entity_id = candidate.get("id") or candidate.get("name")
                    entity_data = candidate  # Use candidate data directly
                else:
                    entity_id = candidate
                    entity_data = await self.transition_service._get_entity_data(entity_id)

                if entity_id and entity_data:
                    # Get entity's ACTUAL layer from data, not the scan parameter
                    # This prevents trying to "promote" entities that are already at a higher layer
                    entity_props = entity_data.get("properties", entity_data)
                    actual_layer = entity_props.get("layer", layer)

                    # Skip if entity is not at the expected layer (already promoted)
                    if actual_layer != layer:
                        logger.debug(
                            f"Skipping entity {entity_id}: expected layer {layer}, actual {actual_layer}"
                        )
                        continue

                    to_layer = "SEMANTIC" if actual_layer == "PERCEPTION" else "REASONING"

                    # Import Layer enum
                    from application.services.layer_transition import Layer

                    record = await self.transition_service._promote_entity(
                        entity_id=entity_id,
                        entity_data=entity_data,
                        from_layer=Layer(actual_layer),
                        to_layer=Layer(to_layer),
                        reason=f"Background scan promotion"
                    )

                    if record and record.status.value == "completed":
                        result["promotions"] += 1

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"Error scanning {layer}: {e}")

        return result

    async def run_once(self) -> Dict[str, Any]:
        """Run a single scan (for manual triggering)."""
        return await self._run_scan()

    def get_statistics(self) -> Dict[str, Any]:
        """Get scanner statistics."""
        return {
            **self.stats,
            "running": self._running,
            "scan_interval_seconds": self.scan_interval,
            "perception_scan_enabled": self.enable_perception_scan,
            "semantic_scan_enabled": self.enable_semantic_scan,
        }


async def main():
    """Entry point for standalone execution."""
    import os
    from composition_root import bootstrap_knowledge_management
    from application.services.automatic_layer_transition import AutomaticLayerTransitionService

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    logger.info("Starting promotion scanner...")

    # Bootstrap services
    backend, event_bus = await bootstrap_knowledge_management()

    # Create transition service
    transition_service = AutomaticLayerTransitionService(
        backend=backend,
        event_bus=event_bus,
        enable_auto_promotion=True
    )

    # Create and start scanner
    scanner = PromotionScannerJob(
        transition_service=transition_service,
        scan_interval_seconds=int(os.getenv("PROMOTION_SCAN_INTERVAL", "300"))
    )

    try:
        await scanner.start()
        # Keep running until interrupted
        while True:
            await asyncio.sleep(60)
            stats = scanner.get_statistics()
            logger.info(f"Scanner stats: {stats['total_scans']} scans, {stats['total_promotions']} promotions")
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        await scanner.stop()


if __name__ == "__main__":
    asyncio.run(main())
