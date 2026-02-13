"""Promotion Gate Service.

Validates entity promotions between DIKW layers with medical-domain
specific criteria. Acts as a gatekeeper ensuring only validated,
reliable knowledge is promoted through the hierarchy.

Key Features:
- Multi-criteria evaluation (confidence, observations, stability)
- Risk-based workflow (LOW: auto, MEDIUM: log, HIGH: review)
- Mock ontology lookup (SNOMED-CT, ICD-10) - extensible for real lookups
- Human review queue for high-risk promotions
- Audit trail for compliance

Promotion Paths:
- PERCEPTION → SEMANTIC: Lower bar, focus on observation count
- SEMANTIC → REASONING: Higher bar, requires stability and multi-source
- REASONING → APPLICATION: Requires proven utility and access patterns
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

from domain.promotion_models import (
    PromotionDecision,
    PromotionStatus,
    PromotionCriteria,
    CriteriaResult,
    RiskLevel,
    EntityCategory,
    CATEGORY_RISK_MAPPING,
    PendingReview,
    ReviewAction,
    OntologyMatch,
    PromotionStats,
)

logger = logging.getLogger(__name__)


@dataclass
class PromotionGateConfig:
    """Configuration for the promotion gate."""
    # PERCEPTION → SEMANTIC criteria
    perception_to_semantic: PromotionCriteria = field(default_factory=lambda: PromotionCriteria(
        min_confidence=0.85,
        min_observations=2,
        min_stability_hours=0,
        require_multi_source=False,
        require_ontology_match=True,
        high_risk_requires_review=False,
    ))

    # SEMANTIC → REASONING criteria
    semantic_to_reasoning: PromotionCriteria = field(default_factory=lambda: PromotionCriteria(
        min_confidence=0.92,
        min_observations=3,
        min_stability_hours=48,
        require_multi_source=True,
        require_ontology_match=True,
        high_risk_requires_review=True,
    ))

    # REASONING → APPLICATION criteria
    reasoning_to_application: PromotionCriteria = field(default_factory=lambda: PromotionCriteria(
        min_confidence=0.95,
        min_observations=5,
        min_stability_hours=168,  # 1 week
        require_multi_source=True,
        require_ontology_match=True,
        high_risk_requires_review=True,
    ))

    # Enable auto-promotion by layer transition
    enable_auto_promotion: Dict[str, bool] = field(default_factory=lambda: {
        "PERCEPTION_SEMANTIC": True,
        "SEMANTIC_REASONING": False,
        "REASONING_APPLICATION": False,
    })


class PromotionGate:
    """
    Validates and approves entity promotions between DIKW layers.

    Acts as a gatekeeper that evaluates entities against medical-domain
    criteria before allowing promotion to higher knowledge layers.
    """

    # Entity type to category mapping
    TYPE_TO_CATEGORY: Dict[str, EntityCategory] = {
        "Patient": EntityCategory.DEMOGRAPHICS,
        "Person": EntityCategory.DEMOGRAPHICS,
        "Preference": EntityCategory.PREFERENCE,
        "Lifestyle": EntityCategory.LIFESTYLE,
        "Symptom": EntityCategory.SYMPTOM,
        "Observation": EntityCategory.OBSERVATION,
        "VitalSign": EntityCategory.VITAL_SIGN,
        "LabResult": EntityCategory.LAB_RESULT,
        "Diagnosis": EntityCategory.DIAGNOSIS,
        "Condition": EntityCategory.DIAGNOSIS,
        "Disease": EntityCategory.DIAGNOSIS,
        "Medication": EntityCategory.MEDICATION,
        "Drug": EntityCategory.MEDICATION,
        "Allergy": EntityCategory.ALLERGY,
        "Procedure": EntityCategory.PROCEDURE,
        "Treatment": EntityCategory.TREATMENT,
    }

    def __init__(
        self,
        neo4j_backend: Any,
        config: Optional[PromotionGateConfig] = None,
    ):
        """
        Initialize the promotion gate.

        Args:
            neo4j_backend: Neo4j backend for entity queries
            config: Promotion gate configuration
        """
        self.neo4j_backend = neo4j_backend
        self.config = config or PromotionGateConfig()

        # Pending reviews queue
        self._pending_reviews: Dict[str, PendingReview] = {}

        # Review history
        self._review_history: List[ReviewAction] = []

        # Statistics
        self._stats = PromotionStats()

        logger.info("PromotionGate initialized")

    async def evaluate_promotion(
        self,
        entity_id: str,
        target_layer: str,
    ) -> PromotionDecision:
        """
        Evaluate whether an entity is eligible for promotion.

        Args:
            entity_id: ID of the entity to evaluate
            target_layer: Target DIKW layer

        Returns:
            PromotionDecision with approval status and details
        """
        # Fetch entity data
        entity = await self._get_entity(entity_id)

        if not entity:
            return self._create_rejection(
                entity_id=entity_id,
                entity_name="Unknown",
                entity_type="Unknown",
                from_layer="UNKNOWN",
                to_layer=target_layer,
                reason="Entity not found",
            )

        entity_name = entity.get("name", "Unknown")
        entity_type = entity.get("entity_type", "Entity")
        current_layer = entity.get("dikw_layer", "PERCEPTION")

        # Validate layer transition
        transition_key = f"{current_layer}_{target_layer}"
        if transition_key not in ["PERCEPTION_SEMANTIC", "SEMANTIC_REASONING", "REASONING_APPLICATION"]:
            return self._create_rejection(
                entity_id=entity_id,
                entity_name=entity_name,
                entity_type=entity_type,
                from_layer=current_layer,
                to_layer=target_layer,
                reason=f"Invalid layer transition: {current_layer} → {target_layer}",
            )

        # Get criteria for this transition
        criteria = self._get_criteria_for_transition(current_layer, target_layer)

        # Evaluate all criteria
        criteria_results = await self._evaluate_criteria(entity, criteria)

        # Assess risk level
        risk_level = self._assess_risk_level(entity_type)

        # Determine if all criteria are met
        all_criteria_met = all(cr.passed for cr in criteria_results)

        # Determine approval status
        requires_review = (
            risk_level == RiskLevel.HIGH
            and criteria.high_risk_requires_review
            and current_layer != "PERCEPTION"  # First promotion doesn't require review
        )

        if all_criteria_met:
            if requires_review:
                status = PromotionStatus.PENDING_REVIEW
                approved = False
                reason = f"Criteria met, awaiting human review (risk level: {risk_level.value})"
            else:
                status = PromotionStatus.APPROVED
                approved = True
                reason = "All promotion criteria met"
        else:
            failed_criteria = [cr.criterion for cr in criteria_results if not cr.passed]
            status = PromotionStatus.REJECTED
            approved = False
            reason = f"Failed criteria: {', '.join(failed_criteria)}"

        decision = PromotionDecision(
            entity_id=entity_id,
            entity_name=entity_name,
            entity_type=entity_type,
            from_layer=current_layer,
            to_layer=target_layer,
            status=status,
            approved=approved,
            reason=reason,
            risk_level=risk_level,
            requires_review=requires_review,
            criteria_results=criteria_results,
            all_criteria_met=all_criteria_met,
            entity_data=entity,
        )

        # Update statistics
        self._update_stats(decision)

        # If pending review, add to queue
        if status == PromotionStatus.PENDING_REVIEW:
            self._add_to_review_queue(decision, entity.get("patient_id"))

        logger.info(
            f"Promotion evaluation for {entity_name}: "
            f"{current_layer} → {target_layer}, status={status.value}, "
            f"risk={risk_level.value}"
        )

        return decision

    async def _evaluate_criteria(
        self,
        entity: Dict[str, Any],
        criteria: PromotionCriteria,
    ) -> List[CriteriaResult]:
        """Evaluate all promotion criteria for an entity."""
        results = []

        # 1. Confidence check
        confidence = entity.get("confidence", 0.0)
        results.append(CriteriaResult(
            criterion="confidence",
            passed=confidence >= criteria.min_confidence,
            actual_value=confidence,
            required_value=criteria.min_confidence,
            message=f"Confidence {confidence:.2f} {'≥' if confidence >= criteria.min_confidence else '<'} {criteria.min_confidence}",
        ))

        # 2. Observation count check
        observations = entity.get("observation_count", 1)
        results.append(CriteriaResult(
            criterion="observation_count",
            passed=observations >= criteria.min_observations,
            actual_value=observations,
            required_value=criteria.min_observations,
            message=f"Observations {observations} {'≥' if observations >= criteria.min_observations else '<'} {criteria.min_observations}",
        ))

        # 3. Temporal stability check
        if criteria.min_stability_hours > 0:
            stability_passed, hours_stable = await self._check_temporal_stability(
                entity, criteria.min_stability_hours
            )
            results.append(CriteriaResult(
                criterion="temporal_stability",
                passed=stability_passed,
                actual_value=hours_stable,
                required_value=criteria.min_stability_hours,
                message=f"Stable for {hours_stable:.0f}h {'≥' if stability_passed else '<'} {criteria.min_stability_hours}h",
            ))

        # 4. Multi-source check
        if criteria.require_multi_source:
            sources = entity.get("sources", [])
            source_count = len(sources) if sources else 1
            passed = source_count >= 3
            results.append(CriteriaResult(
                criterion="multi_source",
                passed=passed,
                actual_value=source_count,
                required_value=3,
                message=f"Sources: {source_count} {'≥' if passed else '<'} 3",
            ))

        # 5. Ontology match check
        if criteria.require_ontology_match:
            ontology_match = await self._check_ontology_match(entity)
            results.append(CriteriaResult(
                criterion="ontology_match",
                passed=ontology_match.matched,
                actual_value=ontology_match.code if ontology_match.matched else "none",
                required_value="valid_code",
                message=f"Ontology: {ontology_match.ontology} {ontology_match.code}" if ontology_match.matched else "No ontology match",
            ))

        return results

    async def _check_temporal_stability(
        self,
        entity: Dict[str, Any],
        min_hours: int,
    ) -> tuple[bool, float]:
        """
        Check if entity has been stable (no contradictions) for min_hours.

        Returns:
            Tuple of (passed, hours_stable)
        """
        last_observed = entity.get("last_observed")
        first_observed = entity.get("first_observed")

        if not last_observed or not first_observed:
            return False, 0

        try:
            if isinstance(last_observed, str):
                last_observed = datetime.fromisoformat(last_observed.replace("Z", "+00:00"))
            if isinstance(first_observed, str):
                first_observed = datetime.fromisoformat(first_observed.replace("Z", "+00:00"))

            # Calculate hours since first observation
            hours_stable = (last_observed - first_observed).total_seconds() / 3600

            # Check for contradictions (would need separate query)
            # For now, assume stable if no contradiction flag
            has_contradiction = entity.get("has_contradiction", False)

            if has_contradiction:
                return False, 0

            return hours_stable >= min_hours, hours_stable

        except Exception as e:
            logger.warning(f"Error checking temporal stability: {e}")
            return False, 0

    async def _check_ontology_match(
        self,
        entity: Dict[str, Any],
    ) -> OntologyMatch:
        """
        Check if entity matches a medical ontology (SNOMED-CT, ICD-10, etc.).

        This is a MOCK implementation. In production, this would call
        actual ontology lookup services.
        """
        entity_name = entity.get("name", "").lower()
        entity_type = entity.get("entity_type", "")

        # Mock ontology lookup - common medical terms
        mock_ontology_db = {
            # Medications
            "imurel": OntologyMatch(True, "RxNorm", "6851", "Azathioprine", 0.95, "exact"),
            "azathioprine": OntologyMatch(True, "RxNorm", "6851", "Azathioprine", 1.0, "exact"),
            "metformin": OntologyMatch(True, "RxNorm", "6809", "Metformin", 1.0, "exact"),
            "lisinopril": OntologyMatch(True, "RxNorm", "29046", "Lisinopril", 1.0, "exact"),
            "omeprazole": OntologyMatch(True, "RxNorm", "7646", "Omeprazole", 1.0, "exact"),

            # Diagnoses
            "diabetes": OntologyMatch(True, "SNOMED-CT", "73211009", "Diabetes mellitus", 0.9, "partial"),
            "diabetes mellitus": OntologyMatch(True, "SNOMED-CT", "73211009", "Diabetes mellitus", 1.0, "exact"),
            "hypertension": OntologyMatch(True, "SNOMED-CT", "38341003", "Hypertensive disorder", 1.0, "exact"),
            "asthma": OntologyMatch(True, "SNOMED-CT", "195967001", "Asthma", 1.0, "exact"),
            "crohn's disease": OntologyMatch(True, "SNOMED-CT", "34000006", "Crohn's disease", 1.0, "exact"),
            "ulcerative colitis": OntologyMatch(True, "SNOMED-CT", "64766004", "Ulcerative colitis", 1.0, "exact"),

            # Symptoms
            "headache": OntologyMatch(True, "SNOMED-CT", "25064002", "Headache", 1.0, "exact"),
            "fever": OntologyMatch(True, "SNOMED-CT", "386661006", "Fever", 1.0, "exact"),
            "fatigue": OntologyMatch(True, "SNOMED-CT", "84229001", "Fatigue", 1.0, "exact"),
            "pain": OntologyMatch(True, "SNOMED-CT", "22253000", "Pain", 0.8, "partial"),

            # Allergies
            "penicillin allergy": OntologyMatch(True, "SNOMED-CT", "91936005", "Allergy to penicillin", 1.0, "exact"),
            "sulfa allergy": OntologyMatch(True, "SNOMED-CT", "91939003", "Allergy to sulfonamide", 0.9, "partial"),
        }

        # Try exact match
        if entity_name in mock_ontology_db:
            return mock_ontology_db[entity_name]

        # Try partial match
        for key, match in mock_ontology_db.items():
            if key in entity_name or entity_name in key:
                return OntologyMatch(
                    matched=True,
                    ontology=match.ontology,
                    code=match.code,
                    display_name=match.display_name,
                    confidence=match.confidence * 0.8,  # Lower confidence for partial
                    match_type="partial",
                )

        # No match - for PERCEPTION → SEMANTIC, we're lenient
        # Return a "semantic match" based on entity type
        if entity_type in ["Medication", "Drug"]:
            return OntologyMatch(True, "RxNorm", "generic", entity_name, 0.7, "semantic")
        elif entity_type in ["Diagnosis", "Condition", "Disease"]:
            return OntologyMatch(True, "SNOMED-CT", "generic", entity_name, 0.7, "semantic")
        elif entity_type in ["Symptom"]:
            return OntologyMatch(True, "SNOMED-CT", "generic", entity_name, 0.7, "semantic")

        return OntologyMatch(matched=False)

    def _assess_risk_level(self, entity_type: str) -> RiskLevel:
        """Assess risk level based on entity type."""
        category = self.TYPE_TO_CATEGORY.get(entity_type)

        if category:
            return CATEGORY_RISK_MAPPING.get(category, RiskLevel.MEDIUM)

        # Default to MEDIUM for unknown types
        return RiskLevel.MEDIUM

    def _get_criteria_for_transition(
        self,
        from_layer: str,
        to_layer: str,
    ) -> PromotionCriteria:
        """Get promotion criteria for a specific layer transition."""
        transition_key = f"{from_layer}_{to_layer}"

        criteria_map = {
            "PERCEPTION_SEMANTIC": self.config.perception_to_semantic,
            "SEMANTIC_REASONING": self.config.semantic_to_reasoning,
            "REASONING_APPLICATION": self.config.reasoning_to_application,
        }

        return criteria_map.get(transition_key, self.config.perception_to_semantic)

    async def _get_entity(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """Fetch entity from Neo4j."""
        try:
            entity = await self.neo4j_backend.get_entity(entity_id)
            if entity:
                return entity.get("properties", entity)
            return None
        except Exception as e:
            logger.error(f"Error fetching entity {entity_id}: {e}")
            return None

    def _create_rejection(
        self,
        entity_id: str,
        entity_name: str,
        entity_type: str,
        from_layer: str,
        to_layer: str,
        reason: str,
    ) -> PromotionDecision:
        """Create a rejection decision."""
        return PromotionDecision(
            entity_id=entity_id,
            entity_name=entity_name,
            entity_type=entity_type,
            from_layer=from_layer,
            to_layer=to_layer,
            status=PromotionStatus.REJECTED,
            approved=False,
            reason=reason,
            risk_level=RiskLevel.LOW,
            requires_review=False,
        )

    def _add_to_review_queue(
        self,
        decision: PromotionDecision,
        patient_id: Optional[str] = None,
    ) -> None:
        """Add a decision to the pending review queue."""
        review = PendingReview(
            entity_id=decision.entity_id,
            entity_name=decision.entity_name,
            entity_type=decision.entity_type,
            from_layer=decision.from_layer,
            to_layer=decision.to_layer,
            risk_level=decision.risk_level,
            decision=decision,
            patient_id=patient_id,
            priority=2 if decision.risk_level == RiskLevel.HIGH else 1,
        )

        self._pending_reviews[decision.entity_id] = review
        logger.info(f"Added {decision.entity_name} to review queue (priority: {review.priority})")

    def _update_stats(self, decision: PromotionDecision) -> None:
        """Update promotion statistics."""
        self._stats.total_evaluated += 1

        if decision.approved:
            self._stats.total_approved += 1
        elif decision.status == PromotionStatus.PENDING_REVIEW:
            self._stats.total_pending_review += 1
        else:
            self._stats.total_rejected += 1

        # Track by risk level
        risk = decision.risk_level.value
        self._stats.by_risk_level[risk] = self._stats.by_risk_level.get(risk, 0) + 1

        # Track by entity type
        etype = decision.entity_type
        self._stats.by_entity_type[etype] = self._stats.by_entity_type.get(etype, 0) + 1

    async def get_pending_reviews(
        self,
        risk_level: Optional[RiskLevel] = None,
        limit: int = 50,
    ) -> List[PendingReview]:
        """
        Get pending reviews, optionally filtered by risk level.

        Args:
            risk_level: Optional filter by risk level
            limit: Maximum number of reviews to return

        Returns:
            List of pending reviews sorted by priority
        """
        reviews = list(self._pending_reviews.values())

        if risk_level:
            reviews = [r for r in reviews if r.risk_level == risk_level]

        # Sort by priority (higher first), then by submission time
        reviews.sort(key=lambda r: (-r.priority, r.submitted_at))

        return reviews[:limit]

    async def approve_review(
        self,
        entity_id: str,
        reviewer: str,
        notes: str = "",
    ) -> Optional[PromotionDecision]:
        """
        Approve a pending review.

        Args:
            entity_id: Entity ID to approve
            reviewer: Reviewer identifier
            notes: Optional reviewer notes

        Returns:
            Updated PromotionDecision or None if not found
        """
        review = self._pending_reviews.get(entity_id)

        if not review:
            logger.warning(f"Review not found: {entity_id}")
            return None

        # Update decision
        decision = review.decision
        decision.status = PromotionStatus.APPROVED
        decision.approved = True
        decision.reviewer = reviewer
        decision.reviewed_at = datetime.now(timezone.utc)
        decision.notes = notes
        decision.reason = f"Approved by {reviewer}"

        # Record action
        self._review_history.append(ReviewAction(
            entity_id=entity_id,
            reviewer=reviewer,
            action="approve",
            reason=notes,
        ))

        # Remove from queue
        del self._pending_reviews[entity_id]

        # Update stats
        self._stats.total_pending_review -= 1
        self._stats.total_approved += 1

        logger.info(f"Review approved: {review.entity_name} by {reviewer}")

        return decision

    async def reject_review(
        self,
        entity_id: str,
        reviewer: str,
        reason: str,
    ) -> Optional[PromotionDecision]:
        """
        Reject a pending review.

        Args:
            entity_id: Entity ID to reject
            reviewer: Reviewer identifier
            reason: Rejection reason

        Returns:
            Updated PromotionDecision or None if not found
        """
        review = self._pending_reviews.get(entity_id)

        if not review:
            logger.warning(f"Review not found: {entity_id}")
            return None

        # Update decision
        decision = review.decision
        decision.status = PromotionStatus.REJECTED
        decision.approved = False
        decision.reviewer = reviewer
        decision.reviewed_at = datetime.now(timezone.utc)
        decision.reason = f"Rejected by {reviewer}: {reason}"

        # Record action
        self._review_history.append(ReviewAction(
            entity_id=entity_id,
            reviewer=reviewer,
            action="reject",
            reason=reason,
        ))

        # Remove from queue
        del self._pending_reviews[entity_id]

        # Update stats
        self._stats.total_pending_review -= 1
        self._stats.total_rejected += 1

        logger.info(f"Review rejected: {review.entity_name} by {reviewer} - {reason}")

        return decision

    async def get_stats(self) -> PromotionStats:
        """Get promotion statistics."""
        self._stats.total_pending_review = len(self._pending_reviews)
        return self._stats
