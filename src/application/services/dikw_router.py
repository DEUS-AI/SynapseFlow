"""DIKW Router Service.

Routes queries to appropriate DIKW layers based on intent classification.
Implements intelligent fallback logic when higher layers return empty results.

Query Intent → Layer Mapping:
- FACTUAL: "¿cuándo?", "¿cuál?" → SEMANTIC/PERCEPTION
- RELATIONAL: "¿qué medicamentos para X?" → SEMANTIC
- INFERENTIAL: "¿debería preocuparme?" → REASONING
- ACTIONABLE: "¿qué debo hacer?" → APPLICATION
- EXPLORATORY: Open-ended → All layers

Fallback Logic:
- If REASONING empty but query is inferential → SEMANTIC + LLM reasoning
- If APPLICATION empty → REASONING with action synthesis
"""

import re
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple

from domain.query_intent_models import (
    QueryIntent,
    DIKWLayer,
    IntentClassification,
    RoutingDecision,
    INTENT_PATTERNS,
    INTENT_LAYER_MAPPING,
    INTENT_STRATEGY_MAPPING,
)

logger = logging.getLogger(__name__)


@dataclass
class DIKWRouterConfig:
    """Configuration for the DIKW Router."""

    # Minimum confidence to skip secondary intent analysis
    high_confidence_threshold: float = 0.85

    # Enable fallback to lower layers
    enable_fallback: bool = True

    # Maximum layers to try in fallback
    max_fallback_depth: int = 2

    # Default intent when no patterns match
    default_intent: QueryIntent = QueryIntent.EXPLORATORY

    # Enable LLM-based intent classification for low confidence
    enable_llm_classification: bool = False

    # Boost factor for exact pattern matches
    exact_match_boost: float = 0.2


