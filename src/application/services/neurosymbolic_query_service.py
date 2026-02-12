"""Neurosymbolic Query Service.

Executes queries across knowledge graph layers using neurosymbolic reasoning:
- Traverses layers: APPLICATION → REASONING → SEMANTIC → PERCEPTION
- Selects strategy based on query type (symbolic-first, neural-first, collaborative)
- Aggregates confidence using CrossLayerConfidencePropagation
- Handles conflicts between layers

Query Types and Strategies:
- Drug interactions: Symbolic-only (safety-critical)
- Contraindications: Symbolic-only (no hallucination risk)
- Symptom interpretation: Neural-first (requires context)
- Treatment recommendation: Collaborative (hybrid knowledge)
"""

from typing import Dict, Any, List, Optional, Tuple, TYPE_CHECKING
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import logging

from domain.confidence_models import (
    Confidence,
    ConfidenceSource,
    KnowledgeLayer,
    CrossLayerConfidencePropagation,
    create_confidence,
    symbolic_confidence,
    neural_confidence,
)
from domain.event import KnowledgeEvent
from domain.roles import Role
from domain.temporal_models import TemporalQueryContext, TemporalWindow
from domain.query_intent_models import QueryIntent, DIKWLayer, RoutingDecision

if TYPE_CHECKING:
    from application.services.temporal_scoring import TemporalScoringService
    from application.services.dikw_router import DIKWRouter

logger = logging.getLogger(__name__)


class QueryStrategy(str, Enum):
    """Strategy for query execution."""
    SYMBOLIC_ONLY = "symbolic_only"     # Safety-critical, no LLM
    SYMBOLIC_FIRST = "symbolic_first"   # Rules first, LLM fills gaps
    NEURAL_FIRST = "neural_first"       # LLM first, rules validate
    COLLABORATIVE = "collaborative"     # Both in parallel, confidence weighting


class QueryType(str, Enum):
    """Types of queries with different strategy requirements."""
    DRUG_INTERACTION = "drug_interaction"
    CONTRAINDICATION = "contraindication"
    SYMPTOM_INTERPRETATION = "symptom_interpretation"
    TREATMENT_RECOMMENDATION = "treatment_recommendation"
    DISEASE_INFORMATION = "disease_information"
    DATA_CATALOG = "data_catalog"
    GENERAL = "general"


@dataclass
class LayerResult:
    """Result from querying a single layer."""
    layer: KnowledgeLayer
    entities: List[Dict[str, Any]]
    relationships: List[Dict[str, Any]]
    confidence: Confidence
    query_time_ms: float
    cache_hit: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class QueryTrace:
    """Trace of query execution across layers."""
    query_id: str
    query_text: str
    strategy: QueryStrategy
    layers_traversed: List[KnowledgeLayer]
    layer_results: List[LayerResult]
    final_confidence: Confidence
    conflicts_detected: List[Dict[str, Any]]
    total_time_ms: float
    timestamp: datetime = field(default_factory=datetime.now)


