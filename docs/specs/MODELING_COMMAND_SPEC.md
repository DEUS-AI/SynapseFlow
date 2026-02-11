# Modeling Command Feature - Technical Specification

## Architecture Overview

The Modeling Command feature follows the existing clean architecture pattern and integrates seamlessly with the current agent infrastructure. The feature consists of three main components:

1. **Command Layer**: Handles command dispatch and routing
2. **Processing Layer**: Parses DDA documents and extracts structured data
3. **Modeling Layer**: Creates and updates knowledge graphs using Graphiti

## Component Design

### 1. Command Infrastructure

#### ModelingCommand
```python
from pydantic import BaseModel, Field
from typing import Optional
from src.domain.commands import Command

class ModelingCommand(Command, BaseModel):
    """Command to process DDA documents and create/update knowledge graphs."""
    
    dda_path: str = Field(..., description="Path to the DDA document")
    domain: Optional[str] = Field(None, description="Explicit domain specification")
    update_existing: bool = Field(False, description="Update existing graph vs create new")
    validate_only: bool = Field(False, description="Only validate without creating graph")
    output_path: Optional[str] = Field(None, description="Path for output artifacts")
    
    class Config:
        json_schema_extra = {
            "example": {
                "dda_path": "examples/customer_analytics_dda.md",
                "domain": "Customer Analytics",
                "update_existing": False,
                "validate_only": False
            }
        }
```

#### ModelingCommandHandler
```python
from application.commands.base import CommandHandler
from application.agents.data_architect.modeling_workflow import ModelingWorkflow

class ModelingCommandHandler(CommandHandler):
    """Handles ModelingCommand execution."""
    
    def __init__(self, modeling_workflow: ModelingWorkflow):
        self.modeling_workflow = modeling_workflow
    
    async def handle(self, command: ModelingCommand) -> ModelingResult:
        """Execute the modeling workflow."""
        try:
            result = await self.modeling_workflow.execute(command)
            return result
        except Exception as e:
            raise ModelingError(f"Modeling workflow failed: {str(e)}") from e
```

### 2. DDA Processing Layer

#### DDADocument Model
```python
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime

class DataEntity(BaseModel):
    """Represents a data entity from the DDA."""
    name: str
    description: str
    attributes: List[str]
    business_rules: List[str]
    primary_key: Optional[str] = None
    foreign_keys: List[str] = Field(default_factory=list)

class Relationship(BaseModel):
    """Represents a relationship between entities."""
    source_entity: str
    target_entity: str
    relationship_type: str  # 1:1, 1:N, M:N
    description: str
    constraints: List[str] = Field(default_factory=list)

class DDADocument(BaseModel):
    """Complete DDA document structure."""
    domain: str
    stakeholders: List[str]
    data_owner: str
    effective_date: datetime
    business_context: str
    entities: List[DataEntity]
    relationships: List[Relationship]
    data_quality_requirements: Dict[str, Any]
    access_patterns: Dict[str, Any]
    governance: Dict[str, Any]
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
```

#### DDAParser Interface
```python
from abc import ABC, abstractmethod
from typing import List
from domain.dda_models import DDADocument

class DDAParser(ABC):
    """Abstract interface for DDA document parsers."""
    
    @abstractmethod
    async def parse(self, file_path: str) -> DDADocument:
        """Parse a DDA document and return structured data."""
        pass
    
    @abstractmethod
    def supports_format(self, file_path: str) -> bool:
        """Check if this parser supports the given file format."""
        pass
    
    @abstractmethod
    def get_supported_formats(self) -> List[str]:
        """Return list of supported file formats."""
        pass
```

### 3. Modeling Layer

