# Metadata Tests

Este directorio contiene todos los tests unitarios para los modelos de metadatos del sistema.

## Estructura de Tests

```
tests/domain/metadata/
├── __init__.py                 # Inicialización del paquete de tests
├── conftest.py                 # Configuración pytest y fixtures
├── run_tests.py                # Script para ejecutar todos los tests
├── test_base.py                # Tests para MetadataEntity
├── test_database.py            # Tests para Cluster y Database
├── test_schema_table.py        # Tests para Schema, Table, Column y ColumnStats
├── test_metadata_objects.py    # Tests para Tag, Watermark y Description
├── test_workflow.py            # Tests para User y AirflowDag
├── test_relationships.py       # Tests para MetadataRelationship y RelationshipTypes
├── test_integration.py         # Tests de integración del sistema completo
└── README.md                   # Este archivo
```

## Ejecutar Tests

### Ejecutar todos los tests

```bash
# Desde la raíz del proyecto
uv run python tests/domain/metadata/run_tests.py

# O usando pytest directamente
uv run pytest tests/domain/metadata/ -v
```

### Ejecutar tests específicos

```bash
# Test específico
uv run python tests/domain/metadata/run_tests.py test_base

# Usando pytest
uv run pytest tests/domain/metadata/test_base.py -v
uv run pytest tests/domain/metadata/test_database.py -v
```

### Ejecutar tests con coverage

```bash
# Instalar coverage si no está disponible
uv add coverage

# Ejecutar tests con coverage
uv run coverage run -m pytest tests/domain/metadata/ -v
uv run coverage report
uv run coverage html  # Genera reporte HTML
```

## Tipos de Tests

### 1. Tests Unitarios Individuales

- **`test_base.py`**: Tests para la clase base `MetadataEntity`
  - Creación de entidades
  - Gestión de tags y propiedades
  - Serialización
  - Validación

- **`test_database.py`**: Tests para `Cluster` y `Database`
  - Gestión de clusters y bases de datos
  - Relaciones entre entidades
  - Propiedades personalizadas

- **`test_schema_table.py`**: Tests para `Schema`, `Table`, `Column` y `ColumnStats`
  - Jerarquía de esquemas y tablas
  - Gestión de columnas y estadísticas
  - Relaciones y dependencias

- **`test_metadata_objects.py`**: Tests para `Tag`, `Watermark` y `Description`
  - Sistema de etiquetado
  - Gestión de watermarks
  - Sistema de descripciones

- **`test_workflow.py`**: Tests para `User` y `AirflowDag`
  - Gestión de usuarios y permisos
  - Workflows de Airflow
  - Integración de usuarios y DAGs

- **`test_relationships.py`**: Tests para `MetadataRelationship` y `RelationshipTypes`
  - Tipos de relaciones predefinidos
  - Creación y gestión de relaciones
  - Validación de tipos

### 2. Tests de Integración

- **`test_integration.py`**: Tests del sistema completo
  - Jerarquía completa de metadatos
  - Sistema de etiquetado integrado
  - Gestión de watermarks
  - Workflows y permisos
  - Relaciones entre entidades
  - Propiedades personalizadas
  - Validación e integridad
  - Serialización
  - Rendimiento y extensibilidad

## Fixtures de Pytest

El archivo `conftest.py` proporciona fixtures reutilizables:

- **`sample_metadata_entities`**: Entidades de ejemplo para testing
- **`sample_relationships`**: Relaciones de ejemplo para testing
- **`relationship_types`**: Acceso a los tipos de relaciones

## Cobertura de Tests

Los tests cubren:

- ✅ **Creación de entidades**: Todos los modelos pueden ser instanciados correctamente
- ✅ **Validación**: Campos requeridos y tipos de datos
- ✅ **Métodos de negocio**: Funcionalidades específicas de cada modelo
- ✅ **Gestión de propiedades**: Sistema de propiedades personalizadas
- ✅ **Sistema de tags**: Etiquetado de entidades
- ✅ **Relaciones**: Creación y gestión de relaciones entre entidades
- ✅ **Serialización**: Conversión a diccionarios y JSON
- ✅ **Integración**: Funcionamiento del sistema completo
- ✅ **Extensibilidad**: Propiedades y tags personalizados
- ✅ **Rendimiento**: Manejo de grandes volúmenes de datos

