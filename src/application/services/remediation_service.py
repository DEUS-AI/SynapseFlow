"""Ontology Batch Remediation Service.

Provides programmatic access to ontology remediation operations:
- dry_run(): Preview what would change without modifying data
- execute(): Run full batch remediation pipeline
- rollback(): Undo a specific remediation batch
- get_orphans(): List entities flagged as orphans
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)


# ========================================
# Remediation Query Definitions
# ========================================

REMEDIATION_QUERIES: List[Tuple[str, str, str]] = [
    (
        "conversation_structural_migration",
        "Migrate ConversationSession/Message from APPLICATION/usage to structural",
        """
        MATCH (n)
        WHERE any(label IN labels(n) WHERE label IN ['ConversationSession', 'Message'])
          AND NOT coalesce(n._is_structural, false)
        REMOVE n._ontology_mapped, n._canonical_type
        SET n._is_structural = true,
            n._exclude_from_ontology = true,
            n._marked_structural_at = datetime(),
            n._remediation_date = datetime(),
            n._remediation_batch = $batch_id
        RETURN count(n) as updated
        """
    ),
    (
        "business_concept_mapping",
        "Map BusinessConcept/Concept variants to canonical form",
        """
        MATCH (n)
        WHERE (n.type IN ['BusinessConcept', 'businessconcept', 'Concept', 'concept', 'business_concept']
               OR any(label IN labels(n) WHERE label IN ['BusinessConcept', 'Concept']))
          AND NOT coalesce(n._ontology_mapped, false)
        SET n._ontology_mapped = true,
            n._canonical_type = 'business_concept',
            n.layer = COALESCE(n.layer, 'REASONING'),
            n._remediation_date = datetime(),
            n._remediation_batch = $batch_id
        RETURN count(n) as updated
        """
    ),
    (
        "person_mapping",
        "Map Person/People/User variants to person",
        """
        MATCH (n)
        WHERE (n.type IN ['Person', 'person', 'People', 'people', 'User', 'user', 'Owner', 'owner', 'Stakeholder']
               OR any(label IN labels(n) WHERE label IN ['Person', 'People', 'User']))
          AND NOT coalesce(n._ontology_mapped, false)
        SET n._ontology_mapped = true,
            n._canonical_type = 'person',
            n.layer = COALESCE(n.layer, 'SEMANTIC'),
            n._remediation_date = datetime(),
            n._remediation_batch = $batch_id
        RETURN count(n) as updated
        """
    ),
    (
        "data_product_mapping",
        "Map DataProduct variants to data_product",
        """
        MATCH (n)
        WHERE (n.type IN ['DataProduct', 'data_product', 'Data Product', 'dataproduct', 'Product']
               OR any(label IN labels(n) WHERE label IN ['DataProduct', 'InformationAsset']))
          AND NOT coalesce(n._ontology_mapped, false)
        SET n._ontology_mapped = true,
            n._canonical_type = 'data_product',
            n.layer = COALESCE(n.layer, 'SEMANTIC'),
            n._remediation_date = datetime(),
            n._remediation_batch = $batch_id
        RETURN count(n) as updated
        """
    ),
    (
        "table_mapping",
        "Map Table/DataEntity variants to table",
        """
        MATCH (n)
        WHERE (n.type IN ['Table', 'table', 'DataEntity', 'data_entity', 'Entity', 'entity']
               OR any(label IN labels(n) WHERE label IN ['Table', 'DataEntity']))
          AND NOT any(label IN labels(n) WHERE label IN ['Chunk', 'Document', 'ExtractedEntity'])
          AND NOT coalesce(n._ontology_mapped, false)
        SET n._ontology_mapped = true,
            n._canonical_type = 'table',
            n.layer = COALESCE(n.layer, 'PERCEPTION'),
            n._remediation_date = datetime(),
            n._remediation_batch = $batch_id
        RETURN count(n) as updated
        """
    ),
    (
        "column_mapping",
        "Map Column/Attribute variants to column",
        """
        MATCH (n)
        WHERE (n.type IN ['Column', 'column', 'Attribute', 'attribute', 'Field', 'field']
               OR any(label IN labels(n) WHERE label IN ['Column', 'Attribute']))
          AND NOT coalesce(n._ontology_mapped, false)
        SET n._ontology_mapped = true,
            n._canonical_type = 'column',
            n.layer = COALESCE(n.layer, 'PERCEPTION'),
            n._remediation_date = datetime(),
            n._remediation_batch = $batch_id
        RETURN count(n) as updated
        """
    ),
    (
        "process_mapping",
        "Map Process/Pipeline/ETL variants to process",
        """
        MATCH (n)
        WHERE (n.type IN ['Process', 'process', 'Pipeline', 'pipeline', 'ETL', 'Job', 'job', 'Workflow']
               OR any(label IN labels(n) WHERE label IN ['Process', 'Pipeline']))
          AND NOT coalesce(n._ontology_mapped, false)
        SET n._ontology_mapped = true,
            n._canonical_type = 'process',
            n.layer = COALESCE(n.layer, 'REASONING'),
            n._remediation_date = datetime(),
            n._remediation_batch = $batch_id
        RETURN count(n) as updated
        """
    ),
    (
        "disease_mapping",
        "Map Disease/Condition variants to disease",
        """
        MATCH (n)
        WHERE (n.type IN ['Disease', 'disease', 'medical_condition', 'MedicalCondition', 'Condition', 'condition', 'Disorder']
               OR any(label IN labels(n) WHERE label IN ['Disease', 'Condition']))
          AND NOT coalesce(n._ontology_mapped, false)
        SET n._ontology_mapped = true,
            n._canonical_type = 'disease',
            n.layer = COALESCE(n.layer, 'SEMANTIC'),
            n._remediation_date = datetime(),
            n._remediation_batch = $batch_id
        RETURN count(n) as updated
        """
    ),
    (
        "drug_mapping",
        "Map Drug/Medication variants to drug",
        """
        MATCH (n)
        WHERE (n.type IN ['Drug', 'drug', 'Medication', 'medication', 'Medicine', 'Pharmaceutical']
               OR any(label IN labels(n) WHERE label IN ['Drug', 'Medication']))
          AND NOT coalesce(n._ontology_mapped, false)
        SET n._ontology_mapped = true,
            n._canonical_type = 'drug',
            n.layer = COALESCE(n.layer, 'SEMANTIC'),
            n._remediation_date = datetime(),
            n._remediation_batch = $batch_id
        RETURN count(n) as updated
        """
    ),
    (
        "symptom_mapping",
        "Map Symptom variants to symptom",
        """
        MATCH (n)
        WHERE (n.type IN ['Symptom', 'symptom', 'Sign', 'Manifestation']
               OR any(label IN labels(n) WHERE label IN ['Symptom']))
          AND NOT coalesce(n._ontology_mapped, false)
        SET n._ontology_mapped = true,
            n._canonical_type = 'symptom',
            n.layer = COALESCE(n.layer, 'PERCEPTION'),
            n._remediation_date = datetime(),
            n._remediation_batch = $batch_id
        RETURN count(n) as updated
        """
    ),
    (
        "treatment_mapping",
        "Map Treatment/Therapy variants to treatment",
        """
        MATCH (n)
        WHERE (n.type IN ['Treatment', 'treatment', 'Therapy', 'therapy', 'Procedure', 'Intervention']
               OR any(label IN labels(n) WHERE label IN ['Treatment', 'Therapy']))
          AND NOT coalesce(n._ontology_mapped, false)
        SET n._ontology_mapped = true,
            n._canonical_type = 'treatment',
            n.layer = COALESCE(n.layer, 'SEMANTIC'),
            n._remediation_date = datetime(),
            n._remediation_batch = $batch_id
        RETURN count(n) as updated
        """
    ),
    (
        "organization_mapping",
        "Map Organization variants to organization",
        """
        MATCH (n)
        WHERE (n.type IN ['Organization', 'organization', 'Company', 'company', 'Institution', 'University', 'Hospital']
               OR any(label IN labels(n) WHERE label IN ['Organization']))
          AND NOT coalesce(n._ontology_mapped, false)
        SET n._ontology_mapped = true,
            n._canonical_type = 'organization',
            n.layer = COALESCE(n.layer, 'APPLICATION'),
            n._remediation_date = datetime(),
            n._remediation_batch = $batch_id
        RETURN count(n) as updated
        """
    ),
    (
        "gene_mapping",
        "Map Gene variants to gene",
        """
        MATCH (n)
        WHERE (n.type IN ['Gene', 'gene', 'GeneticMarker', 'genetic_marker']
               OR any(label IN labels(n) WHERE label IN ['Gene']))
          AND NOT coalesce(n._ontology_mapped, false)
        SET n._ontology_mapped = true,
            n._canonical_type = 'gene',
            n.layer = COALESCE(n.layer, 'REASONING'),
            n._remediation_date = datetime(),
            n._remediation_batch = $batch_id
        RETURN count(n) as updated
        """
    ),
    (
        "metric_mapping",
        "Map Metric/KPI variants to metric",
        """
        MATCH (n)
        WHERE (n.type IN ['Metric', 'metric', 'KPI', 'kpi', 'Indicator', 'Measure']
               OR any(label IN labels(n) WHERE label IN ['Metric', 'KPI']))
          AND NOT coalesce(n._ontology_mapped, false)
        SET n._ontology_mapped = true,
            n._canonical_type = 'metric',
            n.layer = COALESCE(n.layer, 'APPLICATION'),
            n._remediation_date = datetime(),
            n._remediation_batch = $batch_id
        RETURN count(n) as updated
        """
    ),
    (
        "system_mapping",
        "Map System/Application variants to system",
        """
        MATCH (n)
        WHERE (n.type IN ['System', 'system', 'Application', 'application', 'Service', 'service']
               OR any(label IN labels(n) WHERE label IN ['System', 'Application']))
          AND NOT coalesce(n._ontology_mapped, false)
        SET n._ontology_mapped = true,
            n._canonical_type = 'system',
            n.layer = COALESCE(n.layer, 'PERCEPTION'),
            n._remediation_date = datetime(),
            n._remediation_batch = $batch_id
        RETURN count(n) as updated
        """
    ),
    (
        "database_mapping",
        "Map Database variants to database",
        """
        MATCH (n)
        WHERE (n.type IN ['Database', 'database', 'DB', 'db']
               OR any(label IN labels(n) WHERE label IN ['Database']))
          AND NOT coalesce(n._ontology_mapped, false)
        SET n._ontology_mapped = true,
            n._canonical_type = 'database',
            n.layer = COALESCE(n.layer, 'PERCEPTION'),
            n._remediation_date = datetime(),
            n._remediation_batch = $batch_id
        RETURN count(n) as updated
        """
    ),
    (
        "factunit_mapping",
        "Map FactUnit/Bridge entities to business_concept",
        """
        MATCH (n)
        WHERE any(label IN labels(n) WHERE label IN ['FactUnit', 'Bridge'])
          AND NOT coalesce(n._ontology_mapped, false)
        SET n._ontology_mapped = true,
            n._canonical_type = 'business_concept',
            n.layer = COALESCE(n.layer, 'REASONING'),
            n._remediation_date = datetime(),
            n._remediation_batch = $batch_id
        RETURN count(n) as updated
        """
    ),
    (
        "patient_mapping",
        "Map Patient entities to person",
        """
        MATCH (n)
        WHERE any(label IN labels(n) WHERE label IN ['Patient', 'patient'])
          AND NOT coalesce(n._ontology_mapped, false)
        SET n._ontology_mapped = true,
            n._canonical_type = 'person',
            n.layer = COALESCE(n.layer, 'SEMANTIC'),
            n._remediation_date = datetime(),
            n._remediation_batch = $batch_id
        RETURN count(n) as updated
        """
    ),
    (
        "medication_mapping",
        "Map Medication/MedicalEntity entities to drug",
        """
        MATCH (n)
        WHERE any(label IN labels(n) WHERE label IN ['Medication', 'MedicalEntity'])
          AND NOT coalesce(n._ontology_mapped, false)
        SET n._ontology_mapped = true,
            n._canonical_type = 'drug',
            n.layer = COALESCE(n.layer, 'SEMANTIC'),
            n._remediation_date = datetime(),
            n._remediation_batch = $batch_id
        RETURN count(n) as updated
        """
    ),
    (
        "diagnosis_mapping",
        "Map Diagnosis entities to disease",
        """
        MATCH (n)
        WHERE any(label IN labels(n) WHERE label IN ['Diagnosis'])
          AND NOT coalesce(n._ontology_mapped, false)
        SET n._ontology_mapped = true,
            n._canonical_type = 'disease',
            n.layer = COALESCE(n.layer, 'SEMANTIC'),
            n._remediation_date = datetime(),
            n._remediation_batch = $batch_id
        RETURN count(n) as updated
        """
    ),
    (
        "protein_mapping",
        "Map Protein/Enzyme variants to protein",
        """
        MATCH (n)
        WHERE (n.type IN ['Protein', 'protein', 'Enzyme', 'enzyme']
               OR any(label IN labels(n) WHERE label IN ['Protein', 'Enzyme']))
          AND NOT coalesce(n._ontology_mapped, false)
        SET n._ontology_mapped = true,
            n._canonical_type = 'protein',
            n.layer = COALESCE(n.layer, 'SEMANTIC'),
            n._remediation_date = datetime(),
            n._remediation_batch = $batch_id
        RETURN count(n) as updated
        """
    ),
    (
        "biomarker_mapping",
        "Map Biomarker variants to biomarker",
        """
        MATCH (n)
        WHERE (n.type IN ['Biomarker', 'biomarker', 'BiologicalMarker', 'biological_marker']
               OR any(label IN labels(n) WHERE label IN ['Biomarker']))
          AND NOT coalesce(n._ontology_mapped, false)
        SET n._ontology_mapped = true,
            n._canonical_type = 'biomarker',
            n.layer = COALESCE(n.layer, 'PERCEPTION'),
            n._remediation_date = datetime(),
            n._remediation_batch = $batch_id
        RETURN count(n) as updated
        """
    ),
    (
        "cell_type_mapping",
        "Map Cell Type variants to cell_type",
        """
        MATCH (n)
        WHERE (n.type IN ['Cell Type', 'cell_type', 'CellType', 'celltype', 'Cell']
               OR any(label IN labels(n) WHERE label IN ['CellType', 'Cell']))
          AND NOT coalesce(n._ontology_mapped, false)
        SET n._ontology_mapped = true,
            n._canonical_type = 'cell_type',
            n.layer = COALESCE(n.layer, 'SEMANTIC'),
            n._remediation_date = datetime(),
            n._remediation_batch = $batch_id
        RETURN count(n) as updated
        """
    ),
    (
        "organism_mapping",
        "Map Organism/Species/Pathogen variants to organism",
        """
        MATCH (n)
        WHERE (n.type IN ['Organism', 'organism', 'Species', 'species', 'Pathogen', 'pathogen', 'Bacterium', 'bacteria']
               OR any(label IN labels(n) WHERE label IN ['Organism', 'Species', 'Pathogen']))
          AND NOT coalesce(n._ontology_mapped, false)
        SET n._ontology_mapped = true,
            n._canonical_type = 'organism',
            n.layer = COALESCE(n.layer, 'SEMANTIC'),
            n._remediation_date = datetime(),
            n._remediation_batch = $batch_id
        RETURN count(n) as updated
        """
    ),
    (
        "virus_mapping",
        "Map Virus variants to virus",
        """
        MATCH (n)
        WHERE (n.type IN ['Virus', 'virus', 'ViralAgent', 'viral_agent']
               OR any(label IN labels(n) WHERE label IN ['Virus']))
          AND NOT coalesce(n._ontology_mapped, false)
        SET n._ontology_mapped = true,
            n._canonical_type = 'virus',
            n.layer = COALESCE(n.layer, 'SEMANTIC'),
            n._remediation_date = datetime(),
            n._remediation_batch = $batch_id
        RETURN count(n) as updated
        """
    ),
    (
        "food_component_mapping",
        "Map FoodComponent/Nutrient/Vitamin variants to food_component",
        """
        MATCH (n)
        WHERE (n.type IN ['FoodComponent', 'food_component', 'Food Component', 'Nutrient', 'nutrient', 'Vitamin', 'vitamin', 'DietarySubstance']
               OR any(label IN labels(n) WHERE label IN ['FoodComponent', 'Nutrient']))
          AND NOT coalesce(n._ontology_mapped, false)
        SET n._ontology_mapped = true,
            n._canonical_type = 'food_component',
            n.layer = COALESCE(n.layer, 'SEMANTIC'),
            n._remediation_date = datetime(),
            n._remediation_batch = $batch_id
        RETURN count(n) as updated
        """
    ),
    (
        "genus_mapping",
        "Map Genus variants to organism",
        """
        MATCH (n)
        WHERE (n.type IN ['Genus', 'genus']
               OR any(label IN labels(n) WHERE label IN ['Genus']))
          AND NOT coalesce(n._ontology_mapped, false)
        SET n._ontology_mapped = true,
            n._canonical_type = 'organism',
            n.layer = COALESCE(n.layer, 'SEMANTIC'),
            n._remediation_date = datetime(),
            n._remediation_batch = $batch_id
        RETURN count(n) as updated
        """
    ),
    (
        "model_organism_mapping",
        "Map Model Organism variants to organism",
        """
        MATCH (n)
        WHERE (n.type IN ['Model Organism', 'model_organism', 'ModelOrganism']
               OR any(label IN labels(n) WHERE label IN ['ModelOrganism']))
          AND NOT coalesce(n._ontology_mapped, false)
        SET n._ontology_mapped = true,
            n._canonical_type = 'organism',
            n.layer = COALESCE(n.layer, 'SEMANTIC'),
            n._remediation_date = datetime(),
            n._remediation_batch = $batch_id
        RETURN count(n) as updated
        """
    ),
    (
        "null_type_label_inference",
        "Infer type for null-type entities from their Neo4j labels",
        """
        MATCH (n)
        WHERE n.type IS NULL
          AND NOT coalesce(n._ontology_mapped, false)
          AND NOT coalesce(n._is_structural, false)
          AND any(label IN labels(n) WHERE label IN [
            'Disease', 'Drug', 'Symptom', 'Treatment', 'Test', 'Gene',
            'Pathway', 'Organization', 'Study', 'Protein', 'Biomarker',
            'Virus', 'Organism', 'CellType', 'Condition', 'Anatomy',
            'Mechanism', 'Interaction', 'Guideline', 'Protocol', 'FoodComponent'
          ])
        WITH n, [label IN labels(n) WHERE label IN [
            'Disease', 'Drug', 'Symptom', 'Treatment', 'Test', 'Gene',
            'Pathway', 'Organization', 'Study', 'Protein', 'Biomarker',
            'Virus', 'Organism', 'CellType', 'Condition', 'Anatomy',
            'Mechanism', 'Interaction', 'Guideline', 'Protocol', 'FoodComponent'
          ]][0] AS inferred_type
        SET n.type = inferred_type,
            n._canonical_type = toLower(inferred_type),
            n._ontology_mapped = true,
            n._type_inferred_from = 'label',
            n._remediation_date = datetime(),
            n._remediation_batch = $batch_id
        RETURN count(n) as updated
        """
    ),
    (
        "null_type_flag_review",
        "Flag remaining null-type entities for manual review",
        """
        MATCH (n)
        WHERE n.type IS NULL
          AND NOT coalesce(n._ontology_mapped, false)
          AND NOT coalesce(n._is_structural, false)
          AND NOT coalesce(n._is_noise, false)
          AND NOT coalesce(n._needs_review, false)
        SET n._needs_review = true,
            n._review_reason = 'null_type',
            n._remediation_date = datetime(),
            n._remediation_batch = $batch_id
        RETURN count(n) as updated
        """
    ),
    (
        "unknown_type_flag_review",
        "Flag Unknown-type entities for review without ontology mapping",
        """
        MATCH (n)
        WHERE n.type IN ['Unknown', 'unknown']
          AND NOT coalesce(n._ontology_mapped, false)
          AND NOT coalesce(n._is_structural, false)
          AND NOT coalesce(n._is_noise, false)
          AND NOT coalesce(n._needs_review, false)
        SET n._needs_review = true,
            n._review_reason = 'unknown_type',
            n._remediation_date = datetime(),
            n._remediation_batch = $batch_id
        RETURN count(n) as updated
        """
    ),
    (
        "orphan_node_flagging",
        "Flag entities with zero relationships as orphans",
        """
        MATCH (n)
        WHERE n.id IS NOT NULL
          AND NOT coalesce(n._is_structural, false)
          AND NOT coalesce(n._is_orphan, false)
          AND NOT EXISTS { MATCH (n)-[]-() }
        SET n._is_orphan = true,
            n._remediation_date = datetime(),
            n._remediation_batch = $batch_id
        RETURN count(n) as updated
        """
    ),
    (
        "orphan_source_classification",
        "Classify orphan nodes by source graph (episodic/knowledge/unclassified)",
        """
        MATCH (n)
        WHERE coalesce(n._is_orphan, false) = true
          AND n._orphan_source IS NULL
        SET n._orphan_source = CASE
            WHEN any(label IN labels(n) WHERE label IN ['EntityNode', 'EpisodicNode']) THEN 'episodic'
            WHEN any(label IN labels(n) WHERE label IN [
                'Disease', 'Drug', 'Symptom', 'Treatment', 'Test', 'Gene',
                'Pathway', 'Organization', 'Study', 'Protein', 'Biomarker',
                'Virus', 'Organism', 'CellType', 'Condition', 'Anatomy',
                'Mechanism', 'Interaction', 'Guideline', 'Protocol', 'FoodComponent',
                'DataEntity', 'Attribute', 'InformationAsset', 'BusinessConcept',
                'Domain', 'DataQualityRule'
            ]) THEN 'knowledge'
            ELSE 'unclassified'
            END,
            n._remediation_date = datetime(),
            n._remediation_batch = $batch_id
        RETURN count(n) as updated
        """
    ),
    (
        "type_consistency_normalization",
        "Normalize inconsistent canonical type mappings",
        """
        MATCH (n)
        WHERE coalesce(n._ontology_mapped, false) = true
          AND n.type IS NOT NULL
          AND n._canonical_type IS NOT NULL
          AND NOT coalesce(n._consistency_fixed, false)
          AND n._canonical_type <> CASE toLower(trim(replace(replace(n.type, '-', '_'), ' ', '_')))
            WHEN 'diseases' THEN 'disease'
            WHEN 'medical_condition' THEN 'disease'
            WHEN 'disorder' THEN 'disease'
            WHEN 'syndrome' THEN 'disease'
            WHEN 'illness' THEN 'disease'
            WHEN 'conditions' THEN 'condition'
            WHEN 'medications' THEN 'drug'
            WHEN 'medication' THEN 'drug'
            WHEN 'compound' THEN 'drug'
            WHEN 'pharmaceutical' THEN 'drug'
            WHEN 'medicine' THEN 'drug'
            WHEN 'therapy' THEN 'treatment'
            WHEN 'procedure' THEN 'treatment'
            WHEN 'intervention' THEN 'treatment'
            WHEN 'sign' THEN 'symptom'
            WHEN 'signs' THEN 'symptom'
            WHEN 'manifestation' THEN 'symptom'
            WHEN 'organisms' THEN 'organism'
            WHEN 'species' THEN 'organism'
            WHEN 'pathogen' THEN 'organism'
            WHEN 'bacterium' THEN 'organism'
            WHEN 'bacteria' THEN 'organism'
            WHEN 'genus' THEN 'organism'
            WHEN 'model_organism' THEN 'organism'
            WHEN 'proteins' THEN 'protein'
            WHEN 'enzyme' THEN 'protein'
            WHEN 'enzymes' THEN 'protein'
            WHEN 'nutrient' THEN 'food_component'
            WHEN 'nutrients' THEN 'food_component'
            WHEN 'vitamin' THEN 'food_component'
            WHEN 'vitamins' THEN 'food_component'
            WHEN 'dietary_substance' THEN 'food_component'
            ELSE toLower(trim(replace(replace(n.type, '-', '_'), ' ', '_')))
            END
        SET n._canonical_type = CASE toLower(trim(replace(replace(n.type, '-', '_'), ' ', '_')))
            WHEN 'diseases' THEN 'disease'
            WHEN 'medical_condition' THEN 'disease'
            WHEN 'disorder' THEN 'disease'
            WHEN 'syndrome' THEN 'disease'
            WHEN 'illness' THEN 'disease'
            WHEN 'conditions' THEN 'condition'
            WHEN 'medications' THEN 'drug'
            WHEN 'medication' THEN 'drug'
            WHEN 'compound' THEN 'drug'
            WHEN 'pharmaceutical' THEN 'drug'
            WHEN 'medicine' THEN 'drug'
            WHEN 'therapy' THEN 'treatment'
            WHEN 'procedure' THEN 'treatment'
            WHEN 'intervention' THEN 'treatment'
            WHEN 'sign' THEN 'symptom'
            WHEN 'signs' THEN 'symptom'
            WHEN 'manifestation' THEN 'symptom'
            WHEN 'organisms' THEN 'organism'
            WHEN 'species' THEN 'organism'
            WHEN 'pathogen' THEN 'organism'
            WHEN 'bacterium' THEN 'organism'
            WHEN 'bacteria' THEN 'organism'
            WHEN 'genus' THEN 'organism'
            WHEN 'model_organism' THEN 'organism'
            WHEN 'proteins' THEN 'protein'
            WHEN 'enzyme' THEN 'protein'
            WHEN 'enzymes' THEN 'protein'
            WHEN 'nutrient' THEN 'food_component'
            WHEN 'nutrients' THEN 'food_component'
            WHEN 'vitamin' THEN 'food_component'
            WHEN 'vitamins' THEN 'food_component'
            WHEN 'dietary_substance' THEN 'food_component'
            ELSE toLower(trim(replace(replace(n.type, '-', '_'), ' ', '_')))
            END,
            n._consistency_fixed = true,
            n._remediation_date = datetime(),
            n._remediation_batch = $batch_id
        RETURN count(n) as updated
        """
    ),
]

MARK_STRUCTURAL_QUERY = """
MATCH (n)
WHERE any(label IN labels(n) WHERE label IN ['Chunk', 'StructuralChunk', 'Document', 'DocumentQuality', 'ExtractedEntity', 'ConversationSession', 'Message'])
  AND NOT coalesce(n._is_structural, false)
