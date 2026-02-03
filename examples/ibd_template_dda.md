# Data Delivery Agreement (DDA) - Inflammatory Bowel Disease

## Document Information
- **Domain**: Inflammatory Bowel Disease
- **Stakeholders**: Clinical Team
- **Data Owner**: Data Owner
- **Effective Date**: 2025-01-01
- **Review Cycle**: Quarterly

## Business Context
The purpose of this DDA is to model patient and encounter data for inflammatory bowel disease research and care.

## Data Entities

### Patient
- **Description**: Patient demographic information.
- **Key Attributes**:
  - Patient ID (Primary Key)
  - Name
  - Date of Birth
- **Business Rules**:
  - Patient ID must be unique.

### Encounter
- **Description**: Clinical encounter records for patients.
- **Key Attributes**:
  - Encounter ID (Primary Key)
  - Patient ID (Foreign Key)
  - Encounter Date
- **Business Rules**:
  - Patient ID must reference a valid Patient.

## Relationships

### Clinical
- **Patient** → **Encounter** (1:N)
  - Each patient can have multiple encounters.
  - Constraint: Patient ID foreign key in Encounter.
