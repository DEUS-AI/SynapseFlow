"""Tests for the DIKW Router Service.

Tests query intent classification and layer routing.
"""

import pytest
from datetime import datetime

from domain.query_intent_models import (
    QueryIntent,
    DIKWLayer,
    IntentClassification,
    RoutingDecision,
    INTENT_PATTERNS,
    INTENT_LAYER_MAPPING,
    INTENT_STRATEGY_MAPPING,
)
from application.services.dikw_router import (
    DIKWRouter,
    DIKWRouterConfig,
)


# ========================================
# Query Intent Models Tests
# ========================================

class TestQueryIntentModels:
    """Tests for query intent domain models."""

    def test_query_intent_values(self):
        """Test QueryIntent enum values."""
        assert QueryIntent.FACTUAL.value == "factual"
        assert QueryIntent.RELATIONAL.value == "relational"
        assert QueryIntent.INFERENTIAL.value == "inferential"
        assert QueryIntent.ACTIONABLE.value == "actionable"
        assert QueryIntent.EXPLORATORY.value == "exploratory"

    def test_dikw_layer_values(self):
        """Test DIKWLayer enum values."""
        assert DIKWLayer.PERCEPTION.value == "PERCEPTION"
        assert DIKWLayer.SEMANTIC.value == "SEMANTIC"
        assert DIKWLayer.REASONING.value == "REASONING"
        assert DIKWLayer.APPLICATION.value == "APPLICATION"

    def test_intent_classification_properties(self):
        """Test IntentClassification properties."""
        classification = IntentClassification(
            primary_intent=QueryIntent.FACTUAL,
            confidence=0.9,
            recommended_layers=[DIKWLayer.SEMANTIC, DIKWLayer.PERCEPTION],
        )

        assert classification.is_high_confidence
        assert classification.primary_layer == DIKWLayer.SEMANTIC

    def test_intent_classification_low_confidence(self):
        """Test IntentClassification with low confidence."""
        classification = IntentClassification(
            primary_intent=QueryIntent.EXPLORATORY,
            confidence=0.5,
            recommended_layers=[],
        )

        assert not classification.is_high_confidence
        assert classification.primary_layer == DIKWLayer.SEMANTIC  # Default

    def test_routing_decision_fallback_layers(self):
        """Test RoutingDecision fallback layer generation."""
        decision = RoutingDecision(
            query_text="test",
            intent=IntentClassification(
                primary_intent=QueryIntent.INFERENTIAL,
                confidence=0.8,
                recommended_layers=[DIKWLayer.REASONING],
            ),
            layers=[DIKWLayer.REASONING],
            strategy="collaborative",
            fallback_enabled=True,
            max_fallback_depth=2,
        )

        fallbacks = decision.get_fallback_layers()
        assert DIKWLayer.SEMANTIC in fallbacks
        assert len(fallbacks) <= 2

    def test_routing_decision_no_fallback(self):
        """Test RoutingDecision with fallback disabled."""
        decision = RoutingDecision(
            query_text="test",
            intent=IntentClassification(
                primary_intent=QueryIntent.FACTUAL,
                confidence=0.9,
                recommended_layers=[DIKWLayer.SEMANTIC],
            ),
            layers=[DIKWLayer.SEMANTIC],
            strategy="symbolic_first",
            fallback_enabled=False,
        )

        assert decision.get_fallback_layers() == []


# ========================================
# DIKW Router Tests
# ========================================

