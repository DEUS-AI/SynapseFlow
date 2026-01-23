# Metadata Models

Este módulo contiene todos los modelos de metadatos para el grafo de conocimiento del sistema multi-agente. Los modelos representan la estructura completa de un catálogo de datos, incluyendo infraestructura, esquemas, tablas, columnas y flujos de trabajo.

## Estructura de Archivos

```
src/domain/metadata/
├── __init__.py           # Exports de todos los modelos
├── base.py               # Clase base MetadataEntity
├── database.py           # Database y Cluster
├── schema.py             # Schema
├── table.py              # Table, Column y ColumnStats
├── metadata_objects.py   # Tag, Watermark y Description
├── workflow.py           # User y AirflowDag
├── relationships.py      # MetadataRelationship y RelationshipTypes
└── README.md            # Esta documentación
```

## Modelos de Entidades

### 1. MetadataEntity (Base)
Clase base para todas las entidades de metadatos con campos comunes:
- `id`: Identificador único
- `name`: Nombre legible
- `description`: Descripción opcional
- `created_at` / `updated_at`: Timestamps
- `tags`: Lista de etiquetas
- `properties`: Propiedades adicionales
- `entity_type`: Tipo de entidad

### 2. Infraestructura de Base de Datos

#### Cluster
Representa un cluster computacional que aloja bases de datos:
```python
from src.domain.metadata import Cluster

cluster = Cluster(
    name="Production Cluster East",
    description="Primary production cluster",
    cluster_type="production",
    region="us-east-1",
    environment="prod"
)
```

#### Database
Representa una instancia de base de datos:
```python
from src.domain.metadata import Database

database = Database(
    name="customer_analytics_db",
    description="Customer analytics database",
    database_type="postgresql",
    version="14.0",
    cluster_id=cluster.id
)
```

### 3. Estructura de Datos

#### Schema
Contenedor lógico para objetos de base de datos:
```python
from src.domain.metadata import Schema

schema = Schema(
    name="analytics_schema",
    description="Analytics schema",
    database_id=database.id,
    schema_name="analytics"
)
```

#### Table
Tabla de base de datos con columnas:
```python
from src.domain.metadata import Table

table = Table(
    name="customers",
    description="Customer information table",
    schema_id=schema.id,
    table_name="customers",
    storage_format="parquet"
)
```

#### Column
Columna de una tabla:
```python
from src.domain.metadata import Column

column = Column(
    name="customer_id",
    description="Unique customer identifier",
    table_id=table.id,
    column_name="customer_id",
    data_type="integer",
    nullable=False,
    primary_key=True,
    position=1
)
```

#### ColumnStats
Estadísticas de una columna:
```python
from src.domain.metadata import ColumnStats

stats = ColumnStats(
    name="customer_id_stats",
    description="Statistics for customer_id column",
    column_id=column.id,
    row_count=1000000,
    null_count=0,
    unique_count=1000000,
    data_type="integer"
)
```

### 4. Objetos de Metadatos

#### Tag
Etiquetas para categorizar entidades:
```python
from src.domain.metadata import Tag

tag = Tag(
    name="PII",
    description="Personally Identifiable Information",
    tag_name="PII",
    tag_type="governance",
    color="#FF0000",
    category="data_privacy"
)
```

#### Watermark
Información sobre frescura de datos:
```python
from src.domain.metadata import Watermark

watermark = Watermark(
    name="customer_table_watermark",
    description="Last update watermark",
    watermark_type="last_updated",
    watermark_value="2024-01-15T10:30:00",
    watermark_format="iso_timestamp",
    entity_id=table.id,
    entity_type="Table"
)
```

#### Description
Descripciones detalladas de entidades:
```python
from src.domain.metadata import Description

description = Description(
    name="customer_table_description",
    description="Description for customer table",
    content="This table contains customer information...",
    entity_id=table.id,
    entity_type="Table",
    author="data_analyst_001"
)
```

### 5. Flujos de Trabajo

#### User
Usuario del sistema con permisos:
```python
from src.domain.metadata import User

user = User(
    name="john_doe",
    description="Data Analyst",
    username="john_doe",
    email="john.doe@company.com",
    full_name="John Doe",
    role="Data Analyst",
    department="Data Team"
)
```

