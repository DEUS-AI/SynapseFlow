#!/usr/bin/env python3
"""
Script to generate multiple DDA documents for autoimmune and inflammatory bowel disease domains.
This creates a comprehensive set of DDA documents covering various medical specialties.
"""

import os
from datetime import datetime

# Define the DDA domains and their specific content
DDA_DOMAINS = [
    {
        "name": "Ulcerative Colitis Management",
        "stakeholders": "Gastroenterologists, IBD Specialists, Colorectal Surgeons, Research Teams",
        "data_owner": "Director of IBD Center",
        "entities": [
            "Patient", "Disease Extent Assessment", "Colonoscopy Report", "Medication Therapy", 
            "Nutritional Assessment", "Surgical Intervention", "Quality of Life Assessment"
        ],
        "relationships": [
            "Patient → Disease Extent Assessment (1:N)",
            "Patient → Colonoscopy Report (1:N)",
            "Patient → Medication Therapy (1:N)",
            "Medication Therapy → Disease Extent Assessment (M:N)"
        ]
    },
    {
        "name": "Rheumatoid Arthritis Management",
        "stakeholders": "Rheumatologists, Physical Therapists, Occupational Therapists, Research Teams",
        "data_owner": "Chief Rheumatologist",
        "entities": [
            "Patient", "Joint Assessment", "Radiological Imaging", "Medication Therapy", 
            "Physical Therapy Session", "Functional Assessment", "Quality of Life Assessment"
        ],
        "relationships": [
            "Patient → Joint Assessment (1:N)",
            "Patient → Radiological Imaging (1:N)",
            "Patient → Medication Therapy (1:N)",
            "Joint Assessment → Radiological Imaging (M:N)"
        ]
    },
    {
        "name": "Multiple Sclerosis Management",
        "stakeholders": "Neurologists, MS Specialists, Physical Therapists, Research Teams",
        "data_owner": "Director of MS Center",
        "entities": [
            "Patient", "Neurological Assessment", "MRI Report", "Medication Therapy", 
            "Physical Therapy Session", "Cognitive Assessment", "Quality of Life Assessment"
        ],
        "relationships": [
            "Patient → Neurological Assessment (1:N)",
            "Patient → MRI Report (1:N)",
            "Patient → Medication Therapy (1:N)",
            "Neurological Assessment → MRI Report (M:N)"
        ]
    },
    {
        "name": "Lupus Management",
        "stakeholders": "Rheumatologists, Nephrologists, Dermatologists, Research Teams",
        "data_owner": "Chief Rheumatologist",
        "entities": [
            "Patient", "Disease Activity Assessment", "Laboratory Test", "Medication Therapy", 
            "Organ Involvement Assessment", "Skin Assessment", "Quality of Life Assessment"
        ],
        "relationships": [
            "Patient → Disease Activity Assessment (1:N)",
            "Patient → Laboratory Test (1:N)",
            "Patient → Medication Therapy (1:N)",
            "Disease Activity Assessment → Laboratory Test (M:N)"
        ]
    },
    {
        "name": "Psoriasis Management",
        "stakeholders": "Dermatologists, Rheumatologists, Primary Care Physicians, Research Teams",
        "data_owner": "Chief Dermatologist",
        "entities": [
            "Patient", "Skin Assessment", "Biopsy Report", "Medication Therapy", 
            "Phototherapy Session", "Joint Assessment", "Quality of Life Assessment"
        ],
        "relationships": [
            "Patient → Skin Assessment (1:N)",
            "Patient → Biopsy Report (1:N)",
            "Patient → Medication Therapy (1:N)",
            "Skin Assessment → Biopsy Report (M:N)"
        ]
    },
    {
        "name": "Type 1 Diabetes Management",
        "stakeholders": "Endocrinologists, Diabetes Educators, Primary Care Physicians, Research Teams",
        "data_owner": "Chief Endocrinologist",
        "entities": [
            "Patient", "Glucose Monitoring", "HbA1c Test", "Insulin Therapy", 
            "Complication Assessment", "Nutritional Assessment", "Quality of Life Assessment"
        ],
        "relationships": [
            "Patient → Glucose Monitoring (1:N)",
            "Patient → HbA1c Test (1:N)",
            "Patient → Insulin Therapy (1:N)",
            "Glucose Monitoring → HbA1c Test (M:N)"
        ]
    },
    {
        "name": "Celiac Disease Management",
        "stakeholders": "Gastroenterologists, Nutritionists, Primary Care Physicians, Research Teams",
        "data_owner": "Director of Gastroenterology",
        "entities": [
            "Patient", "Serological Test", "Endoscopy Report", "Dietary Assessment", 
            "Nutritional Assessment", "Complication Assessment", "Quality of Life Assessment"
        ],
        "relationships": [
            "Patient → Serological Test (1:N)",
            "Patient → Endoscopy Report (1:N)",
            "Patient → Dietary Assessment (1:N)",
            "Serological Test → Endoscopy Report (M:N)"
        ]
    },
    {
        "name": "Ankylosing Spondylitis Management",
        "stakeholders": "Rheumatologists, Physical Therapists, Radiologists, Research Teams",
        "data_owner": "Chief Rheumatologist",
        "entities": [
            "Patient", "Spinal Assessment", "Radiological Imaging", "Medication Therapy", 
            "Physical Therapy Session", "Functional Assessment", "Quality of Life Assessment"
        ],
        "relationships": [
            "Patient → Spinal Assessment (1:N)",
            "Patient → Radiological Imaging (1:N)",
            "Patient → Medication Therapy (1:N)",
            "Spinal Assessment → Radiological Imaging (M:N)"
        ]
    },
    {
        "name": "Sjögren's Syndrome Management",
        "stakeholders": "Rheumatologists, Ophthalmologists, Dentists, Research Teams",
        "data_owner": "Chief Rheumatologist",
        "entities": [
            "Patient", "Ocular Assessment", "Salivary Assessment", "Medication Therapy", 
            "Dental Assessment", "Systemic Assessment", "Quality of Life Assessment"
        ],
        "relationships": [
            "Patient → Ocular Assessment (1:N)",
            "Patient → Salivary Assessment (1:N)",
            "Patient → Medication Therapy (1:N)",
            "Ocular Assessment → Salivary Assessment (M:N)"
        ]
    },
    {
        "name": "Vasculitis Management",
        "stakeholders": "Rheumatologists, Nephrologists, Pulmonologists, Research Teams",
        "data_owner": "Chief Rheumatologist",
        "entities": [
            "Patient", "Vascular Assessment", "Biopsy Report", "Medication Therapy", 
            "Organ Involvement Assessment", "Imaging Study", "Quality of Life Assessment"
        ],
        "relationships": [
            "Patient → Vascular Assessment (1:N)",
            "Patient → Biopsy Report (1:N)",
            "Patient → Medication Therapy (1:N)",
            "Vascular Assessment → Biopsy Report (M:N)"
        ]
    },
    {
        "name": "Inflammatory Bowel Disease Research",
        "stakeholders": "Research Scientists, Clinical Trial Coordinators, Statisticians, Regulatory Teams",
        "data_owner": "Director of Clinical Research",
        "entities": [
            "Research Participant", "Clinical Trial", "Study Visit", "Laboratory Result", 
            "Adverse Event", "Study Medication", "Outcome Assessment"
        ],
        "relationships": [
            "Research Participant → Clinical Trial (M:N)",
            "Research Participant → Study Visit (1:N)",
            "Clinical Trial → Study Medication (1:N)",
            "Study Visit → Laboratory Result (1:N)"
        ]
    },
    {
        "name": "Autoimmune Disease Biobank",
        "stakeholders": "Laboratory Scientists, Research Coordinators, Data Managers, Regulatory Teams",
        "data_owner": "Director of Biobank",
        "entities": [
            "Donor", "Biospecimen", "Laboratory Test", "Storage Location", 
            "Quality Control", "Research Project", "Data Analysis"
        ],
        "relationships": [
            "Donor → Biospecimen (1:N)",
            "Biospecimen → Laboratory Test (1:N)",
            "Biospecimen → Storage Location (1:N)",
            "Research Project → Biospecimen (M:N)"
        ]
    },
    {
        "name": "Pediatric Autoimmune Disease Management",
        "stakeholders": "Pediatric Rheumatologists, Pediatric Gastroenterologists, Child Psychologists, Research Teams",
        "data_owner": "Chief Pediatric Rheumatologist",
        "entities": [
            "Pediatric Patient", "Growth Assessment", "Disease Activity Assessment", "Medication Therapy", 
            "Family Assessment", "Educational Assessment", "Quality of Life Assessment"
        ],
        "relationships": [
            "Pediatric Patient → Growth Assessment (1:N)",
            "Pediatric Patient → Disease Activity Assessment (1:N)",
            "Pediatric Patient → Medication Therapy (1:N)",
            "Growth Assessment → Disease Activity Assessment (M:N)"
        ]
    },
    {
        "name": "Autoimmune Disease Telemedicine",
        "stakeholders": "Telemedicine Physicians, IT Support, Patient Coordinators, Quality Assurance Teams",
        "data_owner": "Director of Telemedicine",
        "entities": [
            "Patient", "Telemedicine Visit", "Remote Monitoring", "Medication Management", 
            "Patient Education", "Follow-up Assessment", "Quality Metrics"
        ],
        "relationships": [
            "Patient → Telemedicine Visit (1:N)",
            "Patient → Remote Monitoring (1:N)",
            "Patient → Medication Management (1:N)",
            "Telemedicine Visit → Remote Monitoring (M:N)"
        ]
    },
    {
        "name": "Autoimmune Disease Clinical Trials",
        "stakeholders": "Clinical Research Coordinators, Principal Investigators, Regulatory Affairs, Data Managers",
        "data_owner": "Director of Clinical Trials",
        "entities": [
            "Trial Participant", "Clinical Trial", "Study Visit", "Adverse Event", 
            "Study Medication", "Outcome Measure", "Data Collection"
        ],
        "relationships": [
            "Trial Participant → Clinical Trial (M:N)",
            "Trial Participant → Study Visit (1:N)",
            "Clinical Trial → Study Medication (1:N)",
            "Study Visit → Adverse Event (1:N)"
        ]
    }
]

