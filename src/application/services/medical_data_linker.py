"""
Medical-to-Data Entity Linking Service

This service creates semantic bridges between medical knowledge entities
(diseases, treatments, drugs) and DDA metadata entities (tables, columns, rules).

Uses Neo4j as the unified backend for both medical KG and DDA metadata.

Uses multiple matching strategies:
1. Exact name matching
2. Description/context matching
3. Semantic similarity (embedding-based) - TODO
4. LLM-based inference - TODO

Creates SEMANTIC layer relationships:
- (medical_entity)-[:REPRESENTS_IN]->(column)
- (medical_entity)-[:APPLICABLE_TO]->(table)
- (medical_entity)-[:INFORMS_RULE]->(dq_rule)
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
from neo4j import GraphDatabase
import os

logger = logging.getLogger(__name__)


@dataclass
class EntityLink:
    """Represents a link between a medical entity and a data entity."""
    medical_entity_id: int
    medical_entity_name: str
    medical_entity_type: str
    data_entity_id: int
    data_entity_name: str
    data_entity_type: str
    confidence: float
    linking_strategy: str
    relationship_type: str
    reasoning: str


@dataclass
class LinkingResult:
    """Results of entity linking operation."""
    links_created: int
    exact_count: int
    description_count: int
    semantic_count: int
    llm_count: int
    skipped_count: int
    links: List[EntityLink]


class MedicalDataLinker:
    """Links medical knowledge entities to data catalog entities using Neo4j."""

    # Medical terms that commonly appear in data entity names
    MEDICAL_TERM_PATTERNS = [
        # Diseases
        "crohn", "colitis", "lupus", "arthritis", "diabetes", "sclerosis",
        "psoriasis", "celiac", "spondylitis", "vasculitis", "syndrome",
        # Treatments
        "treatment", "therapy", "medication", "drug", "biologic", "infusion",
        # Clinical concepts
        "patient", "diagnosis", "symptom", "disease", "clinical", "medical",
        "lab", "test", "assessment", "biomarker", "inflammation"
    ]

    def __init__(
        self,
        neo4j_uri: Optional[str] = None,
        neo4j_user: Optional[str] = None,
        neo4j_password: Optional[str] = None
    ):
        """Initialize the medical data linker with Neo4j connection."""
        # Get credentials from environment if not provided
        self.uri = neo4j_uri or os.getenv("NEO4J_URI", "bolt://localhost:7687")
        # Handle multiple URIs in .env (take the last one)
        if '\n' in self.uri:
            self.uri = self.uri.split('\n')[-1].strip()

        self.user = neo4j_user or os.getenv("NEO4J_USERNAME", "neo4j")
        self.password = neo4j_password or os.getenv("NEO4J_PASSWORD", "")

        logger.info(f"Connecting to Neo4j at {self.uri}")
        self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))

    def __del__(self):
        """Close Neo4j connection."""
        if hasattr(self, 'driver'):
            self.driver.close()

    async def link_medical_to_data(
        self,
        confidence_threshold: float = 0.75
    ) -> LinkingResult:
        """
        Create links between medical entities and data entities.

        Args:
            confidence_threshold: Minimum confidence score to create a link

        Returns:
            LinkingResult with statistics and created links
        """
        logger.info(f"Starting medical-to-data entity linking (threshold: {confidence_threshold})")

        with self.driver.session() as session:
            # Get all medical entities (from PDF ingestion)
            medical_entities = self._get_medical_entities(session)
            logger.info(f"Found {len(medical_entities)} medical entities")

            # Get all data entities (from DDA processing)
            data_entities = self._get_data_entities(session)
            logger.info(f"Found {len(data_entities)} data entities")

            if not medical_entities or not data_entities:
                logger.warning("No entities to link")
                return LinkingResult(0, 0, 0, 0, 0, 0, [])

            # Track results
            links: List[EntityLink] = []
            exact_count = 0
            description_count = 0
            semantic_count = 0
            llm_count = 0
            skipped_count = 0

            # Process each medical entity
            for med_entity in medical_entities:
                # Strategy 1: Exact name matching
                exact_matches = self._find_exact_matches(med_entity, data_entities)

                # Strategy 2: Description/context matching
                description_matches = self._find_description_matches(med_entity, data_entities)

                # Combine and deduplicate matches
                all_matches = self._combine_matches(exact_matches, description_matches)

                # Create links for high-confidence matches
                for match in all_matches:
                    if match.confidence >= confidence_threshold:
                        # Determine relationship type
                        rel_type = self._determine_relationship_type(
                            match.medical_entity_type,
                            match.data_entity_type
                        )
                        match.relationship_type = rel_type

                        # Create link in Neo4j
                        success = self._create_link(session, match)

                        if success:
                            links.append(match)
                            if match.linking_strategy == "exact":
                                exact_count += 1
                            elif match.linking_strategy == "description":
                                description_count += 1
                            elif match.linking_strategy == "semantic":
                                semantic_count += 1
                            elif match.linking_strategy == "llm":
                                llm_count += 1
                        else:
                            skipped_count += 1

        result = LinkingResult(
            links_created=len(links),
            exact_count=exact_count,
            description_count=description_count,
            semantic_count=semantic_count,
            llm_count=llm_count,
            skipped_count=skipped_count,
            links=links
        )

        logger.info(f"Linking complete: {result.links_created} links created")
        logger.info(f"  - Exact: {result.exact_count}")
        logger.info(f"  - Description: {result.description_count}")
        logger.info(f"  - Semantic: {result.semantic_count}")
        logger.info(f"  - LLM: {result.llm_count}")
        logger.info(f"  - Skipped: {result.skipped_count}")

        return result

    def _get_medical_entities(self, session) -> List[Dict[str, Any]]:
        """Get all medical entities from Neo4j (migrated from FalkorDB)."""
        # Medical entities are labeled MedicalEntity after migration
        query = """
        MATCH (n:MedicalEntity)
        WHERE n.type = 'Disease' OR n.type = 'Treatment' OR n.type = 'Drug'
           OR n.type = 'Symptom' OR n.type = 'Test' OR n.type = 'Gene'
           OR n.type = 'Pathway' OR n.type = 'Organization' OR n.type = 'Study'
        RETURN
            id(n) as id,
            n.name as name,
            n.type as type,
            coalesce(n.description, '') as description
        LIMIT 1000
        """

        result = session.run(query)

        entities = []
        for record in result:
            entities.append({
                "id": record["id"],
                "name": record["name"],
                "type": record["type"],
                "description": record["description"]
            })

        return entities

    def _get_data_entities(self, session) -> List[Dict[str, Any]]:
        """Get all data entities from Neo4j (from DDA processing)."""
        # Data entities are Tables and Columns
        query = """
        MATCH (n)
        WHERE n:Table OR n:Column OR n:DataEntity
        RETURN
            id(n) as id,
            n.name as name,
            labels(n)[0] as type,
            coalesce(n.description, '') as description,
            coalesce(n.business_context, '') as business_context
        LIMIT 1000
        """

        result = session.run(query)

        entities = []
        for record in result:
            entities.append({
                "id": record["id"],
                "name": record["name"],
                "type": record["type"],
                "description": record["description"],
                "business_context": record["business_context"]
            })

        return entities

    def _find_exact_matches(
        self,
        med_entity: Dict[str, Any],
        data_entities: List[Dict[str, Any]]
    ) -> List[EntityLink]:
        """Find data entities with exact name matches."""
        matches = []
        med_name_lower = med_entity["name"].lower()

        for data_entity in data_entities:
            data_name_lower = data_entity["name"].lower()

            # Check if medical term appears in data entity name
            if med_name_lower in data_name_lower or data_name_lower in med_name_lower:
                matches.append(EntityLink(
                    medical_entity_id=med_entity["id"],
                    medical_entity_name=med_entity["name"],
                    medical_entity_type=med_entity["type"],
                    data_entity_id=data_entity["id"],
                    data_entity_name=data_entity["name"],
                    data_entity_type=data_entity["type"],
                    confidence=0.95,  # High confidence for exact match
                    linking_strategy="exact",
                    relationship_type="",  # Determined later
                    reasoning=f"Exact name match: '{med_entity['name']}' in '{data_entity['name']}'"
                ))

        return matches

    def _find_description_matches(
        self,
        med_entity: Dict[str, Any],
        data_entities: List[Dict[str, Any]]
    ) -> List[EntityLink]:
        """Find data entities where medical term appears in description/context."""
        matches = []
        med_name_lower = med_entity["name"].lower()

        for data_entity in data_entities:
            description = (data_entity.get("description", "") or "").lower()
            business_context = (data_entity.get("business_context", "") or "").lower()

            # Check if medical term appears in description or business context
            if med_name_lower in description or med_name_lower in business_context:
                matches.append(EntityLink(
                    medical_entity_id=med_entity["id"],
                    medical_entity_name=med_entity["name"],
                    medical_entity_type=med_entity["type"],
                    data_entity_id=data_entity["id"],
                    data_entity_name=data_entity["name"],
                    data_entity_type=data_entity["type"],
                    confidence=0.85,  # Good confidence for description match
                    linking_strategy="description",
                    relationship_type="",  # Determined later
                    reasoning=f"Found '{med_entity['name']}' in description/context"
                ))

        return matches

    def _combine_matches(
        self,
        exact_matches: List[EntityLink],
        description_matches: List[EntityLink]
    ) -> List[EntityLink]:
        """Combine and deduplicate matches from different strategies."""
        # Use a dict to track best match for each (med_id, data_id) pair
        best_matches: Dict[Tuple[int, int], EntityLink] = {}

        for match in exact_matches + description_matches:
            key = (match.medical_entity_id, match.data_entity_id)

            if key not in best_matches or match.confidence > best_matches[key].confidence:
                best_matches[key] = match

        return list(best_matches.values())

    def _determine_relationship_type(
        self,
        medical_type: str,
        data_type: str
    ) -> str:
        """Determine the appropriate relationship type."""
        # Disease/Treatment -> Column: data represents the medical concept
        if data_type == "Column":
            return "REPRESENTS_IN"

        # Disease/Treatment -> Table: medical concept applicable to table
        elif data_type == "Table" or data_type == "DataEntity":
            return "APPLICABLE_TO"

        # Disease/Treatment -> dq_rule: medical concept informs validation rule
        elif data_type == "dq_rule":
            return "INFORMS_RULE"

        # Default
        return "RELATES_TO"

    def _create_link(
        self,
        session,
        link: EntityLink
    ) -> bool:
        """Create a link relationship in Neo4j."""
        try:
            # Use MERGE to avoid duplicates
            # Escape single quotes in strings
            reasoning_escaped = link.reasoning.replace("'", "\\'")

            query = f"""
            MATCH (m), (d)
            WHERE id(m) = $med_id AND id(d) = $data_id
            MERGE (m)-[r:{link.relationship_type}]->(d)
            SET r.confidence = $confidence,
                r.linking_strategy = $strategy,
                r.reasoning = $reasoning,
                r.layer = 'SEMANTIC',
                r.created_at = $created_at
            RETURN id(r) as rel_id
            """

            result = session.run(
                query,
                med_id=link.medical_entity_id,
                data_id=link.data_entity_id,
                confidence=link.confidence,
                strategy=link.linking_strategy,
                reasoning=link.reasoning,
                created_at=datetime.now().isoformat()
            )

            return result.single() is not None

        except Exception as e:
            logger.error(f"Failed to create link: {e}")
            return False

    def get_links_for_medical_entity(self, entity_name: str) -> List[Dict[str, Any]]:
        """Get all data entities linked to a medical entity."""
        with self.driver.session() as session:
            query = """
            MATCH (m)-[r:REPRESENTS_IN|APPLICABLE_TO|INFORMS_RULE]->(d)
            WHERE toLower(m.name) = toLower($entity_name)
            RETURN
                m.name as medical_entity,
                m.type as medical_type,
                type(r) as relationship,
                d.name as data_entity,
                labels(d)[0] as data_type,
                r.confidence as confidence,
                r.linking_strategy as strategy
            """

            result = session.run(query, entity_name=entity_name)

            links = []
            for record in result:
                links.append({
                    "medical_entity": record["medical_entity"],
                    "medical_type": record["medical_type"],
                    "relationship": record["relationship"],
                    "data_entity": record["data_entity"],
                    "data_type": record["data_type"],
                    "confidence": record["confidence"],
                    "strategy": record["strategy"]
                })

            return links
