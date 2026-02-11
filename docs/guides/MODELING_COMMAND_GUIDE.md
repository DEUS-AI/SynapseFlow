# Modeling Command Feature - User Guide

## Overview

The Modeling Command feature enables automated creation and management of domain knowledge graphs from Data Delivery Agreement (DDA) documents. This feature integrates seamlessly with the multi-agent system, allowing Data Architects to create domain models that Data Engineers can then use for building knowledge graphs.

## Architecture

The Modeling Command feature follows a clean architecture pattern with three main layers:

1. **Command Layer**: Handles command dispatch and routing
2. **Processing Layer**: Parses DDA documents and extracts structured data
3. **Modeling Layer**: Creates and updates knowledge graphs using Graphiti

### Key Components

- **ModelingCommand**: Command to process DDA documents
- **ModelingCommandHandler**: Handles command execution
- **ModelingWorkflow**: Orchestrates the complete workflow
- **DomainModeler**: Creates and updates knowledge graphs
- **DDAParserFactory**: Manages document parsers
- **MarkdownDDAParser**: Parses Markdown DDA documents

## Installation & Setup

### Prerequisites

1. **Neo4j Database**: Running Neo4j instance
2. **Graphiti**: Knowledge graph management system
3. **Python Dependencies**: See `pyproject.toml`

### Environment Configuration

Create a `.env` file with the following variables:

```bash
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password
```

### Installation

```bash
# Install dependencies
uv sync

# Initialize Graphiti indices and constraints
uv run python -m src.interfaces.cli model --init-graphiti
```

## Usage

### Basic Usage

#### Create a New Domain Graph

```bash
# Process a DDA document and create a new knowledge graph
uv run python -m src.interfaces.cli model \
  --dda-path examples/customer_analytics_dda.md \
  --domain "Customer Analytics"
```

#### Update Existing Domain Graph

```bash
# Update an existing domain graph with new information
uv run python -m src.interfaces.cli model \
  --dda-path examples/updated_customer_analytics_dda.md \
  --domain "Customer Analytics" \
  --update-existing
```

#### Validate Only (No Graph Creation)

```bash
# Validate a DDA document without creating a graph
uv run python -m src.interfaces.cli model \
  --dda-path examples/customer_analytics_dda.md \
  --domain "Customer Analytics" \
  --validate-only
```

### Advanced Usage

#### Batch Processing

```python
from src.application.agents.data_architect.domain_modeler import DomainModeler
from src.domain.dda_models import DDADocument

# Create multiple domain graphs in batch
dda_documents = [dda1, dda2, dda3]  # List of DDADocument objects
results = await domain_modeler.batch_create_domain_graphs(dda_documents)
```

#### Cache Management

```python
from src.application.agents.data_architect.domain_modeler import DomainModeler

# Get cache statistics
cache_stats = domain_modeler.get_cache_stats()
print(f"Cache entries: {cache_stats['total_cache_entries']}")

# Clear cache
domain_modeler.clear_cache()
```

#### Backup Management

```python
from src.application.agents.data_architect.modeling_workflow import ModelingWorkflow

# List available backups
backups = await workflow.list_backups("Customer Analytics")
for backup in backups:
    print(f"Backup: {backup['filename']}, Created: {backup['created']}")

# Clean up old backups (keep last 30 days)
cleanup_result = await workflow.cleanup_old_backups(keep_days=30)
print(f"Deleted {cleanup_result['deleted_count']} old backups")
```

## DDA Document Format

### Markdown Format

The Modeling Command supports DDA documents in Markdown format with the following structure:

```markdown
# Domain Name Data Delivery Agreement

## Domain Information
- **Domain**: Domain Name
- **Data Owner**: Data Owner Name
- **Stakeholders**: Stakeholder 1, Stakeholder 2
- **Effective Date**: YYYY-MM-DD

## Business Context
Description of the business context and purpose of this domain.

## Data Entities

### EntityName
- **Description**: Description of the entity
- **Attributes**: attr1, attr2, attr3
- **Primary Key**: primary_key_attribute
- **Foreign Keys**: foreign_key1, foreign_key2
- **Business Rules**: 
  - Rule 1
  - Rule 2

## Relationships

### SourceEntity -> TargetEntity (1:N)
- **Description**: Description of the relationship
- **Type**: One-to-Many, Many-to-Many, One-to-One
- **Constraints**: Relationship constraints

## Data Quality Requirements

### Completeness
- Entity records: X% complete

### Accuracy
- Data accuracy: X% accurate

### Timeliness
- Updates: Within X hours

## Access Patterns

### Common Queries
- Query 1
- Query 2

### Performance Requirements
- Response time: < X seconds

## Governance

### Privacy
- Privacy requirements

### Security
- Security requirements

### Compliance
- Compliance requirements
```