SET n._is_structural = true,
    n._exclude_from_ontology = true,
    n._marked_structural_at = datetime()
RETURN count(n) as updated
"""

STOPWORDS = [
    "the", "a", "an", "and", "or", "is", "are", "was", "were",
    "this", "that", "these", "those", "it", "its",
    "however", "therefore", "thus", "hence",
    "also", "although", "because", "since", "while",
    "but", "yet", "so", "for", "nor",
    "be", "been", "being", "have", "has", "had",
    "do", "does", "did", "will", "would", "could", "should",
    "may", "might", "must", "can",
    "not", "no", "none", "all", "any", "some",
    "of", "in", "on", "at", "to", "from", "by", "with",
    "as", "if", "then", "else", "when", "where", "which", "who",
]

MARK_NOISE_QUERY = f"""
MATCH (e)
WHERE e.name IS NOT NULL
  AND NOT coalesce(e._is_structural, false)
  AND NOT coalesce(e._is_noise, false)
  AND (
    size(e.name) < 3
    OR toLower(trim(e.name)) IN {STOPWORDS}
  )
SET e._is_noise = true,
    e._exclude_from_ontology = true,
    e._noise_reason = CASE
        WHEN size(e.name) < 3 THEN 'short_name'
        ELSE 'stopword'
    END,
    e._marked_noise_at = datetime()
