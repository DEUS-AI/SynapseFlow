"""Handler for GenerateMetadataCommand."""

from typing import Dict, Any
from application.commands.base import CommandHandler
from application.commands.metadata_command import GenerateMetadataCommand
from application.agents.data_engineer.metadata_workflow import MetadataGenerationWorkflow


class GenerateMetadataCommandHandler(CommandHandler):
    """Handles GenerateMetadataCommand execution."""
    
    def __init__(self, workflow: MetadataGenerationWorkflow):
        """Initialize the handler with a metadata generation workflow.
        
        Args:
            workflow: The metadata generation workflow to execute
        """
        self.workflow = workflow
    
    async def handle(self, command: GenerateMetadataCommand) -> Dict[str, Any]:
        """Execute the metadata generation workflow.
        
        Args:
            command: The GenerateMetadataCommand to execute
        
        Returns:
            Dictionary with success status and results
        """
        try:
            result = await self.workflow.execute(command)
            return result
        except Exception as e:
            return {
                "success": False,
                "errors": [f"Metadata generation workflow failed: {str(e)}"],
                "warnings": []
            }

