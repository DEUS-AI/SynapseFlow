"""Medical Rules Engine.

Provides rule-based reasoning for medical knowledge:
- Drug interactions (medication + medication → warning)
- Contraindications (condition + medication → alert)
- Allergy cross-reactivity (allergy + medication → alert)
- Symptom patterns (symptom X + Y + Z → suggests condition W)

The engine evaluates rules against patient context and returns
alerts, warnings, and recommendations.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Any, Set

from domain.medical_rules_models import (
    MedicalRule,
    DrugInteractionRule,
    ContraindicationRule,
    AllergyRule,
    SymptomPatternRule,
    RuleEvaluationResult,
    RuleEvaluationSummary,
    RuleSeverity,
    RuleCategory,
    InteractionType,
)

logger = logging.getLogger(__name__)


@dataclass
class PatientContext:
    """Patient context for rule evaluation.

    Attributes:
        patient_id: Patient identifier
        medications: Current medications
        conditions: Known conditions/diagnoses
        allergies: Known allergies
        symptoms: Current symptoms
        vital_signs: Current vital signs
        lab_results: Recent lab results
    """

    patient_id: str
    medications: List[str] = None
    conditions: List[str] = None
    allergies: List[str] = None
    symptoms: List[str] = None
    vital_signs: Dict[str, Any] = None
    lab_results: Dict[str, Any] = None

    def __post_init__(self):
        self.medications = self.medications or []
        self.conditions = self.conditions or []
        self.allergies = self.allergies or []
        self.symptoms = self.symptoms or []
        self.vital_signs = self.vital_signs or {}
        self.lab_results = self.lab_results or {}


@dataclass
class MedicalRulesConfig:
    """Configuration for the Medical Rules Engine."""

    # Enable different rule categories
    enable_drug_interactions: bool = True
    enable_contraindications: bool = True
    enable_allergy_alerts: bool = True
    enable_symptom_patterns: bool = True

    # Minimum severity to report
    min_severity: RuleSeverity = RuleSeverity.LOW

    # Maximum rules to evaluate (0 = unlimited)
    max_rules_per_category: int = 0

    # Include informational rules
    include_info_rules: bool = False


class MedicalRulesEngine:
    """Engine for evaluating medical rules.

    Applies rule-based reasoning to patient context to identify
    potential drug interactions, contraindications, and concerning
    symptom patterns.

    Example:
        >>> engine = MedicalRulesEngine()
        >>> context = PatientContext(
        ...     patient_id="patient:123",
        ...     medications=["Warfarin", "Aspirin"],
        ...     allergies=["Penicillin"],
        ... )
        >>> summary = engine.evaluate(context)
        >>> if summary.has_critical_alerts:
        ...     print("Critical alerts found!")
    """

    def __init__(self, config: Optional[MedicalRulesConfig] = None):
        """Initialize the Medical Rules Engine.

        Args:
            config: Optional configuration
        """
        self.config = config or MedicalRulesConfig()

        # Rule storage by category
        self._drug_interactions: List[DrugInteractionRule] = []
        self._contraindications: List[ContraindicationRule] = []
        self._allergy_rules: List[AllergyRule] = []
        self._symptom_patterns: List[SymptomPatternRule] = []

        # Initialize with built-in rules
        self._load_builtin_rules()

        # Statistics
        self.stats = {
            "total_evaluations": 0,
            "total_alerts": 0,
            "critical_alerts": 0,
            "by_category": {cat.value: 0 for cat in RuleCategory},
        }

    def _load_builtin_rules(self) -> None:
        """Load built-in medical rules."""
        self._load_drug_interaction_rules()
        self._load_contraindication_rules()
        self._load_allergy_rules()
        self._load_symptom_pattern_rules()

        logger.info(
            f"Loaded {len(self._drug_interactions)} drug interactions, "
            f"{len(self._contraindications)} contraindications, "
            f"{len(self._allergy_rules)} allergy rules, "
            f"{len(self._symptom_patterns)} symptom patterns"
        )

    def _load_drug_interaction_rules(self) -> None:
        """Load drug interaction rules."""
        interactions = [
            # Anticoagulant interactions
            DrugInteractionRule(
                rule_id="DI001",
                name="Warfarin + Aspirin Interaction",
                category=RuleCategory.DRUG_INTERACTION,
                severity=RuleSeverity.HIGH,
                description="Concurrent use increases bleeding risk",
                drug_a="warfarin",
                drug_b="aspirin",
                interaction_type=InteractionType.ADDITIVE,
                effect="Increased risk of bleeding",
                mechanism="Both drugs affect hemostasis via different mechanisms",
                recommendation="Monitor for signs of bleeding. Consider gastroprotection.",
            ),
            DrugInteractionRule(
                rule_id="DI002",
                name="Warfarin + NSAIDs Interaction",
                category=RuleCategory.DRUG_INTERACTION,
                severity=RuleSeverity.HIGH,
                description="NSAIDs increase warfarin bleeding risk",
                drug_a="warfarin",
                drug_b="ibuprofen",
                interaction_type=InteractionType.PHARMACODYNAMIC,
                effect="Significantly increased bleeding risk",
                mechanism="NSAIDs inhibit platelet function and may cause GI ulceration",
                recommendation="Avoid combination. Use acetaminophen for pain if needed.",
            ),
            DrugInteractionRule(
                rule_id="DI003",
                name="Warfarin + Naproxen Interaction",
                category=RuleCategory.DRUG_INTERACTION,
                severity=RuleSeverity.HIGH,
                description="Naproxen increases warfarin bleeding risk",
                drug_a="warfarin",
                drug_b="naproxen",
                interaction_type=InteractionType.PHARMACODYNAMIC,
                effect="Significantly increased bleeding risk",
                mechanism="NSAIDs inhibit platelet function",
                recommendation="Avoid combination if possible.",
            ),

            # Immunosuppressant interactions
            DrugInteractionRule(
                rule_id="DI004",
                name="Azathioprine + Allopurinol Interaction",
                category=RuleCategory.DRUG_INTERACTION,
                severity=RuleSeverity.CRITICAL,
                description="Allopurinol inhibits azathioprine metabolism",
                drug_a="azathioprine",
                drug_b="allopurinol",
                interaction_type=InteractionType.PHARMACOKINETIC,
                effect="Severe myelosuppression risk",
                mechanism="Allopurinol inhibits xanthine oxidase, preventing azathioprine breakdown",
                recommendation="Reduce azathioprine dose by 50-75% or avoid combination.",
            ),
            DrugInteractionRule(
                rule_id="DI005",
                name="Imurel + Allopurinol Interaction",
                category=RuleCategory.DRUG_INTERACTION,
                severity=RuleSeverity.CRITICAL,
                description="Allopurinol inhibits Imurel (azathioprine) metabolism",
                drug_a="imurel",
                drug_b="allopurinol",
                interaction_type=InteractionType.PHARMACOKINETIC,
                effect="Severe myelosuppression risk",
                mechanism="Allopurinol inhibits xanthine oxidase",
                recommendation="Reduce Imurel dose significantly or avoid combination.",
            ),

            # Metformin interactions
            DrugInteractionRule(
                rule_id="DI006",
                name="Metformin + Contrast Media",
                category=RuleCategory.DRUG_INTERACTION,
                severity=RuleSeverity.HIGH,
                description="Risk of lactic acidosis with iodinated contrast",
                drug_a="metformin",
                drug_b="contrast",
                interaction_type=InteractionType.PHARMACODYNAMIC,
                effect="Risk of lactic acidosis",
                mechanism="Contrast can impair renal function, reducing metformin clearance",
                recommendation="Withhold metformin 48h before and after contrast administration.",
            ),

            # ACE inhibitors + Potassium
            DrugInteractionRule(
                rule_id="DI007",
                name="ACE Inhibitor + Potassium Supplements",
                category=RuleCategory.DRUG_INTERACTION,
                severity=RuleSeverity.MODERATE,
                description="Risk of hyperkalemia",
                drug_a="enalapril",
                drug_b="potassium",
                interaction_type=InteractionType.ADDITIVE,
                effect="Hyperkalemia risk",
                mechanism="ACE inhibitors reduce aldosterone, retaining potassium",
                recommendation="Monitor potassium levels regularly.",
            ),
            DrugInteractionRule(
                rule_id="DI008",
                name="Lisinopril + Potassium Interaction",
                category=RuleCategory.DRUG_INTERACTION,
                severity=RuleSeverity.MODERATE,
                description="Risk of hyperkalemia",
                drug_a="lisinopril",
                drug_b="potassium",
                interaction_type=InteractionType.ADDITIVE,
                effect="Hyperkalemia risk",
                mechanism="ACE inhibitors reduce aldosterone",
                recommendation="Monitor potassium levels.",
            ),

            # Statins + Macrolides
            DrugInteractionRule(
                rule_id="DI009",
                name="Simvastatin + Clarithromycin",
                category=RuleCategory.DRUG_INTERACTION,
                severity=RuleSeverity.HIGH,
                description="Increased risk of myopathy/rhabdomyolysis",
                drug_a="simvastatin",
                drug_b="clarithromycin",
                interaction_type=InteractionType.PHARMACOKINETIC,
                effect="Significantly increased statin levels",
                mechanism="CYP3A4 inhibition by clarithromycin",
                recommendation="Suspend simvastatin during clarithromycin course.",
            ),

            # Opioids + Benzodiazepines
            DrugInteractionRule(
                rule_id="DI010",
                name="Opioid + Benzodiazepine Interaction",
                category=RuleCategory.DRUG_INTERACTION,
                severity=RuleSeverity.CRITICAL,
                description="Risk of respiratory depression",
                drug_a="tramadol",
                drug_b="diazepam",
                interaction_type=InteractionType.SYNERGISTIC,
                effect="Life-threatening respiratory depression",
                mechanism="Additive CNS depression",
                recommendation="Avoid combination. If necessary, use lowest doses and monitor closely.",
            ),
        ]

        self._drug_interactions.extend(interactions)

    def _load_contraindication_rules(self) -> None:
        """Load contraindication rules."""
        contraindications = [
            # Renal impairment
            ContraindicationRule(
                rule_id="CI001",
                name="Metformin in Renal Impairment",
                category=RuleCategory.CONTRAINDICATION,
                severity=RuleSeverity.HIGH,
                description="Metformin contraindicated in severe renal impairment",
                medication="metformin",
                condition="renal impairment",
                absolute=False,
                alternatives=["insulin", "sulfonylurea"],
            ),
            ContraindicationRule(
                rule_id="CI002",
                name="Metformin in Kidney Disease",
                category=RuleCategory.CONTRAINDICATION,
                severity=RuleSeverity.HIGH,
                description="Metformin requires dose adjustment or avoidance in CKD",
                medication="metformin",
                condition="chronic kidney disease",
                absolute=False,
                alternatives=["insulin", "DPP-4 inhibitor"],
            ),

            # Liver disease
            ContraindicationRule(
                rule_id="CI003",
                name="Statins in Liver Disease",
                category=RuleCategory.CONTRAINDICATION,
                severity=RuleSeverity.HIGH,
                description="Most statins contraindicated in active liver disease",
                medication="atorvastatin",
                condition="liver disease",
                absolute=True,
                alternatives=["ezetimibe", "PCSK9 inhibitor"],
            ),

            # Pregnancy
            ContraindicationRule(
                rule_id="CI004",
                name="ACE Inhibitors in Pregnancy",
                category=RuleCategory.CONTRAINDICATION,
                severity=RuleSeverity.CRITICAL,
                description="ACE inhibitors cause fetal harm",
                medication="lisinopril",
                condition="pregnancy",
                absolute=True,
                alternatives=["labetalol", "methyldopa", "nifedipine"],
            ),
            ContraindicationRule(
                rule_id="CI005",
                name="Warfarin in Pregnancy",
                category=RuleCategory.CONTRAINDICATION,
                severity=RuleSeverity.CRITICAL,
                description="Warfarin is teratogenic",
                medication="warfarin",
                condition="pregnancy",
                absolute=True,
                alternatives=["low molecular weight heparin"],
            ),

            # GI bleeding
            ContraindicationRule(
                rule_id="CI006",
                name="NSAIDs in GI Bleeding",
                category=RuleCategory.CONTRAINDICATION,
                severity=RuleSeverity.CRITICAL,
                description="NSAIDs worsen GI bleeding",
                medication="ibuprofen",
                condition="gastrointestinal bleeding",
                absolute=True,
                alternatives=["acetaminophen"],
            ),

            # Heart failure
            ContraindicationRule(
                rule_id="CI007",
                name="NSAIDs in Heart Failure",
                category=RuleCategory.CONTRAINDICATION,
                severity=RuleSeverity.HIGH,
                description="NSAIDs cause fluid retention and worsen heart failure",
                medication="ibuprofen",
                condition="heart failure",
                absolute=False,
                alternatives=["acetaminophen"],
            ),

            # Asthma
            ContraindicationRule(
                rule_id="CI008",
                name="Beta-blockers in Asthma",
                category=RuleCategory.CONTRAINDICATION,
                severity=RuleSeverity.HIGH,
                description="Non-selective beta-blockers can trigger bronchospasm",
                medication="propranolol",
                condition="asthma",
                absolute=True,
                alternatives=["cardioselective beta-blocker if essential"],
            ),
        ]

        self._contraindications.extend(contraindications)

    def _load_allergy_rules(self) -> None:
        """Load allergy cross-reactivity rules."""
        allergy_rules = [
            # Penicillin cross-reactivity
            AllergyRule(
                rule_id="AR001",
                name="Penicillin Cross-Reactivity with Cephalosporins",
                category=RuleCategory.ALLERGY_ALERT,
                severity=RuleSeverity.HIGH,
                description="Patients with penicillin allergy may react to cephalosporins",
                allergen="penicillin",
                cross_reactive=["cephalexin", "cefazolin", "ceftriaxone", "cefuroxime"],
                reaction_type="cross-reactivity",
            ),
            AllergyRule(
                rule_id="AR002",
                name="Penicillin Cross-Reactivity with Amoxicillin",
                category=RuleCategory.ALLERGY_ALERT,
                severity=RuleSeverity.CRITICAL,
                description="Amoxicillin is a penicillin-type antibiotic",
                allergen="penicillin",
                cross_reactive=["amoxicillin", "ampicillin", "amoxicillin-clavulanate"],
                reaction_type="same class",
            ),

            # Sulfa allergies
            AllergyRule(
                rule_id="AR003",
                name="Sulfa Antibiotic Allergy",
                category=RuleCategory.ALLERGY_ALERT,
                severity=RuleSeverity.HIGH,
                description="Sulfa allergy - avoid sulfonamide antibiotics",
                allergen="sulfa",
                cross_reactive=["sulfamethoxazole", "sulfasalazine", "trimethoprim-sulfamethoxazole"],
                reaction_type="sulfonamide",
            ),

            # NSAID allergies
            AllergyRule(
                rule_id="AR004",
                name="Aspirin/NSAID Cross-Reactivity",
                category=RuleCategory.ALLERGY_ALERT,
                severity=RuleSeverity.HIGH,
                description="Cross-reactivity between aspirin and other NSAIDs",
                allergen="aspirin",
                cross_reactive=["ibuprofen", "naproxen", "diclofenac", "ketorolac"],
                reaction_type="NSAID cross-reactivity",
            ),

            # Codeine/Morphine
            AllergyRule(
                rule_id="AR005",
                name="Opioid Cross-Reactivity",
                category=RuleCategory.ALLERGY_ALERT,
                severity=RuleSeverity.HIGH,
                description="Cross-reactivity between opioids possible",
                allergen="codeine",
                cross_reactive=["morphine", "hydrocodone", "oxycodone"],
                reaction_type="opioid",
            ),
        ]

        self._allergy_rules.extend(allergy_rules)

    def _load_symptom_pattern_rules(self) -> None:
        """Load symptom pattern recognition rules."""
        patterns = [
            # Cardiac symptoms
            SymptomPatternRule(
                rule_id="SP001",
                name="Possible Acute Coronary Syndrome",
                category=RuleCategory.SYMPTOM_PATTERN,
                severity=RuleSeverity.CRITICAL,
                description="Symptom pattern suggestive of ACS",
                symptoms=["chest pain", "shortness of breath", "sweating", "nausea", "arm pain"],
                min_symptoms=2,
                suggested_conditions=["acute coronary syndrome", "unstable angina", "myocardial infarction"],
                urgency="emergency",
                recommended_actions=["Seek immediate medical attention", "Call emergency services"],
            ),
            SymptomPatternRule(
                rule_id="SP002",
                name="Heart Failure Exacerbation",
                category=RuleCategory.SYMPTOM_PATTERN,
                severity=RuleSeverity.HIGH,
                description="Symptoms suggesting heart failure worsening",
                symptoms=["shortness of breath", "leg swelling", "fatigue", "weight gain", "orthopnea"],
                min_symptoms=2,
                suggested_conditions=["heart failure exacerbation"],
                urgency="urgent",
                recommended_actions=["Contact healthcare provider today", "Monitor weight daily"],
            ),

            # Stroke symptoms
            SymptomPatternRule(
                rule_id="SP003",
                name="Possible Stroke (FAST)",
                category=RuleCategory.SYMPTOM_PATTERN,
                severity=RuleSeverity.CRITICAL,
                description="Symptoms suggestive of stroke",
                symptoms=["facial drooping", "arm weakness", "speech difficulty", "sudden confusion", "severe headache"],
                min_symptoms=1,
                suggested_conditions=["stroke", "transient ischemic attack"],
                urgency="emergency",
                recommended_actions=["Call emergency services immediately", "Note time of symptom onset"],
            ),

            # Diabetic emergency
            SymptomPatternRule(
                rule_id="SP004",
                name="Diabetic Ketoacidosis Warning",
                category=RuleCategory.SYMPTOM_PATTERN,
                severity=RuleSeverity.CRITICAL,
                description="Symptoms suggesting DKA",
                symptoms=["excessive thirst", "frequent urination", "nausea", "vomiting", "abdominal pain", "fruity breath"],
                min_symptoms=3,
                suggested_conditions=["diabetic ketoacidosis"],
                urgency="emergency",
                recommended_actions=["Check blood glucose", "Seek emergency care if glucose very high"],
            ),

            # Infection patterns
            SymptomPatternRule(
                rule_id="SP005",
                name="Possible Sepsis",
                category=RuleCategory.SYMPTOM_PATTERN,
                severity=RuleSeverity.CRITICAL,
                description="Symptoms suggesting possible sepsis",
                symptoms=["fever", "chills", "confusion", "rapid breathing", "rapid heart rate", "low blood pressure"],
                min_symptoms=3,
                suggested_conditions=["sepsis", "severe infection"],
                urgency="emergency",
                recommended_actions=["Seek immediate medical attention"],
            ),
            SymptomPatternRule(
                rule_id="SP006",
                name="Respiratory Infection Pattern",
                category=RuleCategory.SYMPTOM_PATTERN,
                severity=RuleSeverity.MODERATE,
                description="Common respiratory infection symptoms",
                symptoms=["cough", "fever", "sore throat", "runny nose", "body aches"],
                min_symptoms=3,
                suggested_conditions=["upper respiratory infection", "influenza", "COVID-19"],
                urgency="routine",
                recommended_actions=["Rest and hydration", "Consider testing for flu/COVID"],
            ),

            # GI patterns
            SymptomPatternRule(
                rule_id="SP007",
                name="Possible Appendicitis",
                category=RuleCategory.SYMPTOM_PATTERN,
                severity=RuleSeverity.HIGH,
                description="Symptoms suggesting appendicitis",
                symptoms=["abdominal pain", "right lower quadrant pain", "nausea", "vomiting", "fever", "loss of appetite"],
                min_symptoms=3,
                suggested_conditions=["appendicitis"],
                urgency="urgent",
                recommended_actions=["Seek medical evaluation today"],
            ),

            # Medication side effects
            SymptomPatternRule(
                rule_id="SP008",
                name="Statin Myopathy",
                category=RuleCategory.SYMPTOM_PATTERN,
                severity=RuleSeverity.MODERATE,
                description="Muscle symptoms possibly related to statin use",
                symptoms=["muscle pain", "muscle weakness", "fatigue", "muscle cramps"],
                min_symptoms=2,
                suggested_conditions=["statin-induced myopathy"],
                urgency="routine",
                recommended_actions=["Report to healthcare provider", "Consider CK level check"],
            ),
        ]

        self._symptom_patterns.extend(patterns)

    def evaluate(self, context: PatientContext) -> RuleEvaluationSummary:
        """Evaluate all applicable rules against patient context.

        Args:
            context: Patient context with medications, conditions, etc.

        Returns:
            Summary of all rule evaluations
        """
        self.stats["total_evaluations"] += 1
        summary = RuleEvaluationSummary()

        # Evaluate drug interactions
        if self.config.enable_drug_interactions and context.medications:
            for rule in self._drug_interactions:
                if not rule.active:
                    continue
                result = self._evaluate_drug_interaction(rule, context)
                if result.triggered:
                    summary.add_result(result)
                    self.stats["by_category"][RuleCategory.DRUG_INTERACTION.value] += 1

        # Evaluate contraindications
        if self.config.enable_contraindications and context.medications:
            for rule in self._contraindications:
                if not rule.active:
                    continue
                result = self._evaluate_contraindication(rule, context)
                if result.triggered:
                    summary.add_result(result)
                    self.stats["by_category"][RuleCategory.CONTRAINDICATION.value] += 1

        # Evaluate allergy rules
        if self.config.enable_allergy_alerts and context.allergies:
            for rule in self._allergy_rules:
                if not rule.active:
                    continue
                result = self._evaluate_allergy_rule(rule, context)
                if result.triggered:
                    summary.add_result(result)
                    self.stats["by_category"][RuleCategory.ALLERGY_ALERT.value] += 1

        # Evaluate symptom patterns
        if self.config.enable_symptom_patterns and context.symptoms:
            for rule in self._symptom_patterns:
                if not rule.active:
                    continue
                result = self._evaluate_symptom_pattern(rule, context)
                if result.triggered:
                    summary.add_result(result)
                    self.stats["by_category"][RuleCategory.SYMPTOM_PATTERN.value] += 1

        # Update statistics
        self.stats["total_alerts"] += summary.triggered_rules
        self.stats["critical_alerts"] += summary.critical_alerts

        logger.info(
            f"Evaluated {summary.total_rules_evaluated} rules for patient {context.patient_id}: "
            f"{summary.triggered_rules} triggered, {summary.critical_alerts} critical"
        )

        return summary

    def _evaluate_drug_interaction(
        self,
        rule: DrugInteractionRule,
        context: PatientContext,
    ) -> RuleEvaluationResult:
        """Evaluate a drug interaction rule."""
        if rule.matches(context.medications):
            return RuleEvaluationResult(
                rule=rule,
                triggered=True,
                severity=rule.severity,
                message=f"{rule.name}: {rule.effect}",
                entities_involved=[rule.drug_a, rule.drug_b],
                recommendations=[rule.recommendation] if rule.recommendation else [],
            )

        return RuleEvaluationResult(
            rule=rule,
            triggered=False,
            severity=rule.severity,
            message="",
        )

    def _evaluate_contraindication(
        self,
        rule: ContraindicationRule,
        context: PatientContext,
    ) -> RuleEvaluationResult:
        """Evaluate a contraindication rule."""
        if rule.matches(context.medications, context.conditions):
            absolute = "absolutely" if rule.absolute else "relatively"
            message = f"{rule.medication} is {absolute} contraindicated with {rule.condition}"

            recommendations = []
            if rule.alternatives:
                recommendations.append(f"Consider alternatives: {', '.join(rule.alternatives)}")

            return RuleEvaluationResult(
                rule=rule,
                triggered=True,
                severity=rule.severity,
                message=message,
                entities_involved=[rule.medication, rule.condition],
                recommendations=recommendations,
            )

        return RuleEvaluationResult(
            rule=rule,
            triggered=False,
            severity=rule.severity,
            message="",
        )

    def _evaluate_allergy_rule(
        self,
        rule: AllergyRule,
        context: PatientContext,
    ) -> RuleEvaluationResult:
        """Evaluate an allergy rule."""
        if rule.matches(context.allergies, context.medications):
            # Find which medication triggered
            meds_lower = [m.lower() for m in context.medications]
            triggered_meds = [
                m for m in rule.cross_reactive
                if m.lower() in meds_lower
            ]

            message = (
                f"Allergy alert: {rule.allergen} allergy may cause reaction to "
                f"{', '.join(triggered_meds)}"
            )

            return RuleEvaluationResult(
                rule=rule,
                triggered=True,
                severity=rule.severity,
                message=message,
                entities_involved=[rule.allergen] + triggered_meds,
                recommendations=[f"Avoid {', '.join(triggered_meds)} due to {rule.reaction_type}"],
            )

        return RuleEvaluationResult(
            rule=rule,
            triggered=False,
            severity=rule.severity,
            message="",
        )

    def _evaluate_symptom_pattern(
        self,
        rule: SymptomPatternRule,
        context: PatientContext,
    ) -> RuleEvaluationResult:
        """Evaluate a symptom pattern rule."""
        match_count = rule.matches(context.symptoms)

        if match_count >= rule.min_symptoms:
            # Find which symptoms matched
            symptoms_lower = [s.lower() for s in context.symptoms]
            matched = [
                s for s in rule.symptoms
                if any(s.lower() in ps for ps in symptoms_lower)
            ]

            message = (
                f"{rule.name}: {match_count} of {len(rule.symptoms)} symptoms present. "
                f"Consider {', '.join(rule.suggested_conditions)}."
            )

            return RuleEvaluationResult(
                rule=rule,
                triggered=True,
                severity=rule.severity,
                message=message,
                entities_involved=matched,
                recommendations=rule.recommended_actions,
                confidence=min(1.0, match_count / len(rule.symptoms)),
            )

        return RuleEvaluationResult(
            rule=rule,
            triggered=False,
            severity=rule.severity,
            message="",
        )

    def add_rule(self, rule: MedicalRule) -> None:
        """Add a custom rule to the engine."""
        if isinstance(rule, DrugInteractionRule):
            self._drug_interactions.append(rule)
        elif isinstance(rule, ContraindicationRule):
            self._contraindications.append(rule)
        elif isinstance(rule, AllergyRule):
            self._allergy_rules.append(rule)
        elif isinstance(rule, SymptomPatternRule):
            self._symptom_patterns.append(rule)

        logger.debug(f"Added rule: {rule.rule_id} - {rule.name}")

    def get_rule(self, rule_id: str) -> Optional[MedicalRule]:
        """Get a rule by ID."""
        for rules in [
            self._drug_interactions,
            self._contraindications,
            self._allergy_rules,
            self._symptom_patterns,
        ]:
            for rule in rules:
                if rule.rule_id == rule_id:
                    return rule
        return None

    def disable_rule(self, rule_id: str) -> bool:
        """Disable a rule by ID."""
        rule = self.get_rule(rule_id)
        if rule:
            rule.active = False
            return True
        return False

    def enable_rule(self, rule_id: str) -> bool:
        """Enable a rule by ID."""
        rule = self.get_rule(rule_id)
        if rule:
            rule.active = True
            return True
        return False

    def get_statistics(self) -> Dict[str, Any]:
        """Get engine statistics."""
        return {
            **self.stats,
            "rules_loaded": {
                "drug_interactions": len(self._drug_interactions),
                "contraindications": len(self._contraindications),
                "allergy_rules": len(self._allergy_rules),
                "symptom_patterns": len(self._symptom_patterns),
            },
            "config": {
                "enable_drug_interactions": self.config.enable_drug_interactions,
                "enable_contraindications": self.config.enable_contraindications,
                "enable_allergy_alerts": self.config.enable_allergy_alerts,
                "enable_symptom_patterns": self.config.enable_symptom_patterns,
            },
        }

    def list_rules(self, category: Optional[RuleCategory] = None) -> List[Dict[str, Any]]:
        """List all rules, optionally filtered by category."""
        rules = []

        if category is None or category == RuleCategory.DRUG_INTERACTION:
            rules.extend([r.to_dict() for r in self._drug_interactions])

        if category is None or category == RuleCategory.CONTRAINDICATION:
            rules.extend([r.to_dict() for r in self._contraindications])

        if category is None or category == RuleCategory.ALLERGY_ALERT:
            rules.extend([r.to_dict() for r in self._allergy_rules])

        if category is None or category == RuleCategory.SYMPTOM_PATTERN:
            rules.extend([r.to_dict() for r in self._symptom_patterns])

        return rules
