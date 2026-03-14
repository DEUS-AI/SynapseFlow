## ADDED Requirements

### Requirement: ACR with Basic tier
The system SHALL provision an Azure Container Registry with Basic SKU. The registry name SHALL be globally unique and alphanumeric (e.g., `acrodindev`). Admin user SHALL be disabled — image pulls use AKS managed identity.

#### Scenario: ACR provisioning
- **WHEN** Terraform applies the ACR module
- **THEN** a container registry is created with Basic SKU
- **AND** admin user is disabled
- **AND** the AKS managed identity has `AcrPull` role assignment on the registry

### Requirement: Image naming convention
Container images pushed to ACR SHALL follow the naming convention `{acr_login_server}/synapseflow/{component}:{tag}` where component is one of: `agent`, `backend`.

#### Scenario: Agent image reference
- **WHEN** an agent deployment references an image
- **THEN** the image SHALL be `acrodindev.azurecr.io/synapseflow/agent:{git-sha}`

#### Scenario: Backend image reference
- **WHEN** the backend deployment references an image
- **THEN** the image SHALL be `acrodindev.azurecr.io/synapseflow/backend:{git-sha}`

### Requirement: Module outputs
The ACR module SHALL output `acr_login_server`, `acr_id`, and `acr_name` for use by AKS role assignment and CI/CD pipelines.

#### Scenario: CI/CD image push
- **WHEN** GitHub Actions builds a container image
- **THEN** the workflow SHALL use `module.acr.acr_login_server` to tag and push
