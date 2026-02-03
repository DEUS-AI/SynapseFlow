"""
Table, Column and ColumnStats metadata models.

This module contains models for data structure entities including tables,
columns and their statistics.
"""

from pydantic import Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from .base import MetadataEntity


class ColumnStats(MetadataEntity):
    """
    Column statistics entity representing statistical information about a column.
    
    This entity tracks various statistics about column data including counts,
    distributions, and historical information.
    """
    
    column_id: str = Field(..., description="ID of the column these stats belong to")
    previous_stats_id: Optional[str] = Field(None, description="ID of the previous stats snapshot")
    row_count: int = Field(default=0, description="Total number of rows")
    null_count: int = Field(default=0, description="Number of null values")
    unique_count: int = Field(default=0, description="Number of unique values")
    min_value: Optional[Any] = Field(None, description="Minimum value in the column")
    max_value: Optional[Any] = Field(None, description="Maximum value in the column")
    avg_value: Optional[float] = Field(None, description="Average value (for numeric columns)")
    distinct_values: List[Any] = Field(default_factory=list, description="List of distinct values (sampled)")
    data_type: str = Field(..., description="Data type of the column")
    last_analyzed: datetime = Field(default_factory=datetime.now, description="When stats were last calculated")
    
    def __init__(self, **data):
        data['entity_type'] = "ColumnStats"
        super().__init__(**data)
    
    def update_stats(self, new_stats: Dict[str, Any]) -> None:
        """Update statistics with new values."""
        for key, value in new_stats.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self.last_analyzed = datetime.now()
        self.updated_at = datetime.now()
    
    def get_null_percentage(self) -> float:
        """Calculate the percentage of null values."""
        if self.row_count == 0:
            return 0.0
        return (self.null_count / self.row_count) * 100
    
    def get_uniqueness_ratio(self) -> float:
        """Calculate the uniqueness ratio of the column."""
        if self.row_count == 0:
            return 0.0
        return (self.unique_count / self.row_count) * 100
    
    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "id": "stats-001",
                "name": "customer_id_stats",
                "description": "Statistics for customer_id column",
                "column_id": "col-001",
                "row_count": 1000000,
                "null_count": 0,
                "unique_count": 1000000,
                "min_value": 1,
                "max_value": 1000000,
                "data_type": "integer",
                "last_analyzed": "2024-01-15T10:30:00"
            }
        }


class Column(MetadataEntity):
    """
    Column entity representing a column in a database table.
    
    A column defines the structure and properties of data within a table.
    """
    
    table_id: str = Field(..., description="ID of the table containing this column")
    column_name: str = Field(..., description="Name of the column in the table")
    data_type: str = Field(..., description="Data type of the column")
    nullable: bool = Field(default=True, description="Whether the column can contain null values")
    primary_key: bool = Field(default=False, description="Whether this column is part of the primary key")
    foreign_key: bool = Field(default=False, description="Whether this column is a foreign key")
    referenced_table: Optional[str] = Field(None, description="Table referenced by foreign key")
    referenced_column: Optional[str] = Field(None, description="Column referenced by foreign key")
    default_value: Optional[Any] = Field(None, description="Default value for the column")
    constraints: List[str] = Field(default_factory=list, description="List of constraints on the column")
    stats_id: Optional[str] = Field(None, description="ID of the column statistics")
    position: int = Field(..., description="Position of the column in the table")
    
    def __init__(self, **data):
        data['entity_type'] = "Column"
        super().__init__(**data)
    
    def set_stats(self, stats_id: str) -> None:
        """Set the statistics for this column."""
        self.stats_id = stats_id
        self.updated_at = datetime.now()
    
    def add_constraint(self, constraint: str) -> None:
        """Add a constraint to this column."""
        if constraint not in self.constraints:
            self.constraints.append(constraint)
            self.updated_at = datetime.now()
    
    def remove_constraint(self, constraint: str) -> None:
        """Remove a constraint from this column."""
        if constraint in self.constraints:
            self.constraints.remove(constraint)
            self.updated_at = datetime.now()
    
    def set_foreign_key_reference(self, table: str, column: str) -> None:
        """Set the foreign key reference."""
        self.foreign_key = True
        self.referenced_table = table
        self.referenced_column = column
        self.updated_at = datetime.now()
    
    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "id": "col-001",
                "name": "customer_id",
                "description": "Unique identifier for customer",
                "table_id": "table-001",
                "column_name": "customer_id",
                "data_type": "integer",
                "nullable": False,
                "primary_key": True,
                "foreign_key": False,
                "position": 1,
                "constraints": ["NOT NULL", "UNIQUE"]
            }
        }


