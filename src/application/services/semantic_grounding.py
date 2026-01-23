"""Semantic Grounding Service.

This service bridges text embeddings (FAISS) with graph structure (Neo4j/Graphiti),
enabling hybrid queries that combine semantic similarity with graph relationships.

Key capabilities:
- Generate embeddings for graph entities
- Link text embeddings with graph nodes
- Hybrid queries (vector similarity + graph traversal)
- Semantic search within knowledge graph
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import logging
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class GroundedEntity:
    """Represents an entity with both graph and embedding representations."""
    entity_id: str
    entity_name: str
    entity_type: str
    embedding: Optional[np.ndarray] = None
    properties: Dict[str, Any] = None
    neighbors: List[str] = None

    def __post_init__(self):
        if self.properties is None:
            self.properties = {}
        if self.neighbors is None:
            self.neighbors = []


@dataclass
class HybridSearchResult:
    """Result from a hybrid search combining vector and graph similarity."""
    entity_id: str
    entity_name: str
    vector_score: float
    graph_score: float
    combined_score: float
    properties: Dict[str, Any]
    explanation: str


class SemanticGroundingService:
    """
    Service for grounding text semantics in the knowledge graph structure.

    Bridges the gap between neural (embeddings) and symbolic (graph) representations.
    """

    def __init__(
        self,
        backend: Any,
        embedding_model: str = "all-MiniLM-L6-v2",
        vector_weight: float = 0.7,
        graph_weight: float = 0.3
    ):
        """
        Initialize the semantic grounding service.

        Args:
            backend: Knowledge graph backend
            embedding_model: Sentence transformer model name
            vector_weight: Weight for vector similarity (0.0-1.0)
            graph_weight: Weight for graph similarity (0.0-1.0)
        """
        self.backend = backend
        self.vector_weight = vector_weight
        self.graph_weight = graph_weight

        # Lazy load embedding model
        self._embedding_model = None
        self._embedding_model_name = embedding_model

        # Cache for entity embeddings
        self._embedding_cache: Dict[str, np.ndarray] = {}

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
                    "Semantic grounding will be disabled. "
                    "Install with: pip install sentence-transformers"
                )
                self._embedding_model = None
        return self._embedding_model

    def generate_entity_embedding(self, entity_name: str, entity_properties: Optional[Dict[str, Any]] = None) -> Optional[np.ndarray]:
        """
        Generate embedding for a graph entity.

        Combines entity name with relevant properties for richer representation.

        Args:
            entity_name: Name of the entity
            entity_properties: Optional entity properties

        Returns:
            Embedding vector or None if model not available
        """
        if self.embedding_model is None:
            return None

        # Create text representation
        text_parts = [entity_name]

        if entity_properties:
            # Add description if available
            if "description" in entity_properties:
                text_parts.append(entity_properties["description"])

            # Add other text fields
            for key, value in entity_properties.items():
                if isinstance(value, str) and key not in ["id", "name", "description"]:
                    text_parts.append(f"{key}: {value}")

        text = " ".join(text_parts)

        # Generate embedding
        embedding = self.embedding_model.encode([text])[0]

        return embedding

    async def ground_entity(
        self,
        entity_id: str,
        force_recompute: bool = False
    ) -> Optional[GroundedEntity]:
        """
        Create grounded representation of an entity.

        Args:
            entity_id: Entity identifier
            force_recompute: Force recomputation of embedding

        Returns:
            GroundedEntity or None if entity not found
        """
        # Query entity from graph
        try:
            query = f"""
            MATCH (e)
            WHERE e.id = $entity_id OR id(e) = $entity_id
            OPTIONAL MATCH (e)-[r]-(n)
            RETURN e, collect(DISTINCT n.id) as neighbors
            LIMIT 1
            """

            results = await self.backend.query(query, {"entity_id": entity_id})

            if not results:
                logger.warning(f"Entity {entity_id} not found in graph")
                return None

            entity_data = results[0]["e"]
            neighbors = results[0].get("neighbors", [])

            # Get or generate embedding
            if entity_id in self._embedding_cache and not force_recompute:
                embedding = self._embedding_cache[entity_id]
            else:
                embedding = self.generate_entity_embedding(
                    entity_data.get("name", str(entity_id)),
                    entity_data
                )
                if embedding is not None:
                    self._embedding_cache[entity_id] = embedding

            return GroundedEntity(
                entity_id=entity_id,
                entity_name=entity_data.get("name", str(entity_id)),
                entity_type=entity_data.get("type", "Unknown"),
                embedding=embedding,
                properties=dict(entity_data),
                neighbors=[n for n in neighbors if n is not None]
            )

        except Exception as e:
            logger.error(f"Error grounding entity {entity_id}: {e}")
            return None

    async def hybrid_search(
        self,
        query_text: str,
        entity_type: Optional[str] = None,
        top_k: int = 10,
        min_combined_score: float = 0.3
    ) -> List[HybridSearchResult]:
        """
        Perform hybrid search combining vector similarity and graph structure.

        Args:
            query_text: Query text
            entity_type: Optional entity type filter
            top_k: Number of top results to return
            min_combined_score: Minimum combined score threshold

        Returns:
            List of hybrid search results
        """
        if self.embedding_model is None:
            logger.warning("Embedding model not available, falling back to name-based search")
            return await self._fallback_search(query_text, entity_type, top_k)

        # Generate query embedding
        query_embedding = self.embedding_model.encode([query_text])[0]

        # Get candidate entities from graph
        candidates = await self._get_candidate_entities(entity_type)

        if not candidates:
            return []

        # Compute scores for each candidate
        results = []

        for candidate in candidates:
            # Ground entity (get embedding)
            grounded = await self.ground_entity(candidate["id"])

            if grounded is None or grounded.embedding is None:
                continue

            # Vector similarity
            vector_score = self._cosine_similarity(query_embedding, grounded.embedding)

            # Graph similarity (based on centrality, connectivity)
            graph_score = self._compute_graph_score(grounded)

            # Combined score
            combined_score = (
                self.vector_weight * vector_score +
                self.graph_weight * graph_score
            )

            if combined_score >= min_combined_score:
                results.append(HybridSearchResult(
                    entity_id=grounded.entity_id,
                    entity_name=grounded.entity_name,
                    vector_score=vector_score,
                    graph_score=graph_score,
                    combined_score=combined_score,
                    properties=grounded.properties,
                    explanation=self._generate_explanation(vector_score, graph_score, grounded)
                ))

        # Sort by combined score
        results.sort(key=lambda x: x.combined_score, reverse=True)

        return results[:top_k]

    async def find_similar_entities(
        self,
        entity_id: str,
        top_k: int = 5,
        similarity_threshold: float = 0.7
    ) -> List[Tuple[str, float]]:
        """
        Find entities similar to a given entity using embeddings.

        Args:
            entity_id: Reference entity ID
            top_k: Number of similar entities to return
            similarity_threshold: Minimum similarity threshold

        Returns:
            List of (entity_id, similarity_score) tuples
        """
        # Ground reference entity
        reference = await self.ground_entity(entity_id)

        if reference is None or reference.embedding is None:
            return []

        # Get all entities of same type
        candidates = await self._get_candidate_entities(reference.entity_type)

        # Compute similarities
        similarities = []

        for candidate in candidates:
            if candidate["id"] == entity_id:
                continue  # Skip self

            grounded = await self.ground_entity(candidate["id"])

            if grounded is None or grounded.embedding is None:
                continue

            similarity = self._cosine_similarity(reference.embedding, grounded.embedding)

            if similarity >= similarity_threshold:
                similarities.append((grounded.entity_id, float(similarity)))

        # Sort by similarity
        similarities.sort(key=lambda x: x[1], reverse=True)

        return similarities[:top_k]

    async def _get_candidate_entities(self, entity_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get candidate entities from graph."""
        try:
            if entity_type:
                query = f"""
                MATCH (e:{entity_type})
                RETURN e.id as id, e.name as name, e.type as type
                LIMIT 1000
                """
            else:
                query = """
                MATCH (e)
                WHERE e.id IS NOT NULL
                RETURN e.id as id, e.name as name, labels(e)[0] as type
                LIMIT 1000
                """

            results = await self.backend.query(query)
            return [dict(r) for r in results]

        except Exception as e:
            logger.error(f"Error getting candidate entities: {e}")
            return []

    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Compute cosine similarity between two vectors."""
        from sklearn.metrics.pairwise import cosine_similarity

        similarity = cosine_similarity(
            vec1.reshape(1, -1),
            vec2.reshape(1, -1)
        )[0][0]

        return float(similarity)

    def _compute_graph_score(self, entity: GroundedEntity) -> float:
        """
        Compute graph-based score for an entity.

        Factors:
        - Number of neighbors (connectivity)
        - Entity type (some types are more central)
        - Properties richness
        """
        score = 0.0

        # Connectivity score (normalized)
        if entity.neighbors:
            connectivity = min(len(entity.neighbors) / 10.0, 1.0)  # Normalize to max 10 neighbors
            score += 0.4 * connectivity

        # Property richness score
        if entity.properties:
            property_count = len([v for v in entity.properties.values() if v is not None])
            richness = min(property_count / 5.0, 1.0)  # Normalize to max 5 properties
            score += 0.3 * richness

        # Type score (higher for semantic layer entities)
        type_scores = {
            "BusinessConcept": 1.0,
            "Domain": 0.9,
            "InformationAsset": 0.8,
            "Table": 0.6,
            "Column": 0.4
        }
        type_score = type_scores.get(entity.entity_type, 0.5)
        score += 0.3 * type_score

        return score

    def _generate_explanation(
        self,
        vector_score: float,
        graph_score: float,
        entity: GroundedEntity
    ) -> str:
        """Generate explanation for hybrid score."""
        explanations = []

        if vector_score > 0.8:
            explanations.append(f"High semantic similarity ({vector_score:.2f})")
        elif vector_score > 0.6:
            explanations.append(f"Moderate semantic similarity ({vector_score:.2f})")

        if graph_score > 0.7:
            explanations.append(f"Well-connected in graph ({len(entity.neighbors)} neighbors)")

        if not explanations:
            explanations.append(f"Low confidence match (vector={vector_score:.2f}, graph={graph_score:.2f})")

        return "; ".join(explanations)

    async def _fallback_search(
        self,
        query_text: str,
        entity_type: Optional[str],
        top_k: int
    ) -> List[HybridSearchResult]:
        """Fallback to name-based search when embeddings not available."""
        try:
            query_lower = query_text.lower()

            if entity_type:
                cypher = f"""
                MATCH (e:{entity_type})
                WHERE toLower(e.name) CONTAINS $query
                RETURN e.id as id, e.name as name, e as properties
                LIMIT $top_k
                """
            else:
                cypher = """
                MATCH (e)
                WHERE toLower(e.name) CONTAINS $query
                RETURN e.id as id, e.name as name, e as properties
                LIMIT $top_k
                """

            results = await self.backend.query(cypher, {"query": query_lower, "top_k": top_k})

            fallback_results = []
            for r in results:
                # Simple name-based score
                name_lower = r["name"].lower()
                if query_lower == name_lower:
                    score = 1.0
                elif query_lower in name_lower:
                    score = 0.8
                else:
                    score = 0.5

                fallback_results.append(HybridSearchResult(
                    entity_id=r["id"],
                    entity_name=r["name"],
                    vector_score=0.0,
                    graph_score=score,
                    combined_score=score,
                    properties=dict(r["properties"]),
                    explanation=f"Name-based match (embeddings unavailable)"
                ))

            return fallback_results

        except Exception as e:
            logger.error(f"Error in fallback search: {e}")
            return []

    def clear_cache(self) -> None:
        """Clear the embedding cache."""
        self._embedding_cache.clear()
        logger.info("Cleared embedding cache")

    def get_cache_size(self) -> int:
        """Get number of cached embeddings."""
        return len(self._embedding_cache)
