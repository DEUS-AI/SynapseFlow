"""Tests for ReasoningEngine — pure-logic rules, strategies, provenance, cross-layer."""

import logging
import pytest
from unittest.mock import AsyncMock, MagicMock

from domain.event import KnowledgeEvent
from domain.roles import Role
from application.agents.knowledge_manager.reasoning_engine import ReasoningEngine
from application.agents.knowledge_manager.reasoning_config import (
    ReasoningEngineConfig,
    ConfidenceThresholds,
    ScoringConfig,
    StrategyConfig,
    CrossLayerConfig,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_backend():
    backend = AsyncMock()
    backend.list_relationships = AsyncMock(return_value=[])
    backend.query_raw = AsyncMock(return_value=[])
    return backend


@pytest.fixture
def engine(mock_backend):
    """ReasoningEngine with no LLM, no medical rules engine."""
    return ReasoningEngine(
        backend=mock_backend,
        llm=None,
        medical_rules_engine=MagicMock(),  # avoid real import
    )


@pytest.fixture
def custom_config():
    """A config with tweaked values for override testing."""
    cfg = ReasoningEngineConfig()
    cfg.confidence.person_keyword_confidence = 0.9
    cfg.strategy.symbolic_first_min_inferences = 5
    return cfg


def _entity_event(entity_id="test_entity", properties=None, labels=None) -> KnowledgeEvent:
    data = {"id": entity_id, "properties": properties or {}}
    if labels:
        data["labels"] = labels
    return KnowledgeEvent(action="create_entity", data=data, role=Role.DATA_ARCHITECT)


def _relationship_event(source="a", target="b", rel_type="related_to") -> KnowledgeEvent:
    return KnowledgeEvent(
        action="create_relationship",
        data={"source": source, "target": target, "type": rel_type},
        role=Role.DATA_ARCHITECT,
    )


def _chat_event(question="", medical_entities=None, **extra) -> KnowledgeEvent:
    data = {"question": question, "medical_entities": medical_entities or []}
    data.update(extra)
    return KnowledgeEvent(action="chat_query", data=data, role=Role.KNOWLEDGE_MANAGER)


# ---------------------------------------------------------------------------
# 4.2  Pure-logic create_entity rules
# ---------------------------------------------------------------------------


class TestInferProperties:
    async def test_id_pattern_identifier(self, engine):
        result = await engine._infer_properties(_entity_event("customer_id"))
        assert result is not None
        inferences = result["inferences"]
        id_inf = [i for i in inferences if i["value"] == "identifier"]
        assert len(id_inf) == 1
        assert id_inf[0]["confidence"] == engine.config.confidence.id_pattern_confidence

    async def test_person_keyword(self, engine):
        result = await engine._infer_properties(_entity_event("customer_profile"))
        inferences = result["inferences"]
        person = [i for i in inferences if i["value"] == "person"]
        assert len(person) == 1
        assert person[0]["confidence"] == engine.config.confidence.person_keyword_confidence

    async def test_transaction_keyword(self, engine):
        result = await engine._infer_properties(_entity_event("order_details"))
        inferences = result["inferences"]
        txn = [i for i in inferences if i["value"] == "transaction"]
        assert len(txn) == 1
        assert txn[0]["confidence"] == engine.config.confidence.transaction_keyword_confidence

    async def test_email_contact_info(self, engine):
        result = await engine._infer_properties(
            _entity_event("x", properties={"email": "a@b.com"})
        )
        assert any(i["property"] == "has_contact_info" for i in result["inferences"])

    async def test_temporal_property(self, engine):
        result = await engine._infer_properties(
            _entity_event("x", properties={"created_date": "2025-01-01"})
        )
        assert any(i["property"] == "is_temporal" for i in result["inferences"])

    async def test_no_matches_returns_none(self, engine):
        result = await engine._infer_properties(
            _entity_event("xyz", properties={"color": "blue"})
        )
        assert result is None

    async def test_custom_config_overrides(self, mock_backend, custom_config):
        eng = ReasoningEngine(
            backend=mock_backend, llm=None,
            medical_rules_engine=MagicMock(), config=custom_config,
        )
        result = await eng._infer_properties(_entity_event("customer_x"))
        person = [i for i in result["inferences"] if i["value"] == "person"]
        assert person[0]["confidence"] == 0.9


class TestClassifyEntity:
    async def test_person_classification(self, engine):
        result = await engine._classify_entity(
            _entity_event("x", properties={"name": "Alice", "email": "a@b.com"})
        )
        assert result is not None
        assert result["suggestions"][0]["classification"] == "person"

    async def test_financial_classification(self, engine):
        result = await engine._classify_entity(
            _entity_event("x", properties={"amount": 100})
        )
        assert result["suggestions"][0]["classification"] == "financial"

    async def test_process_classification(self, engine):
        result = await engine._classify_entity(
            _entity_event("x", properties={"status": "active", "created_date": "2025-01-01"})
        )
        assert result["suggestions"][0]["classification"] == "process"

    async def test_no_match(self, engine):
        result = await engine._classify_entity(_entity_event("x", properties={"foo": "bar"}))
        assert result is None


class TestSuggestRelationships:
    async def test_email_relationship(self, engine):
        result = await engine._suggest_relationships(
            _entity_event("x", properties={"email": "a@b.com"})
        )
        assert result is not None
        assert result["suggestions"][0]["relationship_type"] == "HAS_EMAIL"

    async def test_date_relationship(self, engine):
        result = await engine._suggest_relationships(
            _entity_event("x", properties={"created_date": "2025-01-01"})
        )
        assert result["suggestions"][0]["relationship_type"] == "CREATED_ON"

    async def test_no_suggestions(self, engine):
        result = await engine._suggest_relationships(
            _entity_event("x", properties={"color": "red"})
        )
        assert result is None


# ---------------------------------------------------------------------------
# 4.3  create_relationship rules
# ---------------------------------------------------------------------------


class TestValidateRelationshipLogic:
    async def test_self_reference_warning(self, engine):
        result = await engine._validate_relationship_logic(
            _relationship_event(source="A", target="A", rel_type="is_a")
        )
        assert result is not None
        assert any(w["type"] == "logical_inconsistency" for w in result["warnings"])

    async def test_naming_convention_warning(self, engine):
        result = await engine._validate_relationship_logic(
            _relationship_event(source="A", target="B", rel_type="is_a")
        )
        assert result is not None
        assert any(w["type"] == "naming_convention" for w in result["warnings"])

    async def test_valid_relationship(self, engine):
        result = await engine._validate_relationship_logic(
            _relationship_event(source="A", target="B", rel_type="HAS_PART")
        )
        assert result is None


class TestSuggestInverseRelationship:
    @pytest.mark.parametrize("rel_type,expected_inverse", [
        ("is_a", "has_instance"),
        ("has_part", "part_of"),
        ("owns", "owned_by"),
        ("manages", "managed_by"),
        ("reports_to", "has_subordinate"),
    ])
    async def test_known_inverses(self, engine, rel_type, expected_inverse):
        result = await engine._suggest_inverse_relationship(
            _relationship_event(rel_type=rel_type)
        )
        assert result is not None
        assert result["suggestions"][0]["inverse_type"] == expected_inverse
        assert result["suggestions"][0]["confidence"] == engine.config.confidence.inverse_relationship_confidence

    async def test_unknown_type_returns_none(self, engine):
        result = await engine._suggest_inverse_relationship(
            _relationship_event(rel_type="unknown_type")
        )
        assert result is None


# ---------------------------------------------------------------------------
# 4.4  chat_query rules
# ---------------------------------------------------------------------------


class TestValidateMedicalContext:
    async def test_high_confidence_entity(self, engine):
        entities = [{"name": "Aspirin", "type": "drug", "confidence": 0.9}]
        result = await engine._validate_medical_context(
            _chat_event(medical_entities=entities)
        )
        assert result is not None
        assert any(i["type"] == "validated_medical_entity" for i in result["inferences"])

    async def test_low_confidence_warning(self, engine):
        entities = [{"name": "Aspirin", "type": "drug", "confidence": 0.3}]
        result = await engine._validate_medical_context(
            _chat_event(medical_entities=entities)
        )
        assert result is not None
        assert len(result["warnings"]) > 0

    async def test_no_entities(self, engine):
        result = await engine._validate_medical_context(_chat_event())
        assert result is None


class TestCheckTreatmentRecommendations:
    @pytest.mark.parametrize("question", [
        "should i take aspirin",
        "what medication for headache",
        "recommend a treatment",
        "best treatment for cold",
    ])
    async def test_detection(self, engine, question):
        result = await engine._check_treatment_recommendations(
            _chat_event(question=question)
        )
        assert result is not None
        assert any(i.get("disclaimer_required") for i in result["inferences"])

    async def test_no_match(self, engine):
        result = await engine._check_treatment_recommendations(
            _chat_event(question="what is diabetes?")
        )
        assert result is None


class TestInferCrossGraphRelationships:
    async def test_table_name_match(self, engine):
        result = await engine._infer_cross_graph_relationships(
            _chat_event(
                medical_entities=[{"name": "diabetes"}],
                data_tables=[{"name": "diabetes_patients"}],
            )
        )
        assert result is not None
        link = result["inferences"][0]
        assert link["type"] == "inferred_cross_graph_link"
        assert link["data_type"] == "table"

    async def test_column_name_match(self, engine):
        result = await engine._infer_cross_graph_relationships(
            _chat_event(
                medical_entities=[{"name": "glucose"}],
                data_columns=[{"name": "glucose_level"}],
            )
        )
        assert result is not None
        assert result["inferences"][0]["data_type"] == "column"

    async def test_no_medical_entities(self, engine):
        result = await engine._infer_cross_graph_relationships(
            _chat_event(data_tables=[{"name": "foo"}])
        )
        assert result is None


class TestAssessDataAvailability:
    async def test_scoring_with_full_context(self, engine):
        result = await engine._assess_data_availability(
            _chat_event(
                medical_entities=[{"name": "a"}, {"name": "b"}, {"name": "c"}],
                medical_relationships=[{"type": "r1"}, {"type": "r2"}],
                data_tables=[{"name": "t1"}],
                data_columns=[{"name": "c1"}],
            )
        )
        score = result["inferences"][0]["score"]
        # 0.5 + 0.3 (3 entities) + 0.2 (2 rels) + 0.1 (1 table) + 0.05 (columns) = 1.0 capped
        assert score <= 1.0
        assert score > 0.8

    async def test_base_score_only(self, engine):
        result = await engine._assess_data_availability(_chat_event())
        score = result["inferences"][0]["score"]
        assert score == engine.config.scoring.base_availability_score


class TestScoreAnswerConfidence:
    async def test_base_confidence(self, engine):
        result = await engine._score_answer_confidence(_chat_event())
        score = result["inferences"][0]["score"]
        assert score == engine.config.scoring.base_answer_confidence

    async def test_boost_from_entities(self, engine):
        result = await engine._score_answer_confidence(
            _chat_event(medical_entities=[{"confidence": 0.9}, {"confidence": 0.85}])
        )
        score = result["inferences"][0]["score"]
        assert score > engine.config.scoring.base_answer_confidence

    async def test_warning_penalty(self, engine):
        result = await engine._score_answer_confidence(
            _chat_event(warnings=["some warning"])
        )
        score = result["inferences"][0]["score"]
        expected = engine.config.scoring.base_answer_confidence * engine.config.scoring.warning_penalty_factor
        assert abs(score - expected) < 0.001


# ---------------------------------------------------------------------------
# 4.5  Strategy tests
# ---------------------------------------------------------------------------


class TestStrategies:
    async def test_collaborative_no_llm(self, engine):
        event = _entity_event("customer_id", properties={"email": "a@b.com"})
        result = await engine.apply_reasoning(event, strategy="collaborative")
        assert "applied_rules" in result
        assert result["strategy"] == "collaborative"
        assert len(result["inferences"]) > 0

    async def test_neural_first_no_llm(self, engine):
        event = _entity_event("customer_id")
        result = await engine.apply_reasoning(event, strategy="neural_first")
        assert result["strategy"] == "neural_first"
        # Without LLM, only symbolic rules should fire
        assert "llm_semantic_inference" not in result["applied_rules"]

    async def test_symbolic_first_no_llm(self, engine):
        event = _entity_event("customer_id", properties={"email": "a@b.com"})
        result = await engine.apply_reasoning(event, strategy="symbolic_first")
        assert result["strategy"] == "symbolic_first"

    async def test_symbolic_first_gap_filling_threshold(self, mock_backend, custom_config):
        """With min_inferences=5, LLM gap-fill should be desired but skipped (no LLM)."""
        eng = ReasoningEngine(
            backend=mock_backend, llm=None,
            medical_rules_engine=MagicMock(), config=custom_config,
        )
        event = _entity_event("customer_id")
        result = await eng.apply_reasoning(event, strategy="symbolic_first")
        # Shouldn't crash, LLM is None so gap-fill is skipped
        assert result is not None

    async def test_reasoning_time_recorded(self, engine):
        event = _entity_event("x")
        result = await engine.apply_reasoning(event)
        assert result["reasoning_time"].endswith("ms")


# ---------------------------------------------------------------------------
# 4.6  Provenance tests
# ---------------------------------------------------------------------------


class TestProvenance:
    async def test_provenance_recorded(self, engine):
        event = _entity_event("prov_test", properties={"email": "a@b.com"})
        await engine.apply_reasoning(event)
        prov = engine.get_inference_provenance("prov_test")
        assert prov is not None
        assert len(prov) > 0
        assert "rule" in prov[0]
        assert "type" in prov[0]

    async def test_provenance_unknown_entity(self, engine):
        assert engine.get_inference_provenance("nonexistent") is None


# ---------------------------------------------------------------------------
# 4.7  Custom rule tests
# ---------------------------------------------------------------------------


class TestCustomRules:
    async def test_add_and_execute_custom_rule(self, engine):
        async def my_rule(event):
            return {"inferences": [{"type": "custom", "confidence": 1.0}]}

        engine.add_custom_reasoning_rule(
            "create_entity",
            {"name": "my_custom_rule", "reasoner": my_rule, "priority": "high"},
        )
        event = _entity_event("x")
        result = await engine.apply_reasoning(event)
        assert "my_custom_rule" in result["applied_rules"]

    def test_remove_existing_rule(self, engine):
        assert engine.remove_reasoning_rule("create_entity", "ontology_mapping") is True

    def test_remove_nonexistent_rule(self, engine):
        assert engine.remove_reasoning_rule("create_entity", "does_not_exist") is False

    def test_remove_from_nonexistent_action(self, engine):
        assert engine.remove_reasoning_rule("nonexistent_action", "rule") is False


# ---------------------------------------------------------------------------
# 4.8  Cross-layer reasoning tests
# ---------------------------------------------------------------------------


class TestCrossLayerReasoning:
    async def test_perception_to_semantic(self, engine):
        entity_data = {
            "type": "Table",
            "id": "table:customers",
            "properties": {
                "name": "customers",
                "columns": ["customer_id", "customer_name", "email", "phone"],
            },
        }
        result = await engine.apply_cross_layer_reasoning(entity_data, "PERCEPTION")
        assert "perception_to_semantic" in result["cross_layer_rules_applied"]
        concepts = [i for i in result["inferences"] if i["type"] == "business_concept_inference"]
        assert len(concepts) > 0
        assert concepts[0]["concept"] == "Customer"

    async def test_semantic_to_reasoning(self, engine):
        entity_data = {
            "properties": {"concept_type": "Customer"},
        }
        result = await engine.apply_cross_layer_reasoning(entity_data, "SEMANTIC")
        assert "semantic_to_reasoning" in result["cross_layer_rules_applied"]
        rules = [i for i in result["inferences"] if i["type"] == "quality_rule"]
        assert len(rules) > 0
        rule_names = [r["rule_name"] for r in rules]
        assert "email_required" in rule_names

    async def test_reasoning_to_application(self, engine):
        entity_data = {
            "properties": {"reasoning_type": "quality_rule", "rule_name": "unique_email"},
        }
        result = await engine.apply_cross_layer_reasoning(entity_data, "REASONING")
        assert "reasoning_to_application" in result["cross_layer_rules_applied"]
        patterns = [i for i in result["inferences"] if i["type"] == "query_pattern"]
        assert len(patterns) > 0

    async def test_unknown_layer_returns_empty(self, engine):
        result = await engine.apply_cross_layer_reasoning({"properties": {}}, "UNKNOWN")
        assert result["inferences"] == []
        assert result["suggestions"] == []
        assert result["cross_layer_rules_applied"] == []


# ---------------------------------------------------------------------------
# 4.9  Advanced reasoning tests
# ---------------------------------------------------------------------------


class TestAdvancedReasoning:
    async def test_orphaned_relationship_detection(self, engine):
        events = [
            _entity_event("entity_A"),
            KnowledgeEvent(
                action="create_relationship",
                data={"source": "entity_A", "target": "entity_MISSING", "type": "HAS"},
                role=Role.DATA_ARCHITECT,
            ),
        ]
        result = await engine.apply_advanced_reasoning(events)
        orphaned = [c for c in result["consistency_checks"] if c["type"] == "orphaned_relationship"]
        assert len(orphaned) > 0

    async def test_relationship_consolidation_suggestion(self, engine):
        events = []
        for i in range(12):
            events.append(
                KnowledgeEvent(
                    action="create_relationship",
                    data={"source": "A", "target": "B", "type": f"REL_TYPE_{i}"},
                    role=Role.DATA_ARCHITECT,
                )
            )
        result = await engine.apply_advanced_reasoning(events)
        suggestions = [s for s in result["optimization_suggestions"] if s["type"] == "relationship_consolidation"]
        assert len(suggestions) > 0

    async def test_no_consolidation_under_threshold(self, engine):
        events = [
            KnowledgeEvent(
                action="create_relationship",
                data={"source": "A", "target": "B", "type": f"REL_{i}"},
                role=Role.DATA_ARCHITECT,
            )
            for i in range(5)
        ]
        result = await engine.apply_advanced_reasoning(events)
        assert len(result["optimization_suggestions"]) == 0


# ---------------------------------------------------------------------------
# Config override validation — prove config values are actually wired
# ---------------------------------------------------------------------------


class TestConfigOverrides:
    """Verify that custom config values propagate to rule outputs."""

    async def test_medical_high_threshold_override(self, mock_backend):
        cfg = ReasoningEngineConfig()
        cfg.confidence.medical_high_threshold = 0.95  # raise threshold
        eng = ReasoningEngine(backend=mock_backend, llm=None, medical_rules_engine=MagicMock(), config=cfg)

        # Entity at 0.9 would normally be "high" — with threshold=0.95 it should NOT be
        entities = [{"name": "Aspirin", "type": "drug", "confidence": 0.9}]
        result = await eng._validate_medical_context(
            _chat_event(medical_entities=entities)
        )
        validated = [i for i in (result or {}).get("inferences", []) if i["type"] == "validated_medical_entity"]
        assert len(validated) == 0  # 0.9 < 0.95 threshold

    async def test_medical_low_threshold_override(self, mock_backend):
        cfg = ReasoningEngineConfig()
        cfg.confidence.medical_low_threshold = 0.2  # lower the warning threshold
        eng = ReasoningEngine(backend=mock_backend, llm=None, medical_rules_engine=MagicMock(), config=cfg)

        entities = [{"name": "Aspirin", "type": "drug", "confidence": 0.3}]
        result = await eng._validate_medical_context(
            _chat_event(medical_entities=entities)
        )
        # 0.3 >= 0.2, so should NOT trigger low-confidence warning
        assert result is None or len(result.get("warnings", [])) == 0

    async def test_scoring_base_override(self, mock_backend):
        cfg = ReasoningEngineConfig()
        cfg.scoring.base_availability_score = 0.9
        eng = ReasoningEngine(backend=mock_backend, llm=None, medical_rules_engine=MagicMock(), config=cfg)

        result = await eng._assess_data_availability(_chat_event())
        score = result["inferences"][0]["score"]
        assert score == 0.9

    async def test_answer_confidence_base_override(self, mock_backend):
        cfg = ReasoningEngineConfig()
        cfg.scoring.base_answer_confidence = 0.1
        eng = ReasoningEngine(backend=mock_backend, llm=None, medical_rules_engine=MagicMock(), config=cfg)

        result = await eng._score_answer_confidence(_chat_event())
        score = result["inferences"][0]["score"]
        assert score == 0.1

    async def test_warning_penalty_override(self, mock_backend):
        cfg = ReasoningEngineConfig()
        cfg.scoring.base_answer_confidence = 1.0
        cfg.scoring.warning_penalty_factor = 0.5
        eng = ReasoningEngine(backend=mock_backend, llm=None, medical_rules_engine=MagicMock(), config=cfg)

        result = await eng._score_answer_confidence(
            _chat_event(warnings=["w1"])
        )
        assert result["inferences"][0]["score"] == 0.5

    async def test_symbolic_first_min_inferences_override(self, mock_backend):
        """With min_inferences=0, gap-filling should never trigger (already >= 0)."""
        cfg = ReasoningEngineConfig()
        cfg.strategy.symbolic_first_min_inferences = 0
        eng = ReasoningEngine(backend=mock_backend, llm=None, medical_rules_engine=MagicMock(), config=cfg)

        event = _entity_event("x", properties={"color": "blue"})
        result = await eng.apply_reasoning(event, strategy="symbolic_first")
        # Should not crash; LLM is None anyway, but the threshold change is exercised
        assert result is not None

    async def test_cross_layer_concept_match_override(self, mock_backend):
        cfg = ReasoningEngineConfig()
        cfg.cross_layer.concept_match_threshold = 1.0  # impossibly high
        eng = ReasoningEngine(backend=mock_backend, llm=None, medical_rules_engine=MagicMock(), config=cfg)

        entity_data = {
            "type": "Table",
            "id": "table:customers",
            "properties": {
                "name": "customers",
                "columns": ["customer_id", "email"],
            },
        }
        result = await eng.apply_cross_layer_reasoning(entity_data, "PERCEPTION")
        concepts = [i for i in result["inferences"] if i["type"] == "business_concept_inference"]
        assert len(concepts) == 0  # nothing can reach 100% match

    async def test_consolidation_threshold_override(self, mock_backend):
        cfg = ReasoningEngineConfig()
        cfg.strategy.relationship_type_consolidation_threshold = 3
        eng = ReasoningEngine(backend=mock_backend, llm=None, medical_rules_engine=MagicMock(), config=cfg)

        events = [
            KnowledgeEvent(
                action="create_relationship",
                data={"source": "A", "target": "B", "type": f"REL_{i}"},
                role=Role.DATA_ARCHITECT,
            )
            for i in range(5)
        ]
        result = await eng.apply_advanced_reasoning(events)
        # 5 types > 3 threshold, so should suggest consolidation
        assert len(result["optimization_suggestions"]) > 0

    async def test_classify_confidence_override(self, mock_backend):
        cfg = ReasoningEngineConfig()
        cfg.confidence.classify_person_confidence = 0.99
        eng = ReasoningEngine(backend=mock_backend, llm=None, medical_rules_engine=MagicMock(), config=cfg)

        result = await eng._classify_entity(
            _entity_event("x", properties={"name": "Alice", "email": "a@b.com"})
        )
        assert result["suggestions"][0]["confidence"] == 0.99

    async def test_cross_graph_confidence_override(self, mock_backend):
        cfg = ReasoningEngineConfig()
        cfg.confidence.cross_graph_table_confidence = 0.55
        eng = ReasoningEngine(backend=mock_backend, llm=None, medical_rules_engine=MagicMock(), config=cfg)

        result = await eng._infer_cross_graph_relationships(
            _chat_event(
                medical_entities=[{"name": "diabetes"}],
                data_tables=[{"name": "diabetes_patients"}],
            )
        )
        assert result["inferences"][0]["confidence"] == 0.55


# ---------------------------------------------------------------------------
# Config dataclass construction tests
# ---------------------------------------------------------------------------


class TestConfigDataclasses:
    """Verify config dataclasses instantiate correctly."""

    def test_default_config_has_all_subconfigs(self):
        cfg = ReasoningEngineConfig()
        assert isinstance(cfg.confidence, ConfidenceThresholds)
        assert isinstance(cfg.scoring, ScoringConfig)
        assert isinstance(cfg.strategy, StrategyConfig)
        assert isinstance(cfg.cross_layer, CrossLayerConfig)

    def test_default_confidence_values(self):
        c = ConfidenceThresholds()
        assert c.id_pattern_confidence == 0.8
        assert c.person_keyword_confidence == 0.7
        assert c.medical_high_threshold == 0.8
        assert c.medical_low_threshold == 0.6

    def test_default_scoring_values(self):
        s = ScoringConfig()
        assert s.base_availability_score == 0.5
        assert s.base_answer_confidence == 0.5
        assert s.warning_penalty_factor == 0.95

    def test_default_strategy_values(self):
        s = StrategyConfig()
        assert s.symbolic_first_min_inferences == 2
        assert s.default_neural_confidence == 0.7
        assert s.relationship_type_consolidation_threshold == 10

    def test_default_cross_layer_values(self):
        cl = CrossLayerConfig()
        assert cl.concept_match_threshold == 0.4
        assert cl.materialized_view_threshold == 0.9
        assert cl.high_access_threshold == 100

    def test_two_default_configs_are_equal(self):
        assert ReasoningEngineConfig() == ReasoningEngineConfig()

    def test_engine_none_config_uses_defaults(self, mock_backend):
        eng = ReasoningEngine(backend=mock_backend, llm=None, medical_rules_engine=MagicMock())
        assert eng.config == ReasoningEngineConfig()


# ---------------------------------------------------------------------------
# Observability logging tests
# ---------------------------------------------------------------------------


class TestObservabilityLogging:
    """Verify structured logging fires at the right levels."""

    async def test_strategy_selection_logged_at_info(self, engine, caplog):
        event = _entity_event("x")
        with caplog.at_level(logging.INFO, logger="application.agents.knowledge_manager.reasoning_engine"):
            await engine.apply_reasoning(event)

        info_messages = [r.message for r in caplog.records if r.levelno == logging.INFO]
        strategy_msgs = [m for m in info_messages if m.startswith("Reasoning: strategy=")]
        assert len(strategy_msgs) >= 1
        assert "collaborative" in strategy_msgs[0]

    async def test_summary_logged_at_info(self, engine, caplog):
        event = _entity_event("x")
        with caplog.at_level(logging.INFO, logger="application.agents.knowledge_manager.reasoning_engine"):
            await engine.apply_reasoning(event)

        info_messages = [r.message for r in caplog.records if r.levelno == logging.INFO]
        summary_msgs = [m for m in info_messages if m.startswith("Reasoning complete:")]
        assert len(summary_msgs) >= 1
        assert "rules_fired=" in summary_msgs[0]
        assert "time=" in summary_msgs[0]

    async def test_rule_fired_logged_at_debug(self, engine, caplog):
        event = _entity_event("customer_id", properties={"email": "a@b.com"})
        with caplog.at_level(logging.DEBUG, logger="application.agents.knowledge_manager.reasoning_engine"):
            await engine.apply_reasoning(event)

        debug_messages = [r.message for r in caplog.records if r.levelno == logging.DEBUG]
        fired_msgs = [m for m in debug_messages if m.startswith("Rule fired:")]
        assert len(fired_msgs) > 0

    async def test_rule_skipped_logged_at_debug(self, engine, caplog):
        # Entity with no properties — most rules will skip
        event = _entity_event("xyz", properties={})
        with caplog.at_level(logging.DEBUG, logger="application.agents.knowledge_manager.reasoning_engine"):
            await engine.apply_reasoning(event)

        debug_messages = [r.message for r in caplog.records if r.levelno == logging.DEBUG]
        skipped_msgs = [m for m in debug_messages if m.startswith("Rule skipped:")]
        assert len(skipped_msgs) > 0

    async def test_cross_layer_logged_at_debug(self, engine, caplog):
        entity_data = {"properties": {"concept_type": "Customer"}}
        with caplog.at_level(logging.DEBUG, logger="application.agents.knowledge_manager.reasoning_engine"):
            await engine.apply_cross_layer_reasoning(entity_data, "SEMANTIC")

        debug_messages = [r.message for r in caplog.records if r.levelno == logging.DEBUG]
        cl_msgs = [m for m in debug_messages if m.startswith("Cross-layer reasoning:")]
        assert len(cl_msgs) >= 1
        assert "layer=SEMANTIC" in cl_msgs[0]


# ---------------------------------------------------------------------------
# LLMReasonerConfig and ValidationLimits wiring tests
# ---------------------------------------------------------------------------


class TestPeripheralConfigs:
    """Verify LLMReasonerConfig and ValidationLimits are properly wired."""

    def test_llm_reasoner_config_defaults(self):
        from application.agents.knowledge_manager.llm_reasoner import LLMReasonerConfig
        cfg = LLMReasonerConfig()
        assert cfg.default_inference_confidence == 0.7
        assert cfg.default_linking_confidence == 0.8

    def test_validation_limits_defaults(self):
        from application.agents.knowledge_manager.validation_engine import ValidationLimits
        cfg = ValidationLimits()
        assert cfg.max_id_length == 100
        assert cfg.max_property_value_size == 1000
        assert cfg.max_relationship_type_length == 50

    def test_validation_engine_accepts_config(self, mock_backend):
        from application.agents.knowledge_manager.validation_engine import ValidationEngine, ValidationLimits
        cfg = ValidationLimits(max_id_length=10)
        ve = ValidationEngine(backend=mock_backend, config=cfg)
        assert ve.config.max_id_length == 10

    def test_validation_engine_default_config(self, mock_backend):
        from application.agents.knowledge_manager.validation_engine import ValidationEngine, ValidationLimits
        ve = ValidationEngine(backend=mock_backend)
        assert ve.config == ValidationLimits()