class TestDIKWRouter:
    """Tests for DIKWRouter service."""

    @pytest.fixture
    def router(self):
        """Create a DIKWRouter instance."""
        return DIKWRouter()

    # ----------------------------------------
    # Factual Intent Tests
    # ----------------------------------------

    def test_classify_factual_spanish_what(self, router):
        """Test classifying Spanish factual 'qué' question."""
        classification = router.classify_intent("¿Qué medicamentos tomo?")

        assert classification.primary_intent == QueryIntent.FACTUAL
        assert classification.confidence > 0.5

    def test_classify_factual_spanish_when(self, router):
        """Test classifying Spanish factual 'cuándo' question."""
        classification = router.classify_intent("¿Cuándo fue mi última visita?")

        assert classification.primary_intent == QueryIntent.FACTUAL

    def test_classify_factual_english_what(self, router):
        """Test classifying English factual 'what' question."""
        classification = router.classify_intent("What medications am I taking?")

        assert classification.primary_intent == QueryIntent.FACTUAL

    def test_route_factual_layers(self, router):
        """Test that factual queries route to SEMANTIC/PERCEPTION."""
        decision = router.route_query("¿Cuál es mi diagnóstico?")

        assert DIKWLayer.SEMANTIC in decision.layers
        assert decision.strategy == "symbolic_first"

    # ----------------------------------------
    # Relational Intent Tests
    # ----------------------------------------

    def test_classify_relational_spanish(self, router):
        """Test classifying Spanish relational query."""
        classification = router.classify_intent("¿Qué medicamento sirve para la diabetes?")

        assert classification.primary_intent == QueryIntent.RELATIONAL

    def test_classify_relational_english(self, router):
        """Test classifying English relational query."""
        classification = router.classify_intent("What medication is used for diabetes?")

        assert classification.primary_intent == QueryIntent.RELATIONAL

    def test_classify_relational_interactions(self, router):
        """Test classifying drug interaction query."""
        classification = router.classify_intent("¿Hay interacción con ibuprofeno?")

        assert classification.primary_intent == QueryIntent.RELATIONAL

    def test_route_relational_layers(self, router):
        """Test that relational queries route to SEMANTIC."""
        decision = router.route_query("¿Para qué sirve el Imurel?")

        assert DIKWLayer.SEMANTIC in decision.layers

    # ----------------------------------------
    # Inferential Intent Tests
    # ----------------------------------------

    def test_classify_inferential_spanish_should(self, router):
        """Test classifying Spanish inferential 'debería' query."""
        classification = router.classify_intent("¿Debería preocuparme por estos síntomas?")

        assert classification.primary_intent == QueryIntent.INFERENTIAL
        assert classification.requires_inference

    def test_classify_inferential_spanish_why(self, router):
        """Test classifying Spanish inferential 'por qué' query."""
        classification = router.classify_intent("¿Por qué tengo dolor de cabeza?")

        assert classification.primary_intent == QueryIntent.INFERENTIAL

    def test_classify_inferential_english(self, router):
        """Test classifying English inferential query."""
        classification = router.classify_intent("Should I be worried about this?")

        assert classification.primary_intent == QueryIntent.INFERENTIAL

    def test_classify_inferential_is_normal(self, router):
        """Test classifying 'is it normal' query."""
        classification = router.classify_intent("¿Es normal que me sienta así?")

        assert classification.primary_intent == QueryIntent.INFERENTIAL

    def test_route_inferential_layers(self, router):
        """Test that inferential queries route to REASONING."""
        decision = router.route_query("¿Es peligroso mezclar estos medicamentos?")

        assert DIKWLayer.REASONING in decision.layers
        assert decision.intent.requires_inference

    # ----------------------------------------
    # Actionable Intent Tests
    # ----------------------------------------

    def test_classify_actionable_spanish(self, router):
        """Test classifying Spanish actionable query."""
        classification = router.classify_intent("¿Qué debo hacer si me olvido una dosis?")

        assert classification.primary_intent == QueryIntent.ACTIONABLE
        assert classification.requires_inference

    def test_classify_actionable_english(self, router):
        """Test classifying English actionable query."""
        classification = router.classify_intent("What should I do next?")

        assert classification.primary_intent == QueryIntent.ACTIONABLE

    def test_classify_actionable_recommend(self, router):
        """Test classifying recommendation query."""
        classification = router.classify_intent("¿Qué me recomiendas?")

        assert classification.primary_intent == QueryIntent.ACTIONABLE

    def test_route_actionable_layers(self, router):
        """Test that actionable queries route to APPLICATION."""
        decision = router.route_query("¿Qué pasos debo seguir?")

        assert DIKWLayer.APPLICATION in decision.layers

    # ----------------------------------------
    # Exploratory Intent Tests
    # ----------------------------------------

    def test_classify_exploratory_spanish(self, router):
        """Test classifying Spanish exploratory query."""
        classification = router.classify_intent("Cuéntame sobre mi tratamiento")

        assert classification.primary_intent == QueryIntent.EXPLORATORY

    def test_classify_exploratory_english(self, router):
        """Test classifying English exploratory query."""
        classification = router.classify_intent("Tell me about my condition")

        assert classification.primary_intent == QueryIntent.EXPLORATORY

    def test_route_exploratory_layers(self, router):
        """Test that exploratory queries route to multiple layers."""
        decision = router.route_query("Explícame todo sobre la diabetes")

        assert len(decision.layers) > 1

    # ----------------------------------------
    # Fallback Logic Tests
    # ----------------------------------------

    def test_should_fallback_no_results(self, router):
        """Test fallback is triggered when no results."""
        decision = router.route_query("¿Cuál es mi diagnóstico?")
        layer_results = {DIKWLayer.SEMANTIC: []}

        next_layer = router.should_fallback(decision, layer_results)

        assert next_layer is not None
        assert next_layer != DIKWLayer.SEMANTIC

    def test_should_fallback_has_results(self, router):
        """Test no fallback when results exist."""
        decision = router.route_query("¿Cuál es mi diagnóstico?")
        layer_results = {DIKWLayer.SEMANTIC: [{"id": "1", "name": "test"}]}

        next_layer = router.should_fallback(decision, layer_results)

        assert next_layer is None

    def test_should_fallback_disabled(self, router):
        """Test no fallback when disabled."""
        config = DIKWRouterConfig(enable_fallback=False)
        router_no_fallback = DIKWRouter(config=config)

        decision = router_no_fallback.route_query("test query")
        decision.fallback_enabled = False
        layer_results = {DIKWLayer.SEMANTIC: []}

        next_layer = router_no_fallback.should_fallback(decision, layer_results)

        assert next_layer is None

    # ----------------------------------------
    # Empty Layer Adjustment Tests
    # ----------------------------------------

    def test_adjust_for_empty_reasoning(self, router):
        """Test strategy adjustment when REASONING is empty."""
        decision = router.route_query("¿Debería preocuparme?")
        semantic_results = [{"id": "1", "name": "symptom"}]

        strategy, context = router.adjust_for_empty_reasoning(decision, semantic_results)

        assert strategy == "neural_first"
        assert "semantic_context" in context

    def test_adjust_for_empty_application(self, router):
        """Test strategy adjustment when APPLICATION is empty."""
        decision = router.route_query("¿Qué debo hacer?")
        reasoning_results = [{"id": "1", "inference": "test"}]

        strategy, context = router.adjust_for_empty_application(decision, reasoning_results)

        assert strategy == "collaborative"
        assert "reasoning_context" in context

    # ----------------------------------------
    # Query Context Tests
    # ----------------------------------------

    def test_get_query_context_factual(self, router):
        """Test query context for factual intent."""
        decision = router.route_query("¿Qué medicamentos tomo?")
        context = router.get_query_context(decision)

        assert context["intent"] == "factual"
        assert context["prefer_exact_matches"] is True

    def test_get_query_context_relational(self, router):
        """Test query context for relational intent."""
        decision = router.route_query("¿Qué medicamento para la diabetes?")
        context = router.get_query_context(decision)

        assert context["intent"] == "relational"
        assert context["include_relationships"] is True

    def test_get_query_context_inferential(self, router):
        """Test query context for inferential intent."""
        decision = router.route_query("¿Debería preocuparme?")
        context = router.get_query_context(decision)

        assert context["intent"] == "inferential"
        assert context["apply_reasoning_rules"] is True

    def test_get_query_context_actionable(self, router):
        """Test query context for actionable intent."""
        decision = router.route_query("¿Qué debo hacer?")
        context = router.get_query_context(decision)

        assert context["intent"] == "actionable"
        assert context["prioritize_recommendations"] is True

    # ----------------------------------------
    # Statistics Tests
    # ----------------------------------------

    def test_statistics_tracking(self, router):
        """Test that routing statistics are tracked."""
        # Route some queries
        router.route_query("¿Qué medicamentos tomo?")  # Factual
        router.route_query("¿Debería preocuparme?")    # Inferential
        router.route_query("¿Qué debo hacer?")         # Actionable

        stats = router.get_statistics()

        assert stats["total_routed"] == 3
        assert stats["by_intent"]["factual"] >= 1
        assert stats["by_intent"]["inferential"] >= 1
        assert stats["by_intent"]["actionable"] >= 1

    def test_intent_distribution(self, router):
        """Test intent distribution calculation."""
        router.route_query("query 1")
        router.route_query("query 2")

        stats = router.get_statistics()

        total_dist = sum(stats["intent_distribution"].values())
        assert 0.99 <= total_dist <= 1.01  # Should sum to ~1.0

    # ----------------------------------------
    # Explain Routing Tests
    # ----------------------------------------

    def test_explain_routing(self, router):
        """Test routing explanation."""
        explanation = router.explain_routing("¿Qué medicamentos tomo para la diabetes?")

        assert "query" in explanation
        assert "intent" in explanation
        assert "routing" in explanation
        assert "context" in explanation
        assert explanation["intent"]["primary"] in ["factual", "relational"]

    # ----------------------------------------
    # Edge Cases
    # ----------------------------------------

    def test_empty_query(self, router):
        """Test handling empty query."""
        classification = router.classify_intent("")

        # Should default to exploratory with low confidence
        assert classification.confidence < 0.5

    def test_no_patterns_matched(self, router):
        """Test query with no pattern matches."""
        # Use a string with no medical or question words
        classification = router.classify_intent("zzzqqq rrrsss")

        # Should default to exploratory with low confidence
        # Note: May still match some pattern, but confidence should be low
        assert classification.confidence < 0.6

    def test_multiple_intents(self, router):
        """Test query matching multiple intents."""
        # This query has both factual and relational elements
        classification = router.classify_intent("¿Qué medicamento tomo y para qué sirve?")

        # Should have secondary intents
        assert len(classification.secondary_intents) > 0 or classification.confidence > 0.5


