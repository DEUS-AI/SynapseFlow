"""Command for generating metadata graphs from DDA documents."""

from pydantic import BaseModel, Field, field_validator
from typing import Optional
from domain.commands import Command
import os


class GenerateMetadataCommand(Command, BaseModel):
    """Command to generate metadata graph from DDA and architecture graph."""
    
    dda_path: str = Field(..., description="Path to the DDA document")
    domain: str = Field(..., description="Domain name")
    architecture_graph_ref: Optional[str] = Field(
        None,
        description="Reference to architecture graph (group_id or episode_uuid)"
    )
    validate_against_architecture: bool = Field(
        default=True,
        description="Validate DDA against existing architecture graph"
    )
    
    @field_validator('dda_path')
    @classmethod
    def validate_dda_path(cls, v):
        """Validate that the DDA file exists and is accessible."""
        if not os.path.exists(v):
            raise ValueError(f"DDA file not found: {v}")
        if not os.path.isfile(v):
            raise ValueError(f"Path is not a file: {v}")
        return v
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "dda_path": "examples/sample_dda.md",
                "domain": "Customer Analytics",
                "architecture_graph_ref": "dda_customer_analytics",
                "validate_against_architecture": True
            }
        }
    }