RETURN count(e) as updated
"""

PRE_STATS_QUERY = """
MATCH (n)
WHERE n.id IS NOT NULL
WITH n,
     coalesce(n._exclude_from_ontology, false) as excluded,
     coalesce(n._ontology_mapped, false) as mapped,
     any(label IN labels(n) WHERE label IN ['Chunk', 'Document', 'ExtractedEntity', 'ConversationSession', 'Message']) as is_structural
RETURN
    count(n) as total,
    sum(CASE WHEN NOT is_structural AND NOT excluded THEN 1 ELSE 0 END) as knowledge_entities,
    sum(CASE WHEN mapped THEN 1 ELSE 0 END) as already_mapped,
    sum(CASE WHEN is_structural THEN 1 ELSE 0 END) as structural_entities,
    sum(CASE WHEN excluded THEN 1 ELSE 0 END) as excluded_entities
"""

UNMAPPED_TYPES_QUERY = """
MATCH (n)
WHERE n.id IS NOT NULL
  AND NOT coalesce(n._ontology_mapped, false)
  AND NOT any(label IN labels(n) WHERE label IN ['Chunk', 'Document', 'ExtractedEntity', 'ConversationSession', 'Message'])
RETURN n.type as type, count(n) as count
ORDER BY count DESC
LIMIT $limit
"""

ROLLBACK_QUERY = """
MATCH (n)
WHERE n._remediation_batch = $batch_id
REMOVE n._ontology_mapped, n._canonical_type, n._remediation_date, n._remediation_batch
RETURN count(n) as rolled_back
"""

ORPHANS_QUERY = """
MATCH (n)
WHERE coalesce(n._is_orphan, false) = true
RETURN n.id as id, n.name as name, n.type as type, labels(n) as labels,
       n._canonical_type as canonical_type, n.layer as layer,
       n._orphan_source as orphan_source
