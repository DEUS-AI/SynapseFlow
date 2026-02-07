"""RLHF Data Extractor Service.

Extracts training data for Reinforcement Learning from Human Feedback (RLHF).

Features:
- Preference pair extraction from feedback history
- Layer-specific training data generation
- Quality filtering and deduplication
- Multiple output format support (DPO, SFT, Alpaca)
"""

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import logging
import hashlib
import json

logger = logging.getLogger(__name__)


class TrainingDataFormat(str, Enum):
    """Supported training data formats."""
    DPO = "dpo"              # Direct Preference Optimization
    SFT = "sft"              # Supervised Fine-Tuning
    ALPACA = "alpaca"        # Alpaca instruction format
    SHAREGPT = "sharegpt"    # ShareGPT conversation format
    JSONL = "jsonl"          # Raw JSONL


class KnowledgeLayer(str, Enum):
    """Knowledge graph layers."""
    PERCEPTION = "PERCEPTION"
    SEMANTIC = "SEMANTIC"
    REASONING = "REASONING"
    APPLICATION = "APPLICATION"


@dataclass
class PreferencePair:
    """A preference pair for DPO training."""
    pair_id: str
    prompt: str
    chosen: str
    rejected: str
    chosen_rating: float
    rejected_rating: float
    rating_gap: float
    source: str  # "correction", "rating_comparison", "layer_analysis"
    layers_involved: List[str] = field(default_factory=list)
    entities_involved: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dpo_format(self) -> Dict[str, str]:
        """Convert to DPO training format."""
        return {
            "prompt": self.prompt,
            "chosen": self.chosen,
            "rejected": self.rejected,
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "pair_id": self.pair_id,
            "prompt": self.prompt,
            "chosen": self.chosen,
            "rejected": self.rejected,
            "chosen_rating": self.chosen_rating,
            "rejected_rating": self.rejected_rating,
            "rating_gap": self.rating_gap,
            "source": self.source,
            "layers_involved": self.layers_involved,
            "entities_involved": self.entities_involved,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class SFTExample:
    """A supervised fine-tuning example."""
    example_id: str
    instruction: str
    input: str
    output: str
    source: str  # "correction", "high_rated"
    rating: float
    layers_involved: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_alpaca_format(self) -> Dict[str, str]:
        """Convert to Alpaca format."""
        return {
            "instruction": self.instruction,
            "input": self.input,
            "output": self.output,
        }

    def to_sft_format(self) -> Dict[str, str]:
        """Convert to simple SFT format."""
        return {
            "prompt": f"{self.instruction}\n\n{self.input}" if self.input else self.instruction,
            "completion": self.output,
        }


@dataclass
class LayerAnalysis:
    """Analysis of layer-specific performance."""
    layer: str
    total_queries: int
    average_rating: float
    negative_rate: float
    common_failure_patterns: List[str]
    improvement_suggestions: List[str]


@dataclass
class ExtractionResult:
    """Result of RLHF data extraction."""
    preference_pairs: List[PreferencePair]
    sft_examples: List[SFTExample]
    layer_analysis: Dict[str, LayerAnalysis]
    statistics: Dict[str, Any]
    extracted_at: datetime = field(default_factory=datetime.now)


class RLHFDataExtractor:
    """
    Extracts and processes training data for RLHF.

    Capabilities:
    1. Extract preference pairs from feedback comparisons
    2. Generate SFT examples from corrections
    3. Analyze layer-specific failures
    4. Quality filter and deduplicate
    5. Export in multiple formats
    """

    def __init__(
        self,
        backend: Any,
        min_rating_gap: float = 2.0,
        min_rating_for_sft: float = 4.0,
        dedup_threshold: float = 0.9,
    ):
        """
        Initialize RLHF data extractor.

        Args:
            backend: Knowledge graph backend (Neo4j)
            min_rating_gap: Minimum rating gap for preference pairs
            min_rating_for_sft: Minimum rating for SFT examples
            dedup_threshold: Similarity threshold for deduplication
        """
        self.backend = backend
        self.min_rating_gap = min_rating_gap
        self.min_rating_for_sft = min_rating_for_sft
        self.dedup_threshold = dedup_threshold

        # Cache for extracted data
        self._preference_pairs: List[PreferencePair] = []
        self._sft_examples: List[SFTExample] = []
        self._seen_hashes: set = set()

    async def extract_all(
        self,
        since: Optional[datetime] = None,
        layer_filter: Optional[str] = None,
    ) -> ExtractionResult:
        """
        Extract all training data from feedback history.

        Args:
            since: Only extract feedback since this datetime
            layer_filter: Only extract data involving this layer

        Returns:
            ExtractionResult with all extracted data
        """
        logger.info(f"Starting RLHF data extraction (since={since}, layer={layer_filter})")

        # Extract from different sources
        pairs_from_corrections = await self._extract_from_corrections(since, layer_filter)
        pairs_from_ratings = await self._extract_from_rating_comparisons(since, layer_filter)
        sft_from_corrections = await self._extract_sft_from_corrections(since, layer_filter)
        sft_from_high_rated = await self._extract_sft_from_high_rated(since, layer_filter)

        # Combine and deduplicate
        all_pairs = self._deduplicate_pairs(pairs_from_corrections + pairs_from_ratings)
        all_sft = self._deduplicate_sft(sft_from_corrections + sft_from_high_rated)

        # Analyze layers
        layer_analysis = await self._analyze_layers(since)

        # Calculate statistics
        statistics = self._calculate_statistics(all_pairs, all_sft, layer_analysis)

        logger.info(
            f"Extraction complete: {len(all_pairs)} preference pairs, "
            f"{len(all_sft)} SFT examples"
        )

        return ExtractionResult(
            preference_pairs=all_pairs,
            sft_examples=all_sft,
            layer_analysis=layer_analysis,
            statistics=statistics,
        )

    async def _extract_from_corrections(
        self,
        since: Optional[datetime],
        layer_filter: Optional[str],
    ) -> List[PreferencePair]:
        """Extract preference pairs from user corrections."""
        pairs = []

        query = """
        MATCH (f:UserFeedback)
        WHERE f.correction_text IS NOT NULL
        AND f.correction_text <> ''
        """

        params = {}

        if since:
            query += " AND f.created_at >= $since"
            params["since"] = since.isoformat()

        if layer_filter:
            query += " AND $layer IN f.layers_traversed"
            params["layer"] = layer_filter

        query += """
        RETURN f.feedback_id as id,
               f.query_text as query,
               f.response_text as original,
               f.correction_text as correction,
               f.rating as rating,
               f.layers_traversed as layers,
               f.entities_involved as entities,
               f.feedback_type as feedback_type
        ORDER BY f.created_at DESC
        """

        try:
            results = await self.backend.query_raw(query, params)

            for record in results or []:
                # Correction is preferred over original
                pair = PreferencePair(
                    pair_id=f"corr_{record['id']}",
                    prompt=record["query"],
                    chosen=record["correction"],
                    rejected=record["original"],
                    chosen_rating=5.0,  # Correction assumed to be ideal
                    rejected_rating=float(record["rating"]),
                    rating_gap=5.0 - float(record["rating"]),
                    source="correction",
                    layers_involved=record.get("layers") or [],
                    entities_involved=record.get("entities") or [],
                    metadata={
                        "feedback_type": record.get("feedback_type"),
                        "original_rating": record["rating"],
                    },
                )
                pairs.append(pair)

        except Exception as e:
            logger.warning(f"Error extracting from corrections: {e}")

        return pairs

    async def _extract_from_rating_comparisons(
        self,
        since: Optional[datetime],
        layer_filter: Optional[str],
    ) -> List[PreferencePair]:
        """
        Extract preference pairs by comparing responses to similar queries.

        Finds queries that were asked multiple times with different ratings.
        """
        pairs = []

        # Find queries with multiple feedbacks and rating variance
        query = """
        MATCH (f1:UserFeedback), (f2:UserFeedback)
        WHERE f1.query_text = f2.query_text
        AND f1.feedback_id <> f2.feedback_id
        AND f1.rating > f2.rating
        AND (f1.rating - f2.rating) >= $min_gap
        """

        params = {"min_gap": self.min_rating_gap}

        if since:
            query += " AND f1.created_at >= $since AND f2.created_at >= $since"
            params["since"] = since.isoformat()

        if layer_filter:
            query += " AND ($layer IN f1.layers_traversed OR $layer IN f2.layers_traversed)"
            params["layer"] = layer_filter

        query += """
        RETURN f1.query_text as query,
               f1.response_text as chosen,
               f1.rating as chosen_rating,
               f2.response_text as rejected,
               f2.rating as rejected_rating,
               f1.layers_traversed + f2.layers_traversed as layers,
               f1.entities_involved + f2.entities_involved as entities,
               f1.feedback_id as id1,
               f2.feedback_id as id2
        ORDER BY (f1.rating - f2.rating) DESC
        LIMIT 1000
        """

        try:
            results = await self.backend.query_raw(query, params)

            for record in results or []:
                # Skip if chosen and rejected are identical
                if record["chosen"] == record["rejected"]:
                    continue

                pair = PreferencePair(
                    pair_id=f"cmp_{record['id1']}_{record['id2']}",
                    prompt=record["query"],
                    chosen=record["chosen"],
                    rejected=record["rejected"],
                    chosen_rating=float(record["chosen_rating"]),
                    rejected_rating=float(record["rejected_rating"]),
                    rating_gap=float(record["chosen_rating"]) - float(record["rejected_rating"]),
                    source="rating_comparison",
                    layers_involved=list(set(record.get("layers") or [])),
                    entities_involved=list(set(record.get("entities") or [])),
                )
                pairs.append(pair)

        except Exception as e:
            logger.warning(f"Error extracting from rating comparisons: {e}")

        return pairs

    async def _extract_sft_from_corrections(
        self,
        since: Optional[datetime],
        layer_filter: Optional[str],
    ) -> List[SFTExample]:
        """Extract SFT examples from user corrections."""
        examples = []

        query = """
        MATCH (f:UserFeedback)
        WHERE f.correction_text IS NOT NULL
        AND f.correction_text <> ''
        """

        params = {}

        if since:
            query += " AND f.created_at >= $since"
            params["since"] = since.isoformat()

        if layer_filter:
            query += " AND $layer IN f.layers_traversed"
            params["layer"] = layer_filter

        query += """
        RETURN f.feedback_id as id,
               f.query_text as query,
               f.correction_text as correction,
               f.rating as rating,
               f.layers_traversed as layers
        ORDER BY f.created_at DESC
        """

        try:
            results = await self.backend.query_raw(query, params)

            for record in results or []:
                example = SFTExample(
                    example_id=f"sft_corr_{record['id']}",
                    instruction="Answer the following medical knowledge question accurately and helpfully.",
                    input=record["query"],
                    output=record["correction"],
                    source="correction",
                    rating=5.0,  # Corrections are assumed ideal
                    layers_involved=record.get("layers") or [],
                    metadata={"original_rating": record["rating"]},
                )
                examples.append(example)

        except Exception as e:
            logger.warning(f"Error extracting SFT from corrections: {e}")

        return examples

    async def _extract_sft_from_high_rated(
        self,
        since: Optional[datetime],
        layer_filter: Optional[str],
    ) -> List[SFTExample]:
        """Extract SFT examples from highly-rated responses."""
        examples = []

        query = f"""
        MATCH (f:UserFeedback)
        WHERE f.rating >= {self.min_rating_for_sft}
        AND f.response_text IS NOT NULL
        AND f.response_text <> ''
        """

        params = {}

        if since:
            query += " AND f.created_at >= $since"
            params["since"] = since.isoformat()

        if layer_filter:
            query += " AND $layer IN f.layers_traversed"
            params["layer"] = layer_filter

        query += """
        RETURN f.feedback_id as id,
               f.query_text as query,
               f.response_text as response,
               f.rating as rating,
               f.layers_traversed as layers
        ORDER BY f.rating DESC, f.created_at DESC
        LIMIT 500
        """

        try:
            results = await self.backend.query_raw(query, params)

            for record in results or []:
                example = SFTExample(
                    example_id=f"sft_rated_{record['id']}",
                    instruction="Answer the following medical knowledge question accurately and helpfully.",
                    input=record["query"],
                    output=record["response"],
                    source="high_rated",
                    rating=float(record["rating"]),
                    layers_involved=record.get("layers") or [],
                )
                examples.append(example)

        except Exception as e:
            logger.warning(f"Error extracting SFT from high-rated: {e}")

        return examples

    async def _analyze_layers(
        self,
        since: Optional[datetime],
    ) -> Dict[str, LayerAnalysis]:
        """Analyze performance by layer."""
        analysis = {}

        for layer in KnowledgeLayer:
            query = """
            MATCH (f:UserFeedback)
            WHERE $layer IN f.layers_traversed
            """

            params = {"layer": layer.value}

            if since:
                query += " AND f.created_at >= $since"
                params["since"] = since.isoformat()

            query += """
            RETURN count(f) as total,
                   avg(f.rating) as avg_rating,
                   sum(CASE WHEN f.rating <= 2 THEN 1 ELSE 0 END) as negative_count,
                   collect(CASE WHEN f.rating <= 2 THEN f.feedback_type ELSE null END) as failure_types
            """

            try:
                results = await self.backend.query_raw(query, params)

                if results and results[0]["total"] > 0:
                    record = results[0]
                    total = record["total"]

                    # Count failure patterns
                    failure_types = [t for t in record.get("failure_types", []) if t]
                    failure_counts = {}
                    for ft in failure_types:
                        failure_counts[ft] = failure_counts.get(ft, 0) + 1

                    common_failures = sorted(
                        failure_counts.keys(),
                        key=lambda x: failure_counts[x],
                        reverse=True
                    )[:5]

                    analysis[layer.value] = LayerAnalysis(
                        layer=layer.value,
                        total_queries=total,
                        average_rating=record["avg_rating"] or 0.0,
                        negative_rate=record["negative_count"] / total if total > 0 else 0.0,
                        common_failure_patterns=common_failures,
                        improvement_suggestions=self._generate_suggestions(
                            layer.value,
                            record["avg_rating"] or 0.0,
                            common_failures,
                        ),
                    )

            except Exception as e:
                logger.warning(f"Error analyzing layer {layer.value}: {e}")

        return analysis

    def _generate_suggestions(
        self,
        layer: str,
        avg_rating: float,
        failure_patterns: List[str],
    ) -> List[str]:
        """Generate improvement suggestions based on layer analysis."""
        suggestions = []

        if avg_rating < 3.0:
            suggestions.append(f"Critical: {layer} layer needs significant improvement")

        if layer == "PERCEPTION":
            if "incorrect" in failure_patterns:
                suggestions.append("Improve entity extraction accuracy from source documents")
            if "missing_info" in failure_patterns:
                suggestions.append("Expand document coverage for better information retrieval")

        elif layer == "SEMANTIC":
            if "incorrect" in failure_patterns:
                suggestions.append("Review ontology mappings for accuracy")
            if "partially_correct" in failure_patterns:
                suggestions.append("Improve concept disambiguation")

        elif layer == "REASONING":
            if "incorrect" in failure_patterns:
                suggestions.append("Review inference rules for logical consistency")
            if "unhelpful" in failure_patterns:
                suggestions.append("Improve relevance scoring in reasoning")

        elif layer == "APPLICATION":
            if avg_rating < 4.0:
                suggestions.append("Consider retraining with recent preference data")

        return suggestions

    def _deduplicate_pairs(self, pairs: List[PreferencePair]) -> List[PreferencePair]:
        """Deduplicate preference pairs based on content similarity."""
        unique_pairs = []

        for pair in pairs:
            # Create hash of content
            content_hash = self._hash_content(pair.prompt + pair.chosen + pair.rejected)

            if content_hash not in self._seen_hashes:
                self._seen_hashes.add(content_hash)
                unique_pairs.append(pair)

        return unique_pairs

    def _deduplicate_sft(self, examples: List[SFTExample]) -> List[SFTExample]:
        """Deduplicate SFT examples based on content similarity."""
        unique_examples = []

        for example in examples:
            content_hash = self._hash_content(example.instruction + example.input + example.output)

            if content_hash not in self._seen_hashes:
                self._seen_hashes.add(content_hash)
                unique_examples.append(example)

        return unique_examples

    def _hash_content(self, content: str) -> str:
        """Create a hash of content for deduplication."""
        # Normalize content
        normalized = content.lower().strip()
        return hashlib.md5(normalized.encode()).hexdigest()

    def _calculate_statistics(
        self,
        pairs: List[PreferencePair],
        sft_examples: List[SFTExample],
        layer_analysis: Dict[str, LayerAnalysis],
    ) -> Dict[str, Any]:
        """Calculate extraction statistics."""
        stats = {
            "total_preference_pairs": len(pairs),
            "total_sft_examples": len(sft_examples),
            "pairs_by_source": {},
            "sft_by_source": {},
            "avg_rating_gap": 0.0,
            "layers_analyzed": list(layer_analysis.keys()),
        }

        # Count by source
        for pair in pairs:
            stats["pairs_by_source"][pair.source] = \
                stats["pairs_by_source"].get(pair.source, 0) + 1

        for example in sft_examples:
            stats["sft_by_source"][example.source] = \
                stats["sft_by_source"].get(example.source, 0) + 1

        # Average rating gap
        if pairs:
            stats["avg_rating_gap"] = sum(p.rating_gap for p in pairs) / len(pairs)

        return stats

    def export_dpo_format(self, pairs: List[PreferencePair]) -> List[Dict[str, str]]:
        """Export preference pairs in DPO format."""
        return [pair.to_dpo_format() for pair in pairs]

    def export_sft_format(self, examples: List[SFTExample]) -> List[Dict[str, str]]:
        """Export SFT examples in simple format."""
        return [example.to_sft_format() for example in examples]

    def export_alpaca_format(self, examples: List[SFTExample]) -> List[Dict[str, str]]:
        """Export SFT examples in Alpaca format."""
        return [example.to_alpaca_format() for example in examples]

    def export_sharegpt_format(
        self,
        pairs: List[PreferencePair],
        examples: List[SFTExample],
    ) -> List[Dict[str, Any]]:
        """Export in ShareGPT conversation format."""
        conversations = []

        # Convert SFT examples to conversations
        for example in examples:
            conv = {
                "conversations": [
                    {"from": "human", "value": example.input or example.instruction},
                    {"from": "gpt", "value": example.output},
                ],
                "source": example.source,
                "rating": example.rating,
            }
            conversations.append(conv)

        return conversations

    def export_jsonl(
        self,
        result: ExtractionResult,
        include_metadata: bool = True,
    ) -> List[str]:
        """Export extraction result as JSONL lines."""
        lines = []

        # Export preference pairs
        for pair in result.preference_pairs:
            data = pair.to_dpo_format()
            if include_metadata:
                data["_metadata"] = {
                    "pair_id": pair.pair_id,
                    "source": pair.source,
                    "rating_gap": pair.rating_gap,
                    "layers": pair.layers_involved,
                }
            lines.append(json.dumps(data))

        # Export SFT examples
        for example in result.sft_examples:
            data = example.to_alpaca_format()
            if include_metadata:
                data["_metadata"] = {
                    "example_id": example.example_id,
                    "source": example.source,
                    "rating": example.rating,
                    "layers": example.layers_involved,
                }
            lines.append(json.dumps(data))

        return lines

    async def extract_layer_specific(
        self,
        layer: str,
        min_rating_gap: Optional[float] = None,
    ) -> ExtractionResult:
        """
        Extract training data specific to a layer's failures.

        Use this to generate targeted training data for improving
        a specific layer's performance.
        """
        return await self.extract_all(
            layer_filter=layer,
        )

    def clear_cache(self) -> None:
        """Clear extraction cache."""
        self._preference_pairs.clear()
        self._sft_examples.clear()
        self._seen_hashes.clear()
