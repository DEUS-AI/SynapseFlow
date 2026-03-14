## ADDED Requirements

### Requirement: Cost Management budget with alerts
The system SHALL create an Azure Cost Management budget scoped to the resource group with a monthly limit matching `var.budget_amount` (default: $100 for dev). The budget SHALL have notification thresholds at 50%, 80%, and 100% of the limit.

#### Scenario: Budget creation
- **WHEN** Terraform applies the finops module
- **THEN** a budget named `budget-odin-{env}` is created on `RG-ODINDATA-DEV`
- **AND** the budget amount is $100 for `var.environment = "dev"`

#### Scenario: Alert at 80% spend
- **WHEN** actual spend reaches 80% of the budget ($80)
- **THEN** an email notification SHALL be sent to the configured contact

#### Scenario: Alert at 100% spend
- **WHEN** actual spend reaches 100% of the budget ($100)
- **THEN** an email notification SHALL be sent with urgency indicating overspend

### Requirement: Resource tagging strategy
All Terraform-managed resources SHALL have the following tags: `environment` (`dev`/`staging`/`prod`), `service` (the component name), `cost-center` (`synapseflow`), and `managed-by` (`terraform`).

#### Scenario: Tag consistency
- **WHEN** any resource is created by Terraform
- **THEN** it SHALL have all four required tags
- **AND** the `environment` tag SHALL match `var.environment`

### Requirement: FinOps module outputs
The module SHALL output `budget_id` and a summary of estimated monthly costs per service based on the selected SKUs.

#### Scenario: Cost visibility
- **WHEN** `terraform plan` runs
- **THEN** the finops module output SHALL display the estimated monthly cost breakdown