#### AirflowDag
Pipeline de datos automatizado:
```python
from src.domain.metadata import AirflowDag

dag = AirflowDag(
    name="customer_etl_pipeline",
    description="ETL pipeline for customer data",
    dag_id="customer_etl_pipeline",
    schedule_interval="0 2 * * *",
    owner="data_engineering_team"
)
```

### 6. Relaciones

#### MetadataRelationship
Representa las conexiones entre entidades:
```python
from src.domain.metadata import MetadataRelationship, RelationshipTypes

relationship = MetadataRelationship(
    source_entity_id=database.id,
    source_entity_type="Database",
    target_entity_id=cluster.id,
    target_entity_type="Cluster",
    relationship_type=RelationshipTypes.HAS_CLUSTER
)
```

#### RelationshipTypes
Constantes para tipos de relaciones predefinidas:
```python
from src.domain.metadata import RelationshipTypes

# Tipos disponibles
print(RelationshipTypes.get_all_types())

# Verificar si un tipo es válido
is_valid = RelationshipTypes.is_valid_type("has_cluster")
```

## Uso del Sistema

### Crear una Jerarquía Completa

```python
from src.domain.metadata import *

# 1. Crear cluster
cluster = Cluster(
    name="Production Cluster",
    description="Main production cluster",
    cluster_type="production",
    region="us-east-1",
    environment="prod"
)

# 2. Crear base de datos
database = Database(
    name="analytics_db",
    description="Analytics database",
    database_type="postgresql",
    cluster_id=cluster.id
)

# 3. Crear esquema
schema = Schema(
    name="public",
    description="Public schema",
    database_id=database.id,
    schema_name="public"
)

# 4. Crear tabla
table = Table(
    name="customers",
    description="Customer table",
    schema_id=schema.id,
    table_name="customers"
)

# 5. Crear columna
column = Column(
    name="customer_id",
    description="Customer ID",
    table_id=table.id,
    column_name="customer_id",
    data_type="integer",
    primary_key=True
)

# 6. Establecer relaciones
cluster.add_database(database.id)
database.add_schema(schema.id)
schema.add_table(table.id)
table.add_column(column.id)
```

### Operaciones de Metadatos

```python
# Agregar etiquetas
table.add_tag("customer")
table.add_tag("core")

# Agregar permisos
user.add_permission("read")
user.add_permission("write")

# Configurar DAG
dag.add_read_table(table.id)
dag.add_write_table(table.id)

# Crear estadísticas
stats = ColumnStats(
    name="customer_id_stats",
    column_id=column.id,
    row_count=1000000,
    data_type="integer"
)
column.set_stats(stats.id)
```

## Validación y Serialización

Todos los modelos usan Pydantic para validación automática:

```python
# Validación automática
try:
    table = Table(
        name="test",
        schema_id="invalid_id",  # Esto fallará si no es un UUID válido
        table_name="test"
    )
except ValidationError as e:
    print(f"Error de validación: {e}")

# Serialización a dict
table_dict = table.to_dict()

# Serialización a JSON
import json
table_json = json.dumps(table_dict, indent=2)
```

## Extensibilidad

Los modelos están diseñados para ser extensibles:

1. **Propiedades personalizadas**: Use el campo `properties` para metadatos específicos
2. **Nuevos tipos de entidades**: Herede de `MetadataEntity`
3. **Nuevos tipos de relaciones**: Agregue a `RelationshipTypes`
4. **Validaciones personalizadas**: Use decoradores de Pydantic

## Integración con el Sistema

Estos modelos se integran con:

- **Graphiti**: Backend principal del grafo de conocimiento
- **Neo4j**: Backend alternativo para desarrollo
- **Agentes**: Data Architect, Data Engineer, Knowledge Manager
- **Event Bus**: Sistema de eventos para actualizaciones asíncronas
- **API REST**: Endpoints para operaciones CRUD

## Próximos Pasos

1. **Metadata Parser**: Implementar parser que convierta DDAs en metadatos
2. **Metadata Modeler**: Crear modelador que mapee a Graphiti/Neo4j
3. **API Graph**: Implementar endpoints REST para metadatos
4. **Integración**: Conectar con el sistema de agentes existente
5. **Testing**: Crear tests unitarios y de integración
