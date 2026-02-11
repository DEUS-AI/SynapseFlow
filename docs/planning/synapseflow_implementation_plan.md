# SynapseFlow — Plan de Implementación para Claude Code

## Contexto del Proyecto

SynapseFlow es un asistente médico ("Matucha") con arquitectura de memoria 3+1 capas:
- **Redis**: Cache conversacional
- **Mem0**: Memoria semántica vectorial
- **Neo4j**: Knowledge Graph DIKW (PERCEPTION → SEMANTIC → REASONING → APPLICATION)
- **Graphiti + FalkorDB**: Memoria episódica (conversaciones, eventos temporales)

**Problema central**: Graphiti extrae entidades a FalkorDB, pero no existe pipeline para transferir ese conocimiento al Knowledge Graph DIKW en Neo4j. Las capas DIKW están vacías o desconectadas de la memoria episódica.

**Lenguaje común**: Ambos sistemas (FalkorDB y Neo4j) usan Cypher → base para reglas de alineación cross-database.

---

## Orden de Ejecución

| Fase | Nombre | Prioridad | Dependencias |
|------|--------|-----------|--------------|
| 1 | Crystallization Pipeline (Graphiti → Neo4j DIKW) | CRÍTICA | Ninguna |
| 2 | Validation Gate SEMANTIC → REASONING | CRÍTICA | Fase 1 |
| 3 | Percepción Temporal Mejorada | ALTA | Ninguna (paralela) |
| 4 | LangGraph Dynamic Routing por DIKW | MEDIA | Fases 1-2 |
| 5 | Capa REASONING con Garantías | MEDIA | Fases 1-2 |
| 6 | Mejoras Experiencia Chat | BAJA | Todas anteriores |

---

## FASE 1: Crystallization Pipeline (Graphiti → Neo4j DIKW)

### Objetivo
Crear un servicio que extrae entidades y relaciones de Graphiti/FalkorDB, las transforma según el modelo DIKW, y las materializa en Neo4j como nodos PERCEPTION y SEMANTIC.

### Decisiones Arquitectónicas

**Modelo: Event-driven con batch periódico (híbrido)**
- Los episodios nuevos en Graphiti emiten evento al bus in-memory existente
- Un `CrystallizationService` escucha esos eventos y acumula en buffer
- Cada N minutos (configurable) o al alcanzar threshold de entidades, ejecuta batch de cristalización
- Esto evita overhead de procesamiento por cada mensaje individual

**Deduplicación**: Por `entity_name` normalizado + `entity_type`. Si ya existe en Neo4j DIKW, se enriquece (merge) en lugar de duplicar.

**Mapping de capas**:
- Entidad Graphiti recién extraída → PERCEPTION (dato crudo observado)
- Entidad con confidence ≥ 0.85 + match SNOMED-CT → promoción automática a SEMANTIC
- SEMANTIC → REASONING requiere Validation Gate (Fase 2)

### Archivos a Crear

#### 1.1 `synapseflow/services/crystallization_service.py`

