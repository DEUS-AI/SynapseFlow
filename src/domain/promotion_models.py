"""Promotion Models for DIKW Layer Transitions.

Defines domain models for the entity promotion pipeline, including
promotion decisions, risk levels, and validation criteria.

Used by:
- PromotionGate: Evaluates promotion eligibility
- CrystallizationService: Identifies promotion candidates
- AutomaticLayerTransitionService: Executes promotions
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Any, Optional


class RiskLevel(str, Enum):
    """Risk level for medical entity promotions.

    Risk levels determine the approval workflow:
    - LOW: Auto-promote without review
    - MEDIUM: Auto-promote with logging/monitoring
    - HIGH: Requires human review before promotion
    """
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class PromotionStatus(str, Enum):
    """Status of a promotion decision."""
    APPROVED = "approved"
    PENDING_REVIEW = "pending_review"
    REJECTED = "rejected"
    DEFERRED = "deferred"


class EntityCategory(str, Enum):
    """Medical entity category for risk assessment.

    Categories map to risk levels:
    - LOW: preferences, demographics
    - MEDIUM: symptoms, habits, observations
    - HIGH: diagnoses, medications, allergies, procedures
    """
    DEMOGRAPHICS = "demographics"
    PREFERENCE = "preference"
    LIFESTYLE = "lifestyle"
    SYMPTOM = "symptom"
    OBSERVATION = "observation"
    VITAL_SIGN = "vital_sign"
    LAB_RESULT = "lab_result"
    DIAGNOSIS = "diagnosis"
    MEDICATION = "medication"
    ALLERGY = "allergy"
    PROCEDURE = "procedure"
    TREATMENT = "treatment"


# Risk level mapping by entity category
CATEGORY_RISK_MAPPING: Dict[EntityCategory, RiskLevel] = {
    EntityCategory.DEMOGRAPHICS: RiskLevel.LOW,
    EntityCategory.PREFERENCE: RiskLevel.LOW,
    EntityCategory.LIFESTYLE: RiskLevel.LOW,
    EntityCategory.SYMPTOM: RiskLevel.MEDIUM,
    EntityCategory.OBSERVATION: RiskLevel.MEDIUM,
    EntityCategory.VITAL_SIGN: RiskLevel.MEDIUM,
    EntityCategory.LAB_RESULT: RiskLevel.MEDIUM,
    EntityCategory.DIAGNOSIS: RiskLevel.HIGH,
    EntityCategory.MEDICATION: RiskLevel.HIGH,
    EntityCategory.ALLERGY: RiskLevel.HIGH,
    EntityCategory.PROCEDURE: RiskLevel.HIGH,
    EntityCategory.TREATMENT: RiskLevel.HIGH,
}


@dataclass
class PromotionCriteria:
    """Criteria checked during promotion evaluation."""
    min_confidence: float = 0.85
    min_observations: int = 2
    min_stability_hours: int = 0  # Hours without contradiction
    require_multi_source: bool = False
    require_ontology_match: bool = False
    high_risk_requires_review: bool = True


@dataclass
class CriteriaResult:
    """Result of checking a single criterion."""
    criterion: str
    passed: bool
    actual_value: Any
    required_value: Any
    message: str = ""


@dataclass
class PromotionDecision:
    """Decision result for an entity promotion request.

    Captures the full context of the promotion decision including
    which criteria passed/failed and the risk assessment.
    """
    entity_id: str
    entity_name: str
    entity_type: str
    from_layer: str
    to_layer: str

    # Decision outcome
    status: PromotionStatus
    approved: bool
    reason: str

    # Risk assessment
    risk_level: RiskLevel
    requires_review: bool

    # Criteria evaluation
    criteria_results: List[CriteriaResult] = field(default_factory=list)
    all_criteria_met: bool = False

    # Metadata
    evaluated_at: datetime = field(default_factory=datetime.utcnow)
    evaluated_by: str = "system"
    reviewer: Optional[str] = None
    reviewed_at: Optional[datetime] = None

    # Additional context
    entity_data: Dict[str, Any] = field(default_factory=dict)
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "entity_id": self.entity_id,
            "entity_name": self.entity_name,
            "entity_type": self.entity_type,
            "from_layer": self.from_layer,
            "to_layer": self.to_layer,
            "status": self.status.value,
            "approved": self.approved,
            "reason": self.reason,
            "risk_level": self.risk_level.value,
            "requires_review": self.requires_review,
            "criteria_results": [
                {
                    "criterion": cr.criterion,
                    "passed": cr.passed,
                    "actual_value": cr.actual_value,
                    "required_value": cr.required_value,
                    "message": cr.message,
                }
                for cr in self.criteria_results
            ],
            "all_criteria_met": self.all_criteria_met,
            "evaluated_at": self.evaluated_at.isoformat(),
            "evaluated_by": self.evaluated_by,
            "reviewer": self.reviewer,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "notes": self.notes,
        }


@dataclass
class PendingReview:
    """An entity awaiting human review for promotion."""
    entity_id: str
    entity_name: str
    entity_type: str
    from_layer: str
    to_layer: str
    risk_level: RiskLevel
    decision: PromotionDecision
    submitted_at: datetime = field(default_factory=datetime.utcnow)
    priority: int = 0  # Higher = more urgent
    patient_id: Optional[str] = None
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "entity_id": self.entity_id,
            "entity_name": self.entity_name,
            "entity_type": self.entity_type,
            "from_layer": self.from_layer,
            "to_layer": self.to_layer,
            "risk_level": self.risk_level.value,
            "submitted_at": self.submitted_at.isoformat(),
            "priority": self.priority,
            "patient_id": self.patient_id,
            "notes": self.notes,
            "decision_summary": {
                "reason": self.decision.reason,
                "criteria_met": self.decision.all_criteria_met,
            },
        }


@dataclass
class ReviewAction:
    """Action taken by a reviewer on a pending review."""
    entity_id: str
    reviewer: str
    action: str  # "approve", "reject", "defer"
    reason: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    notes: str = ""


@dataclass
class OntologyMatch:
    """Result of ontology lookup for an entity."""
    matched: bool
    ontology: str = ""  # "SNOMED-CT", "ICD-10", "RxNorm", etc.
    code: str = ""
    display_name: str = ""
    confidence: float = 0.0
    match_type: str = "none"  # "exact", "partial", "semantic"


@dataclass
class PromotionStats:
    """Statistics about promotion processing."""
    total_evaluated: int = 0
    total_approved: int = 0
    total_pending_review: int = 0
    total_rejected: int = 0
    by_risk_level: Dict[str, int] = field(default_factory=dict)
    by_entity_type: Dict[str, int] = field(default_factory=dict)
    average_confidence: float = 0.0
    average_observations: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "total_evaluated": self.total_evaluated,
            "total_approved": self.total_approved,
            "total_pending_review": self.total_pending_review,
            "total_rejected": self.total_rejected,
            "by_risk_level": self.by_risk_level,
            "by_entity_type": self.by_entity_type,
            "average_confidence": self.average_confidence,
            "average_observations": self.average_observations,
        }
