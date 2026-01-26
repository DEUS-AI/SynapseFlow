# Data Domain Architecture: Test Promotion Pipeline

**Domain**: promotion_test
**Data Owner**: System Test
**Stakeholders**: QA Team, Development
**Effective Date**: 2026-01-26

## Business Context
Test domain for validating the 4-layer promotion pipeline. This DDA creates entities that will be used to test the automatic promotion from PERCEPTION to SEMANTIC layer.

## Data Entities

### PromotionTestEntity
- **Description**: A test entity for promotion pipeline validation
- **Key Attributes**:
  - test_id (Primary Key)
  - entity_name
  - test_value
  - created_at
- **Business Rules**:
  - Test entities must have a name
  - Values must be positive integers

### RelatedTestEntity
- **Description**: Another test entity for relationship testing
- **Key Attributes**:
  - related_id (Primary Key)
  - test_id (Foreign Key)
  - description
- **Business Rules**:
  - Must reference a valid PromotionTestEntity

## Relationships

- **PromotionTestEntity** → **RelatedTestEntity** (one-to-many)
  - A test entity can have many related entities