```
Responsabilidad: Orquesta el pipeline de cristalización Graphiti → Neo4j DIKW.

Clase: CrystallizationService
  - __init__(neo4j_backend, graphiti_backend, validation_engine, event_bus)
  - async crystallize_batch() → CrystallizationResult
      1. Query FalkorDB vía graphiti_backend.get_entities() para entidades recientes
      2. Para cada entidad:
         a. Normalizar nombre (lowercase, trim, stemming médico básico)
         b. Verificar duplicado en Neo4j (MATCH por name + type en capa PERCEPTION/SEMANTIC)
         c. Si nueva: crear nodo PERCEPTION en Neo4j con metadatos de origen
         d. Si existente: merge propiedades, incrementar observation_count
      3. Evaluar candidatos a promoción PERCEPTION → SEMANTIC
         - Usar validation_engine.validate_layer_transition()
         - Aplicar reglas: confidence ≥ 0.85, source_count ≥ 2, SNOMED-CT match
      4. Ejecutar promociones aprobadas vía neo4j_backend.promote_entity()
      5. Emitir evento "crystallization_complete" al bus
      6. Retornar estadísticas (nuevas, merged, promovidas)

  - async crystallize_relationships() → RelationshipResult
      1. Query relaciones (edges) de Graphiti
      2. Mapear a relaciones DIKW preservando temporalidad
      3. Crear en Neo4j con propiedades: source="graphiti", valid_from, valid_to

  - async schedule_periodic(interval_minutes=5)
      Bucle con asyncio.sleep que invoca crystallize_batch() periódicamente

  - _normalize_entity_name(name: str) → str
      Normalización: lowercase, strip, quitar acentos, mapeo sinónimos médicos básicos

  - _build_perception_node(graphiti_entity) → dict
      Transforma entidad Graphiti al schema PERCEPTION de Neo4j:
      {
        "name": normalized_name,
        "entity_type": mapped_type,
        "dikw_layer": "PERCEPTION",
        "source": "graphiti_episodic",
        "source_episode_id": episode_id,
        "confidence": initial_confidence,
        "observation_count": 1,
        "first_observed": timestamp,
        "last_observed": timestamp,
        "graphiti_entity_id": original_id  # traceability
      }
```

#### 1.2 `synapseflow/services/entity_resolver.py`

```
Responsabilidad: Deduplicación y resolución de entidades cross-database.

Clase: EntityResolver
  - __init__(neo4j_backend)

  - async find_existing(name: str, entity_type: str) → Optional[dict]
      Query Neo4j:
      MATCH (n) WHERE n.dikw_layer IN ['PERCEPTION', 'SEMANTIC']
        AND toLower(n.name) = $normalized_name
        AND n.entity_type = $entity_type
      RETURN n

  - async merge_entity(existing_id: str, new_data: dict) → dict
      MATCH (n) WHERE elementId(n) = $id
      SET n.observation_count = n.observation_count + 1,
          n.last_observed = $timestamp,
          n.confidence = CASE
            WHEN $new_confidence > n.confidence THEN $new_confidence
            ELSE n.confidence
          END
      RETURN n

  - async find_similar(name: str, threshold: float = 0.8) → List[dict]
      Búsqueda fuzzy para casos de variación de nombres
      (Levenshtein o vector similarity si disponible)
```

### Archivos a Modificar

#### 1.3 Modificar `knowledge_manager/agent.py` (KnowledgeManagerAgent)

```
Cambios:
1. Importar CrystallizationService
2. En __init__: instanciar CrystallizationService con dependencias existentes
3. Registrar handler en event_bus para "episode_added":
   - Cuando Graphiti añade un episodio, acumular en buffer
   - Si buffer.size >= BATCH_THRESHOLD: trigger crystallize_batch()
4. En startup: lanzar schedule_periodic() como task asyncio
5. Añadir método get_crystallization_stats() para monitorización
```

#### 1.4 Modificar `episodic_memory_service.py`

```
Cambios:
1. En add_episode(): después de graphiti.add_episode(), emitir evento al bus:
   event_bus.emit("episode_added", {
     "episode_id": result.episode_id,
     "entities_extracted": result.entities,
     "timestamp": datetime.utcnow()
   })
2. Esto conecta el flujo: episodio → Graphiti → evento → cristalización
```

### Queries Cypher Clave

