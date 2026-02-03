from pydantic import BaseModel, Field, field_validator
from typing import Optional
from domain.commands import Command
import os


class ModelingCommand(Command, BaseModel):
    """Command to process DDA documents and create/update knowledge graphs."""
    
    dda_path: str = Field(..., description="Path to the DDA document")
    domain: Optional[str] = Field(None, description="Explicit domain specification")
    update_existing: bool = Field(default=False, description="Update existing graph vs create new")
    validate_only: bool = Field(default=False, description="Only validate without creating graph")
    output_path: Optional[str] = Field(default=None, description="Path for output artifacts")
    
    @field_validator('dda_path')
    @classmethod
    def validate_dda_path(cls, v):
        """Validate that the DDA file exists and is accessible."""
        if not os.path.exists(v):
            raise ValueError(f"DDA file not found: {v}")
        if not os.path.isfile(v):
            raise ValueError(f"Path is not a file: {v}")
        return v
    
    @field_validator('output_path')
    @classmethod
    def validate_output_path(cls, v):
        """Validate output path if provided."""
        if v is not None:
            # Ensure the directory exists
            output_dir = os.path.dirname(v) if os.path.dirname(v) else '.'
            if not os.path.exists(output_dir):
                try:
                    os.makedirs(output_dir, exist_ok=True)
                except OSError:
                    raise ValueError(f"Cannot create output directory: {output_dir}")
        return v
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "dda_path": "examples/customer_analytics_dda.md",
                "domain": "Customer Analytics",
                "update_existing": False,
                "validate_only": False,
                "output_path": "output/modeling_results.json"
            }
        }
    } 