#### DomainModeler
```python
from graphiti.graph import Graph
from graphiti.llm import LLM
from domain.dda_models import DDADocument
from typing import List, Dict, Any

class DomainModeler:
    """Creates and updates domain knowledge graphs from DDA documents."""
    
    def __init__(self, graph: Graph, llm: LLM):
        self.graph = graph
        self.llm = llm
    
    async def create_domain_graph(self, dda_document: DDADocument) -> GraphDocument:
        """Create a new domain knowledge graph from DDA document."""
        
        # 1. Create domain node
        domain_node = await self.graph.upsert_node(
            "Domain",
            dda_document.domain,
            {
                "description": dda_document.business_context,
                "stakeholders": dda_document.stakeholders,
                "data_owner": dda_document.data_owner,
                "effective_date": dda_document.effective_date.isoformat()
            }
        )
        
        # 2. Create entity nodes
        entity_nodes = []
        for entity in dda_document.entities:
            entity_node = await self.graph.upsert_node(
                "DataEntity",
                entity.name,
                {
                    "description": entity.description,
                    "attributes": entity.attributes,
                    "business_rules": entity.business_rules,
                    "primary_key": entity.primary_key,
                    "foreign_keys": entity.foreign_keys
                }
            )
            entity_nodes.append(entity_node)
            
            # Create relationship to domain
            await self.graph.upsert_relationship(
                "BELONGS_TO",
                entity_node.id,
                domain_node.id
            )
        
        # 3. Create relationship nodes
        for relationship in dda_document.relationships:
            await self.graph.upsert_relationship(
                relationship.relationship_type,
                f"{relationship.source_entity}_{relationship.target_entity}",
                {
                    "description": relationship.description,
                    "constraints": relationship.constraints
                }
            )
        
        return GraphDocument(
            nodes=[domain_node] + entity_nodes,
            relationships=dda_document.relationships
        )
    
    async def update_domain_graph(self, dda_document: DDADocument) -> GraphDocument:
        """Update existing domain knowledge graph with new DDA information."""
        # Implementation for updating existing graphs
        pass
```

#### ModelingWorkflow
```python
from typing import List
from domain.dda_models import DDADocument
from application.agents.data_architect.dda_parser import DDAParserFactory
from application.agents.data_architect.domain_modeler import DomainModeler

class ModelingWorkflow:
    """Orchestrates the complete modeling workflow."""
    
    def __init__(self, parser_factory: DDAParserFactory, domain_modeler: DomainModeler):
        self.parser_factory = parser_factory
        self.domain_modeler = domain_modeler
    
    async def execute(self, command: ModelingCommand) -> ModelingResult:
        """Execute the complete modeling workflow."""
        
        # 1. Parse DDA document
        parser = self.parser_factory.get_parser(command.dda_path)
        dda_document = await parser.parse(command.dda_path)
        
        # 2. Validate document
        validation_result = await self._validate_dda_document(dda_document)
        if not validation_result.is_valid:
            return ModelingResult(
                success=False,
                errors=validation_result.errors,
                warnings=validation_result.warnings
            )
        
        # 3. Create or update knowledge graph
        if command.update_existing:
            graph_document = await self.domain_modeler.update_domain_graph(dda_document)
        else:
            graph_document = await self.domain_modeler.create_domain_graph(dda_document)
        
        # 4. Generate output artifacts
        artifacts = await self._generate_artifacts(dda_document, graph_document, command)
        
        return ModelingResult(
            success=True,
            graph_document=graph_document,
            artifacts=artifacts,
            warnings=validation_result.warnings
        )
    
    async def _validate_dda_document(self, dda_document: DDADocument) -> ValidationResult:
        """Validate the parsed DDA document."""
        errors = []
        warnings = []
        
        # Check required fields
        if not dda_document.domain:
            errors.append("Domain is required")
        
        if not dda_document.entities:
            errors.append("At least one data entity is required")
        
        # Check entity consistency
        entity_names = {entity.name for entity in dda_document.entities}
        for relationship in dda_document.relationships:
            if relationship.source_entity not in entity_names:
                errors.append(f"Relationship references unknown entity: {relationship.source_entity}")
            if relationship.target_entity not in entity_names:
                errors.append(f"Relationship references unknown entity: {relationship.target_entity}")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
```