```cypher
-- Extraer entidades recientes de FalkorDB (Graphiti)
-- (ejecutar contra FalkorDB)
MATCH (e:Entity)
WHERE e.created_at > $last_crystallization_timestamp
RETURN e.name, e.entity_type, e.summary, e.created_at
ORDER BY e.created_at

-- Crear nodo PERCEPTION en Neo4j
MERGE (n:Entity:PERCEPTION {name: $name, entity_type: $type})
ON CREATE SET
  n.dikw_layer = 'PERCEPTION',
  n.source = 'graphiti_episodic',
  n.confidence = $confidence,
  n.observation_count = 1,
  n.first_observed = $timestamp,
  n.last_observed = $timestamp,
  n.graphiti_entity_id = $graphiti_id
ON MATCH SET
  n.observation_count = n.observation_count + 1,
  n.last_observed = $timestamp,
  n.confidence = CASE WHEN $confidence > n.confidence THEN $confidence ELSE n.confidence END

-- Candidatos a promoción PERCEPTION → SEMANTIC
MATCH (n:PERCEPTION)
WHERE n.confidence >= 0.85
  AND n.observation_count >= 2
  AND n.snomed_code IS NOT NULL
RETURN n
```

### Tests a Crear

```
tests/test_crystallization_service.py
  - test_new_entity_creates_perception_node
  - test_duplicate_entity_merges
  - test_promotion_criteria_met
  - test_promotion_criteria_not_met
  - test_relationship_crystallization
  - test_batch_scheduling
  - test_event_bus_integration
```

---

## FASE 2: Validation Gate SEMANTIC → REASONING

### Objetivo
Establecer reglas estrictas para que una entidad o relación pueda ascender de SEMANTIC a REASONING, especialmente crítico en dominio médico donde inferencias incorrectas pueden ser peligrosas.

### Decisiones Arquitectónicas

**Criterios de promoción SEMANTIC → REASONING:**
1. **Multi-source corroboration**: La información debe venir de ≥ 3 episodios independientes O de 1 fuente autoritativa (guía clínica, prescripción médica)
2. **Confidence threshold**: ≥ 0.92 (más alto que PERCEPTION → SEMANTIC)
3. **Temporal stability**: La información debe ser estable durante ≥ 48h (no contradicha)
4. **Domain validation**: Match contra ontología médica (SNOMED-CT, ICD-10)
5. **Human-in-the-loop (opcional)**: Flag para revisión humana en inferencias de alto riesgo

**Categorías de riesgo médico:**
- BAJO: preferencias del paciente, datos demográficos → auto-promoción si criterios 1-4
- MEDIO: síntomas reportados, hábitos → auto-promoción con logging detallado
- ALTO: diagnósticos, interacciones medicamentosas, alergias → requiere flag human review

### Archivos a Crear

#### 2.1 `synapseflow/services/promotion_gate.py`

```
Clase: PromotionGate
  - __init__(neo4j_backend, validation_engine)

  - async evaluate_promotion(entity_id: str, target_layer: str) → PromotionDecision
      Retorna: {approved: bool, reason: str, risk_level: str, requires_review: bool}

  - _check_multi_source(entity) → bool
      Verificar observation_count >= 3 OR has_authoritative_source

  - _check_temporal_stability(entity) → bool
      Verificar que no existen contradicciones en las últimas 48h
      Query: buscar entidades con mismo nombre pero datos conflictivos

  - _check_domain_validation(entity) → bool
      Validar contra SNOMED-CT / ICD-10 si aplica
      Usar validation_engine.validate_entity()

  - _assess_risk_level(entity) → RiskLevel
      Clasificar según entity_type:
      - BAJO: "patient_preference", "demographic", "lifestyle"
      - MEDIO: "symptom", "habit", "vital_sign"
      - ALTO: "diagnosis", "medication", "allergy", "drug_interaction"

  - async get_pending_reviews() → List[dict]
      Entidades flaggeadas para human review

  - async approve_review(entity_id: str, reviewer: str) → bool
      Aprobar manualmente una promoción pendiente
```

#### 2.2 `synapseflow/models/promotion_models.py`

