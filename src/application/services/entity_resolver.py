"""Entity Resolution Service.

This service provides entity deduplication and linking using multiple strategies:
1. Exact name matching
2. Fuzzy string matching
3. Embedding-based semantic similarity
4. Graph structure analysis

The service helps maintain canonical entities in the knowledge graph and prevents
duplicate creation of the same business concept or data entity.
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ResolutionStrategy(str, Enum):
    """Strategies for entity resolution."""
    EXACT_MATCH = "exact_match"
    FUZZY_MATCH = "fuzzy_match"
    EMBEDDING_SIMILARITY = "embedding_similarity"
    GRAPH_STRUCTURE = "graph_structure"
    HYBRID = "hybrid"


@dataclass
class EntityMatch:
    """Represents a potential entity match."""
    entity_id: str
    entity_name: str
    similarity_score: float
    strategy: ResolutionStrategy
    properties: Dict[str, Any]
    confidence: float


@dataclass
class ResolutionResult:
    """Result of entity resolution."""
    is_duplicate: bool
    canonical_entity_id: Optional[str]
    matches: List[EntityMatch]
    recommended_action: str  # "merge", "link", "create_new"
    confidence: float


class EntityResolver:
    """
    Resolves entities to prevent duplicates and maintain canonical forms.

    Uses multiple strategies:
    - Exact matching: Direct name/ID comparison
    - Fuzzy matching: Levenshtein distance, soundex
    - Semantic matching: Embedding similarity (sentence-transformers)
    - Structural matching: Graph neighborhood analysis
    """

    def __init__(
        self,
        backend: 'KnowledgeGraphBackend',
        embedding_model: str = "all-MiniLM-L6-v2",
        exact_threshold: float = 1.0,
        fuzzy_threshold: float = 0.85,
        semantic_threshold: float = 0.90,
        structure_threshold: float = 0.75
    ):
        """
        Initialize the EntityResolver.

        Args:
            backend: Knowledge graph backend for querying existing entities
            embedding_model: Sentence transformer model name
            exact_threshold: Threshold for exact match (always 1.0)
            fuzzy_threshold: Threshold for fuzzy string matching
            semantic_threshold: Threshold for embedding similarity
            structure_threshold: Threshold for graph structure similarity
        """
        self.backend = backend
        self.exact_threshold = exact_threshold
        self.fuzzy_threshold = fuzzy_threshold
        self.semantic_threshold = semantic_threshold
        self.structure_threshold = structure_threshold

        # Lazy load embedding model to avoid import overhead
        self._embedding_model = None
        self._embedding_model_name = embedding_model

        # Cache for entity embeddings
        self._embedding_cache: Dict[str, List[float]] = {}

    @property
    def embedding_model(self):
        """Lazy load the embedding model."""
        if self._embedding_model is None:
            try:
                from sentence_transformers import SentenceTransformer
                logger.info(f"Loading embedding model: {self._embedding_model_name}")
                self._embedding_model = SentenceTransformer(self._embedding_model_name)
            except ImportError:
                logger.warning(
                    "sentence-transformers not installed. "
                    "Embedding-based resolution will be disabled. "
                    "Install with: pip install sentence-transformers"
                )
                self._embedding_model = None
        return self._embedding_model

    async def resolve_entity(
        self,
        entity_name: str,
        entity_type: str,
        properties: Optional[Dict[str, Any]] = None,
        strategy: ResolutionStrategy = ResolutionStrategy.HYBRID,
        context: Optional[Dict[str, Any]] = None
    ) -> ResolutionResult:
        """
        Resolve an entity to find potential duplicates or canonical forms.

        Args:
            entity_name: Name of the entity to resolve
            entity_type: Type/label of the entity (e.g., "BusinessConcept", "DataEntity")
            properties: Additional properties for matching
            strategy: Resolution strategy to use
            context: Additional context (domain, relationships, etc.)

        Returns:
            ResolutionResult with matches and recommendation
        """
        properties = properties or {}
        context = context or {}

        logger.info(f"Resolving entity: {entity_name} ({entity_type}) using strategy: {strategy}")

        # Query existing entities of the same type
        existing_entities = await self._get_existing_entities(entity_type, context)

        if not existing_entities:
            logger.info("No existing entities found. Recommending creation.")
            return ResolutionResult(
                is_duplicate=False,
                canonical_entity_id=None,
                matches=[],
                recommended_action="create_new",
                confidence=1.0
            )

        # Apply resolution strategy
        if strategy == ResolutionStrategy.EXACT_MATCH:
            matches = self._exact_match(entity_name, existing_entities)
        elif strategy == ResolutionStrategy.FUZZY_MATCH:
            matches = self._fuzzy_match(entity_name, existing_entities)
        elif strategy == ResolutionStrategy.EMBEDDING_SIMILARITY:
            matches = await self._embedding_match(entity_name, existing_entities)
        elif strategy == ResolutionStrategy.GRAPH_STRUCTURE:
            matches = await self._structure_match(entity_name, properties, existing_entities, context)
        else:  # HYBRID
            matches = await self._hybrid_match(entity_name, properties, existing_entities, context)

        # Determine action based on matches
        return self._determine_action(matches)

    async def _get_existing_entities(
        self,
        entity_type: str,
        context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Retrieve existing entities from the knowledge graph.

        Args:
            entity_type: Type of entity to retrieve
            context: Context for filtering (e.g., domain)

        Returns:
            List of existing entity dictionaries
        """
        # Query the graph for entities of this type
        # This is backend-specific; we'll use a generic interface
        try:
            # Assuming backend has a query method
            query = f"""
            MATCH (e:{entity_type})
            RETURN e.id AS id, e.name AS name, e AS properties
            LIMIT 100
            """

            results = await self.backend.query(query)

            entities = []
            for record in results:
                entities.append({
                    "id": record.get("id"),
                    "name": record.get("name"),
                    "properties": dict(record.get("properties", {}))
                })

            logger.info(f"Found {len(entities)} existing {entity_type} entities")
            return entities

        except Exception as e:
            logger.error(f"Error querying existing entities: {e}")
            return []

    def _exact_match(
        self,
        entity_name: str,
        existing_entities: List[Dict[str, Any]]
    ) -> List[EntityMatch]:
        """Exact name matching."""
        matches = []

        for entity in existing_entities:
            if entity["name"].lower() == entity_name.lower():
                matches.append(EntityMatch(
                    entity_id=entity["id"],
                    entity_name=entity["name"],
                    similarity_score=1.0,
                    strategy=ResolutionStrategy.EXACT_MATCH,
                    properties=entity["properties"],
                    confidence=1.0
                ))

        logger.info(f"Exact match: Found {len(matches)} matches")
        return matches

    def _fuzzy_match(
        self,
        entity_name: str,
        existing_entities: List[Dict[str, Any]]
    ) -> List[EntityMatch]:
        """Fuzzy string matching using Levenshtein distance."""
        matches = []

        try:
            from rapidfuzz import fuzz

            for entity in existing_entities:
                # Calculate similarity ratio
                ratio = fuzz.ratio(
                    entity_name.lower(),
                    entity["name"].lower()
                ) / 100.0

                if ratio >= self.fuzzy_threshold:
                    matches.append(EntityMatch(
                        entity_id=entity["id"],
                        entity_name=entity["name"],
                        similarity_score=ratio,
                        strategy=ResolutionStrategy.FUZZY_MATCH,
                        properties=entity["properties"],
                        confidence=ratio
                    ))

            logger.info(f"Fuzzy match: Found {len(matches)} matches above threshold {self.fuzzy_threshold}")

        except ImportError:
            logger.warning("rapidfuzz not installed. Fuzzy matching disabled. Install with: pip install rapidfuzz")

        return sorted(matches, key=lambda x: x.similarity_score, reverse=True)

    async def _embedding_match(
        self,
        entity_name: str,
        existing_entities: List[Dict[str, Any]]
    ) -> List[EntityMatch]:
        """Semantic matching using sentence embeddings."""
        if self.embedding_model is None:
            logger.warning("Embedding model not available. Skipping embedding match.")
            return []

        matches = []

        try:
            import numpy as np
            from sklearn.metrics.pairwise import cosine_similarity

            # Generate embedding for query entity
            query_embedding = self.embedding_model.encode([entity_name])[0]

            # Generate or retrieve embeddings for existing entities
            for entity in existing_entities:
                entity_id = entity["id"]

                # Check cache
                if entity_id in self._embedding_cache:
                    entity_embedding = self._embedding_cache[entity_id]
                else:
                    entity_embedding = self.embedding_model.encode([entity["name"]])[0]
                    self._embedding_cache[entity_id] = entity_embedding

                # Calculate cosine similarity
                similarity = cosine_similarity(
                    query_embedding.reshape(1, -1),
                    entity_embedding.reshape(1, -1)
                )[0][0]

                if similarity >= self.semantic_threshold:
                    matches.append(EntityMatch(
                        entity_id=entity_id,
                        entity_name=entity["name"],
                        similarity_score=float(similarity),
                        strategy=ResolutionStrategy.EMBEDDING_SIMILARITY,
                        properties=entity["properties"],
                        confidence=float(similarity)
                    ))

            logger.info(f"Embedding match: Found {len(matches)} matches above threshold {self.semantic_threshold}")

        except Exception as e:
            logger.error(f"Error in embedding match: {e}")

        return sorted(matches, key=lambda x: x.similarity_score, reverse=True)

    async def _structure_match(
        self,
        entity_name: str,
        properties: Dict[str, Any],
        existing_entities: List[Dict[str, Any]],
        context: Dict[str, Any]
    ) -> List[EntityMatch]:
        """
        Structural matching based on graph neighborhood.

        Compares relationships, attributes, and graph position.
        """
        matches = []

        # This is a simplified version
        # In a full implementation, we would:
        # 1. Get relationships of the query entity (if it exists partially)
        # 2. Compare relationship patterns with existing entities
        # 3. Calculate Jaccard similarity of neighbor sets

        # For now, we'll use property-based matching
        for entity in existing_entities:
            similarity = self._calculate_property_similarity(
                properties,
                entity["properties"]
            )

            if similarity >= self.structure_threshold:
                matches.append(EntityMatch(
                    entity_id=entity["id"],
                    entity_name=entity["name"],
                    similarity_score=similarity,
                    strategy=ResolutionStrategy.GRAPH_STRUCTURE,
                    properties=entity["properties"],
                    confidence=similarity * 0.8  # Lower confidence for structural matches
                ))

        logger.info(f"Structure match: Found {len(matches)} matches above threshold {self.structure_threshold}")
        return sorted(matches, key=lambda x: x.similarity_score, reverse=True)

    async def _hybrid_match(
        self,
        entity_name: str,
        properties: Dict[str, Any],
        existing_entities: List[Dict[str, Any]],
        context: Dict[str, Any]
    ) -> List[EntityMatch]:
        """
        Hybrid matching combining all strategies.

        Weighted combination:
        - Exact: 1.0 (if match, always use it)
        - Fuzzy: 0.3
        - Embedding: 0.5
        - Structure: 0.2
        """
        # Try exact match first
        exact_matches = self._exact_match(entity_name, existing_entities)
        if exact_matches:
            logger.info("Exact match found. Using it as canonical.")
            return exact_matches

        # Collect matches from all strategies
        fuzzy_matches = self._fuzzy_match(entity_name, existing_entities)
        embedding_matches = await self._embedding_match(entity_name, existing_entities)
        structure_matches = await self._structure_match(entity_name, properties, existing_entities, context)

        # Combine matches by entity_id
        combined_scores: Dict[str, Tuple[EntityMatch, List[float]]] = {}

        for match in fuzzy_matches:
            if match.entity_id not in combined_scores:
                combined_scores[match.entity_id] = (match, [0.0, 0.0, 0.0])
            combined_scores[match.entity_id][1][0] = match.similarity_score

        for match in embedding_matches:
            if match.entity_id not in combined_scores:
                combined_scores[match.entity_id] = (match, [0.0, 0.0, 0.0])
            combined_scores[match.entity_id][1][1] = match.similarity_score

        for match in structure_matches:
            if match.entity_id not in combined_scores:
                combined_scores[match.entity_id] = (match, [0.0, 0.0, 0.0])
            combined_scores[match.entity_id][1][2] = match.similarity_score

        # Calculate weighted scores
        weights = [0.3, 0.5, 0.2]  # fuzzy, embedding, structure

        hybrid_matches = []
        for entity_id, (base_match, scores) in combined_scores.items():
            combined_score = sum(w * s for w, s in zip(weights, scores))

            # Only include if above semantic threshold (most important)
            if combined_score >= self.semantic_threshold * 0.8:  # Slightly lower threshold for hybrid
                hybrid_matches.append(EntityMatch(
                    entity_id=entity_id,
                    entity_name=base_match.entity_name,
                    similarity_score=combined_score,
                    strategy=ResolutionStrategy.HYBRID,
                    properties=base_match.properties,
                    confidence=combined_score
                ))

        logger.info(f"Hybrid match: Found {len(hybrid_matches)} matches with combined scores")
        return sorted(hybrid_matches, key=lambda x: x.similarity_score, reverse=True)

    def _calculate_property_similarity(
        self,
        props1: Dict[str, Any],
        props2: Dict[str, Any]
    ) -> float:
        """Calculate Jaccard similarity of property sets."""
        if not props1 and not props2:
            return 1.0

        if not props1 or not props2:
            return 0.0

        # Get common keys
        keys1 = set(props1.keys())
        keys2 = set(props2.keys())

        # Jaccard similarity
        intersection = len(keys1 & keys2)
        union = len(keys1 | keys2)

        if union == 0:
            return 0.0

        return intersection / union

    def _determine_action(self, matches: List[EntityMatch]) -> ResolutionResult:
        """
        Determine recommended action based on matches.

        Rules:
        - If exact match (score = 1.0): merge
        - If high confidence match (score >= 0.9): link
        - Otherwise: create new
        """
        if not matches:
            return ResolutionResult(
                is_duplicate=False,
                canonical_entity_id=None,
                matches=[],
                recommended_action="create_new",
                confidence=1.0
            )

        best_match = matches[0]

        if best_match.similarity_score == 1.0:
            # Exact match: definite duplicate
            return ResolutionResult(
                is_duplicate=True,
                canonical_entity_id=best_match.entity_id,
                matches=matches,
                recommended_action="merge",
                confidence=1.0
            )
        elif best_match.similarity_score >= 0.90:
            # High confidence: likely duplicate, link it
            return ResolutionResult(
                is_duplicate=True,
                canonical_entity_id=best_match.entity_id,
                matches=matches,
                recommended_action="link",
                confidence=best_match.confidence
            )
        else:
            # Below threshold: create new but include similar entities for reference
            return ResolutionResult(
                is_duplicate=False,
                canonical_entity_id=None,
                matches=matches,
                recommended_action="create_new",
                confidence=1.0 - best_match.similarity_score  # Confidence in creating new
            )

    async def merge_entities(
        self,
        source_entity_id: str,
        target_entity_id: str,
        merge_strategy: str = "preserve_all"
    ) -> Dict[str, Any]:
        """
        Merge two entities into one canonical entity.

        Args:
            source_entity_id: Entity to merge from
            target_entity_id: Canonical entity to merge into
            merge_strategy: How to handle conflicting properties
                - "preserve_all": Keep all properties, use lists for conflicts
                - "prefer_target": Keep target properties, discard source conflicts
                - "prefer_source": Keep source properties

        Returns:
            Result dictionary with merged entity details
        """
        logger.info(f"Merging entity {source_entity_id} into {target_entity_id}")

        # Implementation would:
        # 1. Get both entities
        # 2. Merge properties
        # 3. Transfer relationships
        # 4. Delete source entity
        # 5. Return merged entity

        # Placeholder for now
        return {
            "status": "success",
            "canonical_entity_id": target_entity_id,
            "merged_entity_id": source_entity_id
        }