### Example DDA Document

```markdown
# Customer Analytics Data Delivery Agreement

## Domain Information
- **Domain**: Customer Analytics
- **Data Owner**: VP of Customer Experience
- **Stakeholders**: Marketing Team, Sales Team, Customer Success
- **Effective Date**: 2024-01-15

## Business Context
This domain covers customer behavior analysis, purchase patterns, and engagement metrics to drive business decisions.

## Data Entities

### Customer
- **Description**: Individual customer records with demographic and behavioral data
- **Attributes**: customer_id, name, email, phone, address, registration_date
- **Primary Key**: customer_id
- **Business Rules**: 
  - Customer ID must be unique
  - Email must be valid format

### Product
- **Description**: Product catalog with pricing and category information
- **Attributes**: product_id, name, description, category, price
- **Primary Key**: product_id
- **Business Rules**:
  - Product ID must be unique
  - Price must be positive

## Relationships

### Customer -> Purchase (1:N)
- **Description**: A customer can make multiple purchases
- **Type**: One-to-Many
- **Constraints**: Customer must exist before purchase

## Data Quality Requirements

### Completeness
- Customer records: 95% complete
- Product records: 98% complete

### Accuracy
- Customer data: 90% accurate
- Product pricing: 99% accurate

### Timeliness
- Customer updates: Within 24 hours
- Product updates: Within 1 hour

## Access Patterns

### Common Queries
- Customer purchase history
- Product sales by category

### Performance Requirements
- Customer queries: < 2 seconds
- Product queries: < 1 second

## Governance

### Privacy
- Customer data encryption at rest
- PII masking in analytics

### Security
- Role-based access control
- Audit logging

### Compliance
- GDPR compliance
- PCI DSS for payment data
```

## Agent Collaboration

### Data Architect → Data Engineer

The Data Architect creates domain models that the Data Engineer can access:

```python
from src.application.agents.data_engineer.handlers.build_kg import BuildKGCommandHandler

# Data Engineer accesses domain models created by Data Architect
handler = BuildKGCommandHandler(graph)
result = await handler.handle(BuildKGCommand(
    domain="Customer Analytics",
    source_data={"content": "Customer purchase data", "type": "transaction"}
))
```

### Feedback Mechanism

Agents can provide feedback on each other's work:

```python
from src.application.commands.collaboration_commands import ModelingFeedbackCommand

# Provide feedback on domain modeling
feedback = ModelingFeedbackCommand(
    domain="Customer Analytics",
    episode_uuid="episode-uuid",
    feedback_type="entity_quality",
    feedback_content="Customer entity needs additional attributes",
    rating=4,
    suggestions=["Add customer_type attribute", "Include loyalty_status"]
)
```

## Performance Optimization

### Caching

The system automatically caches parsed DDA documents to improve performance:

- **Document Cache**: Caches parsed DDA content
- **Domain Cache**: Caches domain search results
- **Cache Statistics**: Monitor cache performance

### Batch Processing

For processing multiple documents:

```python
# Process multiple DDA documents in batch
results = await domain_modeler.batch_create_domain_graphs(dda_documents)
```

### Performance Targets

- **DDA Parsing**: < 5 seconds for 50-page documents
- **Graph Creation**: < 10 seconds for 100 entities
- **Validation**: < 2 seconds for complex documents
- **Memory Usage**: < 500MB for large documents

## Error Handling & Recovery

### Automatic Backup

The system automatically creates backups before updating existing graphs:

```bash
# Backup automatically created
Backup Created: backups/modeling/customer_analytics_20250721_001552.json
```

### Rollback Mechanism

If operations fail, the system attempts to rollback to the previous state:

```python
# Rollback information in workflow state
workflow_state = {
    "backup_created": True,
    "rollback_performed": True,
    "backup_path": "backups/modeling/domain_timestamp.json"
}
```

### Error Types

1. **Parsing Errors**: Invalid DDA document format
2. **Validation Errors**: Missing required fields or invalid data
3. **Graph Creation Errors**: Graphiti operation failures
4. **Network Errors**: Database connection issues

## Testing

### Unit Tests

```bash
# Run unit tests
uv run pytest tests/application/test_modeling_command.py -v
```

### Integration Tests

```bash
# Run integration tests
uv run pytest tests/integration/test_modeling_integration.py -v
```

### Performance Tests

```bash
# Run performance benchmarks
uv run pytest tests/performance/test_modeling_performance.py -v
```

## Monitoring & Observability

### Metrics