## Estándares de Testing

### Convenciones de Naming

- **Clases de test**: `Test{ModelName}` (ej: `TestMetadataEntity`)
- **Métodos de test**: `test_{functionality}` (ej: `test_entity_creation`)
- **Fixtures**: Nombres descriptivos en snake_case

### Estructura de Tests

```python
class TestModelName(unittest.TestCase):
    """Test cases for ModelName."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Preparar datos de prueba
        
    def test_functionality(self):
        """Test specific functionality."""
        # Arrange
        # Act
        # Assert
        
    def tearDown(self):
        """Clean up after tests."""
        # Limpiar recursos si es necesario
```

### Assertions Utilizados

- `self.assertEqual()`: Verificar igualdad exacta
- `self.assertIn()`: Verificar pertenencia a colecciones
- `self.assertIsInstance()`: Verificar tipos
- `self.assertTrue()` / `self.assertFalse()`: Verificar valores booleanos
- `self.assertRaises()`: Verificar excepciones

## Debugging de Tests

### Ejecutar tests con más detalle

```bash
# Verbosidad máxima
uv run pytest tests/domain/metadata/ -vvv

# Mostrar output de print statements
uv run pytest tests/domain/metadata/ -s

# Ejecutar solo tests que fallen
uv run pytest tests/domain/metadata/ --lf
```

### Tests específicos para debugging

```bash
# Ejecutar test específico con más detalle
uv run pytest tests/domain/metadata/test_base.py::TestMetadataEntity::test_entity_creation -vvv -s

# Ejecutar tests que contengan cierto patrón
uv run pytest tests/domain/metadata/ -k "creation" -v
```

## Mantenimiento de Tests

### Agregar nuevos tests

1. Crear archivo `test_{model_name}.py`
2. Seguir las convenciones de naming
3. Incluir tests para todas las funcionalidades del modelo
4. Agregar tests de integración si es necesario

### Actualizar tests existentes

1. Mantener compatibilidad hacia atrás
2. Actualizar fixtures si cambian los modelos
3. Verificar que todos los tests pasen después de cambios

### Refactoring de tests

1. Extraer código común a fixtures
2. Agrupar tests relacionados en clases
3. Mantener tests independientes y aislados

## Integración con CI/CD

Los tests están diseñados para ejecutarse en pipelines de CI/CD:

```yaml
# Ejemplo de GitHub Actions
- name: Run Metadata Tests
  run: |
    uv run pytest tests/domain/metadata/ -v --tb=short
    uv run coverage run -m pytest tests/domain/metadata/
    uv run coverage report --fail-under=90
```

## Reportes y Métricas

### Generar reportes de coverage

```bash
# Reporte en consola
uv run coverage report

# Reporte HTML (abrir htmlcov/index.html)
uv run coverage html

# Reporte XML para CI/CD
uv run coverage xml
```

### Métricas de calidad

- **Cobertura de código**: Objetivo >90%
- **Tests por modelo**: Mínimo 10 tests por modelo
- **Tests de integración**: Cubrir todos los flujos principales
- **Tiempo de ejecución**: <30 segundos para todos los tests

## Troubleshooting

### Problemas comunes

1. **Import errors**: Verificar que `src` esté en el PYTHONPATH
2. **Pydantic validation errors**: Verificar que los campos requeridos estén presentes
3. **Tests que fallan intermitentemente**: Verificar que los tests sean independientes

### Soluciones

```bash
# Verificar imports
uv run python -c "from domain.metadata.base import MetadataEntity; print('OK')"

# Ejecutar tests con debug
uv run pytest tests/domain/metadata/ -vvv --tb=long

# Limpiar cache de pytest
uv run pytest --cache-clear
```