class Table(MetadataEntity):
    """
    Table entity representing a database table.
    
    A table is a collection of related data organized in rows and columns.
    It belongs to a specific schema and contains columns.
    """
    
    schema_id: str = Field(..., description="ID of the schema containing this table")
    table_name: str = Field(..., description="Name of the table in the database")
    columns: List[str] = Field(default_factory=list, description="List of column IDs in this table")
    primary_keys: List[str] = Field(default_factory=list, description="List of primary key column IDs")
    foreign_keys: List[str] = Field(default_factory=list, description="List of foreign key column IDs")
    indexes: List[str] = Field(default_factory=list, description="List of index IDs on this table")
    row_count: Optional[int] = Field(None, description="Approximate number of rows in the table")
    size_bytes: Optional[int] = Field(None, description="Size of the table in bytes")
    watermark_id: Optional[str] = Field(None, description="ID of the watermark for this table")
    replicated_from: Optional[str] = Field(None, description="ID of the table this is replicated from")
    partition_key: Optional[str] = Field(None, description="Partition key column if table is partitioned")
    storage_format: Optional[str] = Field(None, description="Storage format (e.g., 'parquet', 'orc', 'text')")
    
    def __init__(self, **data):
        data['entity_type'] = "Table"
        super().__init__(**data)
    
    def add_column(self, column_id: str) -> None:
        """Add a column to this table."""
        if column_id not in self.columns:
            self.columns.append(column_id)
            self.updated_at = datetime.now()
    
    def remove_column(self, column_id: str) -> None:
        """Remove a column from this table."""
        if column_id in self.columns:
            self.columns.remove(column_id)
            self.updated_at = datetime.now()
    
    def add_primary_key(self, column_id: str) -> None:
        """Add a column as primary key."""
        if column_id not in self.primary_keys:
            self.primary_keys.append(column_id)
            self.updated_at = datetime.now()
    
    def remove_primary_key(self, column_id: str) -> None:
        """Remove a column from primary keys."""
        if column_id in self.primary_keys:
            self.primary_keys.remove(column_id)
            self.updated_at = datetime.now()
    
    def add_foreign_key(self, column_id: str) -> None:
        """Add a column as foreign key."""
        if column_id not in self.foreign_keys:
            self.foreign_keys.append(column_id)
            self.updated_at = datetime.now()
    
    def remove_foreign_key(self, column_id: str) -> None:
        """Remove a column from foreign keys."""
        if column_id in self.foreign_keys:
            self.foreign_keys.remove(column_id)
            self.updated_at = datetime.now()
    
    def add_index(self, index_id: str) -> None:
        """Add an index to this table."""
        if index_id not in self.indexes:
            self.indexes.append(index_id)
            self.updated_at = datetime.now()
    
    def remove_index(self, index_id: str) -> None:
        """Remove an index from this table."""
        if index_id in self.indexes:
            self.indexes.remove(index_id)
            self.updated_at = datetime.now()
    
    def set_watermark(self, watermark_id: str) -> None:
        """Set the watermark for this table."""
        self.watermark_id = watermark_id
        self.updated_at = datetime.now()
    
    def get_column_count(self) -> int:
        """Get the total number of columns in this table."""
        return len(self.columns)
    
    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "id": "table-001",
                "name": "customers",
                "description": "Customer information table",
                "schema_id": "schema-001",
                "table_name": "customers",
                "columns": ["col-001", "col-002", "col-003"],
                "primary_keys": ["col-001"],
                "foreign_keys": [],
                "row_count": 1000000,
                "size_bytes": 52428800,
                "storage_format": "parquet"
            }
        }
