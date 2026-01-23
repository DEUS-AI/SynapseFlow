from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime


class DataEntity(BaseModel):
    """Represents a data entity from the DDA."""
    name: str = Field(..., description="Name of the data entity")
    description: str = Field(..., description="Description of the entity")
    attributes: List[str] = Field(default_factory=list, description="List of entity attributes")
    business_rules: List[str] = Field(default_factory=list, description="Business rules for the entity")
    primary_key: Optional[str] = Field(None, description="Primary key attribute")
    foreign_keys: List[str] = Field(default_factory=list, description="Foreign key attributes")
    origin: Optional[str] = Field(None, description="Origin/source system for this entity")


class Relationship(BaseModel):
    """Represents a relationship between entities."""
    source_entity: str = Field(..., description="Source entity name")
    target_entity: str = Field(..., description="Target entity name")
    relationship_type: str = Field(..., description="Relationship type (1:1, 1:N, M:N)")
    description: str = Field(..., description="Description of the relationship")
    constraints: List[str] = Field(default_factory=list, description="Relationship constraints")


class DataQualityRequirement(BaseModel):
    """Represents data quality requirements."""
    completeness: Dict[str, Any] = Field(default_factory=dict, description="Completeness requirements")
    accuracy: Dict[str, Any] = Field(default_factory=dict, description="Accuracy requirements")
    timeliness: Dict[str, Any] = Field(default_factory=dict, description="Timeliness requirements")


class AccessPattern(BaseModel):
    """Represents data access patterns."""
    common_queries: List[str] = Field(default_factory=list, description="Common query patterns")
    performance_requirements: Dict[str, Any] = Field(default_factory=dict, description="Performance requirements")


class Governance(BaseModel):
    """Represents data governance requirements."""
    privacy: Dict[str, Any] = Field(default_factory=dict, description="Privacy requirements")
    security: Dict[str, Any] = Field(default_factory=dict, description="Security requirements")
    compliance: Dict[str, Any] = Field(default_factory=dict, description="Compliance requirements")


class DDADocument(BaseModel):
    """Complete DDA document structure."""
    domain: str = Field(..., description="Business domain name")
    stakeholders: List[str] = Field(default_factory=list, description="List of stakeholders")
    data_owner: str = Field(..., description="Data owner")
    effective_date: datetime = Field(..., description="Effective date of the DDA")
    business_context: str = Field(..., description="Business context description")
    entities: List[DataEntity] = Field(default_factory=list, description="Data entities")
    relationships: List[Relationship] = Field(default_factory=list, description="Entity relationships")
    data_quality_requirements: DataQualityRequirement = Field(
        default_factory=DataQualityRequirement, 
        description="Data quality requirements"
    )
    access_patterns: AccessPattern = Field(
        default_factory=AccessPattern, 
        description="Data access patterns"
    )
    governance: Governance = Field(
        default_factory=Governance, 
        description="Data governance requirements"
    )
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "domain": "Customer Analytics",
                "stakeholders": ["Marketing Team", "Sales Team"],
                "data_owner": "VP of Customer Experience",
                "effective_date": "2024-01-15T00:00:00",
                "business_context": "Customer behavior analysis and campaign tracking",
                "entities": [
                    {
                        "name": "Customer",
                        "description": "Core customer information",
                        "attributes": ["Customer ID", "Name", "Email"],
                        "business_rules": ["Customer ID must be unique"],
                        "primary_key": "Customer ID"
                    }
                ],
                "relationships": [
                    {
                        "source_entity": "Customer",
                        "target_entity": "Campaign",
                        "relationship_type": "M:N",
                        "description": "Customers participate in campaigns"
                    }
                ]
            }
        }
    } 