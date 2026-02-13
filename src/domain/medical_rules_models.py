"""Medical Rules Domain Models.

Defines rule types, severity levels, and data structures for
medical knowledge rules including drug interactions, contraindications,
and symptom patterns.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Set, Any


class RuleSeverity(str, Enum):
    """Severity level for medical rules."""

    CRITICAL = "critical"      # Life-threatening, must block
    HIGH = "high"              # Serious risk, strong warning
    MODERATE = "moderate"      # Notable concern, caution advised
    LOW = "low"                # Minor issue, informational
    INFO = "info"              # Educational, no action needed


class RuleCategory(str, Enum):
    """Categories of medical rules."""

    DRUG_INTERACTION = "drug_interaction"
    CONTRAINDICATION = "contraindication"
    ALLERGY_ALERT = "allergy_alert"
    SYMPTOM_PATTERN = "symptom_pattern"
    DOSAGE_WARNING = "dosage_warning"
    LIFESTYLE = "lifestyle"
    MONITORING = "monitoring"


class InteractionType(str, Enum):
    """Types of drug interactions."""

    PHARMACOKINETIC = "pharmacokinetic"  # Affects absorption/metabolism
    PHARMACODYNAMIC = "pharmacodynamic"  # Affects drug action
    ADDITIVE = "additive"                # Combined effect
    SYNERGISTIC = "synergistic"          # Amplified effect
    ANTAGONISTIC = "antagonistic"        # Reduced effect


@dataclass
class MedicalRule:
    """Base class for medical rules.

    Attributes:
        rule_id: Unique identifier
        name: Human-readable rule name
        category: Rule category
        severity: Severity level
        description: Detailed description
        evidence_level: Quality of supporting evidence
        source: Source of the rule (guideline, study, etc.)
        active: Whether the rule is currently active
    """

    rule_id: str
    name: str
    category: RuleCategory
    severity: RuleSeverity
    description: str
    evidence_level: str = "clinical_practice"
    source: str = "medical_guidelines"
    active: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        """Convert rule to dictionary."""
        return {
            "rule_id": self.rule_id,
            "name": self.name,
            "category": self.category.value,
            "severity": self.severity.value,
            "description": self.description,
            "evidence_level": self.evidence_level,
            "source": self.source,
            "active": self.active,
            "metadata": self.metadata,
        }


@dataclass
class DrugInteractionRule(MedicalRule):
    """Rule for drug-drug interactions.

    Attributes:
        drug_a: First drug (name or class)
        drug_b: Second drug (name or class)
        interaction_type: Type of interaction
        effect: Clinical effect of interaction
        mechanism: Mechanism of interaction
        recommendation: Clinical recommendation
    """

    drug_a: str = ""
    drug_b: str = ""
    interaction_type: InteractionType = InteractionType.PHARMACODYNAMIC
    effect: str = ""
    mechanism: str = ""
    recommendation: str = ""

    def matches(self, medications: List[str]) -> bool:
        """Check if this rule matches a list of medications."""
        meds_lower = [m.lower() for m in medications]
        return (
            self.drug_a.lower() in meds_lower and
            self.drug_b.lower() in meds_lower
        )


@dataclass
class ContraindicationRule(MedicalRule):
    """Rule for contraindications.

    Attributes:
        medication: Drug that is contraindicated
        condition: Condition that contraindicates the drug
        absolute: Whether contraindication is absolute or relative
        alternatives: Suggested alternative medications
    """

    medication: str = ""
    condition: str = ""
    absolute: bool = True
    alternatives: List[str] = field(default_factory=list)

    def matches(self, medications: List[str], conditions: List[str]) -> bool:
        """Check if this rule matches medications and conditions."""
        meds_lower = [m.lower() for m in medications]
        conds_lower = [c.lower() for c in conditions]
        return (
            self.medication.lower() in meds_lower and
            self.condition.lower() in conds_lower
        )


@dataclass
class AllergyRule(MedicalRule):
    """Rule for allergy cross-reactivity.

    Attributes:
        allergen: Known allergen
        cross_reactive: Medications that may cross-react
        reaction_type: Type of allergic reaction
    """

    allergen: str = ""
    cross_reactive: List[str] = field(default_factory=list)
    reaction_type: str = "hypersensitivity"

    def matches(self, allergies: List[str], medications: List[str]) -> bool:
        """Check if this rule matches allergies and medications."""
        allergies_lower = [a.lower() for a in allergies]
        meds_lower = [m.lower() for m in medications]

        if self.allergen.lower() not in allergies_lower:
            return False

        return any(
            cross.lower() in meds_lower
            for cross in self.cross_reactive
        )


@dataclass
class SymptomPatternRule(MedicalRule):
    """Rule for symptom pattern recognition.

    Attributes:
        symptoms: List of symptoms that form the pattern
        min_symptoms: Minimum symptoms needed to trigger
        suggested_conditions: Conditions this pattern may indicate
        urgency: How urgently to investigate
        recommended_actions: Actions to recommend
    """

    symptoms: List[str] = field(default_factory=list)
    min_symptoms: int = 2
    suggested_conditions: List[str] = field(default_factory=list)
    urgency: str = "routine"
    recommended_actions: List[str] = field(default_factory=list)

    def matches(self, patient_symptoms: List[str]) -> int:
        """Return number of matching symptoms."""
        symptoms_lower = [s.lower() for s in patient_symptoms]
        rule_symptoms_lower = [s.lower() for s in self.symptoms]

        matches = sum(
            1 for s in rule_symptoms_lower
            if any(s in ps for ps in symptoms_lower)
        )
        return matches


@dataclass
class RuleEvaluationResult:
    """Result of evaluating a medical rule.

    Attributes:
        rule: The evaluated rule
        triggered: Whether the rule was triggered
        severity: Severity of the triggered rule
        message: Human-readable message
        entities_involved: Entities that triggered the rule
        recommendations: Recommended actions
        confidence: Confidence in the evaluation
    """

    rule: MedicalRule
    triggered: bool
    severity: RuleSeverity
    message: str
    entities_involved: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    confidence: float = 1.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_critical(self) -> bool:
        """Check if this is a critical result."""
        return self.triggered and self.severity == RuleSeverity.CRITICAL

    @property
    def requires_attention(self) -> bool:
        """Check if this result requires attention."""
        return self.triggered and self.severity in [
            RuleSeverity.CRITICAL,
            RuleSeverity.HIGH,
        ]

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "rule_id": self.rule.rule_id,
            "rule_name": self.rule.name,
            "category": self.rule.category.value,
            "triggered": self.triggered,
            "severity": self.severity.value,
            "message": self.message,
            "entities_involved": self.entities_involved,
            "recommendations": self.recommendations,
            "confidence": self.confidence,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class RuleEvaluationSummary:
    """Summary of all rule evaluations for a patient context.

    Attributes:
        total_rules_evaluated: Number of rules evaluated
        triggered_rules: Number of rules that triggered
        critical_alerts: Number of critical alerts
        high_alerts: Number of high severity alerts
        results: All evaluation results
    """

    total_rules_evaluated: int = 0
    triggered_rules: int = 0
    critical_alerts: int = 0
    high_alerts: int = 0
    results: List[RuleEvaluationResult] = field(default_factory=list)

    def add_result(self, result: RuleEvaluationResult) -> None:
        """Add an evaluation result to the summary."""
        self.total_rules_evaluated += 1
        self.results.append(result)

        if result.triggered:
            self.triggered_rules += 1
            if result.severity == RuleSeverity.CRITICAL:
                self.critical_alerts += 1
            elif result.severity == RuleSeverity.HIGH:
                self.high_alerts += 1

    @property
    def has_critical_alerts(self) -> bool:
        """Check if there are any critical alerts."""
        return self.critical_alerts > 0

    @property
    def triggered_results(self) -> List[RuleEvaluationResult]:
        """Get only triggered results."""
        return [r for r in self.results if r.triggered]

    def to_dict(self) -> Dict[str, Any]:
        """Convert summary to dictionary."""
        return {
            "total_rules_evaluated": self.total_rules_evaluated,
            "triggered_rules": self.triggered_rules,
            "critical_alerts": self.critical_alerts,
            "high_alerts": self.high_alerts,
            "has_critical_alerts": self.has_critical_alerts,
            "triggered_results": [r.to_dict() for r in self.triggered_results],
        }
