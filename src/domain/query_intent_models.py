"""Query Intent Domain Models for DIKW Routing.

Defines query intent types and their mappings to DIKW layers.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Set


class QueryIntent(str, Enum):
    """Types of query intents based on information needs."""

    FACTUAL = "factual"          # What/when/where facts → PERCEPTION/SEMANTIC
    RELATIONAL = "relational"    # How things relate → SEMANTIC
    INFERENTIAL = "inferential"  # Why/should I → REASONING
    ACTIONABLE = "actionable"    # What to do → APPLICATION
    EXPLORATORY = "exploratory"  # Open-ended exploration → All layers


class DIKWLayer(str, Enum):
    """DIKW Knowledge Pyramid layers."""

    PERCEPTION = "PERCEPTION"    # Raw observations, low confidence
    SEMANTIC = "SEMANTIC"        # Validated concepts, ontology-mapped
    REASONING = "REASONING"      # Inferred knowledge, rules applied
    APPLICATION = "APPLICATION"  # Cached results, user feedback


@dataclass
class IntentClassification:
    """Result of query intent classification.

    Attributes:
        primary_intent: Most likely intent type
        confidence: Confidence in the classification
        secondary_intents: Other possible intents with scores
        matched_patterns: Patterns that matched in the query
        recommended_layers: Ordered list of layers to query
        requires_inference: Whether LLM reasoning is needed
    """

    primary_intent: QueryIntent
    confidence: float
    secondary_intents: Dict[QueryIntent, float] = field(default_factory=dict)
    matched_patterns: List[str] = field(default_factory=list)
    recommended_layers: List[DIKWLayer] = field(default_factory=list)
    requires_inference: bool = False
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_high_confidence(self) -> bool:
        """Check if classification is high confidence."""
        return self.confidence >= 0.8

    @property
    def primary_layer(self) -> DIKWLayer:
        """Get the primary recommended layer."""
        return self.recommended_layers[0] if self.recommended_layers else DIKWLayer.SEMANTIC


@dataclass
class RoutingDecision:
    """Decision on how to route a query.

    Attributes:
        query_text: Original query
        intent: Classified intent
        layers: Ordered list of layers to query
        strategy: Query execution strategy
        fallback_enabled: Whether to try lower layers if empty
        max_fallback_depth: Maximum number of fallback layers
    """

    query_text: str
    intent: IntentClassification
    layers: List[DIKWLayer]
    strategy: str  # symbolic_only, symbolic_first, neural_first, collaborative
    fallback_enabled: bool = True
    max_fallback_depth: int = 2
    metadata: Dict = field(default_factory=dict)

    def get_fallback_layers(self) -> List[DIKWLayer]:
        """Get layers to try if primary layer returns no results."""
        if not self.fallback_enabled:
            return []

        # Define fallback order based on DIKW hierarchy
        fallback_order = {
            DIKWLayer.APPLICATION: [DIKWLayer.REASONING, DIKWLayer.SEMANTIC],
            DIKWLayer.REASONING: [DIKWLayer.SEMANTIC, DIKWLayer.PERCEPTION],
            DIKWLayer.SEMANTIC: [DIKWLayer.PERCEPTION],
            DIKWLayer.PERCEPTION: [],
        }

        primary = self.layers[0] if self.layers else DIKWLayer.SEMANTIC
        fallbacks = fallback_order.get(primary, [])

        return fallbacks[:self.max_fallback_depth]


# ========================================
# Intent Pattern Definitions
# ========================================

# Spanish and English patterns for intent classification
INTENT_PATTERNS: Dict[QueryIntent, Dict[str, List[str]]] = {
    QueryIntent.FACTUAL: {
        "question_words": [
            # Spanish
            "qué", "cuál", "cuáles", "cuándo", "cuánto", "cuántos",
            "dónde", "quién", "cómo se llama",
            # English
            "what", "which", "when", "how much", "how many",
            "where", "who", "what is called",
        ],
        "patterns": [
            # Spanish
            "qué es", "cuál es", "cuándo fue", "cuánto es",
            "dónde está", "quién es", "cómo se llama",
            "tengo", "tomo", "me recetaron",
            # English
            "what is", "which is", "when was", "how much is",
            "where is", "who is", "what is called",
            "i have", "i take", "was prescribed",
        ],
    },
    QueryIntent.RELATIONAL: {
        "question_words": [
            # Spanish
            "qué relación", "cómo se relaciona", "qué tiene que ver",
            "para qué sirve", "para qué es",
            # English
            "what relation", "how related", "what has to do",
            "what is for", "used for",
        ],
        "patterns": [
            # Spanish
            "medicamento para", "tratamiento para", "sirve para",
            "se usa para", "indicado para", "contraindicado",
            "interacción con", "efectos de", "causas de",
            # English
            "medication for", "treatment for", "used for",
            "is for", "indicated for", "contraindicated",
            "interaction with", "effects of", "causes of",
        ],
    },
    QueryIntent.INFERENTIAL: {
        "question_words": [
            # Spanish
            "por qué", "debería", "podría", "es normal",
            "es peligroso", "me preocupa", "significa que",
            # English
            "why", "should i", "could i", "is it normal",
            "is it dangerous", "worried about", "means that",
        ],
        "patterns": [
            # Spanish
            "debería preocuparme", "es normal que", "significa",
            "podría ser", "es grave", "es peligroso",
            "qué implica", "qué significa", "por qué tengo",
            # English
            "should i worry", "is it normal", "means",
            "could be", "is serious", "is dangerous",
            "what does it imply", "what does it mean", "why do i have",
        ],
    },
    QueryIntent.ACTIONABLE: {
        "question_words": [
            # Spanish
            "qué debo hacer", "qué puedo hacer", "cómo puedo",
            "qué me recomienda", "qué opciones tengo",
            # English
            "what should i do", "what can i do", "how can i",
            "what do you recommend", "what options",
        ],
        "patterns": [
            # Spanish
            "qué hacer", "cómo actuar", "qué pasos",
            "recomiendas", "sugieres", "aconsejas",
            "próximo paso", "siguiente paso",
            # English
            "what to do", "how to act", "what steps",
            "recommend", "suggest", "advise",
            "next step", "following step",
        ],
    },
    QueryIntent.EXPLORATORY: {
        "question_words": [
            # Spanish
            "cuéntame", "explícame", "háblame",
            "todo sobre", "información sobre",
            # English
            "tell me", "explain", "talk about",
            "everything about", "information about",
        ],
        "patterns": [
            # Spanish
            "cuéntame sobre", "explícame", "háblame de",
            "quiero saber", "información general",
            # English
            "tell me about", "explain to me", "talk about",
            "want to know", "general information",
        ],
    },
}


# Layer mappings by intent
INTENT_LAYER_MAPPING: Dict[QueryIntent, List[DIKWLayer]] = {
    QueryIntent.FACTUAL: [DIKWLayer.SEMANTIC, DIKWLayer.PERCEPTION],
    QueryIntent.RELATIONAL: [DIKWLayer.SEMANTIC, DIKWLayer.REASONING],
    QueryIntent.INFERENTIAL: [DIKWLayer.REASONING, DIKWLayer.SEMANTIC],
    QueryIntent.ACTIONABLE: [DIKWLayer.APPLICATION, DIKWLayer.REASONING],
    QueryIntent.EXPLORATORY: [DIKWLayer.SEMANTIC, DIKWLayer.REASONING, DIKWLayer.PERCEPTION],
}


# Strategy mappings by intent
INTENT_STRATEGY_MAPPING: Dict[QueryIntent, str] = {
    QueryIntent.FACTUAL: "symbolic_first",
    QueryIntent.RELATIONAL: "symbolic_first",
    QueryIntent.INFERENTIAL: "collaborative",
    QueryIntent.ACTIONABLE: "collaborative",
    QueryIntent.EXPLORATORY: "collaborative",
}
