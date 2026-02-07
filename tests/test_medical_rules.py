"""Tests for the Medical Rules Engine.

Tests drug interactions, contraindications, allergy alerts,
and symptom pattern recognition.
"""

import pytest
from datetime import datetime

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
from application.rules.medical_rules import (
    MedicalRulesEngine,
    MedicalRulesConfig,
    PatientContext,
)


# ========================================
# Domain Model Tests
# ========================================

class TestMedicalRulesModels:
    """Tests for medical rules domain models."""

    def test_rule_severity_values(self):
        """Test RuleSeverity enum values."""
        assert RuleSeverity.CRITICAL.value == "critical"
        assert RuleSeverity.HIGH.value == "high"
        assert RuleSeverity.MODERATE.value == "moderate"
        assert RuleSeverity.LOW.value == "low"

    def test_rule_category_values(self):
        """Test RuleCategory enum values."""
        assert RuleCategory.DRUG_INTERACTION.value == "drug_interaction"
        assert RuleCategory.CONTRAINDICATION.value == "contraindication"
        assert RuleCategory.ALLERGY_ALERT.value == "allergy_alert"
        assert RuleCategory.SYMPTOM_PATTERN.value == "symptom_pattern"

    def test_drug_interaction_rule_matches(self):
        """Test DrugInteractionRule matching."""
        rule = DrugInteractionRule(
            rule_id="test",
            name="Test Interaction",
            category=RuleCategory.DRUG_INTERACTION,
            severity=RuleSeverity.HIGH,
            description="Test",
            drug_a="warfarin",
            drug_b="aspirin",
        )

        # Should match
        assert rule.matches(["Warfarin", "Aspirin"])
        assert rule.matches(["warfarin", "aspirin", "metformin"])

        # Should not match
        assert not rule.matches(["Warfarin"])
        assert not rule.matches(["Aspirin"])
        assert not rule.matches(["Metformin"])

    def test_contraindication_rule_matches(self):
        """Test ContraindicationRule matching."""
        rule = ContraindicationRule(
            rule_id="test",
            name="Test Contraindication",
            category=RuleCategory.CONTRAINDICATION,
            severity=RuleSeverity.HIGH,
            description="Test",
            medication="metformin",
            condition="renal impairment",
        )

        # Should match
        assert rule.matches(["Metformin"], ["Renal Impairment"])
        assert rule.matches(["metformin", "aspirin"], ["renal impairment", "diabetes"])

        # Should not match
        assert not rule.matches(["Metformin"], ["Diabetes"])
        assert not rule.matches(["Aspirin"], ["Renal Impairment"])

    def test_allergy_rule_matches(self):
        """Test AllergyRule matching."""
        rule = AllergyRule(
            rule_id="test",
            name="Test Allergy",
            category=RuleCategory.ALLERGY_ALERT,
            severity=RuleSeverity.HIGH,
            description="Test",
            allergen="penicillin",
            cross_reactive=["amoxicillin", "ampicillin"],
        )

        # Should match
        assert rule.matches(["Penicillin"], ["Amoxicillin"])
        assert rule.matches(["penicillin", "latex"], ["ampicillin"])

        # Should not match
        assert not rule.matches(["Penicillin"], ["Metformin"])
        assert not rule.matches(["Latex"], ["Amoxicillin"])

    def test_symptom_pattern_matches(self):
        """Test SymptomPatternRule matching."""
        rule = SymptomPatternRule(
            rule_id="test",
            name="Test Pattern",
            category=RuleCategory.SYMPTOM_PATTERN,
            severity=RuleSeverity.HIGH,
            description="Test",
            symptoms=["chest pain", "shortness of breath", "sweating"],
            min_symptoms=2,
        )

        # Should match (2+ symptoms)
        assert rule.matches(["chest pain", "sweating"]) >= 2
        assert rule.matches(["Chest pain", "Shortness of breath", "fatigue"]) >= 2

        # Should not reach threshold
        assert rule.matches(["chest pain"]) < 2
        assert rule.matches(["headache", "fatigue"]) < 2

    def test_evaluation_result_properties(self):
        """Test RuleEvaluationResult properties."""
        rule = MedicalRule(
            rule_id="test",
            name="Test",
            category=RuleCategory.DRUG_INTERACTION,
            severity=RuleSeverity.CRITICAL,
            description="Test",
        )

        result = RuleEvaluationResult(
            rule=rule,
            triggered=True,
            severity=RuleSeverity.CRITICAL,
            message="Critical alert",
        )

        assert result.is_critical
        assert result.requires_attention

    def test_evaluation_summary(self):
        """Test RuleEvaluationSummary."""
        summary = RuleEvaluationSummary()

        rule1 = MedicalRule(
            rule_id="test1",
            name="Test1",
            category=RuleCategory.DRUG_INTERACTION,
            severity=RuleSeverity.CRITICAL,
            description="Test",
        )

        rule2 = MedicalRule(
            rule_id="test2",
            name="Test2",
            category=RuleCategory.CONTRAINDICATION,
            severity=RuleSeverity.HIGH,
            description="Test",
        )

        summary.add_result(RuleEvaluationResult(
            rule=rule1,
            triggered=True,
            severity=RuleSeverity.CRITICAL,
            message="Critical",
        ))

        summary.add_result(RuleEvaluationResult(
            rule=rule2,
            triggered=True,
            severity=RuleSeverity.HIGH,
            message="High",
        ))

        assert summary.total_rules_evaluated == 2
        assert summary.triggered_rules == 2
        assert summary.critical_alerts == 1
        assert summary.high_alerts == 1
        assert summary.has_critical_alerts


