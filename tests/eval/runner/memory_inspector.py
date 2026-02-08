"""
Memory Inspector - Cliente para captura de snapshots y cálculo de diffs.

Este módulo proporciona la clase MemoryInspector que actúa como cliente
para los endpoints de evaluación, permitiendo:
1. Capturar snapshots de memoria vía la API
2. Calcular diffs entre snapshots
3. Esperar a que los pipelines alcancen quiescence
4. Seedear y resetear estado de pacientes
"""

import asyncio
import logging
from datetime import datetime, UTC
from typing import Any, Dict, List, Optional

import httpx

from .models import (
    MemorySnapshot,
    MemoryDiff,
    MemoryEntity,
    MemoryRelationship,
    Mem0Memory,
    EntityChange,
    RedisLayerSnapshot,
    Mem0LayerSnapshot,
    GraphitiLayerSnapshot,
    Neo4jDIKWLayerSnapshot,
    MemoryLayer,
    DIKWLayer,
    normalize_text,
    entities_match,
    relationships_match,
)

logger = logging.getLogger(__name__)


class MemoryInspectorError(Exception):
    """Error en operaciones del Memory Inspector."""
    pass


class QuiescenceTimeoutError(MemoryInspectorError):
    """Timeout esperando quiescence de pipelines."""
    pass