## Integration Points

### 1. Command Bus Integration
```python
# In composition_root.py
def create_modeling_command_handler() -> ModelingCommandHandler:
    parser_factory = DDAParserFactory()
    domain_modeler = DomainModeler(graph, llm)
    workflow = ModelingWorkflow(parser_factory, domain_modeler)
    return ModelingCommandHandler(workflow)

# Register command and handler
command_bus.register_handler(ModelingCommand, create_modeling_command_handler())
```

### 2. Agent Integration
```python
# In DataArchitectAgent
async def process_modeling_command(self, command: ModelingCommand) -> None:
    """Process modeling commands in the Data Architect agent."""
    handler = self.command_bus.get_handler(ModelingCommand)
    result = await handler.handle(command)
    
    if result.success:
        print(f"[{self.agent_id}] Successfully created/updated domain graph")
        print(f"  - Domain: {result.graph_document.domain}")
        print(f"  - Entities: {len(result.graph_document.entities)}")
        print(f"  - Relationships: {len(result.graph_document.relationships)}")
    else:
        print(f"[{self.agent_id}] Modeling failed: {result.errors}")
```

### 3. CLI Integration
```python
# In cli.py
@cli.command()
@click.argument('dda_path', type=click.Path(exists=True))
@click.option('--domain', help='Explicit domain specification')
@click.option('--update-existing', is_flag=True, help='Update existing graph')
@click.option('--validate-only', is_flag=True, help='Only validate without creating graph')
def model(dda_path: str, domain: str, update_existing: bool, validate_only: bool):
    """Process DDA document and create/update knowledge graph."""
    command = ModelingCommand(
        dda_path=dda_path,
        domain=domain,
        update_existing=update_existing,
        validate_only=validate_only
    )
    
    # Execute command through agent runner
    asyncio.run(execute_modeling_command(command))
```

## Error Handling

### ModelingError Hierarchy
```python
class ModelingError(Exception):
    """Base exception for modeling operations."""
    pass

class DDAParsingError(ModelingError):
    """Raised when DDA document parsing fails."""
    pass

class ValidationError(ModelingError):
    """Raised when DDA document validation fails."""
    pass

class GraphCreationError(ModelingError):
    """Raised when knowledge graph creation fails."""
    pass
```

### Error Recovery
- Automatic backup of existing graphs before updates
- Rollback mechanism for failed operations
- Detailed error logging with context
- Graceful degradation for partial failures

## Performance Considerations

### Optimization Strategies
1. **Caching**: Cache parsed DDA documents to avoid re-parsing
2. **Batch Operations**: Batch graph operations for better performance
3. **Async Processing**: Use async/await for I/O operations
4. **Memory Management**: Stream large documents to avoid memory issues

### Performance Targets
- DDA parsing: < 5 seconds for 50-page documents
- Graph creation: < 10 seconds for 100 entities
- Validation: < 2 seconds for complex documents
- Memory usage: < 500MB for large documents

## Testing Strategy

### Unit Tests
- Command and handler logic
- Document parsing functionality
- Graph modeling algorithms
- Validation rules

### Integration Tests
- End-to-end modeling workflow
- Agent collaboration scenarios
- Graphiti integration
- Error handling and recovery

### Performance Tests
- Document processing performance
- Graph creation with large datasets
- Concurrent modeling operations

## Security Considerations

### Input Validation
- Validate file paths to prevent directory traversal
- Sanitize document content to prevent injection attacks
- Validate file sizes to prevent DoS attacks

### Access Control
- Verify user permissions for graph operations
- Audit all modeling operations
- Encrypt sensitive data in transit and at rest

## Monitoring and Observability

### Metrics
- Modeling command execution time
- Success/failure rates
- Document processing performance
- Graph creation statistics

### Logging
- Structured logging for all operations
- Error tracking with context
- Performance monitoring
- Audit trail for compliance 