class NeurosymbolicQueryService:
    """
    Service for executing queries across knowledge graph layers.

    Implements neurosymbolic query execution following the 4-layer architecture:
    1. Check APPLICATION layer for cached results
    2. Query REASONING layer for inferred knowledge
    3. Validate against SEMANTIC layer (ontologies)
    4. Fall back to PERCEPTION layer for raw data

    Strategies are selected based on query type for safety and accuracy.
    """

    # Map query types to strategies
    QUERY_TYPE_STRATEGIES: Dict[QueryType, QueryStrategy] = {
        QueryType.DRUG_INTERACTION: QueryStrategy.SYMBOLIC_ONLY,
        QueryType.CONTRAINDICATION: QueryStrategy.SYMBOLIC_ONLY,
        QueryType.SYMPTOM_INTERPRETATION: QueryStrategy.NEURAL_FIRST,
        QueryType.TREATMENT_RECOMMENDATION: QueryStrategy.COLLABORATIVE,
        QueryType.DISEASE_INFORMATION: QueryStrategy.COLLABORATIVE,
        QueryType.DATA_CATALOG: QueryStrategy.SYMBOLIC_FIRST,
        QueryType.GENERAL: QueryStrategy.COLLABORATIVE,
    }

    # Keywords for detecting query type
    QUERY_TYPE_KEYWORDS: Dict[QueryType, List[str]] = {
        QueryType.DRUG_INTERACTION: [
            "interaction", "interact", "combine", "together with",
            "take with", "mix with", "drug-drug"
        ],
        QueryType.CONTRAINDICATION: [
            "contraindicated", "should not", "dangerous", "avoid",
            "allergic", "allergy", "react to"
        ],
        QueryType.SYMPTOM_INTERPRETATION: [
            "symptom", "feeling", "experiencing", "what does it mean",
            "is it normal", "why do i feel"
        ],
        QueryType.TREATMENT_RECOMMENDATION: [
            "treatment", "recommend", "option", "therapy", "should i",
            "what can i take", "best for"
        ],
        QueryType.DISEASE_INFORMATION: [
            "what is", "tell me about", "explain", "how does",
            "causes of", "symptoms of"
        ],
        QueryType.DATA_CATALOG: [
            "table", "column", "schema", "database", "data",
            "field", "dda", "catalog"
        ],
    }

    def __init__(
        self,
        backend: Any,  # Neo4jBackend or compatible
        reasoning_engine: Optional[Any] = None,
        confidence_propagator: Optional[CrossLayerConfidencePropagation] = None,
        temporal_scoring: Optional["TemporalScoringService"] = None,
        dikw_router: Optional["DIKWRouter"] = None,
        enable_caching: bool = True,
        cache_ttl_seconds: int = 300,
        enable_temporal_scoring: bool = True,
        enable_intent_routing: bool = True,
    ):
        """
        Initialize neurosymbolic query service.

        Args:
            backend: Knowledge graph backend with layer-aware methods
            reasoning_engine: ReasoningEngine for applying rules
            confidence_propagator: Cross-layer confidence handler
            temporal_scoring: Optional temporal scoring service
            dikw_router: Optional DIKW router for intent-based layer selection
            enable_caching: Whether to cache APPLICATION layer results
            cache_ttl_seconds: Cache time-to-live
            enable_temporal_scoring: Whether to apply temporal decay to results
            enable_intent_routing: Whether to use intent-based layer routing
        """
        self.backend = backend
        self.reasoning_engine = reasoning_engine
        self.confidence_propagator = confidence_propagator or CrossLayerConfidencePropagation()
        self.temporal_scoring = temporal_scoring
        self.dikw_router = dikw_router
        self.enable_caching = enable_caching
        self.cache_ttl = cache_ttl_seconds
        self.enable_temporal_scoring = enable_temporal_scoring
        self.enable_intent_routing = enable_intent_routing

        # Query cache (APPLICATION layer)
        self._query_cache: Dict[str, Tuple[Any, datetime]] = {}

        # Query statistics
        self.stats = {
            "total_queries": 0,
            "cache_hits": 0,
            "temporal_adjustments": 0,
            "intent_routed": 0,
            "by_strategy": {s.value: 0 for s in QueryStrategy},
            "by_layer": {l.value: 0 for l in KnowledgeLayer},
            "by_intent": {intent.value: 0 for intent in QueryIntent},
        }

        self._query_counter = 0

    async def execute_query(
        self,
        query_text: str,
        patient_context: Optional[Dict[str, Any]] = None,
        force_strategy: Optional[QueryStrategy] = None,
        trace_execution: bool = True,
    ) -> Tuple[Dict[str, Any], Optional[QueryTrace]]:
        """
        Execute a query across knowledge graph layers.

        Args:
            query_text: Natural language query
            patient_context: Optional patient context for medical queries
            force_strategy: Override automatic strategy selection
            trace_execution: Whether to return execution trace

        Returns:
            Tuple of (query results, optional trace)
        """
        import time
        start_time = time.time()

        self._query_counter += 1
        self.stats["total_queries"] += 1
        query_id = f"query_{self._query_counter:06d}"

        # Use intent-based routing if enabled and router available
        routing_decision = None
        if self.enable_intent_routing and self.dikw_router and not force_strategy:
            routing_decision = self.dikw_router.route_query(query_text)
            strategy = self._map_routing_to_strategy(routing_decision.strategy)
            self.stats["intent_routed"] += 1
            self.stats["by_intent"][routing_decision.intent.primary_intent.value] += 1
            logger.info(
                f"Query {query_id} routed by intent: {routing_decision.intent.primary_intent.value}, "
                f"confidence={routing_decision.intent.confidence:.2f}"
            )
        else:
            # Fall back to query type detection
            query_type = self._detect_query_type(query_text)
            strategy = force_strategy or self.QUERY_TYPE_STRATEGIES.get(
                query_type, QueryStrategy.COLLABORATIVE
            )

        self.stats["by_strategy"][strategy.value] += 1

        logger.info(f"Executing query {query_id}: strategy={strategy.value}")

        # Initialize trace
        trace = QueryTrace(
            query_id=query_id,
            query_text=query_text,
            strategy=strategy,
            layers_traversed=[],
            layer_results=[],
            final_confidence=create_confidence(0.0, ConfidenceSource.HEURISTIC, "initial"),
            conflicts_detected=[],
            total_time_ms=0.0,
        )

        # Execute based on strategy
        if strategy == QueryStrategy.SYMBOLIC_ONLY:
            result = await self._execute_symbolic_only(query_text, patient_context, trace)
        elif strategy == QueryStrategy.SYMBOLIC_FIRST:
            result = await self._execute_symbolic_first(query_text, patient_context, trace)
        elif strategy == QueryStrategy.NEURAL_FIRST:
            result = await self._execute_neural_first(query_text, patient_context, trace)
        else:  # COLLABORATIVE
            result = await self._execute_collaborative(query_text, patient_context, trace)

        # Calculate final confidence
        if trace.layer_results:
            layer_confidences = {
                r.layer: r.confidence for r in trace.layer_results
            }
            trace.final_confidence = self.confidence_propagator.propagate_cross_layer(
                layer_confidences
            )

        # Apply temporal scoring to adjust entity relevance
        temporal_context = None
        if self.enable_temporal_scoring and self.temporal_scoring:
            temporal_context = self.temporal_scoring.parse_temporal_query(query_text)
            result = self._apply_temporal_scoring(result, temporal_context)
            self.stats["temporal_adjustments"] += 1

        # Calculate total time
        total_time = (time.time() - start_time) * 1000
        trace.total_time_ms = total_time

        # Add trace info to result
        result["query_id"] = query_id
        result["strategy"] = strategy.value
        result["layers_traversed"] = [l.value for l in trace.layers_traversed]
        result["confidence"] = trace.final_confidence.score
        result["execution_time_ms"] = total_time

        # Add temporal context info if available
        if temporal_context:
            result["temporal_context"] = {
                "window": temporal_context.window.value,
                "duration_hours": temporal_context.duration_hours,
                "confidence": temporal_context.confidence,
            }

        # Add routing decision info if available
        if routing_decision:
            result["routing"] = {
                "intent": routing_decision.intent.primary_intent.value,
                "intent_confidence": routing_decision.intent.confidence,
                "recommended_layers": [l.value for l in routing_decision.layers],
                "matched_patterns": routing_decision.intent.matched_patterns[:3],
                "requires_inference": routing_decision.intent.requires_inference,
            }

        # Extract entity IDs for feedback tracking
        entity_ids = []
        for entity in result.get("entities", []):
            eid = entity.get("id") or entity.get("entity_id")
            if eid:
                entity_ids.append(str(eid))
        result["entity_ids"] = entity_ids

        logger.info(
            f"Query {query_id} completed: confidence={trace.final_confidence.score:.2f}, "
            f"layers={[l.value for l in trace.layers_traversed]}, time={total_time:.0f}ms, "
            f"entities={len(entity_ids)}"
        )

        return result, trace if trace_execution else None

    def _detect_query_type(self, query_text: str) -> QueryType:
        """Detect query type from text."""
        query_lower = query_text.lower()

        # Check each query type's keywords
        for query_type, keywords in self.QUERY_TYPE_KEYWORDS.items():
            if any(kw in query_lower for kw in keywords):
                return query_type

        return QueryType.GENERAL

    def _map_routing_to_strategy(self, routing_strategy: str) -> QueryStrategy:
        """Map DIKW router strategy to QueryStrategy enum."""
        strategy_map = {
            "symbolic_only": QueryStrategy.SYMBOLIC_ONLY,
            "symbolic_first": QueryStrategy.SYMBOLIC_FIRST,
            "neural_first": QueryStrategy.NEURAL_FIRST,
            "collaborative": QueryStrategy.COLLABORATIVE,
        }
        return strategy_map.get(routing_strategy, QueryStrategy.COLLABORATIVE)

    async def _execute_symbolic_only(
        self,
        query_text: str,
        patient_context: Optional[Dict[str, Any]],
        trace: QueryTrace,
    ) -> Dict[str, Any]:
        """
        Execute query using symbolic rules only (no LLM).

        Used for safety-critical queries like drug interactions and contraindications.
        """
        result = {
            "entities": [],
            "relationships": [],
            "warnings": [],
            "inferences": [],
        }

        # Layer order: SEMANTIC first (ontologies), then REASONING (rules)
        layers_to_query = [KnowledgeLayer.SEMANTIC, KnowledgeLayer.REASONING]

        for layer in layers_to_query:
            layer_result = await self._query_layer(query_text, layer, patient_context)
            trace.layers_traversed.append(layer)
            trace.layer_results.append(layer_result)
            self.stats["by_layer"][layer.value] += 1

            result["entities"].extend(layer_result.entities)
            result["relationships"].extend(layer_result.relationships)

        # Apply symbolic reasoning if engine available
        if self.reasoning_engine:
            event = KnowledgeEvent(
                action="chat_query",
                data={
                    "question": query_text,
                    "medical_entities": result["entities"],
                    "patient_context": patient_context,
                },
                role=Role.SYSTEM_ADMIN,
            )

            reasoning_result = await self.reasoning_engine.apply_reasoning(
                event, strategy="symbolic_first"
            )
            result["inferences"].extend(reasoning_result.get("inferences", []))
            result["warnings"].extend(reasoning_result.get("warnings", []))

        # Add safety disclaimer for symbolic-only queries
        result["disclaimer"] = (
            "This information is based on validated medical knowledge. "
            "Always consult with a healthcare provider for medical decisions."
        )

        return result

    async def _execute_symbolic_first(
        self,
        query_text: str,
        patient_context: Optional[Dict[str, Any]],
        trace: QueryTrace,
    ) -> Dict[str, Any]:
        """
        Execute with symbolic rules first, LLM fills gaps.

        Used for data catalog queries and structured information retrieval.
        """
        result = {
            "entities": [],
            "relationships": [],
            "warnings": [],
            "inferences": [],
        }

        # Check APPLICATION cache first
        if self.enable_caching:
            cache_key = self._get_cache_key(query_text)
            cached = self._get_from_cache(cache_key)
            if cached:
                trace.layers_traversed.append(KnowledgeLayer.APPLICATION)
                trace.layer_results.append(LayerResult(
                    layer=KnowledgeLayer.APPLICATION,
                    entities=cached.get("entities", []),
                    relationships=cached.get("relationships", []),
                    confidence=symbolic_confidence(0.95, "cache"),
                    query_time_ms=0.1,
                    cache_hit=True,
                ))
                self.stats["cache_hits"] += 1
                return cached

        # Query layers in order: SEMANTIC → REASONING → PERCEPTION
        layers_to_query = [
            KnowledgeLayer.SEMANTIC,
            KnowledgeLayer.REASONING,
            KnowledgeLayer.PERCEPTION,
        ]

        for layer in layers_to_query:
            layer_result = await self._query_layer(query_text, layer, patient_context)
            trace.layers_traversed.append(layer)
            trace.layer_results.append(layer_result)
            self.stats["by_layer"][layer.value] += 1

            result["entities"].extend(layer_result.entities)
            result["relationships"].extend(layer_result.relationships)

            # If we have enough results from higher layers, stop
            if len(result["entities"]) >= 5 and layer != KnowledgeLayer.PERCEPTION:
                break

        # Apply reasoning
        if self.reasoning_engine:
            event = KnowledgeEvent(
                action="chat_query",
                data={
                    "question": query_text,
                    "medical_entities": result["entities"],
                    "patient_context": patient_context,
                },
                role=Role.SYSTEM_ADMIN,
            )

            reasoning_result = await self.reasoning_engine.apply_reasoning(
                event, strategy="symbolic_first"
            )
            result["inferences"].extend(reasoning_result.get("inferences", []))
            result["warnings"].extend(reasoning_result.get("warnings", []))

        # Cache result
        if self.enable_caching:
            self._add_to_cache(cache_key, result)

        return result

    async def _execute_neural_first(
        self,
        query_text: str,
        patient_context: Optional[Dict[str, Any]],
        trace: QueryTrace,
    ) -> Dict[str, Any]:
        """
        Execute with LLM first, symbolic rules validate.

        Used for symptom interpretation where context is important.
        """
        result = {
            "entities": [],
            "relationships": [],
            "warnings": [],
            "inferences": [],
        }

        # Query PERCEPTION layer first for raw context
        perception_result = await self._query_layer(
            query_text, KnowledgeLayer.PERCEPTION, patient_context
        )
        trace.layers_traversed.append(KnowledgeLayer.PERCEPTION)
        trace.layer_results.append(perception_result)
        self.stats["by_layer"][KnowledgeLayer.PERCEPTION.value] += 1

        result["entities"].extend(perception_result.entities)
        result["relationships"].extend(perception_result.relationships)

        # Apply neural reasoning first
        if self.reasoning_engine:
            event = KnowledgeEvent(
                action="chat_query",
                data={
                    "question": query_text,
                    "medical_entities": result["entities"],
                    "patient_context": patient_context,
                },
                role=Role.SYSTEM_ADMIN,
            )

            reasoning_result = await self.reasoning_engine.apply_reasoning(
                event, strategy="neural_first"
            )
            result["inferences"].extend(reasoning_result.get("inferences", []))
            result["warnings"].extend(reasoning_result.get("warnings", []))

        # Validate against SEMANTIC layer
        semantic_result = await self._query_layer(
            query_text, KnowledgeLayer.SEMANTIC, patient_context
        )
        trace.layers_traversed.append(KnowledgeLayer.SEMANTIC)
        trace.layer_results.append(semantic_result)
        self.stats["by_layer"][KnowledgeLayer.SEMANTIC.value] += 1

        # Check for conflicts between neural inferences and semantic validation
        conflicts = self._detect_conflicts(
            result["inferences"],
            semantic_result.entities,
        )
        trace.conflicts_detected.extend(conflicts)

        if conflicts:
            result["warnings"].append(
                "Some interpretations may need verification against medical knowledge."
            )

        return result

    async def _execute_collaborative(
        self,
        query_text: str,
        patient_context: Optional[Dict[str, Any]],
        trace: QueryTrace,
    ) -> Dict[str, Any]:
        """
        Execute with both symbolic and neural in parallel, confidence weighting.

        Used for treatment recommendations and general queries.
        """
        result = {
            "entities": [],
            "relationships": [],
            "warnings": [],
            "inferences": [],
        }

        # Check APPLICATION cache
        if self.enable_caching:
            cache_key = self._get_cache_key(query_text)
            cached = self._get_from_cache(cache_key)
            if cached:
                trace.layers_traversed.append(KnowledgeLayer.APPLICATION)
                trace.layer_results.append(LayerResult(
                    layer=KnowledgeLayer.APPLICATION,
                    entities=cached.get("entities", []),
                    relationships=cached.get("relationships", []),
                    confidence=symbolic_confidence(0.95, "cache"),
                    query_time_ms=0.1,
                    cache_hit=True,
                ))
                self.stats["cache_hits"] += 1
                return cached

        # Query all layers
        all_layers = [
            KnowledgeLayer.REASONING,
            KnowledgeLayer.SEMANTIC,
            KnowledgeLayer.PERCEPTION,
        ]

        for layer in all_layers:
            layer_result = await self._query_layer(query_text, layer, patient_context)
            trace.layers_traversed.append(layer)
            trace.layer_results.append(layer_result)
            self.stats["by_layer"][layer.value] += 1

            result["entities"].extend(layer_result.entities)
            result["relationships"].extend(layer_result.relationships)

        # Apply collaborative reasoning
        if self.reasoning_engine:
            event = KnowledgeEvent(
                action="chat_query",
                data={
                    "question": query_text,
                    "medical_entities": result["entities"],
                    "patient_context": patient_context,
                },
                role=Role.SYSTEM_ADMIN,
            )

            reasoning_result = await self.reasoning_engine.apply_reasoning(
                event, strategy="collaborative"
            )
            result["inferences"].extend(reasoning_result.get("inferences", []))
            result["warnings"].extend(reasoning_result.get("warnings", []))

        # Detect and resolve conflicts
        conflicts = self._detect_layer_conflicts(trace.layer_results)
        trace.conflicts_detected.extend(conflicts)

        for conflict in conflicts:
            resolution, reason = self.confidence_propagator.resolve_conflict(
                conflict["layer1"],
                conflict["confidence1"],
                conflict["layer2"],
                conflict["confidence2"],
            )
            conflict["resolution"] = reason
            conflict["resolved_confidence"] = resolution.score

        # Cache result
        if self.enable_caching:
            self._add_to_cache(cache_key, result)

        return result

    async def _query_layer(
        self,
        query_text: str,
        layer: KnowledgeLayer,
        patient_context: Optional[Dict[str, Any]],
    ) -> LayerResult:
        """Query a specific knowledge layer."""
        import time
        start = time.time()

        entities = []
        relationships = []

        # Extract key terms from query for searching
        search_terms = self._extract_search_terms(query_text)

        try:
            # Query backend for entities in this layer
            if hasattr(self.backend, "list_entities_by_layer"):
                layer_entities = await self.backend.list_entities_by_layer(
                    layer=layer,  # Pass enum directly, not layer.value
                    limit=20,
                )
                # Filter by search terms
                for entity in layer_entities:
                    entity_name = entity.get("name", "").lower()
                    if any(term in entity_name for term in search_terms):
                        entities.append(entity)

            # Query relationships if we have entities
            if entities and hasattr(self.backend, "list_relationships"):
                entity_ids = [e.get("id") for e in entities if e.get("id")]
                for eid in entity_ids[:5]:  # Limit to first 5 for performance
                    try:
                        rels = await self.backend.list_relationships(source_id=eid)
                        relationships.extend(rels[:10])  # Limit relationships
                    except Exception:
                        pass

        except Exception as e:
            logger.warning(f"Error querying layer {layer.value}: {e}")

        # Calculate confidence based on layer and result quality
        layer_weight = self.confidence_propagator.get_layer_weight(layer)
        result_confidence = min(0.5 + (len(entities) * 0.1), 1.0) * layer_weight

        query_time = (time.time() - start) * 1000

        return LayerResult(
            layer=layer,
            entities=entities,
            relationships=relationships,
            confidence=create_confidence(
                result_confidence,
                ConfidenceSource.HYBRID,
                f"layer_query_{layer.value}"
            ),
            query_time_ms=query_time,
            metadata={"search_terms": search_terms},
        )

    def _extract_search_terms(self, query_text: str) -> List[str]:
        """Extract key search terms from query."""
        # Simple extraction - remove common words
        stop_words = {
            "what", "is", "the", "a", "an", "how", "does", "can", "i",
            "me", "my", "about", "tell", "for", "with", "to", "of",
            "and", "or", "in", "on", "at", "this", "that"
        }

        words = query_text.lower().split()
        terms = [w.strip("?.,!") for w in words if w.lower() not in stop_words and len(w) > 2]

        return terms[:10]  # Limit to 10 terms

    def _apply_temporal_scoring(
        self,
        result: Dict[str, Any],
        temporal_context: TemporalQueryContext,
    ) -> Dict[str, Any]:
        """Apply temporal scoring to query results.

        Adjusts entity relevance based on temporal decay and query context.
        Symptoms mentioned "ahora" (now) should prioritize recent observations,
        while historical queries should include older data.

        Args:
            result: Query result with entities and relationships
            temporal_context: Parsed temporal context from query

        Returns:
            Result with temporal scores added to entities
        """
        if not self.temporal_scoring or not result.get("entities"):
            return result

        # Apply temporal scoring to entities
        entities = result.get("entities", [])
        scored_entities = self.temporal_scoring.adjust_query_results(
            entities, temporal_context
        )

        # Update result with scored entities
        result["entities"] = scored_entities

        # Add temporal scoring summary
        if scored_entities:
            avg_score = sum(e.get("temporal_score", 0) for e in scored_entities) / len(scored_entities)
            result["temporal_summary"] = {
                "entities_scored": len(scored_entities),
                "average_temporal_score": round(avg_score, 3),
                "temporal_window": temporal_context.window.value,
            }

        return result

    def _detect_conflicts(
        self,
        inferences: List[Dict[str, Any]],
        validation_entities: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Detect conflicts between inferences and validation data."""
        conflicts = []

        # Simple conflict detection based on contradicting confidence
        for inference in inferences:
            inf_conf = inference.get("confidence", 0.5)
            inf_type = inference.get("type", "")

            # Check if any validation entity contradicts
            for entity in validation_entities:
                entity_conf = entity.get("confidence", 0.5)

                if abs(inf_conf - entity_conf) > 0.3:
                    conflicts.append({
                        "type": "confidence_gap",
                        "inference": inf_type,
                        "entity": entity.get("name", ""),
                        "inference_confidence": inf_conf,
                        "entity_confidence": entity_conf,
                    })

        return conflicts

    def _detect_layer_conflicts(
        self,
        layer_results: List[LayerResult],
    ) -> List[Dict[str, Any]]:
        """Detect conflicts between layer results."""
        conflicts = []

        for i, result1 in enumerate(layer_results):
            for result2 in layer_results[i+1:]:
                # Check for significant confidence gaps
                conf_gap = abs(result1.confidence.score - result2.confidence.score)

                if conf_gap > 0.3:
                    conflicts.append({
                        "layer1": result1.layer,
                        "layer2": result2.layer,
                        "confidence1": result1.confidence,
                        "confidence2": result2.confidence,
                        "gap": conf_gap,
                    })

        return conflicts

    def _get_cache_key(self, query_text: str) -> str:
        """Generate cache key for query."""
        import hashlib
        return hashlib.md5(query_text.lower().encode()).hexdigest()

    def _get_from_cache(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Get result from cache if not expired."""
        if cache_key in self._query_cache:
            result, timestamp = self._query_cache[cache_key]
            age = (datetime.now() - timestamp).total_seconds()
            if age < self.cache_ttl:
                return result
            else:
                del self._query_cache[cache_key]
        return None

    def _add_to_cache(self, cache_key: str, result: Dict[str, Any]) -> None:
        """Add result to cache."""
        self._query_cache[cache_key] = (result, datetime.now())

        # Limit cache size
        if len(self._query_cache) > 1000:
            # Remove oldest entries
            oldest_keys = sorted(
                self._query_cache.keys(),
                key=lambda k: self._query_cache[k][1]
            )[:100]
            for key in oldest_keys:
                del self._query_cache[key]

    def get_statistics(self) -> Dict[str, Any]:
        """Get query statistics."""
        stats = {
            **self.stats,
            "cache_size": len(self._query_cache),
            "cache_hit_rate": (
                self.stats["cache_hits"] / self.stats["total_queries"]
                if self.stats["total_queries"] > 0 else 0
            ),
            "temporal_scoring_enabled": self.enable_temporal_scoring,
            "intent_routing_enabled": self.enable_intent_routing,
        }

        # Add temporal scoring stats if available
        if self.temporal_scoring:
            stats["temporal_scoring_config"] = self.temporal_scoring.get_stats()

        # Add DIKW router stats if available
        if self.dikw_router:
            stats["dikw_router_stats"] = self.dikw_router.get_statistics()

        return stats

    def clear_cache(self) -> None:
        """Clear the query cache."""
        self._query_cache.clear()
        logger.info("Query cache cleared")