def generate_dda_content(domain):
    """Generate DDA content for a specific domain."""
    
    template = f"""# Data Delivery Agreement (DDA) - {domain['name']}

## Document Information
- **Domain**: {domain['name']}
- **Stakeholders**: {domain['stakeholders']}
- **Data Owner**: {domain['data_owner']}
- **Effective Date**: 2024-01-15
- **Review Cycle**: Monthly

## Business Context
The {domain['name']} domain supports comprehensive patient care, treatment monitoring, and research for {domain['name'].lower()} conditions. This DDA defines data requirements for patient management, treatment efficacy tracking, and clinical research.

## Data Entities

### Patient
- **Description**: Core patient information and demographics
- **Key Attributes**:
  - Patient ID (Primary Key)
  - First Name, Last Name
  - Date of Birth
  - Gender
  - Diagnosis Date
  - Disease Type
  - Severity Classification
  - Family History
- **Business Rules**:
  - Patient ID must be unique
  - Diagnosis date cannot be future
  - Disease type must be valid

### Assessment
- **Description**: Clinical assessments and measurements
- **Key Attributes**:
  - Assessment ID (Primary Key)
  - Patient ID (Foreign Key)
  - Assessment Date
  - Assessment Type
  - Clinical Score
  - Severity Level
  - Physician Notes
- **Business Rules**:
  - Must reference valid Patient ID
  - Assessment date cannot be future
  - Clinical score must be within valid range

### Laboratory Test
- **Description**: Blood work and diagnostic test results
- **Key Attributes**:
  - Test ID (Primary Key)
  - Patient ID (Foreign Key)
  - Test Type
  - Test Date
  - Result Value
  - Reference Range
  - Abnormal Flag
- **Business Rules**:
  - Must reference valid Patient ID
  - Test date cannot be future
  - Result value must be numeric

### Medication Therapy
- **Description**: Medications and treatment protocols
- **Key Attributes**:
  - Therapy ID (Primary Key)
  - Patient ID (Foreign Key)
  - Medication Name
  - Drug Class
  - Start Date
  - End Date
  - Dosage
  - Response Assessment
- **Business Rules**:
  - Must reference valid Patient ID
  - End date must be after start date
  - Dosage must be positive

### Quality of Life Assessment
- **Description**: Patient-reported quality of life measures
- **Key Attributes**:
  - Assessment ID (Primary Key)
  - Patient ID (Foreign Key)
  - Assessment Date
  - Quality of Life Score
  - Functional Assessment
  - Emotional Well-being
  - Social Functioning
- **Business Rules**:
  - Must reference valid Patient ID
  - Assessment date cannot be future
  - Scores must be within valid ranges

## Relationships

### Patient Relationships
- **Patient** → **Assessment** (1:N)
  - A patient can have multiple assessments
  - Each assessment belongs to exactly one patient

- **Patient** → **Laboratory Test** (1:N)
  - A patient can have multiple laboratory tests
  - Each test belongs to exactly one patient

- **Patient** → **Medication Therapy** (1:N)
  - A patient can have multiple medication therapies
  - Each therapy belongs to exactly one patient

- **Patient** → **Quality of Life Assessment** (1:N)
  - A patient can have multiple quality of life assessments
  - Each assessment belongs to exactly one patient

### Treatment Relationships
- **Medication Therapy** → **Assessment** (M:N)
  - Medication therapies can be evaluated against assessments
  - Assessments can be influenced by multiple therapies

### Cross-Domain Relationships
- **Laboratory Test** → **Assessment** (M:N)
  - Laboratory tests can inform assessments
  - Assessments can be validated by laboratory tests

## Data Quality Requirements

### Completeness
- Patient ID must be present in all related records
- Assessment dates must be provided
- Required clinical scores must be recorded

### Accuracy
- Laboratory values must be within physiological ranges
- Clinical scores must be calculated correctly
- Dates must be in ISO format (YYYY-MM-DD)

### Timeliness
- Assessments must be updated monthly
- Laboratory results must be available within 24 hours
- Medication response must be assessed within 2 weeks

## Access Patterns

### Common Queries
1. Patient disease progression over time
2. Treatment efficacy by patient characteristics
3. Laboratory trends for specific patients
4. Quality of life correlation with disease activity

### Performance Requirements
- Patient history retrieval: < 2 seconds
- Disease activity trend analysis: < 5 seconds
- Treatment response assessment: < 3 seconds

## Data Governance

### Privacy
- HIPAA compliance for all patient data
- PHI encryption at rest and in transit
- Patient consent required for research use

### Security
- Role-based access control (RBAC)
- Audit logging for all clinical data access
- Two-factor authentication for medical staff

### Compliance
- HIPAA compliance
- FDA reporting for adverse events
- Clinical trial data standards

## Success Metrics
- 98% data completeness across all entities
- < 0.5% data quality issues in production
- 99.9% system availability
- < 3 second average query response time
"""
    
    return template

def main():
    """Generate all DDA documents."""
    
    # Create examples directory if it doesn't exist
    os.makedirs("examples", exist_ok=True)
    
    print("🚀 Generating DDA documents for autoimmune and inflammatory bowel disease domains...")
    
    for i, domain in enumerate(DDA_DOMAINS, 1):
        # Create filename
        filename = domain['name'].lower().replace(' ', '_').replace('-', '_') + '_dda.md'
        filepath = os.path.join("examples", filename)
        
        # Generate content
        content = generate_dda_content(domain)
        
        # Write to file
        with open(filepath, 'w') as f:
            f.write(content)
        
        print(f"✅ Created {i:2d}/15: {domain['name']} -> {filepath}")
    
    print(f"\n🎉 Successfully generated {len(DDA_DOMAINS)} DDA documents!")
    print("📁 All documents saved in the 'examples' directory")
    print("\n📋 Generated DDA domains:")
    for i, domain in enumerate(DDA_DOMAINS, 1):
        print(f"   {i:2d}. {domain['name']}")

if __name__ == "__main__":
    main() 