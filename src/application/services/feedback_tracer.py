"""Feedback Tracer Service.

Collects and processes user feedback for RLHF (Reinforcement Learning from Human Feedback).

Features:
- Feedback collection with layer attribution
- Confidence adjustment based on feedback
- Training data extraction for preference pairs
- Feedback propagation to entity confidence
"""

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import logging
import uuid

from domain.event import KnowledgeEvent
from domain.roles import Role
from application.event_bus import EventBus

logger = logging.getLogger(__name__)


class FeedbackType(str, Enum):
    """Types of user feedback."""
    HELPFUL = "helpful"
    UNHELPFUL = "unhelpful"
    INCORRECT = "incorrect"
    PARTIALLY_CORRECT = "partially_correct"
    MISSING_INFO = "missing_info"


class FeedbackSeverity(str, Enum):
    """Severity of feedback issues."""
    CRITICAL = "critical"    # Safety issue, completely wrong
    HIGH = "high"            # Significant error
    MEDIUM = "medium"        # Minor issue
    LOW = "low"              # Minor improvement suggestion


@dataclass
class UserFeedback:
    """User feedback on a response."""
    feedback_id: str
    response_id: str
    patient_id: str
    session_id: str
    query_text: str
    response_text: str
    rating: int  # 1-5
    feedback_type: FeedbackType
    severity: Optional[FeedbackSeverity] = None
    correction_text: Optional[str] = None
    entities_involved: List[str] = field(default_factory=list)
    layers_traversed: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FeedbackStatistics:
    """Aggregated feedback statistics."""
    total_feedbacks: int
    average_rating: float
    rating_distribution: Dict[int, int]
    feedback_type_distribution: Dict[str, int]
    layer_performance: Dict[str, Dict[str, float]]
    recent_trends: Dict[str, Any]