```
@dataclass
class PromotionDecision:
    approved: bool
    reason: str
    risk_level: str  # "LOW", "MEDIUM", "HIGH"
    requires_review: bool
    criteria_met: dict  # detalle de cada criterio
    timestamp: datetime

@dataclass
class PromotionRule:
    source_layer: str
    target_layer: str
    min_confidence: float
    min_observations: int
    min_stability_hours: int
    requires_domain_match: bool
    risk_categories: dict  # mapeo tipo → nivel riesgo

class RiskLevel(Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
```

### Archivos a Modificar

#### 2.3 Modificar `validation_engine.py`

```
Cambios:
1. Añadir método validate_layer_transition(entity, source_layer, target_layer)
   que delega en PromotionGate para SEMANTIC → REASONING
2. Extender SHACL shapes para incluir constraints de REASONING layer:
   - Nodos REASONING requieren: provenance_chain, confidence ≥ 0.92, domain_code
3. Añadir reglas de validación específicas para dominio médico
```

#### 2.4 Modificar `crystallization_service.py`

```
Cambios:
1. Después de cristalizar a PERCEPTION y promover a SEMANTIC,
   evaluar también candidatos SEMANTIC → REASONING via PromotionGate
2. Entidades aprobadas: promover automáticamente
3. Entidades que requieren review: marcar con flag y emitir evento "review_needed"
```

### Tests

```
tests/test_promotion_gate.py
  - test_low_risk_auto_promotion
  - test_high_risk_requires_review
  - test_insufficient_observations_rejected
  - test_temporal_instability_rejected
  - test_domain_validation_required
  - test_manual_approval_flow
```

---

## FASE 3: Percepción Temporal Mejorada

### Objetivo
Ir más allá del filtro binario de 7 días. Explotar el modelo bi-temporal de Graphiti (valid_time, transaction_time) con funciones de decay para relevancia temporal.

### Archivos a Crear

#### 3.1 `synapseflow/services/temporal_scoring.py`

```
Clase: TemporalScoringService
  - __init__(config: TemporalConfig)

  - score_relevance(entity, query_context) → float
      Combina:
      1. Recency score: exponential decay desde last_observed
         score = exp(-lambda * hours_since_observation)
         lambda configurable por entity_type (síntomas decaen rápido, diagnósticos lento)
      2. Frequency score: log(observation_count + 1)
      3. Temporal coherence: ¿la entidad es temporalmente relevante al contexto?
         (ej: "dolor de cabeza ayer" vs "diagnóstico crónico hace 2 años")

  - get_temporal_window(query: str) → TemporalWindow
      Parsear intención temporal del query:
      - "ahora", "hoy" → last 24h, weight=1.0
      - "esta semana" → 7 days, weight=0.8
      - "últimamente" → 30 days, weight=0.6
      - "historial", "siempre" → all time, weight=0.3
      - Sin indicación temporal → adaptive (usar decay functions)

  - _decay_function(hours: float, entity_type: str) → float
      Decay rates por tipo:
      - "symptom": lambda=0.05 (decae en ~20h)
      - "vital_sign": lambda=0.03 (decae en ~33h)
      - "medication": lambda=0.005 (decae en ~200h = ~8 días)
      - "diagnosis": lambda=0.001 (decae en ~1000h = ~42 días)
      - "allergy": lambda=0.0001 (casi permanente)

@dataclass
class TemporalConfig:
    default_lambda: float = 0.01
    decay_rates: dict = field(default_factory=lambda: {...})
    recency_weight: float = 0.5
    frequency_weight: float = 0.3
    coherence_weight: float = 0.2
```

### Archivos a Modificar

#### 3.2 Modificar `episodic_memory_service.py`

```
Cambios:
1. En search(): reemplazar filtro binario 7 días por TemporalScoringService
2. Pasar query_context al scoring para adaptive temporal windows
3. Ordenar resultados por temporal_relevance_score en vez de timestamp puro
4. Mantener el filtro 7 días como fallback configurable
```

#### 3.3 Modificar `neurosymbolic_query_service.py`