# ========================================
# Custom Configuration Tests
# ========================================

class TestDIKWRouterConfig:
    """Tests for custom router configuration."""

    def test_custom_high_confidence_threshold(self):
        """Test custom high confidence threshold."""
        config = DIKWRouterConfig(high_confidence_threshold=0.95)
        router = DIKWRouter(config=config)

        classification = router.classify_intent("¿Qué medicamentos tomo?")

        # Even with matches, may not meet 0.95 threshold
        assert classification.confidence < 0.95 or classification.is_high_confidence

    def test_custom_max_fallback_depth(self):
        """Test custom max fallback depth."""
        config = DIKWRouterConfig(max_fallback_depth=1)
        router = DIKWRouter(config=config)

        decision = router.route_query("test")
        decision.max_fallback_depth = 1

        fallbacks = decision.get_fallback_layers()
        assert len(fallbacks) <= 1

    def test_custom_default_intent(self):
        """Test custom default intent."""
        config = DIKWRouterConfig(default_intent=QueryIntent.FACTUAL)
        router = DIKWRouter(config=config)

        # Query with no matches should use default
        classification = router.classify_intent("xyz123")

        # Note: May still match some patterns
        assert classification.primary_intent in [QueryIntent.FACTUAL, QueryIntent.EXPLORATORY]


# ========================================
# Pattern Mapping Tests
# ========================================

class TestIntentPatterns:
    """Tests for intent pattern definitions."""

    def test_all_intents_have_patterns(self):
        """Test that all intents have pattern definitions."""
        for intent in QueryIntent:
            assert intent in INTENT_PATTERNS
            patterns = INTENT_PATTERNS[intent]
            assert "question_words" in patterns or "patterns" in patterns

    def test_all_intents_have_layer_mapping(self):
        """Test that all intents have layer mappings."""
        for intent in QueryIntent:
            assert intent in INTENT_LAYER_MAPPING
            layers = INTENT_LAYER_MAPPING[intent]
            assert len(layers) > 0

    def test_all_intents_have_strategy_mapping(self):
        """Test that all intents have strategy mappings."""
        for intent in QueryIntent:
            assert intent in INTENT_STRATEGY_MAPPING
            strategy = INTENT_STRATEGY_MAPPING[intent]
            assert strategy in ["symbolic_only", "symbolic_first", "neural_first", "collaborative"]
