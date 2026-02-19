from typing import Dict, Any, List
from application.commands.base import CommandHandler
from application.commands.collaboration_commands import ModelingFeedbackCommand
from graphiti_core import Graphiti


class ModelingFeedbackCommandHandler(CommandHandler):
    """Handles feedback on domain modeling from other agents."""
    
    def __init__(self, graph: Graphiti):
        self.graph = graph
    
    async def handle(self, command: ModelingFeedbackCommand) -> Dict[str, Any]:
        """Process feedback on domain modeling and potentially trigger refinements."""
        try:
            # 1. Store feedback in the knowledge graph
            feedback_episode = await self._store_feedback(command)
            
            # 2. Analyze feedback for actionable insights
            analysis_result = await self._analyze_feedback(command)
            
            # 3. Determine if refinements are needed
            refinement_needed = await self._assess_refinement_needs(analysis_result)
            
            # 4. Generate refinement suggestions
            refinement_suggestions = []
            if refinement_needed:
                refinement_suggestions = await self._generate_refinement_suggestions(command, analysis_result)
            
            return {
                "success": True,
                "domain": command.domain,
                "feedback_episode_uuid": feedback_episode.get("episode_uuid"),
                "feedback_processed": True,
                "rating": command.rating,
                "feedback_type": command.feedback_type,
                "refinement_needed": refinement_needed,
                "refinement_suggestions": refinement_suggestions,
                "analysis_summary": analysis_result.get("summary", "")
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Feedback processing failed: {str(e)}"
            }
    
    async def _store_feedback(self, command: ModelingFeedbackCommand) -> Dict[str, Any]:
        """Store feedback in the knowledge graph as an episode."""
        
        feedback_content = self._create_feedback_episode_content(command)
        
        # Add feedback episode to Graphiti
        episode_results = await self.graph.add_episode(
            name=f"Modeling Feedback - {command.domain}",
            episode_body=feedback_content,
            source_description=f"Feedback on domain modeling for {command.domain}",
            reference_time="2024-01-01",  # Could be made dynamic
            source="message",
            group_id=f"feedback_{command.domain.lower().replace(' ', '_')}",
            update_communities=True
        )
        
        return {
            "episode_uuid": episode_results.episode.uuid if episode_results.episode else None,
            "nodes_created": len(episode_results.nodes) if episode_results.nodes else 0,
            "edges_created": len(episode_results.edges) if episode_results.edges else 0
        }
    
    def _create_feedback_episode_content(self, command: ModelingFeedbackCommand) -> str:
        """Create structured episode content for feedback."""
        
        content_parts = []
        
        # Feedback header
        content_parts.append("DOMAIN MODELING FEEDBACK")
        content_parts.append(f"Domain: {command.domain}")
        content_parts.append(f"Original Episode UUID: {command.episode_uuid}")
        content_parts.append(f"Feedback Type: {command.feedback_type}")
        content_parts.append(f"Rating: {command.rating}/5" if command.rating else "No rating provided")
        
        # Main feedback content
        content_parts.append("\nFEEDBACK CONTENT:")
        content_parts.append(command.feedback_content)
        
        # Entity-specific feedback
        if command.entity_feedback:
            content_parts.append("\nENTITY-SPECIFIC FEEDBACK:")
            for entity_name, feedback in command.entity_feedback.items():
                content_parts.append(f"- {entity_name}: {feedback}")
        
        # Relationship-specific feedback
        if command.relationship_feedback:
            content_parts.append("\nRELATIONSHIP-SPECIFIC FEEDBACK:")
            for rel_name, feedback in command.relationship_feedback.items():
                content_parts.append(f"- {rel_name}: {feedback}")
        
        # Suggestions
        if command.suggestions:
            content_parts.append("\nSUGGESTIONS:")
            for i, suggestion in enumerate(command.suggestions, 1):
                content_parts.append(f"{i}. {suggestion}")
        
        return "\n".join(content_parts)
    
    async def _analyze_feedback(self, command: ModelingFeedbackCommand) -> Dict[str, Any]:
        """Analyze feedback for actionable insights."""
        
        analysis = {
            "summary": "",
            "severity": "low",
            "actionable_items": [],
            "priority": "low"
        }
        
        # Analyze rating
        if command.rating:
            if command.rating <= 2:
                analysis["severity"] = "high"
                analysis["priority"] = "high"
            elif command.rating <= 3:
                analysis["severity"] = "medium"
                analysis["priority"] = "medium"
        
        # Analyze feedback type
        if command.feedback_type in ["entity_quality", "relationship_accuracy"]:
            analysis["actionable_items"].append("Review and refine entity/relationship definitions")
        
        if command.feedback_type == "domain_coverage":
            analysis["actionable_items"].append("Expand domain coverage with additional entities/relationships")
        
        # Analyze suggestions
        if command.suggestions:
            analysis["actionable_items"].extend([f"Consider: {s}" for s in command.suggestions])
        
        # Generate summary
        analysis["summary"] = f"Feedback analysis: {analysis['severity']} severity, {len(analysis['actionable_items'])} actionable items"
        
        return analysis
    
    async def _assess_refinement_needs(self, analysis_result: Dict[str, Any]) -> bool:
        """Determine if refinements are needed based on feedback analysis."""
        
        # High severity feedback always needs refinement
        if analysis_result.get("severity") == "high":
            return True
        
        # Medium severity with actionable items needs refinement
        if analysis_result.get("severity") == "medium" and analysis_result.get("actionable_items"):
            return True
        
        # High priority feedback needs refinement
        if analysis_result.get("priority") == "high":
            return True
        
        return False
    
    async def _generate_refinement_suggestions(self, command: ModelingFeedbackCommand, analysis_result: Dict[str, Any]) -> List[str]:
        """Generate specific refinement suggestions based on feedback."""
        
        suggestions = []
        
        # Entity-related refinements
        if command.entity_feedback:
            suggestions.append("Review and update entity definitions based on specific feedback")
            suggestions.append("Consider adding missing entity attributes or business rules")
        
        # Relationship-related refinements
        if command.relationship_feedback:
            suggestions.append("Review and update relationship definitions and constraints")
            suggestions.append("Consider adding missing relationship types or cardinalities")
        
        # Domain coverage refinements
        if command.feedback_type == "domain_coverage":
            suggestions.append("Expand domain model with additional entities and relationships")
            suggestions.append("Review domain boundaries and consider splitting or merging domains")
        
        # General refinements based on suggestions
        if command.suggestions:
            suggestions.extend([f"Implement: {s}" for s in command.suggestions])
        
        # Add analysis-based suggestions
        if analysis_result.get("actionable_items"):
            suggestions.extend(analysis_result["actionable_items"])
        
        return suggestions 