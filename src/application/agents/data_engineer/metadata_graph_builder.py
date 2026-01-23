"""Metadata graph builder for creating ODIN-compliant metadata graphs from DDA documents."""

from typing import Dict, Any, List, Optional
from domain.dda_models import DDADocument, DataEntity, Relationship
from domain.odin_models import (
    Catalog, Schema, Table, Column, DataTypeEntity, TypeAssignment,
    Constraint, ConstraintType, LineageNode, LineageRelationship, LineageType,
    DataQualityRule, DataQualityScore, UsageStats
)
from domain.kg_backends import KnowledgeGraphBackend
from application.agents.data_engineer.type_inference import TypeInferenceService
from domain.knowledge_layers import KnowledgeLayer


class MetadataGraphBuilder:
    """Builds ODIN-compliant metadata graphs from DDA documents."""
    
    def __init__(
        self,
        kg_backend: KnowledgeGraphBackend,
        type_inference: TypeInferenceService
    ):
        """Initialize the metadata graph builder.
        
        Args:
            kg_backend: Knowledge graph backend for persisting entities and relationships
            type_inference: Service for inferring data types
        """
        self.kg_backend = kg_backend
        self.type_inference = type_inference
    
    async def build_metadata_graph(
        self,
        dda_document: DDADocument
    ) -> Dict[str, Any]:
        """Build a complete ODIN metadata graph from DDA document.
        
        Args:
            dda_document: The parsed DDA document
        
        Returns:
            Summary of created metadata graph with counts
        """
        results = {
            "catalogs_created": 0,
            "schemas_created": 0,
            "tables_created": 0,
            "columns_created": 0,
            "constraints_created": 0,
            "relationships_created": 0
        }
        
        # 1. Create Catalog (from Domain)
        catalog = await self._create_catalog(dda_document)
        results["catalogs_created"] = 1
        
        # 2. Create Schema (from Domain)
        schema = await self._create_schema(dda_document, catalog.name)
        results["schemas_created"] = 1
        
        # 3. Create Tables (from DDA Entities)
        print(f"DEBUG: Found {len(dda_document.entities)} entities in DDA")
        for entity in dda_document.entities:
            table = await self._create_table(dda_document, entity, schema.name)
            results["tables_created"] += 1
            
            # Get full table ID for relationships
            table_id = f"table:{schema.name}.{table.name}"
            
            # 4. Create Columns (from Entity Attributes)
            for attr in entity.attributes:
                column = await self._create_column(entity, attr, table.name, table_id)
                results["columns_created"] += 1
                
                # 5. Create Type Assignments
                await self._create_type_assignment(column, attr, entity, table_id)
                
                # 6. Create Constraints (from Primary/Foreign Keys, Business Rules)
                constraints = await self._create_constraints(
                    entity, attr, column, table.name, table_id, dda_document
                )
                results["constraints_created"] += len(constraints)
        
        # 7. Create Relationships (belongs_to, etc.)
        relationships = await self._create_relationships(
            dda_document, catalog, schema
        )
        results["relationships_created"] = len(relationships)
        
        # 8. Create Lineage (Source -> Table)
        # In a real scenario, this would come from parsing SQL or ETL logs.
        # Here we simulate it based on 'origin' or naming conventions.
        await self._create_lineage(dda_document, schema)
        
        # 9. Create Data Quality Rules & Scores
        # Based on constraints and business rules
        await self._create_data_quality(dda_document, schema)
        
        # 10. Create Usage Stats (Simulated)
        await self._create_usage_stats(dda_document, schema)
        
        return results
    
    async def _create_catalog(self, dda_document: DDADocument) -> Catalog:
        """Create Catalog from Domain."""
        catalog_name = f"{dda_document.domain.lower().replace(' ', '_')}_catalog"
        catalog = Catalog(
            name=catalog_name,
            description=f"Catalog for {dda_document.domain} domain",
            properties={
                "domain": dda_document.domain,
                "effective_date": dda_document.effective_date.isoformat(),
                "business_context": dda_document.business_context,
                "layer": KnowledgeLayer.PERCEPTION
            }
        )
        
        entity_id = f"catalog:{catalog_name}"
        await self.kg_backend.add_entity(entity_id, catalog.model_dump())
        
        return catalog
    
    async def _create_schema(
        self,
        dda_document: DDADocument,
        catalog_name: str
    ) -> Schema:
        """Create Schema from Domain."""
        domain_clean = dda_document.domain.lower().replace(' ', '_').replace("'", '').replace('-', '_')
        schema_name = f"{domain_clean}_schema"
        schema = Schema(
            name=schema_name,
            catalog_name=catalog_name,
            description=f"Schema for {dda_document.domain} domain",
            properties={
                "domain": dda_document.domain,
                "stakeholders": dda_document.stakeholders,
                "layer": KnowledgeLayer.PERCEPTION
            }
        )
        
        entity_id = f"schema:{schema_name}"
        await self.kg_backend.add_entity(entity_id, schema.model_dump())
        
        # Create belongs_to relationship
        await self.kg_backend.add_relationship(
            entity_id,
            "belongs_to",
            f"catalog:{catalog_name}",
            {"layer": KnowledgeLayer.PERCEPTION}
        )
        
        return schema
    
    async def _create_table(
        self,
        dda_document: DDADocument,
        entity: DataEntity,
        schema_name: str
    ) -> Table:
        """Create Table from DDA Entity."""
        table_name = entity.name.lower().replace(' ', '_')
        table = Table(
            name=table_name,
            schema_name=schema_name,
            description=entity.description,
            origin=None,  # Can be populated from actual data sources later
            properties={
                "entity_name": entity.name,
                "business_rules": entity.business_rules,
                "layer": KnowledgeLayer.PERCEPTION
            }
        )
        
        entity_id = f"table:{schema_name}.{table_name}"
        await self.kg_backend.add_entity(entity_id, table.model_dump())
        
        # Create belongs_to relationship
        await self.kg_backend.add_relationship(
            entity_id,
            "belongs_to",
            f"schema:{schema_name}",
            {"layer": KnowledgeLayer.PERCEPTION}
        )
        
        return table
    
    async def _create_column(
        self,
        entity: DataEntity,
        attribute: str,
        table_name: str,
        table_id: str
    ) -> Column:
        """Create Column from Entity Attribute."""
        # Parse attribute name (handle "Customer ID (Primary Key)" format)
        column_name = self._parse_attribute_name(attribute)
        
        column = Column(
            name=column_name,
            table_name=table_name,
            description=f"Column for {attribute}",
            properties={
                "original_attribute": attribute,
                "entity_name": entity.name,
                "layer": KnowledgeLayer.PERCEPTION
            }
        )
        
        entity_id = f"column:{table_name}.{column_name}"
        await self.kg_backend.add_entity(entity_id, column.model_dump())
        
        # Create has_column relationship
        await self.kg_backend.add_relationship(
            table_id,
            "has_column",
            entity_id,
            {"layer": KnowledgeLayer.PERCEPTION}
        )
        
        return column
    
    async def _create_type_assignment(
        self,
        column: Column,
        attribute: str,
        entity: DataEntity,
        table_id: str
    ) -> TypeAssignment:
        """Infer and assign data type to column."""
        # Prepare context for type inference
        context = {
            "entity_name": entity.name,
            "description": entity.description,
            "business_rules": entity.business_rules
        }
        
        # Infer type using TypeInferenceService
        data_type_entity = await self.type_inference.infer_data_type(attribute, context)
        
        # Infer precision
        precision = await self.type_inference.infer_precision(attribute, data_type_entity, context)
        
        # Infer scale
        scale = await self.type_inference.infer_scale(attribute, data_type_entity)
        
        # Get data type name (handle both enum and string)
        data_type_name = data_type_entity.name.value if hasattr(data_type_entity.name, 'value') else str(data_type_entity.name)
        
        type_assignment = TypeAssignment(
            column_name=column.name,
            data_type_name=data_type_name,
            precision=precision,
            scale=scale,
            properties={"layer": KnowledgeLayer.PERCEPTION}
        )
        
        # Create DataType entity if not exists
        await self._ensure_data_type(data_type_entity)
        
        # Create type assignment entity
        assignment_id = f"type_assignment:{column.table_name}.{column.name}"
        await self.kg_backend.add_entity(assignment_id, type_assignment.model_dump())
        
        # Create relationships
        column_id = f"column:{column.table_name}.{column.name}"
        await self.kg_backend.add_relationship(
            column_id,
            "has_type_assignment",
            assignment_id,
            {"layer": KnowledgeLayer.PERCEPTION}
        )
        
        await self.kg_backend.add_relationship(
            assignment_id,
            "typed_as",
            f"datatype:{data_type_name}",
            {"layer": KnowledgeLayer.SEMANTIC} # Linking Perception to Semantic
        )
        
        return type_assignment
    
    async def _create_constraints(
        self,
        entity: DataEntity,
        attribute: str,
        column: Column,
        table_name: str,
        table_id: str,
        dda_document: DDADocument
    ) -> List[Constraint]:
        """Create constraints from primary keys, foreign keys, and business rules."""
        constraints = []
        column_name = column.name
        
        # Primary Key constraint
        if entity.primary_key and self._matches_attribute(attribute, entity.primary_key):
            pk_constraint = Constraint(
                name=f"pk_{table_name}_{column_name}",
                constraint_type=ConstraintType.PRIMARY_KEY,
                column_name=column_name,
                table_name=table_name,
                properties={"layer": KnowledgeLayer.PERCEPTION}
            )
            constraints.append(pk_constraint)
        
        # Foreign Key constraints
        for fk in entity.foreign_keys:
            if self._matches_attribute(attribute, fk):
                # Find referenced table from DDA relationships
                referenced = self._find_referenced_table(fk, dda_document)
                if referenced:
                    fk_constraint = Constraint(
                        name=f"fk_{table_name}_{column_name}",
                        constraint_type=ConstraintType.FOREIGN_KEY,
                        column_name=column_name,
                        table_name=table_name,
                        referenced_table=referenced,
                        referenced_column=self._infer_referenced_column(fk),
                        properties={"layer": KnowledgeLayer.PERCEPTION}
                    )
                    constraints.append(fk_constraint)
        
        # Business Rules → Constraints (e.g., NOT NULL, CHECK)
        for rule in entity.business_rules:
            constraint = self._parse_business_rule_to_constraint(
                rule, column_name, table_name
            )
            if constraint:
                constraints.append(constraint)
        
        # Create constraint entities and relationships
        for constraint in constraints:
            constraint_id = f"constraint:{constraint.name}"
            await self.kg_backend.add_entity(constraint_id, constraint.model_dump())
            
            column_id = f"column:{table_name}.{column_name}"
            await self.kg_backend.add_relationship(
                column_id,
                "constrained_by",
                constraint_id,
                {"layer": KnowledgeLayer.PERCEPTION}
            )
        
        return constraints
    
    async def _create_relationships(
        self,
        dda_document: DDADocument,
        catalog: Catalog,
        schema: Schema
    ) -> List[Dict[str, Any]]:
        """Create all ODIN relationships."""
        relationships = []
        
        # owned_by relationships (tables → data owner)
        for entity in dda_document.entities:
            table_name = entity.name.lower().replace(' ', '_')
            table_id = f"table:{schema.name}.{table_name}"
            
            # Create user entity for data owner if needed
            owner_id = f"user:{dda_document.data_owner}"
            await self._ensure_user(dda_document.data_owner, "data_owner", dda_document.domain)
            
            await self.kg_backend.add_relationship(
                table_id,
                "owned_by",
                owner_id,
                {"layer": KnowledgeLayer.SEMANTIC} # Linking Perception to Semantic
            )
            relationships.append({
                "source": table_id,
                "type": "owned_by",
                "target": owner_id
            })
        
        # read_by relationships (tables → stakeholders)
        for entity in dda_document.entities:
            table_name = entity.name.lower().replace(' ', '_')
            table_id = f"table:{schema.name}.{table_name}"
            
            for stakeholder in dda_document.stakeholders:
                stakeholder_id = f"user:{stakeholder}"
                await self._ensure_user(stakeholder, "stakeholder", dda_document.domain)
                
                await self.kg_backend.add_relationship(
                    table_id,
                    "read_by",
                    stakeholder_id,
                    {"layer": KnowledgeLayer.SEMANTIC} # Linking Perception to Semantic
                )
                relationships.append({
                    "source": table_id,
                    "type": "read_by",
                    "target": stakeholder_id
                })
        
        return relationships
    
    async def _ensure_data_type(self, data_type_entity: DataTypeEntity) -> None:
        """Ensure DataType entity exists in graph."""
        entity_id = f"datatype:{data_type_entity.name}"
        
        # Add layer property
        props = data_type_entity.model_dump()
        props["layer"] = KnowledgeLayer.SEMANTIC
        
        # Simply add/update the data type entity (MERGE will handle duplicates)
        await self.kg_backend.add_entity(
            entity_id,
            props
        )
    
    async def _ensure_user(self, user_name: str, role: str, domain: str) -> None:
        """Ensure User entity exists in graph."""
        entity_id = f"user:{user_name}"
        user_properties = {
            "name": user_name,
            "role": role,
            "domain": domain,
            "layer": KnowledgeLayer.SEMANTIC
        }
        # Directly add/merge the user entity (MERGE will handle duplicates)
        await self.kg_backend.add_entity(entity_id, user_properties)
    
    def _parse_attribute_name(self, attribute: str) -> str:
        """Parse attribute name, handling formats like 'Customer ID (Primary Key)'."""
        # Remove parenthetical notes
        name = attribute.split('(')[0].strip()
        # Convert to snake_case
        return name.lower().replace(' ', '_')
    
    def _matches_attribute(self, attribute: str, key: str) -> bool:
        """Check if attribute matches a key (handling variations)."""
        attr_clean = self._parse_attribute_name(attribute)
        key_clean = key.lower().replace(' ', '_')
        return attr_clean == key_clean or key_clean in attr_clean
    
    def _find_referenced_table(self, fk: str, dda_document: DDADocument) -> Optional[str]:
        """Find referenced table from foreign key and DDA relationships."""
        # Simple heuristic: look for entity with matching primary key
        for entity in dda_document.entities:
            if entity.primary_key and fk.lower() in entity.primary_key.lower():
                return entity.name.lower().replace(' ', '_')
        
        # Also check relationships
        for relationship in dda_document.relationships:
            # If FK contains source entity name, target is referenced
            if relationship.source_entity.lower() in fk.lower():
                return relationship.target_entity.lower().replace(' ', '_')
            # If FK contains target entity name, source is referenced
            if relationship.target_entity.lower() in fk.lower():
                return relationship.source_entity.lower().replace(' ', '_')
        
        return None
    
    def _infer_referenced_column(self, fk: str) -> str:
        """Infer referenced column name from foreign key."""
        # Usually the primary key of the referenced table
        return fk.lower().replace(' ', '_')
    
    def _parse_business_rule_to_constraint(
        self,
        rule: str,
        column_name: str,
        table_name: str
    ) -> Optional[Constraint]:
        """Parse business rule and create constraint if applicable."""
        rule_lower = rule.lower()
        
        if 'must be unique' in rule_lower or 'unique' in rule_lower:
            return Constraint(
                name=f"uk_{table_name}_{column_name}",
                constraint_type=ConstraintType.UNIQUE,
                column_name=column_name,
                table_name=table_name,
                properties={"source": "business_rule", "rule": rule, "layer": KnowledgeLayer.PERCEPTION}
            )
        elif 'cannot be null' in rule_lower or 'must be present' in rule_lower:
            return Constraint(
                name=f"nn_{table_name}_{column_name}",
                constraint_type=ConstraintType.NOT_NULL,
                column_name=column_name,
                table_name=table_name,
                properties={"source": "business_rule", "rule": rule, "layer": KnowledgeLayer.PERCEPTION}
            )
        elif 'must be' in rule_lower and 'format' in rule_lower:
            # Could create CHECK constraint
            return Constraint(
                name=f"chk_{table_name}_{column_name}",
                constraint_type=ConstraintType.CHECK,
                column_name=column_name,
                table_name=table_name,
                expression=rule,
                properties={"source": "business_rule", "rule": rule, "layer": KnowledgeLayer.PERCEPTION}
            )
        
        return None

    async def _create_lineage(
        self,
        dda_document: DDADocument,
        schema: Schema
    ) -> None:
        """Create lineage nodes and relationships."""
        for entity in dda_document.entities:
            table_name = entity.name.lower().replace(' ', '_')
            table_id = f"table:{schema.name}.{table_name}"
            
            # Simulate upstream source based on domain
            source_system = entity.origin or f"{dda_document.domain}_system"
            source_name = f"raw_{table_name}.csv"
            
            # Create Source Node
            source_node = LineageNode(
                name=source_name,
                type="FILE",
                properties={
                    "system": source_system,
                    "path": f"/data/raw/{dda_document.domain}/{source_name}",
                    "layer": KnowledgeLayer.PERCEPTION
                }
            )
            
            source_id = f"file:{source_name}"
            await self.kg_backend.add_entity(source_id, source_node.model_dump())
            
            # Create Transformation Relationship (Source -> Table)
            await self.kg_backend.add_relationship(
                source_id,
                "transforms_into",
                table_id,
                {
                    "type": LineageType.TRANSFORMATION,
                    "logic": "Direct Load",
                    "layer": KnowledgeLayer.SEMANTIC
                }
            )
            
            # Infer Table-to-Table Lineage (e.g., raw_customer -> dim_customer)
            # This is a heuristic: if this table is a 'dim_' or 'fact_' table,
            # look for a corresponding 'raw_' table.
            if table_name.startswith(("dim_", "fact_")):
                base_name = table_name.split('_', 1)[1] # remove prefix
                raw_table_name = f"raw_{base_name}"
                raw_table_id = f"table:{schema.name}.{raw_table_name}"
                
                # We can't easily check if the raw table exists here without querying,
                # but we can optimistically create the relationship or check if we've processed it.
                # For this builder, we assume we process all entities.
                
                # Check if raw table exists in the DDA entities
                raw_entity_exists = any(e.name.lower().replace(' ', '_') == raw_table_name for e in dda_document.entities)
                
                if raw_entity_exists:
                    await self.kg_backend.add_relationship(
                        raw_table_id,
                        "transforms_into",
                        table_id,
                        {
                            "type": LineageType.TRANSFORMATION,
                            "logic": "dbt transformation", # Simulated logic
                            "layer": KnowledgeLayer.SEMANTIC
                        }
                    )

    async def _create_data_quality(
        self,
        dda_document: DDADocument,
        schema: Schema
    ) -> None:
        """Create data quality rules and scores."""
        import random
        from datetime import datetime
        
        for entity in dda_document.entities:
            table_name = entity.name.lower().replace(' ', '_')
            table_id = f"table:{schema.name}.{table_name}"
            
            # 1. Create Rules based on Business Rules
            for i, rule_text in enumerate(entity.business_rules):
                rule_name = f"dq_rule_{table_name}_{i}"
                dq_rule = DataQualityRule(
                    name=rule_name,
                    description=f"Rule derived from: {rule_text}",
                    expression=rule_text,
                    dimension="VALIDITY",
                    properties={"layer": KnowledgeLayer.REASONING}
                )
                
                rule_id = f"dq_rule:{rule_name}"
                await self.kg_backend.add_entity(rule_id, dq_rule.model_dump())
                
                # Link Rule -> Table
                await self.kg_backend.add_relationship(
                    rule_id,
                    "applies_to",
                    table_id,
                    {"layer": KnowledgeLayer.REASONING}
                )
                
                # 2. Generate Simulated Score
                score_val = random.uniform(0.8, 1.0) # Simulate high quality
                score = DataQualityScore(
                    rule_name=rule_name,
                    target_node=table_id,
                    score=score_val,
                    timestamp=datetime.now().isoformat(),
                    properties={"layer": KnowledgeLayer.REASONING}
                )
                
                score_id = f"dq_score:{rule_name}_{datetime.now().timestamp()}"
                await self.kg_backend.add_entity(score_id, score.model_dump())
                
                # Link Score -> Table
                await self.kg_backend.add_relationship(
                    table_id,
                    "has_quality_score",
                    score_id,
                    {"layer": KnowledgeLayer.REASONING}
                )
                
                # Link Score -> Rule
                await self.kg_backend.add_relationship(
                    score_id,
                    "evaluated_by",
                    rule_id,
                    {"layer": KnowledgeLayer.REASONING}
                )

    async def _create_usage_stats(
        self,
        dda_document: DDADocument,
        schema: Schema
    ) -> None:
        """Create usage statistics."""
        import random
        from datetime import datetime, timedelta
        
        for entity in dda_document.entities:
            table_name = entity.name.lower().replace(' ', '_')
            table_id = f"table:{schema.name}.{table_name}"
            
            # Simulate usage
            usage = UsageStats(
                target_node=table_id,
                query_count=random.randint(10, 1000),
                unique_users=random.randint(2, 50),
                last_accessed=(datetime.now() - timedelta(hours=random.randint(0, 48))).isoformat(),
                properties={"layer": KnowledgeLayer.APPLICATION}
            )
            
            usage_id = f"usage:{table_name}"
            await self.kg_backend.add_entity(usage_id, usage.model_dump())
            
            # Link Usage -> Table
            await self.kg_backend.add_relationship(
                table_id,
                "has_usage_stats",
                usage_id,
                {"layer": KnowledgeLayer.APPLICATION}
            )

