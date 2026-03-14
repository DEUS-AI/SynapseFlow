## ADDED Requirements

### Requirement: Key Vault provisioning
The system SHALL provision an Azure Key Vault named `kv-odin-{env}-westeurope` with RBAC authorization (not access policies). Soft delete SHALL be enabled with a 7-day retention (minimum allowed).

#### Scenario: Key Vault creation
- **WHEN** Terraform applies the keyvault module
- **THEN** a Key Vault is created with `enable_rbac_authorization = true`
- **AND** soft delete is enabled with 7-day retention
- **AND** purge protection is disabled (dev only, to allow recreation)

### Requirement: Managed identity access
The AKS kubelet managed identity SHALL be granted `Key Vault Secrets User` role on the Key Vault. This enables the CSI driver to read secrets without additional credentials.

#### Scenario: Pod secret access
- **WHEN** a pod with a `SecretProviderClass` starts
- **THEN** the CSI driver SHALL authenticate via the kubelet managed identity
- **AND** retrieve the requested secrets from Key Vault

### Requirement: Secret seeding
Terraform SHALL create the following secrets in Key Vault during initial provisioning:
- `pg-admin-password`: Generated random password for PostgreSQL admin
- `pg-connection-string`: Full PostgreSQL connection string
- `redis-connection-string`: Redis primary connection string
- `rabbitmq-default-password`: Generated password for RabbitMQ

The `OPENAI_API_KEY` SHALL NOT be managed by Terraform — it MUST be added manually by the operator after initial provisioning.

#### Scenario: Auto-generated secrets
- **WHEN** Terraform creates PostgreSQL and Redis
- **THEN** connection strings SHALL be automatically stored in Key Vault

#### Scenario: Manual secret addition
- **WHEN** an operator needs to add the OpenAI API key
- **THEN** they SHALL run `az keyvault secret set --vault-name kv-odin-dev-westeurope --name openai-api-key --value <key>`

### Requirement: SecretProviderClass manifests
Each namespace SHALL have a `SecretProviderClass` Kubernetes resource that maps Key Vault secrets to pod-accessible secrets.

#### Scenario: Agent pod secret injection
- **WHEN** an agent pod in `synapseflow-agents` starts
- **THEN** the `SecretProviderClass` SHALL mount `pg-connection-string`, `rabbitmq-default-password`, and `openai-api-key` as environment variables
