"""ODIN metadata graph domain models.

This module defines the core entities for the ODIN (Open Data Integration Network)
metadata schema, representing data catalogs, schemas, tables, columns, constraints, and policies.
"""

from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
from enum import Enum


class DataType(str, Enum):
    """Standard SQL data types."""
    VARCHAR = "VARCHAR"
    INTEGER = "INTEGER"
    BIGINT = "BIGINT"
    DECIMAL = "DECIMAL"
    DATE = "DATE"
    TIMESTAMP = "TIMESTAMP"
    BOOLEAN = "BOOLEAN"
    JSON = "JSON"
    ARRAY = "ARRAY"


class ConstraintType(str, Enum):
    """Constraint types for database columns."""
    PRIMARY_KEY = "PRIMARY_KEY"
    FOREIGN_KEY = "FOREIGN_KEY"
    UNIQUE = "UNIQUE"
    NOT_NULL = "NOT_NULL"
    CHECK = "CHECK"
    DEFAULT = "DEFAULT"


class Catalog(BaseModel):
    """ODIN Catalog entity representing the highest level of data organization."""
    name: str = Field(..., description="Catalog name")
    description: Optional[str] = Field(None, description="Catalog description")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Additional catalog properties")


class Schema(BaseModel):
    """ODIN Schema entity representing a schema within a catalog."""
    name: str = Field(..., description="Schema name")
    catalog_name: str = Field(..., description="Name of the catalog this schema belongs to")
    description: Optional[str] = Field(None, description="Schema description")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Additional schema properties")


class Table(BaseModel):
    """ODIN Table entity representing a dataset or model table."""
    name: str = Field(..., description="Table name")
    schema_name: str = Field(..., description="Name of the schema this table belongs to")
    description: Optional[str] = Field(None, description="Table description")
    origin: Optional[str] = Field(None, description="Origin/source system for this table")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Additional table properties")
    # Governance fields
    classification: Optional[str] = Field(None, description="Data classification (e.g., PUBLIC, INTERNAL, CONFIDENTIAL, PII)")
    retention_period: Optional[str] = Field(None, description="Retention period in ISO-8601 duration format")
    access_control: List[str] = Field(default_factory=list, description="Roles or groups allowed to access this table")
    encryption_required: bool = Field(False, description="Whether the table data must be encrypted at rest")
    data_quality_score: Optional[float] = Field(None, description="Quality score (0-1) for the table data")


class Column(BaseModel):
    """ODIN Column entity representing a column within a table."""
    name: str = Field(..., description="Column name")
    table_name: str = Field(..., description="Name of the table this column belongs to")
    description: Optional[str] = Field(None, description="Column description")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Additional column properties")
    # Governance fields
    classification: Optional[str] = Field(None, description="Data classification (e.g., PUBLIC, INTERNAL, CONFIDENTIAL, PII)")
    retention_period: Optional[str] = Field(None, description="Retention period in ISO-8601 duration format")
    access_control: List[str] = Field(default_factory=list, description="Roles or groups allowed to access this column")
    encryption_required: bool = Field(False, description="Whether the column data must be encrypted at rest")
    data_quality_score: Optional[float] = Field(None, description="Quality score (0-1) for the column data")


class DataTypeEntity(BaseModel):
    """ODIN DataType entity representing a data type definition."""
    name: str = Field(..., description="Data type name (e.g., VARCHAR, INTEGER)")
    base_type: str = Field(..., description="Base type category (e.g., STRING, NUMERIC, TEMPORAL)")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Additional data type properties")


class TypeAssignment(BaseModel):
    """ODIN Type Assignment entity linking a column to its data type."""
    column_name: str = Field(..., description="Name of the column")
    data_type_name: str = Field(..., description="Name of the data type")
    precision: Optional[int] = Field(None, description="Precision for numeric/string types (e.g., VARCHAR(50))")
    scale: Optional[int] = Field(None, description="Scale for DECIMAL types (e.g., DECIMAL(10,2))")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Additional type assignment properties")


class Constraint(BaseModel):
    """ODIN Constraint entity representing constraints on columns."""
    name: str = Field(..., description="Constraint name")
    constraint_type: ConstraintType = Field(..., description="Type of constraint")
    column_name: str = Field(..., description="Name of the column this constraint applies to")
    table_name: str = Field(..., description="Name of the table containing the column")
    referenced_table: Optional[str] = Field(None, description="Referenced table (for FOREIGN_KEY constraints)")
    referenced_column: Optional[str] = Field(None, description="Referenced column (for FOREIGN_KEY constraints)")
    expression: Optional[str] = Field(None, description="Constraint expression (for CHECK constraints)")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Additional constraint properties")


class PolicyType(str, Enum):
    """Types of governance policies."""
    DATA_RETENTION = "DATA_RETENTION"
    ENCRYPTION = "ENCRYPTION"
    ACCESS_CONTROL = "ACCESS_CONTROL"
    QUALITY = "QUALITY"


class Policy(BaseModel):
    """ODIN Policy entity representing governance rules that apply to catalogs, schemas, tables, or columns."""
    policy_id: str = Field(..., description="Unique identifier for the policy")
    name: str = Field(..., description="Human-readable policy name")
    description: Optional[str] = Field(None, description="Policy description")
    policy_type: PolicyType = Field(..., description="Category of the policy")
    applies_to: List[str] = Field(default_factory=list, description="List of node IDs (catalog, schema, table, column) this policy applies to")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Additional policy properties (e.g., retention period, encryption algorithm)")


class LineageType(str, Enum):
    """Types of lineage relationships."""
    SOURCE = "SOURCE"
    TRANSFORMATION = "TRANSFORMATION"
    TARGET = "TARGET"


class LineageNode(BaseModel):
    """Node in a lineage graph (e.g., a source file, a table, a report)."""
    name: str = Field(..., description="Name of the lineage node")
    type: str = Field(..., description="Type of node (e.g., TABLE, FILE, REPORT)")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Additional properties")


class LineageRelationship(BaseModel):
    """Relationship between two lineage nodes."""
    source_node: str = Field(..., description="ID of the source node")
    target_node: str = Field(..., description="ID of the target node")
    type: LineageType = Field(..., description="Type of lineage relationship")
    transformation_logic: Optional[str] = Field(None, description="Logic applied during transformation")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Additional properties")


class DataQualityRule(BaseModel):
    """Rule for assessing data quality."""
    name: str = Field(..., description="Name of the rule")
    description: Optional[str] = Field(None, description="Description of the rule")
    expression: str = Field(..., description="Expression or logic to evaluate the rule")
    dimension: str = Field(..., description="Quality dimension (e.g., COMPLETENESS, ACCURACY)")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Additional properties")


class DataQualityScore(BaseModel):
    """Score resulting from a data quality rule evaluation."""
    rule_name: str = Field(..., description="Name of the rule evaluated")
    target_node: str = Field(..., description="ID of the node (table/column) evaluated")
    score: float = Field(..., description="Quality score (0.0 to 1.0)")
    timestamp: str = Field(..., description="Time of evaluation")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Additional properties")


class UsageStats(BaseModel):
    """Usage statistics for a data asset."""
    target_node: str = Field(..., description="ID of the asset (table/column)")
    query_count: int = Field(0, description="Number of times queried")
    unique_users: int = Field(0, description="Number of unique users accessing")
    last_accessed: Optional[str] = Field(None, description="Timestamp of last access")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Additional properties")