class MemoryInspector:
    """
    Cliente para capturar snapshots de memoria y calcular diffs.

    Interactúa con los endpoints de evaluación para:
    - Capturar el estado completo de memoria de un paciente
    - Calcular diferencias entre estados pre y post operación
    - Forzar flush de pipelines asíncronos
    - Verificar quiescence del sistema
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout: float = 30.0,
    ):
        """
        Inicializa el Memory Inspector.

        Args:
            base_url: URL base de la API (e.g., "http://localhost:8000")
            api_key: API key de evaluación (X-Eval-API-Key)
            timeout: Timeout por defecto para requests HTTP
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
        self._client_loop: Optional[asyncio.AbstractEventLoop] = None

    async def __aenter__(self):
        """Context manager entry."""
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            headers={"X-Eval-API-Key": self.api_key},
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        if self._client:
            await self._client.aclose()
            self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        """Retorna el cliente HTTP."""
        # Get current event loop
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None

        # If client exists but was created in a different/closed loop, recreate it
        if self._client is not None:
            if self._client_loop is not current_loop:
                # Close old client synchronously (best effort)
                try:
                    if not self._client.is_closed:
                        # Can't await here, just reset
                        pass
                except Exception:
                    pass
                self._client = None
                self._client_loop = None

        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                headers={"X-Eval-API-Key": self.api_key},
            )
            self._client_loop = current_loop
        return self._client

    async def close(self):
        """Cierra el cliente HTTP."""
        if self._client:
            await self._client.aclose()
            self._client = None

    # ========================================
    # Snapshot Operations
    # ========================================

    async def take_snapshot(
        self,
        patient_id: str,
        include_redis: bool = True,
        include_mem0: bool = True,
        include_graphiti: bool = True,
        include_neo4j: bool = True,
    ) -> MemorySnapshot:
        """
        Captura el estado completo de memoria de un paciente.

        Args:
            patient_id: ID del paciente
            include_redis: Incluir datos de Redis
            include_mem0: Incluir memorias de Mem0
            include_graphiti: Incluir episodios de Graphiti
            include_neo4j: Incluir nodos DIKW de Neo4j

        Returns:
            MemorySnapshot con el estado capturado

        Raises:
            MemoryInspectorError: Si falla la captura
        """
        logger.debug(f"Taking snapshot for patient: {patient_id}")

        params = {
            "include_redis": str(include_redis).lower(),
            "include_mem0": str(include_mem0).lower(),
            "include_graphiti": str(include_graphiti).lower(),
            "include_neo4j": str(include_neo4j).lower(),
        }

        try:
            response = await self.client.get(
                f"/api/eval/memory-snapshot/{patient_id}",
                params=params,
            )
            response.raise_for_status()
            data = response.json()

            snapshot = self._parse_snapshot(data)
            logger.info(
                f"Snapshot captured: {len(snapshot.all_entities())} entities, "
                f"{len(snapshot.all_relationships())} relationships, "
                f"{snapshot.mem0.memory_count} memories"
            )
            return snapshot

        except httpx.HTTPStatusError as e:
            raise MemoryInspectorError(f"HTTP error taking snapshot: {e}") from e
        except Exception as e:
            raise MemoryInspectorError(f"Error taking snapshot: {e}") from e

    def _parse_snapshot(self, data: Dict[str, Any]) -> MemorySnapshot:
        """Parsea la respuesta JSON a un MemorySnapshot."""
        # Parse timestamp
        timestamp = datetime.fromisoformat(
            data.get("timestamp", datetime.now(UTC).isoformat()).replace("Z", "+00:00")
        )

        # Parse Redis layer
        redis_data = data.get("redis", {})
        redis = RedisLayerSnapshot(
            session_data=redis_data.get("session_data", {}),
            active_sessions=redis_data.get("active_sessions", 0),
            ttl_seconds=redis_data.get("ttl_seconds"),
        )

        # Parse Mem0 layer
        mem0_data = data.get("mem0", {})
        memories = []
        for mem in mem0_data.get("memories", []):
            memories.append(Mem0Memory(
                id=mem.get("id", ""),
                text=mem.get("text", ""),
                created_at=self._parse_datetime(mem.get("created_at")),
                metadata=mem.get("metadata", {}),
            ))
        mem0 = Mem0LayerSnapshot(
            memories=memories,
            memory_count=mem0_data.get("memory_count", len(memories)),
        )

        # Parse Graphiti layer
        graphiti_data = data.get("graphiti", {})
        graphiti_entities = [
            self._parse_entity(e, MemoryLayer.GRAPHITI)
            for e in graphiti_data.get("entities", [])
        ]
        graphiti_edges = [
            self._parse_relationship(r, MemoryLayer.GRAPHITI)
            for r in graphiti_data.get("edges", [])
        ]
        graphiti = GraphitiLayerSnapshot(
            episodes=graphiti_data.get("episodes", []),
            entities=graphiti_entities,
            edges=graphiti_edges,
            episode_count=graphiti_data.get("episode_count", 0),
        )

        # Parse Neo4j DIKW layer
        neo4j_data = data.get("neo4j_dikw", {})
        neo4j = Neo4jDIKWLayerSnapshot(
            perception=[
                self._parse_entity(e, MemoryLayer.NEO4J_DIKW, DIKWLayer.PERCEPTION)
                for e in neo4j_data.get("perception", [])
            ],
            semantic=[
                self._parse_entity(e, MemoryLayer.NEO4J_DIKW, DIKWLayer.SEMANTIC)
                for e in neo4j_data.get("semantic", [])
            ],
            reasoning=[
                self._parse_entity(e, MemoryLayer.NEO4J_DIKW, DIKWLayer.REASONING)
                for e in neo4j_data.get("reasoning", [])
            ],
            application=[
                self._parse_entity(e, MemoryLayer.NEO4J_DIKW, DIKWLayer.APPLICATION)
                for e in neo4j_data.get("application", [])
            ],
            relationships=[
                self._parse_relationship(r, MemoryLayer.NEO4J_DIKW)
                for r in neo4j_data.get("relationships", [])
            ],
        )

        return MemorySnapshot(
            patient_id=data.get("patient_id", ""),
            timestamp=timestamp,
            redis=redis,
            mem0=mem0,
            graphiti=graphiti,
            neo4j_dikw=neo4j,
        )

    def _parse_entity(
        self,
        data: Dict[str, Any],
        layer: MemoryLayer,
        dikw_layer: Optional[DIKWLayer] = None,
    ) -> MemoryEntity:
        """Parsea datos de entidad."""
        # Handle dikw_layer from data if not provided
        if dikw_layer is None and data.get("dikw_layer"):
            try:
                dikw_layer = DIKWLayer(data["dikw_layer"])
            except ValueError:
                pass

        return MemoryEntity(
            name=data.get("name", ""),
            entity_type=data.get("entity_type", "Entity"),
            properties=data.get("properties", {}),
            layer=layer,
            dikw_layer=dikw_layer,
            confidence=data.get("confidence"),
            observation_count=data.get("observation_count"),
            first_observed=self._parse_datetime(data.get("first_observed")),
            last_observed=self._parse_datetime(data.get("last_observed")),
        )

    def _parse_relationship(
        self,
        data: Dict[str, Any],
        layer: MemoryLayer,
    ) -> MemoryRelationship:
        """Parsea datos de relación."""
        return MemoryRelationship(
            from_name=data.get("from_name", ""),
            to_name=data.get("to_name", ""),
            relationship_type=data.get("relationship_type", ""),
            properties=data.get("properties", {}),
            layer=layer,
        )

    def _parse_datetime(self, value: Any) -> Optional[datetime]:
        """Parsea datetime desde varios formatos."""
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return None
        return None

    # ========================================
    # Diff Computation
    # ========================================

    def compute_diff(
        self,
        before: MemorySnapshot,
        after: MemorySnapshot,
    ) -> MemoryDiff:
        """
        Calcula las diferencias entre dos snapshots de memoria.

        Args:
            before: Snapshot anterior
            after: Snapshot posterior

        Returns:
            MemoryDiff con los cambios detectados
        """
        logger.debug("Computing memory diff")

        # Index entities by normalized key
        before_entities = {e.normalized_key(): e for e in before.all_entities()}
        after_entities = {e.normalized_key(): e for e in after.all_entities()}

        # Find added entities
        entities_added = [
            after_entities[key]
            for key in after_entities
            if key not in before_entities
        ]

        # Find removed entities
        entities_removed = [
            before_entities[key]
            for key in before_entities
            if key not in after_entities
        ]

        # Find modified entities
        entities_modified = []
        for key in before_entities:
            if key in after_entities:
                changes = self._compare_entities(
                    before_entities[key],
                    after_entities[key],
                )
                entities_modified.extend(changes)

        # Index relationships by normalized key
        before_rels = {r.normalized_key(): r for r in before.all_relationships()}
        after_rels = {r.normalized_key(): r for r in after.all_relationships()}

        # Find added relationships
        relationships_added = [
            after_rels[key]
            for key in after_rels
            if key not in before_rels
        ]

        # Find removed relationships
        relationships_removed = [
            before_rels[key]
            for key in before_rels
            if key not in after_rels
        ]

        # Compare Mem0 memories
        before_mems = {m.id: m for m in before.mem0.memories}
        after_mems = {m.id: m for m in after.mem0.memories}

        memories_added = [
            after_mems[id]
            for id in after_mems
            if id not in before_mems
        ]

        memories_removed = [
            before_mems[id]
            for id in before_mems
            if id not in after_mems
        ]

        diff = MemoryDiff(
            entities_added=entities_added,
            entities_removed=entities_removed,
            entities_modified=entities_modified,
            relationships_added=relationships_added,
            relationships_removed=relationships_removed,
            memories_added=memories_added,
            memories_removed=memories_removed,
        )

        logger.info(
            f"Diff computed: +{len(entities_added)} entities, "
            f"-{len(entities_removed)} entities, "
            f"~{len(entities_modified)} modified, "
            f"+{len(relationships_added)}/-{len(relationships_removed)} relationships"
        )

        return diff

    def _compare_entities(
        self,
        before: MemoryEntity,
        after: MemoryEntity,
    ) -> List[EntityChange]:
        """Compara dos entidades y retorna los cambios."""
        changes = []

        # Compare confidence
        if before.confidence != after.confidence:
            changes.append(EntityChange(
                entity=after,
                field="confidence",
                old_value=before.confidence,
                new_value=after.confidence,
            ))

        # Compare observation_count
        if before.observation_count != after.observation_count:
            changes.append(EntityChange(
                entity=after,
                field="observation_count",
                old_value=before.observation_count,
                new_value=after.observation_count,
            ))

        # Compare dikw_layer
        if before.dikw_layer != after.dikw_layer:
            changes.append(EntityChange(
                entity=after,
                field="dikw_layer",
                old_value=before.dikw_layer,
                new_value=after.dikw_layer,
            ))

        # Compare properties (shallow)
        before_props = set(before.properties.keys())
        after_props = set(after.properties.keys())

        # New properties
        for key in after_props - before_props:
            changes.append(EntityChange(
                entity=after,
                field=f"properties.{key}",
                old_value=None,
                new_value=after.properties[key],
            ))

        # Changed properties
        for key in before_props & after_props:
            if before.properties[key] != after.properties[key]:
                changes.append(EntityChange(
                    entity=after,
                    field=f"properties.{key}",
                    old_value=before.properties[key],
                    new_value=after.properties[key],
                ))

        return changes

    # ========================================
    # Pipeline Control
    # ========================================

    async def flush_pipelines(self) -> Dict[str, Any]:
        """
        Fuerza el procesamiento inmediato de todos los eventos pendientes.

        Returns:
            Resultado del flush con estadísticas

        Raises:
            MemoryInspectorError: Si falla el flush
        """
        logger.debug("Flushing pipelines")

        try:
            response = await self.client.post("/api/eval/flush-pipelines")
            response.raise_for_status()
            result = response.json()

            logger.info(
                f"Pipelines flushed: {result.get('entities_crystallized', 0)} entities crystallized"
            )
            return result

        except httpx.HTTPStatusError as e:
            raise MemoryInspectorError(f"HTTP error flushing pipelines: {e}") from e
        except Exception as e:
            raise MemoryInspectorError(f"Error flushing pipelines: {e}") from e

    async def get_pipeline_status(self) -> Dict[str, Any]:
        """
        Obtiene el estado de los pipelines.

        Returns:
            Estado de quiescence y métricas

        Raises:
            MemoryInspectorError: Si falla la consulta
        """
        try:
            response = await self.client.get("/api/eval/pipeline-status")
            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            raise MemoryInspectorError(f"HTTP error getting pipeline status: {e}") from e
        except Exception as e:
            raise MemoryInspectorError(f"Error getting pipeline status: {e}") from e

    async def wait_for_quiescence(
        self,
        timeout_seconds: float = 30.0,
        poll_interval: float = 0.5,
    ) -> bool:
        """
        Espera a que todos los pipelines alcancen estado quiescent.

        Args:
            timeout_seconds: Timeout máximo de espera
            poll_interval: Intervalo entre checks

        Returns:
            True si se alcanzó quiescence, False si timeout

        Raises:
            QuiescenceTimeoutError: Si el timeout expira sin alcanzar quiescence
        """
        logger.debug(f"Waiting for quiescence (timeout={timeout_seconds}s)")

        start_time = asyncio.get_event_loop().time()
        deadline = start_time + timeout_seconds

        while asyncio.get_event_loop().time() < deadline:
            try:
                status = await self.get_pipeline_status()

                if status.get("quiescent", False):
                    elapsed = asyncio.get_event_loop().time() - start_time
                    logger.info(f"Quiescence reached in {elapsed:.2f}s")
                    return True

                logger.debug(
                    f"Not quiescent: buffer_size={status.get('buffer_size', '?')}, "
                    f"pending_events={status.get('pending_events', '?')}"
                )

            except Exception as e:
                logger.warning(f"Error checking quiescence: {e}")

            await asyncio.sleep(poll_interval)

        logger.warning(f"Quiescence timeout after {timeout_seconds}s")
        return False

    # ========================================
    # State Management
    # ========================================

    async def seed_state(
        self,
        patient_id: str,
        entities: List[Dict[str, Any]],
        relationships: List[Dict[str, Any]],
        clear_existing: bool = False,
    ) -> Dict[str, Any]:
        """
        Seedea el estado de memoria de un paciente.

        Args:
            patient_id: ID del paciente
            entities: Lista de entidades a crear
            relationships: Lista de relaciones a crear
            clear_existing: Si limpiar memoria existente primero

        Returns:
            Resultado del seeding

        Raises:
            MemoryInspectorError: Si falla el seeding
        """
        logger.info(f"Seeding state for patient {patient_id}: {len(entities)} entities")

        try:
            response = await self.client.post(
                "/api/eval/seed-state",
                json={
                    "patient_id": patient_id,
                    "entities": entities,
                    "relationships": relationships,
                    "clear_existing": clear_existing,
                },
            )
            response.raise_for_status()
            result = response.json()

            logger.info(
                f"State seeded: {result.get('entities_created', 0)} entities, "
                f"{result.get('relationships_created', 0)} relationships"
            )
            return result

        except httpx.HTTPStatusError as e:
            raise MemoryInspectorError(f"HTTP error seeding state: {e}") from e
        except Exception as e:
            raise MemoryInspectorError(f"Error seeding state: {e}") from e

    async def reset_patient(self, patient_id: str) -> Dict[str, Any]:
        """
        Limpia toda la memoria de un paciente.

        Args:
            patient_id: ID del paciente

        Returns:
            Resultado del reset

        Raises:
            MemoryInspectorError: Si falla el reset
        """
        logger.info(f"Resetting patient: {patient_id}")

        try:
            response = await self.client.post(f"/api/eval/reset/{patient_id}")
            response.raise_for_status()
            result = response.json()

            logger.info(
                f"Patient reset: {result.get('layers_cleared', [])} layers cleared"
            )
            return result

        except httpx.HTTPStatusError as e:
            raise MemoryInspectorError(f"HTTP error resetting patient: {e}") from e
        except Exception as e:
            raise MemoryInspectorError(f"Error resetting patient: {e}") from e

    # ========================================
    # Chat Operations
    # ========================================

    async def send_chat(
        self,
        patient_id: str,
        message: str,
        session_id: Optional[str] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """
        Envía un mensaje al agente vía el endpoint REST de chat.

        Args:
            patient_id: ID del paciente
            message: Mensaje a enviar
            session_id: ID de sesión (se genera si no se provee)
            conversation_history: Historial de conversación previo

        Returns:
            Respuesta del agente con metadata

        Raises:
            MemoryInspectorError: Si falla el envío
        """
        logger.debug(f"Sending chat: patient={patient_id}, message={message[:50]}...")

        try:
            response = await self.client.post(
                "/api/eval/chat",
                json={
                    "patient_id": patient_id,
                    "session_id": session_id,
                    "message": message,
                    "conversation_history": conversation_history or [],
                },
            )
            response.raise_for_status()
            result = response.json()

            logger.info(
                f"Chat response: {len(result.get('content', ''))} chars, "
                f"confidence={result.get('confidence', 0):.2f}"
            )
            return result

        except httpx.HTTPStatusError as e:
            raise MemoryInspectorError(f"HTTP error sending chat: {e}") from e
        except Exception as e:
            raise MemoryInspectorError(f"Error sending chat: {e}") from e

    # ========================================
    # Health Check
    # ========================================

    async def health_check(self) -> Dict[str, Any]:
        """
        Verifica el estado del framework de evaluación.

        Returns:
            Estado de salud con servicios disponibles

        Raises:
            MemoryInspectorError: Si falla el health check
        """
        try:
            response = await self.client.get("/api/eval/health")
            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            raise MemoryInspectorError(f"HTTP error in health check: {e}") from e
        except Exception as e:
            raise MemoryInspectorError(f"Error in health check: {e}") from e
