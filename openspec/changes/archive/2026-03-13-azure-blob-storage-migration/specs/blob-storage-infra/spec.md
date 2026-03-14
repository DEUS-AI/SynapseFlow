## ADDED Requirements

### Requirement: Storage account Terraform module
The system SHALL provide a Terraform module at `infra/terraform/modules/storage/` that creates an Azure Storage Account with blob containers for document storage.

The module SHALL:
- Create a storage account with naming `st{project}{env}{region}` (no hyphens, lowercase)
- Use `Standard_LRS` SKU and `Hot` access tier
- Create two blob containers: `documents` and `markdown`
- Store the connection string as a secret in Key Vault
- Create a private endpoint on the existing PE subnet
- Accept variables: `resource_group_name`, `location`, `environment`, `subnet_pe_id`, `private_dns_zone_id`, `keyvault_id`, `tags`
- Output: `storage_account_name`, `storage_account_id`

#### Scenario: Module creates storage account
- **WHEN** the storage module is applied in the dev environment
- **THEN** a storage account is created in the resource group with blob containers `documents` and `markdown`

#### Scenario: Connection string stored in Key Vault
- **WHEN** the storage account is provisioned
- **THEN** the primary connection string is stored as a Key Vault secret named `AZURE-STORAGE-CONNECTION-STRING`

#### Scenario: Private endpoint created
- **WHEN** the storage module is applied
- **THEN** a private endpoint for the blob sub-resource is created on the PE subnet

### Requirement: Dev environment wiring
The dev environment main.tf SHALL instantiate the storage module and pass required variables from existing modules (networking, keyvault).

#### Scenario: Storage module in dev environment
- **WHEN** `terraform apply` is run on the dev environment
- **THEN** the storage module is instantiated with the PE subnet, private DNS zone, and Key Vault from existing modules

### Requirement: AKS secret access
The AKS SecretProviderClass SHALL be updated to mount `AZURE-STORAGE-CONNECTION-STRING` from Key Vault into the backend pod.

#### Scenario: Backend pod has storage connection string
- **WHEN** the backend pod starts
- **THEN** the storage connection string is available via the mounted secrets or environment variable
