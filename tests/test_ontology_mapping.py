
import sys
import os
sys.path.append(os.getcwd())

import pytest
from src.application.agents.knowledge_manager.ontology_mapper import OntologyMapper
from domain.ontologies.odin import ODIN
from domain.ontologies.schema_org import SCHEMA

def test_ontology_mapper_table():
    mapper = OntologyMapper()
    labels, _ = mapper.map_entity("Table", {})
    
    assert ODIN.DATA_ENTITY in labels
    assert SCHEMA.DATASET in labels
    assert "Table" in labels

def test_ontology_mapper_column():
    mapper = OntologyMapper()
    labels, _ = mapper.map_entity("Column", {})
    
    assert ODIN.ATTRIBUTE in labels
    assert SCHEMA.PROPERTY in labels
    assert "Column" in labels

def test_ontology_mapper_unknown():
    mapper = OntologyMapper()
    labels, _ = mapper.map_entity("UnknownThing", {})
    
    # Should just keep original
    assert "Unknownthing" in labels # Capitalized
    assert len(labels) == 1

if __name__ == "__main__":
    # Manual run
    try:
        test_ontology_mapper_table()
        print("✅ test_ontology_mapper_table passed")
        test_ontology_mapper_column()
        print("✅ test_ontology_mapper_column passed")
        test_ontology_mapper_unknown()
        print("✅ test_ontology_mapper_unknown passed")
    except Exception as e:
        print(f"❌ Tests failed: {e}")