class DIKWRouter:
    """Service for routing queries to appropriate DIKW layers.

    The router analyzes query text to determine user intent, then
    recommends which DIKW layers to query and in what order.
    It also provides fallback strategies when primary layers
    return insufficient results.

    Example:
        >>> router = DIKWRouter()
        >>> decision = router.route_query("¿Qué medicamentos tomo para la diabetes?")
        >>> print(decision.intent.primary_intent)  # RELATIONAL
        >>> print(decision.layers)  # [SEMANTIC, REASONING]
    """

    def __init__(self, config: Optional[DIKWRouterConfig] = None):
        """Initialize the DIKW Router.

        Args:
            config: Optional router configuration
        """
        self.config = config or DIKWRouterConfig()

        # Pre-compile patterns for efficiency
        self._compiled_patterns: Dict[QueryIntent, List[re.Pattern]] = {}
        self._compile_patterns()

        # Statistics
        self.stats = {
            "total_routed": 0,
            "by_intent": {intent.value: 0 for intent in QueryIntent},
            "fallbacks_triggered": 0,
            "low_confidence_classifications": 0,
        }

    def _compile_patterns(self) -> None:
        """Pre-compile regex patterns for each intent."""
        for intent, pattern_dict in INTENT_PATTERNS.items():
            compiled = []

            # Compile question words as word boundaries
            for word in pattern_dict.get("question_words", []):
                pattern = re.compile(
                    rf"\b{re.escape(word)}\b",
                    re.IGNORECASE | re.UNICODE
                )
                compiled.append(pattern)

            # Compile phrase patterns
            for phrase in pattern_dict.get("patterns", []):
                pattern = re.compile(
                    rf"{re.escape(phrase)}",
                    re.IGNORECASE | re.UNICODE
                )
                compiled.append(pattern)

            self._compiled_patterns[intent] = compiled

    def classify_intent(self, query: str) -> IntentClassification:
        """Classify the intent of a query.

        Analyzes the query text to determine the user's information need
        and recommends appropriate DIKW layers.

        Args:
            query: Natural language query text

        Returns:
            IntentClassification with intent type and confidence
        """
        query_lower = query.lower().strip()

        # Score each intent based on pattern matches
        intent_scores: Dict[QueryIntent, float] = {}
        matched_patterns: Dict[QueryIntent, List[str]] = {}

        for intent, patterns in self._compiled_patterns.items():
            score = 0.0
            matches = []

            for pattern in patterns:
                match = pattern.search(query_lower)
                if match:
                    # Weight by match length (longer = more specific)
                    match_weight = min(1.0, len(match.group()) / 20)
                    score += 0.3 + (match_weight * self.config.exact_match_boost)
                    matches.append(match.group())

            intent_scores[intent] = min(1.0, score)
            matched_patterns[intent] = matches

        # Determine primary intent
        if intent_scores:
            primary_intent = max(intent_scores, key=intent_scores.get)
            primary_score = intent_scores[primary_intent]
        else:
            primary_intent = self.config.default_intent
            primary_score = 0.3

        # Adjust confidence based on score distribution
        if primary_score > 0:
            # Check if there's a clear winner
            sorted_scores = sorted(intent_scores.values(), reverse=True)
            if len(sorted_scores) > 1 and sorted_scores[0] > 0:
                margin = sorted_scores[0] - sorted_scores[1]
                confidence = min(1.0, primary_score * (1 + margin))
            else:
                confidence = primary_score
        else:
            confidence = 0.3  # Default low confidence

        # Track low confidence classifications
        if confidence < self.config.high_confidence_threshold:
            self.stats["low_confidence_classifications"] += 1

        # Get secondary intents
        secondary_intents = {
            intent: score
            for intent, score in intent_scores.items()
            if intent != primary_intent and score > 0.2
        }

        # Determine if inference is required
        requires_inference = primary_intent in [
            QueryIntent.INFERENTIAL,
            QueryIntent.ACTIONABLE,
        ]

        # Get recommended layers
        recommended_layers = INTENT_LAYER_MAPPING.get(
            primary_intent,
            [DIKWLayer.SEMANTIC]
        )

        return IntentClassification(
            primary_intent=primary_intent,
            confidence=confidence,
            secondary_intents=secondary_intents,
            matched_patterns=matched_patterns.get(primary_intent, []),
            recommended_layers=list(recommended_layers),
            requires_inference=requires_inference,
        )

    def route_query(self, query: str) -> RoutingDecision:
        """Route a query to appropriate DIKW layers.

        Classifies intent and determines the optimal routing strategy
        including layer order and fallback options.

        Args:
            query: Natural language query text

        Returns:
            RoutingDecision with layers and strategy
        """
        self.stats["total_routed"] += 1

        # Classify intent
        intent = self.classify_intent(query)
        self.stats["by_intent"][intent.primary_intent.value] += 1

        # Get strategy for this intent
        strategy = INTENT_STRATEGY_MAPPING.get(
            intent.primary_intent,
            "collaborative"
        )

        # Build routing decision
        decision = RoutingDecision(
            query_text=query,
            intent=intent,
            layers=intent.recommended_layers,
            strategy=strategy,
            fallback_enabled=self.config.enable_fallback,
            max_fallback_depth=self.config.max_fallback_depth,
            metadata={
                "confidence": intent.confidence,
                "requires_inference": intent.requires_inference,
            },
        )

        logger.debug(
            f"Routed query: intent={intent.primary_intent.value}, "
            f"confidence={intent.confidence:.2f}, layers={[l.value for l in decision.layers]}"
        )

        return decision

    def should_fallback(
        self,
        decision: RoutingDecision,
        layer_results: Dict[DIKWLayer, List[Any]],
    ) -> Optional[DIKWLayer]:
        """Determine if fallback to a lower layer is needed.

        Checks if the current layer returned sufficient results,
        and if not, recommends the next layer to try.

        Args:
            decision: Original routing decision
            layer_results: Results from each queried layer

        Returns:
            Next layer to try, or None if no fallback needed
        """
        if not decision.fallback_enabled:
            return None

        # Check if any layer returned results
        has_results = any(
            len(results) > 0
            for results in layer_results.values()
        )

        if has_results:
            return None

        # Get fallback layers
        fallback_layers = decision.get_fallback_layers()

        # Find first fallback layer not yet tried
        tried_layers = set(layer_results.keys())
        for layer in fallback_layers:
            if layer not in tried_layers:
                self.stats["fallbacks_triggered"] += 1
                logger.debug(f"Triggering fallback to layer: {layer.value}")
                return layer

        return None

    def adjust_for_empty_reasoning(
        self,
        decision: RoutingDecision,
        semantic_results: List[Any],
    ) -> Tuple[str, Dict[str, Any]]:
        """Adjust strategy when REASONING layer is empty.

        If the query is inferential but REASONING returns nothing,
        use SEMANTIC results with LLM-based inference.

        Args:
            decision: Original routing decision
            semantic_results: Results from SEMANTIC layer

        Returns:
            Tuple of (adjusted_strategy, inference_context)
        """
        if not semantic_results:
            return "collaborative", {}

        # For inferential queries, synthesize reasoning from semantic data
        if decision.intent.primary_intent == QueryIntent.INFERENTIAL:
            return "neural_first", {
                "semantic_context": semantic_results,
                "instruction": "Analyze the semantic data to provide reasoning",
                "requires_medical_validation": True,
            }

        return decision.strategy, {}

    def adjust_for_empty_application(
        self,
        decision: RoutingDecision,
        reasoning_results: List[Any],
    ) -> Tuple[str, Dict[str, Any]]:
        """Adjust strategy when APPLICATION layer is empty.

        If the query is actionable but APPLICATION returns nothing,
        use REASONING results to synthesize action recommendations.

        Args:
            decision: Original routing decision
            reasoning_results: Results from REASONING layer

        Returns:
            Tuple of (adjusted_strategy, action_context)
        """
        if not reasoning_results:
            return "collaborative", {}

        # For actionable queries, synthesize actions from reasoning
        if decision.intent.primary_intent == QueryIntent.ACTIONABLE:
            return "collaborative", {
                "reasoning_context": reasoning_results,
                "instruction": "Synthesize actionable recommendations from reasoning",
                "requires_medical_review": True,
            }

        return decision.strategy, {}

    def get_query_context(
        self,
        decision: RoutingDecision,
    ) -> Dict[str, Any]:
        """Get additional context for query execution.

        Provides hints and constraints based on query intent
        to guide the query execution process.

        Args:
            decision: Routing decision

        Returns:
            Context dictionary for query execution
        """
        intent = decision.intent.primary_intent

        context = {
            "intent": intent.value,
            "strategy": decision.strategy,
            "primary_layer": decision.layers[0].value if decision.layers else "SEMANTIC",
            "requires_inference": decision.intent.requires_inference,
        }

        # Intent-specific context
        if intent == QueryIntent.FACTUAL:
            context.update({
                "prefer_exact_matches": True,
                "include_temporal_context": True,
                "max_results": 5,
            })

        elif intent == QueryIntent.RELATIONAL:
            context.update({
                "include_relationships": True,
                "relationship_depth": 2,
                "max_results": 10,
            })

        elif intent == QueryIntent.INFERENTIAL:
            context.update({
                "apply_reasoning_rules": True,
                "include_confidence_scores": True,
                "explain_inferences": True,
            })

        elif intent == QueryIntent.ACTIONABLE:
            context.update({
                "prioritize_recommendations": True,
                "include_alternatives": True,
                "require_medical_validation": True,
            })

        elif intent == QueryIntent.EXPLORATORY:
            context.update({
                "broad_search": True,
                "include_related_topics": True,
                "max_results": 20,
            })

        return context

    def get_statistics(self) -> Dict[str, Any]:
        """Get router statistics."""
        total = self.stats["total_routed"]
        return {
            **self.stats,
            "intent_distribution": {
                intent: count / total if total > 0 else 0
                for intent, count in self.stats["by_intent"].items()
            },
            "fallback_rate": (
                self.stats["fallbacks_triggered"] / total
                if total > 0 else 0
            ),
            "low_confidence_rate": (
                self.stats["low_confidence_classifications"] / total
                if total > 0 else 0
            ),
        }

    def explain_routing(self, query: str) -> Dict[str, Any]:
        """Explain how a query would be routed.

        Useful for debugging and understanding router behavior.

        Args:
            query: Query to analyze

        Returns:
            Detailed explanation of routing decision
        """
        decision = self.route_query(query)

        return {
            "query": query,
            "intent": {
                "primary": decision.intent.primary_intent.value,
                "confidence": round(decision.intent.confidence, 3),
                "secondary": {
                    k.value: round(v, 3)
                    for k, v in decision.intent.secondary_intents.items()
                },
                "matched_patterns": decision.intent.matched_patterns,
            },
            "routing": {
                "layers": [l.value for l in decision.layers],
                "strategy": decision.strategy,
                "fallback_enabled": decision.fallback_enabled,
                "fallback_layers": [l.value for l in decision.get_fallback_layers()],
            },
            "context": self.get_query_context(decision),
            "requires_inference": decision.intent.requires_inference,
        }