class FeedbackTracerService:
    """
    Service for collecting and processing user feedback.

    Used to:
    1. Collect explicit feedback (ratings, corrections)
    2. Map feedback to specific entities and layers
    3. Propagate feedback signals to entity confidence
    4. Extract training data for RLHF
    """

    def __init__(
        self,
        backend: Any,  # Neo4jBackend or compatible
        event_bus: Optional[EventBus] = None,
        confidence_decay_on_negative: float = 0.05,
        confidence_boost_on_positive: float = 0.02,
    ):
        """
        Initialize feedback tracer service.

        Args:
            backend: Knowledge graph backend
            event_bus: Optional event bus for publishing feedback events
            confidence_decay_on_negative: How much to reduce confidence on negative feedback
            confidence_boost_on_positive: How much to increase confidence on positive feedback
        """
        self.backend = backend
        self.event_bus = event_bus
        self.confidence_decay = confidence_decay_on_negative
        self.confidence_boost = confidence_boost_on_positive

        # In-memory storage (would be persisted in production)
        self._feedbacks: List[UserFeedback] = []
        self._preference_pairs: List[Dict[str, Any]] = []

        # Statistics
        self.stats = {
            "total_collected": 0,
            "positive_count": 0,
            "negative_count": 0,
            "corrections_count": 0,
            "entities_affected": 0,
        }

    async def submit_feedback(
        self,
        response_id: str,
        patient_id: str,
        session_id: str,
        query_text: str,
        response_text: str,
        rating: int,
        feedback_type: FeedbackType,
        severity: Optional[FeedbackSeverity] = None,
        correction_text: Optional[str] = None,
        entities_involved: Optional[List[str]] = None,
        layers_traversed: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> UserFeedback:
        """
        Submit user feedback for a response.

        Args:
            response_id: ID of the response being rated
            patient_id: Patient identifier
            session_id: Session identifier
            query_text: Original query
            response_text: Response that was given
            rating: 1-5 rating
            feedback_type: Type of feedback
            severity: Optional severity level
            correction_text: Optional user correction
            entities_involved: Optional list of entity IDs involved
            layers_traversed: Optional list of layers traversed
            metadata: Optional additional metadata

        Returns:
            Created feedback record
        """
        # Validate rating
        if not 1 <= rating <= 5:
            raise ValueError("Rating must be between 1 and 5")

        # Create feedback record
        feedback = UserFeedback(
            feedback_id=str(uuid.uuid4()),
            response_id=response_id,
            patient_id=patient_id,
            session_id=session_id,
            query_text=query_text,
            response_text=response_text,
            rating=rating,
            feedback_type=feedback_type,
            severity=severity,
            correction_text=correction_text,
            entities_involved=entities_involved or [],
            layers_traversed=layers_traversed or [],
            metadata=metadata or {},
        )

        # Store feedback
        self._feedbacks.append(feedback)
        self.stats["total_collected"] += 1

        if rating >= 4:
            self.stats["positive_count"] += 1
        elif rating <= 2:
            self.stats["negative_count"] += 1

        if correction_text:
            self.stats["corrections_count"] += 1

        logger.info(
            f"Feedback submitted: {feedback.feedback_id}, rating={rating}, "
            f"type={feedback_type.value}"
        )

        # Store in Neo4j if backend available
        await self._store_feedback_in_graph(feedback)

        # Propagate feedback to entities
        if entities_involved:
            await self._propagate_feedback_to_entities(feedback)

        # Publish event if bus available
        if self.event_bus:
            await self._publish_feedback_event(feedback)

        # Check for preference pair creation
        if correction_text:
            await self._create_preference_pair(feedback)

        return feedback

    async def _store_feedback_in_graph(self, feedback: UserFeedback) -> None:
        """Store feedback in Neo4j."""
        if not hasattr(self.backend, "query_raw"):
            return

        try:
            query = """
            CREATE (f:UserFeedback {
                feedback_id: $feedback_id,
                response_id: $response_id,
                patient_id: $patient_id,
                session_id: $session_id,
                query_text: $query_text,
                response_text: $response_text,
                rating: $rating,
                feedback_type: $feedback_type,
                severity: $severity,
                correction_text: $correction_text,
                entities_involved: $entities_involved,
                layers_traversed: $layers_traversed,
                created_at: datetime()
            })
            SET f.layer = 'APPLICATION'
            RETURN elementId(f) as node_id
            """

            await self.backend.query_raw(query, {
                "feedback_id": feedback.feedback_id,
                "response_id": feedback.response_id,
                "patient_id": feedback.patient_id,
                "session_id": feedback.session_id,
                "query_text": feedback.query_text,
                "response_text": feedback.response_text,
                "rating": feedback.rating,
                "feedback_type": feedback.feedback_type.value,
                "severity": feedback.severity.value if feedback.severity else None,
                "correction_text": feedback.correction_text,
                "entities_involved": feedback.entities_involved,
                "layers_traversed": feedback.layers_traversed,
            })

            # Link feedback to involved entities
            for entity_id in feedback.entities_involved:
                link_query = """
                MATCH (f:UserFeedback {feedback_id: $feedback_id})
                MATCH (e) WHERE elementId(e) = $entity_id OR e.id = $entity_id
                MERGE (f)-[:ABOUT_ENTITY]->(e)
                """
                try:
                    await self.backend.query_raw(link_query, {
                        "feedback_id": feedback.feedback_id,
                        "entity_id": entity_id,
                    })
                except Exception:
                    pass  # Entity might not exist

        except Exception as e:
            logger.warning(f"Failed to store feedback in graph: {e}")

    async def _propagate_feedback_to_entities(self, feedback: UserFeedback) -> None:
        """Propagate feedback signals to entity confidence."""
        if not feedback.entities_involved:
            return

        # Calculate confidence adjustment
        is_negative = feedback.rating <= 2
        if is_negative:  # Negative feedback
            adjustment = -self.confidence_decay
            if feedback.severity == FeedbackSeverity.CRITICAL:
                adjustment *= 2
        elif feedback.rating >= 4:  # Positive feedback
            adjustment = self.confidence_boost
        else:  # Neutral
            adjustment = 0

        if adjustment == 0:
            return

        # Update each entity's confidence
        for entity_id in feedback.entities_involved:
            try:
                # Update confidence and feedback counts
                update_query = """
                MATCH (e) WHERE elementId(e) = $entity_id OR e.id = $entity_id
                SET e.confidence = CASE
                    WHEN e.confidence IS NULL THEN 0.5 + $adjustment
                    ELSE CASE
                        WHEN e.confidence + $adjustment > 1.0 THEN 1.0
                        WHEN e.confidence + $adjustment < 0.1 THEN 0.1
                        ELSE e.confidence + $adjustment
                    END
                END,
                e.feedback_count = COALESCE(e.feedback_count, 0) + 1,
                e.last_feedback_at = datetime(),
                e.negative_feedback_count = CASE
                    WHEN $is_negative THEN COALESCE(e.negative_feedback_count, 0) + 1
                    ELSE COALESCE(e.negative_feedback_count, 0)
                END,
                e.positive_feedback_count = CASE
                    WHEN NOT $is_negative AND $adjustment > 0 THEN COALESCE(e.positive_feedback_count, 0) + 1
                    ELSE COALESCE(e.positive_feedback_count, 0)
                END
                """
                await self.backend.query_raw(update_query, {
                    "entity_id": entity_id,
                    "adjustment": adjustment,
                    "is_negative": is_negative,
                })
                self.stats["entities_affected"] += 1

            except Exception as e:
                logger.warning(f"Failed to propagate feedback to entity {entity_id}: {e}")

    async def _publish_feedback_event(self, feedback: UserFeedback) -> None:
        """Publish feedback event to event bus."""
        event = KnowledgeEvent(
            action="feedback_received",
            data={
                "feedback_id": feedback.feedback_id,
                "response_id": feedback.response_id,
                "rating": feedback.rating,
                "feedback_type": feedback.feedback_type.value,
                "entities_involved": feedback.entities_involved,
                "layers_traversed": feedback.layers_traversed,
                "has_correction": bool(feedback.correction_text),
            },
            role=Role.SYSTEM_ADMIN,
        )
        await self.event_bus.publish(event)

    async def _create_preference_pair(self, feedback: UserFeedback) -> None:
        """Create a preference pair for RLHF training."""
        if not feedback.correction_text:
            return

        # Only create pairs for significant rating differences
        if feedback.rating > 3:
            return  # Original was good enough

        pair = {
            "pair_id": str(uuid.uuid4()),
            "query": feedback.query_text,
            "chosen": feedback.correction_text,  # User correction is preferred
            "rejected": feedback.response_text,   # Original response is rejected
            "rating_gap": 5 - feedback.rating,    # How much worse the rejected was
            "feedback_type": feedback.feedback_type.value,
            "entities_involved": feedback.entities_involved,
            "layers_traversed": feedback.layers_traversed,
            "created_at": datetime.now().isoformat(),
        }

        self._preference_pairs.append(pair)

        logger.info(f"Created preference pair: {pair['pair_id']}")

    async def get_feedback_statistics(self) -> FeedbackStatistics:
        """Get aggregated feedback statistics from memory and Neo4j."""
        # Try to load feedbacks from Neo4j if in-memory is empty
        feedbacks_to_analyze = self._feedbacks
        if not feedbacks_to_analyze and hasattr(self.backend, "query_raw"):
            try:
                feedbacks_to_analyze = await self._load_feedbacks_from_neo4j()
            except Exception as e:
                logger.warning(f"Failed to load feedbacks from Neo4j: {e}")
                feedbacks_to_analyze = []

        if not feedbacks_to_analyze:
            return FeedbackStatistics(
                total_feedbacks=0,
                average_rating=0.0,
                rating_distribution={1: 0, 2: 0, 3: 0, 4: 0, 5: 0},
                feedback_type_distribution={},
                layer_performance={},
                recent_trends={},
            )

        # Calculate distributions
        ratings = [f.rating for f in feedbacks_to_analyze]
        rating_dist = {i: ratings.count(i) for i in range(1, 6)}

        type_dist = {}
        for f in feedbacks_to_analyze:
            fb_type = f.feedback_type.value if hasattr(f.feedback_type, 'value') else f.feedback_type
            type_dist[fb_type] = type_dist.get(fb_type, 0) + 1

        # Calculate layer performance
        layer_perf = {}
        for f in feedbacks_to_analyze:
            layers = f.layers_traversed if f.layers_traversed else []
            for layer in layers:
                if layer not in layer_perf:
                    layer_perf[layer] = {"total": 0, "rating_sum": 0, "negative": 0}
                layer_perf[layer]["total"] += 1
                layer_perf[layer]["rating_sum"] += f.rating
                if f.rating <= 2:
                    layer_perf[layer]["negative"] += 1

        # Calculate averages
        for layer in layer_perf:
            total = layer_perf[layer]["total"]
            layer_perf[layer]["avg_rating"] = layer_perf[layer]["rating_sum"] / total
            layer_perf[layer]["negative_rate"] = layer_perf[layer]["negative"] / total

        return FeedbackStatistics(
            total_feedbacks=len(feedbacks_to_analyze),
            average_rating=sum(ratings) / len(ratings),
            rating_distribution=rating_dist,
            feedback_type_distribution=type_dist,
            layer_performance=layer_perf,
            recent_trends=self._calculate_trends(),
        )

    async def _load_feedbacks_from_neo4j(self) -> List[UserFeedback]:
        """Load feedbacks from Neo4j database."""
        query = """
        MATCH (f:UserFeedback)
        RETURN f.feedback_id as feedback_id,
               f.response_id as response_id,
               f.patient_id as patient_id,
               f.session_id as session_id,
               f.query_text as query_text,
               f.response_text as response_text,
               f.rating as rating,
               f.feedback_type as feedback_type,
               f.severity as severity,
               f.correction_text as correction_text,
               f.entities_involved as entities_involved,
               f.layers_traversed as layers_traversed,
               f.created_at as created_at
        ORDER BY f.created_at DESC
        LIMIT 1000
        """
        results = await self.backend.query_raw(query)

        feedbacks = []
        for record in results:
            try:
                # Parse feedback type
                fb_type_str = record.get("feedback_type", "helpful")
                try:
                    fb_type = FeedbackType(fb_type_str)
                except ValueError:
                    fb_type = FeedbackType.HELPFUL

                # Parse severity
                severity_str = record.get("severity")
                severity = None
                if severity_str:
                    try:
                        severity = FeedbackSeverity(severity_str)
                    except ValueError:
                        pass

                feedback = UserFeedback(
                    feedback_id=record.get("feedback_id", ""),
                    response_id=record.get("response_id", ""),
                    patient_id=record.get("patient_id", ""),
                    session_id=record.get("session_id", ""),
                    query_text=record.get("query_text", ""),
                    response_text=record.get("response_text", ""),
                    rating=record.get("rating", 3),
                    feedback_type=fb_type,
                    severity=severity,
                    correction_text=record.get("correction_text"),
                    entities_involved=record.get("entities_involved", []) or [],
                    layers_traversed=record.get("layers_traversed", []) or [],
                    created_at=record.get("created_at") or datetime.now(),
                )
                feedbacks.append(feedback)
            except Exception as e:
                logger.warning(f"Failed to parse feedback record: {e}")
                continue

        logger.info(f"Loaded {len(feedbacks)} feedbacks from Neo4j")
        return feedbacks

    def _calculate_trends(self) -> Dict[str, Any]:
        """Calculate recent feedback trends."""
        if len(self._feedbacks) < 2:
            return {"trend": "insufficient_data"}

        # Get last 10 vs previous 10
        recent = self._feedbacks[-10:]
        previous = self._feedbacks[-20:-10] if len(self._feedbacks) >= 20 else self._feedbacks[:-10]

        if not previous:
            return {"trend": "insufficient_data"}

        recent_avg = sum(f.rating for f in recent) / len(recent)
        previous_avg = sum(f.rating for f in previous) / len(previous)

        if recent_avg > previous_avg + 0.2:
            trend = "improving"
        elif recent_avg < previous_avg - 0.2:
            trend = "declining"
        else:
            trend = "stable"

        return {
            "trend": trend,
            "recent_avg": recent_avg,
            "previous_avg": previous_avg,
            "change": recent_avg - previous_avg,
        }

    async def get_preference_pairs(
        self,
        min_rating_gap: int = 2,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get preference pairs for RLHF training.

        Args:
            min_rating_gap: Minimum rating gap between chosen and rejected
            limit: Maximum number of pairs to return

        Returns:
            List of preference pairs
        """
        # Filter by rating gap
        pairs = [p for p in self._preference_pairs if p["rating_gap"] >= min_rating_gap]

        # Sort by rating gap (highest first)
        pairs.sort(key=lambda p: p["rating_gap"], reverse=True)

        if limit:
            pairs = pairs[:limit]

        return pairs

    async def get_correction_examples(
        self,
        feedback_type: Optional[FeedbackType] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get user correction examples for supervised learning.

        Args:
            feedback_type: Optional filter by feedback type
            limit: Maximum number of examples

        Returns:
            List of correction examples
        """
        corrections = []

        for f in self._feedbacks:
            if not f.correction_text:
                continue

            if feedback_type and f.feedback_type != feedback_type:
                continue

            corrections.append({
                "query": f.query_text,
                "original_response": f.response_text,
                "corrected_response": f.correction_text,
                "feedback_type": f.feedback_type.value,
                "severity": f.severity.value if f.severity else None,
                "entities": f.entities_involved,
                "layers": f.layers_traversed,
                "timestamp": f.timestamp.isoformat(),
            })

        # Sort by timestamp (newest first)
        corrections.sort(key=lambda x: x["timestamp"], reverse=True)

        if limit:
            corrections = corrections[:limit]

        return corrections

    async def export_training_data(self) -> Dict[str, Any]:
        """
        Export all training data for RLHF.

        Returns:
            Dictionary containing all training data types
        """
        return {
            "preference_pairs": await self.get_preference_pairs(),
            "corrections": await self.get_correction_examples(),
            "statistics": (await self.get_feedback_statistics()).__dict__,
            "total_feedbacks": len(self._feedbacks),
            "exported_at": datetime.now().isoformat(),
        }

    def get_statistics(self) -> Dict[str, Any]:
        """Get service statistics."""
        return {
            **self.stats,
            "preference_pairs_count": len(self._preference_pairs),
            "feedbacks_in_memory": len(self._feedbacks),
        }

    async def check_demotion(
        self,
        entity_ids: List[str],
        demotion_threshold: int = 3,
        min_feedback_count: int = 5,
    ) -> List[str]:
        """
        Check if entities should be demoted based on negative feedback.

        Entities are demoted when:
        - They have >= min_feedback_count feedbacks
        - Their negative feedback count >= demotion_threshold

        Demotion path:
        - APPLICATION → REASONING
        - REASONING → SEMANTIC
        - SEMANTIC → PERCEPTION (no further demotion)

        Args:
            entity_ids: List of entity IDs to check
            demotion_threshold: Number of negative feedbacks to trigger demotion
            min_feedback_count: Minimum feedbacks before considering demotion

        Returns:
            List of entity IDs that were demoted
        """
        if not hasattr(self.backend, "query_raw"):
            return []

        demoted_entities = []

        for entity_id in entity_ids:
            try:
                # Check entity's feedback history
                check_query = """
                MATCH (e) WHERE elementId(e) = $entity_id OR e.id = $entity_id
                RETURN
                    e.layer as current_layer,
                    e.confidence as confidence,
                    COALESCE(e.feedback_count, 0) as feedback_count,
                    COALESCE(e.negative_feedback_count, 0) as negative_count
                """
                result = await self.backend.query_raw(check_query, {"entity_id": entity_id})

                if not result:
                    continue

                record = result[0]
                current_layer = record.get("current_layer")
                feedback_count = record.get("feedback_count", 0)
                negative_count = record.get("negative_count", 0)

                # Check demotion criteria
                if feedback_count < min_feedback_count:
                    continue

                if negative_count < demotion_threshold:
                    continue

                # Determine target layer
                demotion_map = {
                    "APPLICATION": "REASONING",
                    "REASONING": "SEMANTIC",
                    "SEMANTIC": "PERCEPTION",
                }

                target_layer = demotion_map.get(current_layer)
                if not target_layer:
                    continue  # Already at PERCEPTION or unknown layer

                # Perform demotion
                demote_query = """
                MATCH (e) WHERE elementId(e) = $entity_id OR e.id = $entity_id
                SET e.layer = $target_layer,
                    e.demoted_at = datetime(),
                    e.demotion_reason = 'repeated_negative_feedback',
                    e.previous_layer = $current_layer,
                    e.negative_feedback_count = 0,
                    e.confidence = CASE
                        WHEN e.confidence > 0.3 THEN e.confidence - 0.2
                        ELSE 0.1
                    END
                RETURN elementId(e) as demoted_id
                """

                demote_result = await self.backend.query_raw(demote_query, {
                    "entity_id": entity_id,
                    "target_layer": target_layer,
                    "current_layer": current_layer,
                })

                if demote_result:
                    demoted_entities.append(entity_id)
                    self.stats["entities_affected"] += 1

                    logger.info(
                        f"Demoted entity {entity_id}: {current_layer} → {target_layer} "
                        f"(negative feedbacks: {negative_count})"
                    )

                    # Publish demotion event
                    if self.event_bus:
                        demotion_event = KnowledgeEvent(
                            action="entity_demoted",
                            data={
                                "entity_id": entity_id,
                                "from_layer": current_layer,
                                "to_layer": target_layer,
                                "reason": "repeated_negative_feedback",
                                "negative_feedback_count": negative_count,
                            },
                            role=Role.SYSTEM_ADMIN,
                        )
                        await self.event_bus.publish(demotion_event)

            except Exception as e:
                logger.warning(f"Error checking demotion for {entity_id}: {e}")

        return demoted_entities

    async def _update_negative_feedback_count(self, entity_id: str) -> None:
        """Update negative feedback counter for an entity."""
        if not hasattr(self.backend, "query_raw"):
            return

        try:
            update_query = """
            MATCH (e) WHERE elementId(e) = $entity_id OR e.id = $entity_id
            SET e.negative_feedback_count = COALESCE(e.negative_feedback_count, 0) + 1
            """
            await self.backend.query_raw(update_query, {"entity_id": entity_id})
        except Exception as e:
            logger.warning(f"Failed to update negative count for {entity_id}: {e}")