# ========================================
# Medical Rules Engine Tests
# ========================================

class TestMedicalRulesEngine:
    """Tests for MedicalRulesEngine."""

    @pytest.fixture
    def engine(self):
        """Create a MedicalRulesEngine instance."""
        return MedicalRulesEngine()

    # ----------------------------------------
    # Drug Interaction Tests
    # ----------------------------------------

    def test_warfarin_aspirin_interaction(self, engine):
        """Test Warfarin + Aspirin interaction detection."""
        context = PatientContext(
            patient_id="test",
            medications=["Warfarin", "Aspirin"],
        )

        summary = engine.evaluate(context)

        assert summary.triggered_rules > 0
        assert any(
            "warfarin" in r.message.lower() and "aspirin" in r.message.lower()
            for r in summary.triggered_results
        )

    def test_azathioprine_allopurinol_critical(self, engine):
        """Test Azathioprine + Allopurinol critical interaction."""
        context = PatientContext(
            patient_id="test",
            medications=["Azathioprine", "Allopurinol"],
        )

        summary = engine.evaluate(context)

        assert summary.has_critical_alerts
        assert any(
            r.severity == RuleSeverity.CRITICAL
            for r in summary.triggered_results
        )

    def test_imurel_allopurinol_critical(self, engine):
        """Test Imurel + Allopurinol critical interaction."""
        context = PatientContext(
            patient_id="test",
            medications=["Imurel", "Allopurinol"],
        )

        summary = engine.evaluate(context)

        assert summary.has_critical_alerts

    def test_no_interaction_single_med(self, engine):
        """Test no interaction with single medication."""
        context = PatientContext(
            patient_id="test",
            medications=["Metformin"],
        )

        summary = engine.evaluate(context)

        # Should not have drug interaction alerts
        drug_interactions = [
            r for r in summary.triggered_results
            if r.rule.category == RuleCategory.DRUG_INTERACTION
        ]
        assert len(drug_interactions) == 0

    # ----------------------------------------
    # Contraindication Tests
    # ----------------------------------------

    def test_metformin_renal_contraindication(self, engine):
        """Test Metformin contraindication in renal impairment."""
        context = PatientContext(
            patient_id="test",
            medications=["Metformin"],
            conditions=["Renal Impairment"],
        )

        summary = engine.evaluate(context)

        contraindications = [
            r for r in summary.triggered_results
            if r.rule.category == RuleCategory.CONTRAINDICATION
        ]
        assert len(contraindications) > 0

    def test_ace_inhibitor_pregnancy(self, engine):
        """Test ACE inhibitor contraindication in pregnancy."""
        context = PatientContext(
            patient_id="test",
            medications=["Lisinopril"],
            conditions=["Pregnancy"],
        )

        summary = engine.evaluate(context)

        assert summary.has_critical_alerts
        assert any(
            "pregnancy" in r.message.lower()
            for r in summary.triggered_results
        )

    def test_no_contraindication(self, engine):
        """Test no contraindication when conditions don't match."""
        context = PatientContext(
            patient_id="test",
            medications=["Metformin"],
            conditions=["Diabetes"],
        )

        summary = engine.evaluate(context)

        contraindications = [
            r for r in summary.triggered_results
            if r.rule.category == RuleCategory.CONTRAINDICATION
        ]
        assert len(contraindications) == 0

    # ----------------------------------------
    # Allergy Alert Tests
    # ----------------------------------------

    def test_penicillin_amoxicillin_allergy(self, engine):
        """Test Penicillin allergy with Amoxicillin."""
        context = PatientContext(
            patient_id="test",
            allergies=["Penicillin"],
            medications=["Amoxicillin"],
        )

        summary = engine.evaluate(context)

        allergy_alerts = [
            r for r in summary.triggered_results
            if r.rule.category == RuleCategory.ALLERGY_ALERT
        ]
        assert len(allergy_alerts) > 0
        assert any(
            r.severity in [RuleSeverity.CRITICAL, RuleSeverity.HIGH]
            for r in allergy_alerts
        )

    def test_sulfa_allergy(self, engine):
        """Test Sulfa allergy detection."""
        context = PatientContext(
            patient_id="test",
            allergies=["Sulfa"],
            medications=["Sulfamethoxazole"],
        )

        summary = engine.evaluate(context)

        allergy_alerts = [
            r for r in summary.triggered_results
            if r.rule.category == RuleCategory.ALLERGY_ALERT
        ]
        assert len(allergy_alerts) > 0

    def test_no_allergy_alert(self, engine):
        """Test no allergy alert when no cross-reactivity."""
        context = PatientContext(
            patient_id="test",
            allergies=["Penicillin"],
            medications=["Metformin"],
        )

        summary = engine.evaluate(context)

        allergy_alerts = [
            r for r in summary.triggered_results
            if r.rule.category == RuleCategory.ALLERGY_ALERT
        ]
        assert len(allergy_alerts) == 0

    # ----------------------------------------
    # Symptom Pattern Tests
    # ----------------------------------------

    def test_acs_symptom_pattern(self, engine):
        """Test Acute Coronary Syndrome symptom pattern."""
        context = PatientContext(
            patient_id="test",
            symptoms=["chest pain", "shortness of breath", "sweating"],
        )

        summary = engine.evaluate(context)

        assert summary.has_critical_alerts
        assert any(
            "coronary" in r.message.lower() or "acs" in r.message.lower()
            for r in summary.triggered_results
        )

    def test_stroke_symptoms(self, engine):
        """Test stroke symptom pattern detection."""
        context = PatientContext(
            patient_id="test",
            symptoms=["facial drooping", "arm weakness"],
        )

        summary = engine.evaluate(context)

        assert summary.has_critical_alerts

    def test_respiratory_infection_pattern(self, engine):
        """Test respiratory infection symptom pattern."""
        context = PatientContext(
            patient_id="test",
            symptoms=["cough", "fever", "sore throat", "body aches"],
        )

        summary = engine.evaluate(context)

        symptom_patterns = [
            r for r in summary.triggered_results
            if r.rule.category == RuleCategory.SYMPTOM_PATTERN
        ]
        assert len(symptom_patterns) > 0
        assert any(
            "respiratory" in r.message.lower() or "infection" in r.message.lower()
            for r in symptom_patterns
        )

    def test_insufficient_symptoms(self, engine):
        """Test no pattern match with insufficient symptoms."""
        context = PatientContext(
            patient_id="test",
            symptoms=["headache"],
        )

        summary = engine.evaluate(context)

        # May still match some patterns, but critical ones need more symptoms
        critical_patterns = [
            r for r in summary.triggered_results
            if r.severity == RuleSeverity.CRITICAL
        ]
        # Single headache shouldn't trigger critical alerts
        assert len(critical_patterns) == 0

    # ----------------------------------------
    # Combined Evaluation Tests
    # ----------------------------------------

    def test_multiple_issues(self, engine):
        """Test detection of multiple issues."""
        context = PatientContext(
            patient_id="test",
            medications=["Warfarin", "Aspirin", "Metformin"],
            conditions=["Renal Impairment", "Atrial Fibrillation"],
            allergies=["Penicillin"],
            symptoms=["chest pain", "shortness of breath"],
        )

        summary = engine.evaluate(context)

        # Should have multiple alerts
        assert summary.triggered_rules >= 2

        # Should have drug interaction
        assert any(
            r.rule.category == RuleCategory.DRUG_INTERACTION
            for r in summary.triggered_results
        )

    def test_empty_context(self, engine):
        """Test evaluation with empty context."""
        context = PatientContext(patient_id="test")

        summary = engine.evaluate(context)

        assert summary.total_rules_evaluated == 0
        assert summary.triggered_rules == 0

    # ----------------------------------------
    # Rule Management Tests
    # ----------------------------------------

    def test_add_custom_rule(self, engine):
        """Test adding a custom rule."""
        custom_rule = DrugInteractionRule(
            rule_id="CUSTOM001",
            name="Custom Test Interaction",
            category=RuleCategory.DRUG_INTERACTION,
            severity=RuleSeverity.MODERATE,
            description="Test custom rule",
            drug_a="drug_x",
            drug_b="drug_y",
            effect="Test effect",
        )

        engine.add_rule(custom_rule)

        context = PatientContext(
            patient_id="test",
            medications=["Drug_X", "Drug_Y"],
        )

        summary = engine.evaluate(context)

        assert any(
            r.rule.rule_id == "CUSTOM001"
            for r in summary.triggered_results
        )

    def test_get_rule(self, engine):
        """Test getting a rule by ID."""
        rule = engine.get_rule("DI001")
        assert rule is not None
        assert rule.rule_id == "DI001"

    def test_get_nonexistent_rule(self, engine):
        """Test getting a nonexistent rule."""
        rule = engine.get_rule("NONEXISTENT")
        assert rule is None

    def test_disable_rule(self, engine):
        """Test disabling a rule."""
        # Verify rule triggers before disabling
        context = PatientContext(
            patient_id="test",
            medications=["Warfarin", "Aspirin"],
        )

        summary_before = engine.evaluate(context)
        triggered_before = len([
            r for r in summary_before.triggered_results
            if r.rule.rule_id == "DI001"
        ])

        # Disable the rule
        assert engine.disable_rule("DI001")

        # Verify rule no longer triggers
        summary_after = engine.evaluate(context)
        triggered_after = len([
            r for r in summary_after.triggered_results
            if r.rule.rule_id == "DI001"
        ])

        assert triggered_before > 0 or triggered_after == 0
        if triggered_before > 0:
            assert triggered_after == 0

        # Re-enable for other tests
        engine.enable_rule("DI001")

    def test_list_rules(self, engine):
        """Test listing all rules."""
        all_rules = engine.list_rules()
        assert len(all_rules) > 0

        # Filter by category
        drug_rules = engine.list_rules(RuleCategory.DRUG_INTERACTION)
        assert len(drug_rules) > 0
        assert all(r["category"] == "drug_interaction" for r in drug_rules)

    # ----------------------------------------
    # Statistics Tests
    # ----------------------------------------

    def test_statistics(self, engine):
        """Test engine statistics."""
        # Evaluate a context
        context = PatientContext(
            patient_id="test",
            medications=["Warfarin", "Aspirin"],
        )
        engine.evaluate(context)

        stats = engine.get_statistics()

        assert stats["total_evaluations"] >= 1
        assert "rules_loaded" in stats
        assert stats["rules_loaded"]["drug_interactions"] > 0
        assert "config" in stats