```
Cambios:
1. En query_by_layer(): incorporar temporal scores como factor en ranking
2. En cross_layer_reasoning(): ponderar evidencia por recencia temporal
3. Añadir parámetro temporal_context a los métodos de query
```

---

## FASE 4: LangGraph Dynamic Routing por DIKW

### Objetivo
Que las queries se enruten dinámicamente a la capa DIKW más apropiada según contenido, en vez de routing estático por tipo.

### Archivos a Crear

#### 4.1 `synapseflow/services/dikw_router.py`

```
Clase: DIKWRouter
  - __init__(neurosymbolic_service, temporal_service)

  - async route_query(query: str, context: dict) → RoutingDecision
      1. Clasificar intención del query:
         - Factual simple ("¿cuándo fue mi última cita?") → PERCEPTION/SEMANTIC
         - Relacional ("¿qué medicamentos tomo para X?") → SEMANTIC
         - Inferencial ("¿debería preocuparme por estos síntomas?") → REASONING
         - Accionable ("¿qué debo hacer?") → APPLICATION
      2. Verificar disponibilidad de datos en capa target
         - Si REASONING vacío pero query inferencial → fallback a SEMANTIC + LLM reasoning
      3. Determinar si necesita cross-layer (combinar capas)
      4. Retornar: {primary_layer, fallback_layer, cross_layer_needed, confidence}

  - _classify_intent(query: str) → QueryIntent
      Usar heurísticas + keywords:
      - "qué", "cuándo", "cuál" → FACTUAL
      - "por qué", "relación entre", "causa" → RELATIONAL
      - "debería", "riesgo", "posible que" → INFERENTIAL
      - "qué hacer", "siguiente paso", "recomienda" → ACTIONABLE

  - _check_layer_availability(layer: str) → LayerStatus
      Query rápido a Neo4j para verificar que la capa tiene contenido relevante
```

### Archivos a Modificar

#### 4.2 Modificar `knowledge_manager/agent.py`

```
Cambios:
1. Integrar DIKWRouter en el flujo de procesamiento de queries
2. En lugar de routing estático, usar router.route_query() para decidir
3. Si cross_layer_needed: invocar neurosymbolic_service.cross_layer_reasoning()
4. Logging de decisiones de routing para análisis posterior
```

---

## FASE 5: Capa REASONING con Garantías

### Objetivo
Poblar la capa REASONING con inferencias médicas validadas, usando el ReasoningEngine existente pero ahora alimentado por el pipeline de cristalización.

### Archivos a Modificar

#### 5.1 Modificar `reasoning_engine.py`

```
Cambios:
1. Añadir reglas de razonamiento médico concretas:
   - Interacciones medicamentosas (si toma A y B → posible interacción)
   - Patrones de síntomas (si síntoma X + Y + Z → sugiere condición W)
   - Contraindicaciones (si alergia a X → evitar familia de medicamentos Y)
2. Cada regla genera nodos REASONING con:
   - provenance_chain: lista de nodos SEMANTIC que soportan la inferencia
   - confidence: calculada como producto de confidences de las fuentes
   - reasoning_type: "drug_interaction", "symptom_pattern", "contraindication"
3. Integrar con PromotionGate para que todas las inferencias pasen validación
```

#### 5.2 Crear `synapseflow/rules/medical_rules.py`

```
Definición de reglas médicas como configuración:

MEDICAL_REASONING_RULES = [
  {
    "id": "drug_interaction_check",
    "type": "cross_entity",
    "conditions": {
      "entity_types": ["medication", "medication"],
      "relationship": "taken_by_same_patient",
      "lookup": "drug_interaction_database"
    },
    "produces": {
      "entity_type": "drug_interaction_warning",
      "dikw_layer": "REASONING",
      "risk_level": "HIGH"
    }
  },
  {
    "id": "allergy_contraindication",
    "type": "cross_entity",
    "conditions": {
      "entity_types": ["allergy", "medication"],
      "relationship": "potential_reaction"
    },
    "produces": {
      "entity_type": "contraindication_alert",
      "dikw_layer": "REASONING",
      "risk_level": "HIGH"
    }
  }
]
```

