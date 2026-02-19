"""Conflict detection and resolution for knowledge graph operations."""

from typing import Dict, Any, List
from domain.kg_backends import KnowledgeGraphBackend
from domain.event import KnowledgeEvent


class ConflictResolver:
    """Detects and resolves conflicts in knowledge graph operations."""

    def __init__(self, backend: KnowledgeGraphBackend):
        self.backend = backend

    async def detect_conflicts(self, event: KnowledgeEvent) -> List[Dict[str, Any]]:
        """Detect potential conflicts for a knowledge event."""
        conflicts = []
        
        if event.action == "create_entity":
            conflicts.extend(await self._detect_entity_conflicts(event))
        elif event.action == "create_relationship":
            conflicts.extend(await self._detect_relationship_conflicts(event))
        
        return conflicts

    async def _detect_entity_conflicts(self, event: KnowledgeEvent) -> List[Dict[str, Any]]:
        """Detect conflicts when creating entities."""
        conflicts = []
        entity_id = event.data.get("id")
        properties = event.data.get("properties", {})
        
        if not entity_id:
            return conflicts
        
        # Check for duplicate entity IDs
        try:
            existing_entity = await self.backend.query(f"MATCH (n {{id: '{entity_id}'}}) RETURN n")
            if existing_entity:
                conflicts.append({
                    "type": "duplicate_entity_id",
                    "entity_id": entity_id,
                    "severity": "high",
                    "description": f"Entity with ID '{entity_id}' already exists",
                    "existing_properties": existing_entity
                })
        except Exception:
            # Query might not be supported by all backends
            pass
        
        # Check for property conflicts (e.g., conflicting data types)
        conflicts.extend(self._detect_property_conflicts(properties))
        
        return conflicts

    async def _detect_relationship_conflicts(self, event: KnowledgeEvent) -> List[Dict[str, Any]]:
        """Detect conflicts when creating relationships."""
        conflicts = []
        source = event.data.get("source")
        target = event.data.get("target")
        rel_type = event.data.get("type")
        
        if not all([source, target, rel_type]):
            return conflicts
        
        # Check if source and target entities exist
        try:
            source_exists = await self.backend.query(f"MATCH (n {{id: '{source}'}}) RETURN n")
            target_exists = await self.backend.query(f"MATCH (n {{id: '{target}'}}) RETURN n")
            
            if not source_exists:
                conflicts.append({
                    "type": "missing_source_entity",
                    "entity_id": source,
                    "severity": "high",
                    "description": f"Source entity '{source}' does not exist"
                })
            
            if not target_exists:
                conflicts.append({
                    "type": "missing_target_entity",
                    "entity_id": target,
                    "severity": "high",
                    "description": f"Target entity '{target}' does not exist"
                })
        except Exception:
            # Query might not be supported by all backends
            pass
        
        # Check for circular relationships
        if source == target:
            conflicts.append({
                "type": "circular_relationship",
                "entity_id": source,
                "severity": "medium",
                "description": f"Circular relationship from '{source}' to itself"
            })
        
        # Check for duplicate relationships
        try:
            existing_rel = await self.backend.query(
                f"MATCH (a {{id: '{source}'}})-[r:{rel_type}]->(b {{id: '{target}'}}) RETURN r"
            )
            if existing_rel:
                conflicts.append({
                    "type": "duplicate_relationship",
                    "source": source,
                    "target": target,
                    "rel_type": rel_type,
                    "severity": "low",
                    "description": f"Relationship {source}-[{rel_type}]->{target} already exists"
                })
        except Exception:
            pass
        
        return conflicts

    def _detect_property_conflicts(self, properties: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Detect conflicts in entity properties."""
        conflicts = []
        
        for key, value in properties.items():
            # Check for invalid property names
            if not isinstance(key, str) or not key.strip():
                conflicts.append({
                    "type": "invalid_property_name",
                    "property": key,
                    "severity": "medium",
                    "description": f"Invalid property name: '{key}'"
                })
            
            # Check for None values
            if value is None:
                conflicts.append({
                    "type": "null_property_value",
                    "property": key,
                    "severity": "low",
                    "description": f"Property '{key}' has null value"
                })
        
        return conflicts

    async def create_resolution_plan(self, conflicts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create a plan to resolve detected conflicts."""
        resolution_plan = {
            "conflicts_count": len(conflicts),
            "resolutions": [],
            "requires_manual_intervention": False,
            "estimated_resolution_time": "0s"
        }
        
        for conflict in conflicts:
            resolution = await self._create_conflict_resolution(conflict)
            resolution_plan["resolutions"].append(resolution)
            
            if resolution["requires_manual_intervention"]:
                resolution_plan["requires_manual_intervention"] = True
        
        # Estimate resolution time
        auto_resolvable = sum(1 for r in resolution_plan["resolutions"] 
                            if not r["requires_manual_intervention"])
        resolution_plan["estimated_resolution_time"] = f"{auto_resolvable * 2}s"
        
        return resolution_plan

    async def _create_conflict_resolution(self, conflict: Dict[str, Any]) -> Dict[str, Any]:
        """Create a resolution plan for a specific conflict."""
        conflict_type = conflict.get("type")
        
        if conflict_type == "duplicate_entity_id":
            return {
                "conflict_id": conflict.get("entity_id"),
                "action": "merge_entities",
                "description": "Merge properties from new entity with existing entity",
                "requires_manual_intervention": False,
                "automatic_resolution": True
            }
        
        elif conflict_type == "missing_source_entity":
            return {
                "conflict_id": conflict.get("entity_id"),
                "action": "create_missing_entity",
                "description": "Create missing source entity with default properties",
                "requires_manual_intervention": False,
                "automatic_resolution": True
            }
        
        elif conflict_type == "missing_target_entity":
            return {
                "conflict_id": conflict.get("entity_id"),
                "action": "create_missing_entity",
                "description": "Create missing target entity with default properties",
                "requires_manual_intervention": False,
                "automatic_resolution": True
            }
        
        elif conflict_type == "circular_relationship":
            return {
                "conflict_id": f"{conflict.get('entity_id')}_circular",
                "action": "reject_operation",
                "description": "Reject circular relationship creation",
                "requires_manual_intervention": False,
                "automatic_resolution": True
            }
        
        elif conflict_type == "duplicate_relationship":
            return {
                "conflict_id": f"{conflict.get('source')}_{conflict.get('type')}_{conflict.get('target')}",
                "action": "skip_duplicate",
                "description": "Skip duplicate relationship creation",
                "requires_manual_intervention": False,
                "automatic_resolution": True
            }
        
        else:
            return {
                "conflict_id": f"unknown_{conflict_type}",
                "action": "manual_review",
                "description": f"Unknown conflict type: {conflict_type}",
                "requires_manual_intervention": True,
                "automatic_resolution": False
            }

    async def apply_automatic_resolutions(self, conflicts: List[Dict[str, Any]]) -> List[str]:
        """Apply automatic resolutions where possible."""
        resolved_conflicts = []
        
        for conflict in conflicts:
            resolution = await self._create_conflict_resolution(conflict)
            
            if resolution["automatic_resolution"]:
                try:
                    await self._apply_resolution(conflict, resolution)
                    resolved_conflicts.append(conflict.get("type", "unknown"))
                except Exception as e:
                    print(f"Failed to automatically resolve conflict: {e}")
        
        return resolved_conflicts

    async def _apply_resolution(self, conflict: Dict[str, Any], resolution: Dict[str, Any]) -> None:
        """Apply a specific resolution to a conflict."""
        action = resolution.get("action")
        
        if action == "merge_entities":
            # This would merge properties from new entity with existing one
            pass
        elif action == "create_missing_entity":
            # This would create missing entities with default properties
            pass
        elif action == "reject_operation":
            # This would reject the operation
            pass
        elif action == "skip_duplicate":
            # This would skip duplicate operations
            pass
        # Additional resolution actions can be implemented here