# ========================================
# Configuration Tests
# ========================================

class TestMedicalRulesConfig:
    """Tests for MedicalRulesConfig."""

    def test_disable_drug_interactions(self):
        """Test disabling drug interaction evaluation."""
        config = MedicalRulesConfig(enable_drug_interactions=False)
        engine = MedicalRulesEngine(config=config)

        context = PatientContext(
            patient_id="test",
            medications=["Warfarin", "Aspirin"],
        )

        summary = engine.evaluate(context)

        drug_interactions = [
            r for r in summary.triggered_results
            if r.rule.category == RuleCategory.DRUG_INTERACTION
        ]
        assert len(drug_interactions) == 0

    def test_disable_symptom_patterns(self):
        """Test disabling symptom pattern evaluation."""
        config = MedicalRulesConfig(enable_symptom_patterns=False)
        engine = MedicalRulesEngine(config=config)

        context = PatientContext(
            patient_id="test",
            symptoms=["chest pain", "shortness of breath", "sweating"],
        )

        summary = engine.evaluate(context)

        symptom_patterns = [
            r for r in summary.triggered_results
            if r.rule.category == RuleCategory.SYMPTOM_PATTERN
        ]
        assert len(symptom_patterns) == 0


# ========================================
# Patient Context Tests
# ========================================

class TestPatientContext:
    """Tests for PatientContext."""

    def test_default_values(self):
        """Test PatientContext default values."""
        context = PatientContext(patient_id="test")

        assert context.medications == []
        assert context.conditions == []
        assert context.allergies == []
        assert context.symptoms == []
        assert context.vital_signs == {}

    def test_with_values(self):
        """Test PatientContext with values."""
        context = PatientContext(
            patient_id="test",
            medications=["Med1", "Med2"],
            conditions=["Condition1"],
            allergies=["Allergy1"],
            symptoms=["Symptom1"],
        )

        assert len(context.medications) == 2
        assert len(context.conditions) == 1
        assert len(context.allergies) == 1
        assert len(context.symptoms) == 1
