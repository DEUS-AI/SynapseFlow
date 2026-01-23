<!-- e09c8d81-f8d7-4f03-b7f2-ed794171e3d3 3371a34b-5830-4951-a5d0-8e0d2b01b44c -->
# ODIN Metadata Graph Implementation Plan

## Overview

Implement Phase 1 of ODIN metadata graph generation: core entities (Catalog, Schema, Table, Column, Constraint, DataType) with DDA → ODIN mapping, Graphiti-based type inference, and full A2A handoff workflow between Data Architect and Data Engineer agents.

## Architecture

- **Domain Layer**: ODIN models (core entities)
- **Application Layer**: MetadataGraphBuilder, MetadataGenerationWorkflow, command/handler
- **Infrastructure**: Uses existing KnowledgeGraphBackend (same instance as architecture graph)
- **Communication**: A2A protocol via agent servers

## Tasks

### Task 1: Create Core ODIN Domain Models

**Files**: `src/domain/odin_models.py`

Create Pydantic models for core ODIN entities:

- `Catalog`: name, description, properties
- `Schema`: name, catalog_name, description, properties  
- `Table`: name, schema_name, description, origin, properties
- `Column`: name, table_name, description, properties
- `DataType`: name (enum: VARCHAR, INTEGER, BIGINT, DECIMAL, DATE, TIMESTAMP, BOOLEAN), base_type, properties
- `TypeAssignment`: column_name, data_type_name, precision, scale, properties
- `Constraint`: name, constraint_type (enum: PRIMARY_KEY, FOREIGN_KEY, UNIQUE, NOT_NULL, CHECK), column_name, table_name, referenced_table, referenced_column, expression, properties

**Tests**: `tests/domain/test_odin_models.py`

- Test model validation
- Test enum values
- Test optional fields
- Test property defaults

**Coverage Target**: >90%

---

### Task 2: Implement Type Inference Service with Graphiti

**Files**: `src/application/agents/data_engineer/type_inference.py`

Create service that uses Graphiti LLM for intelligent type inference:

- `TypeInferenceService.__init__(llm: Graphiti)`
- `infer_data_type(attribute_name: str, context: Dict[str, Any]) -> DataType`: Uses Graphiti to infer type from attribute name and context
- `infer_precision(attribute_name: str, data_type: DataType, context: Dict[str, Any]) -> Optional[int]`: Infers precision using Graphiti
- `infer_scale(attribute_name: str, data_type: DataType) -> Optional[int]`: Infers scale for DECIMAL types

**Implementation Notes**:

- Use Graphiti's `process()` or `add_episode()` to get LLM inference
- Create prompt: "Given attribute name '{attribute_name}' in context '{context}', infer the most appropriate SQL data type"
- Parse LLM response to extract type, precision, scale

**Tests**: `tests/application/test_type_inference.py`

- Mock Graphiti LLM responses
- Test type inference for various attribute patterns (ID, email, date, amount, etc.)
- Test precision/scale inference
- Test error handling

**Coverage Target**: >80%

---

### Task 3: Implement MetadataGraphBuilder Core Logic

**Files**: `src/application/agents/data_engineer/metadata_graph_builder.py`

Create builder class that maps DDA → ODIN entities:

- `MetadataGraphBuilder.__init__(kg_backend: KnowledgeGraphBackend, type_inference: TypeInferenceService)`
- `build_metadata_graph(dda_document: DDADocument) -> Dict[str, Any]`: Main orchestration method
- `_create_catalog(dda_document: DDADocument) -> Catalog`: Creates catalog from domain
- `_create_schema(dda_document: DDADocument, catalog_name: str) -> Schema`: Creates schema from domain
- `_create_table(dda_document: DDADocument, entity: DataEntity, schema_name: str) -> Table`: Creates table from entity
- `_create_column(entity: DataEntity, attribute: str, table_name: str) -> Column`: Creates column from attribute
- `_create_type_assignment(column: Column, attribute: str, context: Dict) -> TypeAssignment`: Uses TypeInferenceService
- `_create_constraints(entity: DataEntity, attribute: str, column: Column, table_name: str, dda_document: DDADocument) -> List[Constraint]`: Creates constraints from PKs, FKs, business rules

**Helper Methods**:

- `_parse_attribute_name(attribute: str) -> str`: Handles formats like "Customer ID (Primary Key)"
- `_matches_attribute(attribute: str, key: str) -> bool`: Checks if attribute matches key
- `_find_referenced_table(fk: str, dda_document: DDADocument) -> Optional[str]`: Finds referenced table from FK
- `_parse_business_rule_to_constraint(rule: str, column_name: str, table_name: str) -> Optional[Constraint]`: Parses business rules

**Implementation Notes**:

- Use `kg_backend.add_entity()` and `kg_backend.add_relationship()` to persist
- Entity IDs format: `catalog:{name}`, `schema:{name}`, `table:{schema}.{name}`, `column:{table}.{name}`, etc.
- Relationship types: `belongs_to`, `has_column`, `has_type_assignment`, `typed_as`, `constrained_by`

**Tests**: `tests/application/test_metadata_graph_builder.py`

- Test catalog creation
- Test schema creation with belongs_to relationship
- Test table creation from entity
- Test column creation from attributes
- Test type assignment creation
- Test constraint creation (PK, FK, business rules)
- Test helper methods
- Mock kg_backend and type_inference
- Test error handling

**Coverage Target**: >75%

---

### Task 4: Create GenerateMetadataCommand and Handler

**Files**:

- `src/application/commands/metadata_command.py`
- `src/application/agents/data_engineer/handlers/generate_metadata.py`

**Command**:

```python
class GenerateMetadataCommand(Command, BaseModel):
    dda_path: str
    domain: str
    architecture_graph_ref: Optional[str] = None  # group_id or episode_uuid
    validate_against_architecture: bool = True
```

**Handler**:

- `GenerateMetadataCommandHandler.__init__(workflow: MetadataGenerationWorkflow)`
- `handle(command: GenerateMetadataCommand) -> Dict[str, Any]`

**Tests**: `tests/application/test_generate_metadata_command.py`

- Test command validation
- Test handler execution
- Test error handling

**Coverage Target**: >80%

---

### Task 5: Implement MetadataGenerationWorkflow

**Files**: `src/application/agents/data_engineer/metadata_workflow.py`

Orchestrates the complete workflow:

- `MetadataGenerationWorkflow.__init__(parser_factory: DDAParserFactory, metadata_builder: MetadataGraphBuilder, graph: Graphiti, kg_backend: KnowledgeGraphBackend)`
- `execute(command: GenerateMetadataCommand) -> Dict[str, Any]`:

  1. Parse DDA document using parser_factory
  2. (Optional) Read architecture graph from Graphiti if reference provided
  3. (Optional) Validate DDA against architecture graph
  4. Call metadata_builder.build_metadata_graph()
  5. Return results

**Helper Methods**:

- `_read_architecture_graph(graph_ref: str) -> Dict[str, Any]`: Query Graphiti for architecture graph nodes
- `_validate_against_architecture(dda_document: DDADocument, architecture_graph: Dict) -> Dict[str, Any]`: Basic validation

**Tests**: `tests/application/test_metadata_workflow.py`

- Test full workflow execution
- Test DDA parsing integration
- Test architecture graph reading (mock Graphiti)
- Test validation logic
- Test error handling and rollback

**Coverage Target**: >75%

---

### Task 6: Integrate Command into Data Engineer Agent

**Files**: `src/application/agents/data_engineer/agent.py`, `src/composition_root.py`

**Changes**:

1. Register `GenerateMetadataCommand` and handler in composition root
2. Add handler to Data Engineer's command bus
3. Update Data Engineer server's `/.well-known/agent.json` to include new tool

**Tests**: `tests/application/test_data_engineer_metadata_integration.py`

- Test command registration
- Test command dispatch from command bus
- Test A2A endpoint receives command

**Coverage Target**: >70%

---

### Task 7: Implement Data Architect Handoff Logic

**Files**: `src/application/agents/data_architect/modeling_workflow.py`, `src/application/agents/data_architect/agent.py`

**Changes**:

1. After `DomainModeler.create_domain_graph()` completes, Data Architect should:

   - Get architecture graph reference (episode_uuid or group_id)
   - Discover Data Engineer agent via A2A (query `/.well-known/agent.json`)
   - Send `GenerateMetadataCommand` via A2A channel to Data Engineer

2. Update `ModelingWorkflow.execute()` to trigger handoff after graph creation

**Implementation**:

- Use `A2ACommunicationChannel` to send message
- Message content: `GenerateMetadataCommand` serialized
- Include `dda_path`, `domain`, `architecture_graph_ref` in message

**Tests**: `tests/application/test_data_architect_handoff.py`

- Test handoff after architecture graph creation
- Test A2A message sending
- Test command serialization
- Mock A2A channel

**Coverage Target**: >75%

---

### Task 8: End-to-End Integration Tests

**Files**: `tests/integration/test_metadata_generation_e2e.py`

Test complete flow:

1. Data Architect processes DDA → creates architecture graph
2. Data Architect hands off to Data Engineer via A2A
3. Data Engineer receives command, generates metadata graph
4. Verify metadata graph entities and relationships created correctly

**Setup**:

- Use `InMemoryGraphBackend` for testing
- Mock Graphiti instances
- Use `InMemoryCommunicationChannel` or mock A2A

**Coverage Target**: >70%

---

## Testing Requirements

- All tests must pass (green)
- Overall coverage >70% for new code
- Use existing test patterns (unittest.IsolatedAsyncioTestCase)
- Mock external dependencies (Graphiti, kg_backend, A2A channel)
- Test both success and error paths

## Code Style

- Follow existing patterns in `domain_modeler.py`, `modeling_workflow.py`
- Use type hints
- Follow clean architecture (domain → application → infrastructure)
- Use async/await consistently
- Add docstrings to public methods

## Dependencies

- Existing: `domain.dda_models`, `domain.kg_backends`, `graphiti_core`, `application.commands.base`
- No new external dependencies required

## Success Criteria

- All 8 tasks completed
- All tests passing with >70% coverage
- Metadata graph correctly created from DDA documents
- Full handoff workflow functional via A2A
- Code follows clean architecture principles

### To-dos

- [ ] Create core ODIN domain models (Catalog, Schema, Table, Column, DataType, TypeAssignment, Constraint) with Pydantic validation and tests
- [ ] Implement TypeInferenceService using Graphiti LLM for intelligent data type inference from attribute names and context
- [ ] Implement MetadataGraphBuilder with DDA → ODIN mapping logic (catalog, schema, table, column, constraints creation)
- [ ] Create GenerateMetadataCommand and handler for Data Engineer agent
- [ ] Implement MetadataGenerationWorkflow orchestrating DDA parsing, architecture graph reading, validation, and metadata graph building
- [ ] Integrate GenerateMetadataCommand into Data Engineer agent server and command bus registration
- [ ] Implement Data Architect handoff logic to send GenerateMetadataCommand to Data Engineer via A2A after architecture graph creation
- [ ] Create end-to-end integration tests for complete workflow: DDA → Architecture Graph → Metadata Graph via A2A handoff