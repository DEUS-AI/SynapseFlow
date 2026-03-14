## ADDED Requirements

### Requirement: Azure Storage backend for Terraform state
The system SHALL use an Azure Storage Account with a blob container for Terraform remote state. State locking SHALL be enabled via blob lease. The storage account SHALL use encryption at rest.

#### Scenario: State backend configuration
- **WHEN** `terraform init` runs in an environment directory
- **THEN** it SHALL connect to storage account `stodindevstate`
- **AND** container `tfstate`
- **AND** key `{env}.terraform.tfstate`

### Requirement: Bootstrap script
The system SHALL include a `scripts/bootstrap-tf-state.sh` script that creates the storage account and blob container via `az` CLI. This script is idempotent and safe to re-run.

#### Scenario: First-time setup
- **WHEN** an operator runs `./scripts/bootstrap-tf-state.sh`
- **THEN** storage account `stodindevstate` is created in `RG-ODINDATA-DEV`
- **AND** container `tfstate` is created
- **AND** the script outputs the backend configuration block to paste into `backend.tf`

#### Scenario: Re-run safety
- **WHEN** the bootstrap script runs against an existing storage account
- **THEN** it SHALL not fail or overwrite existing state
- **AND** it SHALL output a message indicating the resources already exist

### Requirement: State file isolation per environment
Each environment SHALL use a separate state file key within the same container, namespaced by environment name.

#### Scenario: Dev state isolation
- **WHEN** `terraform apply` runs in `environments/dev/`
- **THEN** state is stored at blob key `dev.terraform.tfstate`
- **AND** it SHALL NOT interfere with `staging.terraform.tfstate` or `prod.terraform.tfstate`