ORDER BY n.name
LIMIT $limit
"""


def _convert_to_count_query(query: str) -> str:
    """Convert a remediation query to a count-only query for dry-run."""
    lines = query.strip().split("\n")
    match_where_lines = []
    in_set_block = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("SET "):
            in_set_block = True
            continue
        if stripped.startswith("RETURN "):
            break
        if in_set_block and (stripped.startswith("n.") or stripped.startswith("n._") or stripped.startswith("e.") or stripped.startswith("e._") or stripped == ""):
            continue
        if not in_set_block:
            match_where_lines.append(line)

    return "\n".join(match_where_lines) + "\nRETURN count(n) as would_update"


class RemediationService:
    """Service for ontology batch remediation operations."""

    def __init__(self, driver):
        """Initialize with a Neo4j async driver."""
        self.driver = driver

    async def get_pre_stats(self) -> Dict[str, Any]:
        """Get current statistics before remediation."""
        async with self.driver.session() as session:
            result = await session.run(PRE_STATS_QUERY)
            record = await result.single()
        return dict(record) if record else {}

    async def get_unmapped_types(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get top unmapped entity types."""
        async with self.driver.session() as session:
            result = await session.run(UNMAPPED_TYPES_QUERY, {"limit": limit})
            records = [record async for record in result]
        return [{"type": r["type"], "count": r["count"]} for r in records]

    async def dry_run(self) -> Dict[str, Any]:
        """Preview what remediation would change without modifying data."""
        logger.info("Running remediation dry-run...")

        stats = await self.get_pre_stats()
        unmapped = await self.get_unmapped_types()

        preview = []
        for name, description, query in REMEDIATION_QUERIES:
            count_query = _convert_to_count_query(query)
            try:
                async with self.driver.session() as session:
                    result = await session.run(count_query, {"batch_id": "dry_run"})
                    record = await result.single()
                    count = record["would_update"] if record else 0
                    preview.append({
                        "name": name,
                        "description": description,
                        "would_update": count,
                    })
            except Exception as e:
                logger.warning(f"Could not preview {name}: {e}")
                preview.append({
                    "name": name,
                    "description": description,
                    "would_update": -1,
                    "error": str(e),
                })

        return {
            "pre_stats": stats,
            "unmapped_types": unmapped,
            "remediation_preview": preview,
            "total_would_update": sum(
                p["would_update"] for p in preview
                if isinstance(p["would_update"], int) and p["would_update"] >= 0
            ),
        }

    async def execute(
        self,
        mark_structural: bool = True,
        mark_noise: bool = True,
    ) -> Dict[str, Any]:
        """Execute the full batch remediation pipeline."""
        batch_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        logger.info(f"Starting batch remediation: {batch_id}")

        pre_stats = await self.get_pre_stats()

        results: Dict[str, Any] = {
            "batch_id": batch_id,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "steps": [],
        }

        if mark_structural:
            logger.info("Marking structural entities...")
            async with self.driver.session() as session:
                result = await session.run(MARK_STRUCTURAL_QUERY)
                record = await result.single()
                count = record["updated"] if record else 0
                results["structural_marked"] = count
                logger.info(f"  Marked {count} structural entities")

        if mark_noise:
            logger.info("Marking noise entities...")
            async with self.driver.session() as session:
                result = await session.run(MARK_NOISE_QUERY)
                record = await result.single()
                count = record["updated"] if record else 0
                results["noise_marked"] = count
                logger.info(f"  Marked {count} noise entities")

        total_updated = 0
        for name, description, query in REMEDIATION_QUERIES:
            logger.info(f"Running: {name}")
            try:
                async with self.driver.session() as session:
                    result = await session.run(query, {"batch_id": batch_id})
                    record = await result.single()
                    count = record["updated"] if record else 0
                    total_updated += count
                    results["steps"].append({
                        "name": name,
                        "description": description,
                        "updated": count,
                        "status": "success",
                    })
                    logger.info(f"  Updated {count} entities")
            except Exception as e:
                logger.error(f"  Error: {e}")
                results["steps"].append({
                    "name": name,
                    "description": description,
                    "updated": 0,
                    "status": "error",
                    "error": str(e),
                })

        results["total_updated"] = total_updated
        results["completed_at"] = datetime.now(timezone.utc).isoformat()

        post_stats = await self.get_pre_stats()
        results["pre_stats"] = pre_stats
        results["post_stats"] = post_stats

        pre_mapped = pre_stats.get("already_mapped", 0)
        post_mapped = post_stats.get("already_mapped", 0)
        knowledge_entities = post_stats.get("knowledge_entities", 1)

        results["coverage_before"] = round(pre_mapped / knowledge_entities * 100, 2) if knowledge_entities else 0
        results["coverage_after"] = round(post_mapped / knowledge_entities * 100, 2) if knowledge_entities else 0

        return results

    async def rollback(self, batch_id: str) -> Dict[str, Any]:
        """Rollback a specific remediation batch."""
        logger.info(f"Rolling back batch: {batch_id}")

        async with self.driver.session() as session:
            result = await session.run(ROLLBACK_QUERY, {"batch_id": batch_id})
            record = await result.single()

        count = record["rolled_back"] if record else 0
        logger.info(f"Rolled back {count} entities")

        return {"batch_id": batch_id, "rolled_back": count}

    async def get_orphans(self, limit: int = 100) -> List[Dict[str, Any]]:
        """List entities flagged as orphans."""
        async with self.driver.session() as session:
            result = await session.run(ORPHANS_QUERY, {"limit": limit})
            records = [record async for record in result]

        return [
            {
                "id": r["id"],
                "name": r["name"],
                "type": r["type"],
                "labels": list(r["labels"]) if r["labels"] else [],
                "canonical_type": r["canonical_type"],
                "layer": r["layer"],
                "orphan_source": r["orphan_source"],
            }
            for r in records
        ]