The system provides various metrics for monitoring:

- **Execution Time**: Time taken for each operation
- **Success/Failure Rates**: Success and failure statistics
- **Cache Hit Rates**: Cache performance metrics
- **Memory Usage**: Memory consumption during operations

### Logging

Structured logging is available for all operations:

```python
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Log modeling operations
logger.info("Modeling workflow started", extra={
    "domain": "Customer Analytics",
    "operation": "create_graph"
})
```

### Workflow State Tracking

Complete audit trail of all operations:

```python
workflow_state = {
    "start_time": "2024-01-15T10:00:00",
    "steps_completed": ["parse", "validate", "graph_creation", "artifacts"],
    "backup_created": True,
    "end_time": "2024-01-15T10:05:00",
    "success": True
}
```

## Best Practices

### DDA Document Design

1. **Clear Domain Boundaries**: Define clear domain scope and boundaries
2. **Comprehensive Entity Coverage**: Include all relevant entities
3. **Detailed Business Rules**: Specify clear business rules and constraints
4. **Relationship Documentation**: Document all entity relationships
5. **Quality Requirements**: Define data quality expectations

### Performance Optimization

1. **Use Caching**: Leverage built-in caching for repeated operations
2. **Batch Processing**: Use batch operations for multiple documents
3. **Regular Cleanup**: Clean up old backups periodically
4. **Monitor Performance**: Track performance metrics and optimize bottlenecks

### Error Handling

1. **Validate Early**: Use `--validate-only` to validate documents before processing
2. **Backup Strategy**: Ensure backups are created before updates
3. **Error Monitoring**: Monitor error rates and patterns
4. **Graceful Degradation**: Handle partial failures gracefully

### Collaboration

1. **Clear Communication**: Use structured feedback for agent collaboration
2. **Domain Consistency**: Ensure domain models are consistent across agents
3. **Version Control**: Track changes to domain models over time
4. **Documentation**: Maintain up-to-date documentation

## Troubleshooting

### Common Issues

#### Parsing Errors

**Problem**: DDA document parsing fails
**Solution**: Check document format and ensure it follows the required structure

#### Validation Errors

**Problem**: Document validation fails
**Solution**: Review error messages and fix missing or invalid fields

#### Graph Creation Errors

**Problem**: Knowledge graph creation fails
**Solution**: Check Neo4j connection and Graphiti configuration

#### Performance Issues

**Problem**: Slow processing times
**Solution**: Check cache usage, consider batch processing, monitor system resources

### Debug Mode

Enable debug logging for troubleshooting:

```bash
# Set debug environment variable
export LOG_LEVEL=DEBUG

# Run with debug output
uv run python -m src.interfaces.cli model --dda-path example.md --domain "Test"
```

## API Reference

### ModelingCommand

```python
class ModelingCommand(Command, BaseModel):
    dda_path: str
    domain: Optional[str] = None
    update_existing: bool = False
    validate_only: bool = False
    output_path: Optional[str] = None
```

### ModelingCommandHandler

```python
class ModelingCommandHandler(CommandHandler):
    async def handle(self, command: ModelingCommand) -> Dict[str, Any]
```

### DomainModeler

```python
class DomainModeler:
    async def create_domain_graph(self, dda_document: DDADocument) -> Dict[str, Any]
    async def update_domain_graph(self, dda_document: DDADocument) -> Dict[str, Any]
    async def batch_create_domain_graphs(self, dda_documents: List[DDADocument]) -> List[Dict[str, Any]]
    def clear_cache(self) -> None
    def get_cache_stats(self) -> Dict[str, Any]
```

### ModelingWorkflow

```python
class ModelingWorkflow:
    async def execute(self, command: ModelingCommand) -> Dict[str, Any]
    async def list_backups(self, domain: Optional[str] = None) -> List[Dict[str, Any]]
    async def cleanup_old_backups(self, keep_days: int = 30) -> Dict[str, Any]
```

## Contributing

### Development Setup

1. **Clone Repository**: Clone the project repository
2. **Install Dependencies**: Run `uv sync`
3. **Setup Database**: Configure Neo4j and Graphiti
4. **Run Tests**: Execute test suite
5. **Make Changes**: Implement new features or fixes
6. **Submit PR**: Create pull request with tests

### Code Style

- Follow PEP 8 style guidelines
- Use type hints for all functions
- Write comprehensive docstrings
- Include unit tests for new features

### Testing Guidelines

- Write unit tests for all new functionality
- Include integration tests for workflows
- Add performance tests for critical paths
- Maintain test coverage above 80%

## License

This project is licensed under the MIT License - see the LICENSE file for details. 