---

## FASE 6: Mejoras Experiencia Chat

### Objetivo
Mejorar cómo Matucha usa el conocimiento cristalizado en las conversaciones.

### Cambios Principales

1. **Contexto enriquecido**: Cuando el usuario pregunta, el agente recibe no solo resultados de Graphiti sino también conocimiento cristalizado de Neo4j DIKW, priorizado por capa
2. **Transparencia**: Matucha puede indicar el nivel de confianza de la información ("Basándome en tus últimas visitas..." vs "Esto es una observación preliminar...")
3. **Proactividad**: Si hay alertas en capa REASONING (ej: interacción medicamentosa), Matucha las menciona proactivamente

---

## Resumen de Archivos

### Nuevos (crear)
| Archivo | Fase |
|---------|------|
| `synapseflow/services/crystallization_service.py` | 1 |
| `synapseflow/services/entity_resolver.py` | 1 |
| `synapseflow/services/promotion_gate.py` | 2 |
| `synapseflow/models/promotion_models.py` | 2 |
| `synapseflow/services/temporal_scoring.py` | 3 |
| `synapseflow/services/dikw_router.py` | 4 |
| `synapseflow/rules/medical_rules.py` | 5 |
| `tests/test_crystallization_service.py` | 1 |
| `tests/test_promotion_gate.py` | 2 |

### Existentes (modificar)
| Archivo | Fases | Tipo de cambio |
|---------|-------|----------------|
| `knowledge_manager/agent.py` | 1, 4 | Integrar crystallization + router |
| `episodic_memory_service.py` | 1, 3 | Emitir eventos + temporal scoring |
| `validation_engine.py` | 2 | Añadir layer transition rules |
| `neurosymbolic_query_service.py` | 3 | Temporal context en queries |
| `reasoning_engine.py` | 5 | Reglas médicas concretas |

---

## Configuración y Feature Flags

```python
# synapseflow/config/crystallization_config.py

CRYSTALLIZATION_CONFIG = {
    "batch_interval_minutes": 5,
    "batch_threshold": 10,  # entidades antes de forzar batch
    "enable_auto_promotion_perception_semantic": True,
    "enable_auto_promotion_semantic_reasoning": False,  # empezar con review manual
    "promotion_rules": {
        "perception_to_semantic": {
            "min_confidence": 0.85,
            "min_observations": 2,
            "require_snomed_match": True
        },
        "semantic_to_reasoning": {
            "min_confidence": 0.92,
            "min_observations": 3,
            "min_stability_hours": 48,
            "require_domain_validation": True,
            "high_risk_requires_review": True
        }
    },
    "temporal": {
        "default_decay_lambda": 0.01,
        "use_adaptive_windows": True
    }
}
```

---

## Instrucciones para Claude Code

**Orden de ejecución estricto**: Fase 1 → Fase 2 → (Fase 3 en paralelo) → Fase 4 → Fase 5 → Fase 6.

**Para cada archivo nuevo**:
1. Crear el archivo con la estructura indicada
2. Implementar todos los métodos descritos
3. Escribir docstrings en español
4. Usar type hints completos (Python 3.10+)
5. Seguir el patrón async/await del proyecto existente
6. Escribir tests unitarios correspondientes

**Para cada archivo modificado**:
1. Leer el archivo actual completo antes de modificar
2. Identificar los puntos de inserción exactos
3. Mantener backward compatibility
4. No romper imports existentes
5. Añadir imports necesarios al inicio del archivo

**Convenciones del proyecto**:
- Pydantic v2 para modelos
- asyncio para operaciones async
- Neo4j driver async
- Logging con structlog o logging estándar
- Event bus in-memory (no RabbitMQ por ahora)
- Cypher para queries tanto FalkorDB como Neo4j
