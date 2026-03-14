## ADDED Requirements

### Requirement: Azure Database for PostgreSQL Flexible Server
The system SHALL provision a PostgreSQL Flexible Server with Burstable B1ms SKU (1 vCPU, 2 GB RAM) for the dev environment. The server SHALL use PostgreSQL version 16 and connect via private endpoint only (public access disabled).

#### Scenario: PostgreSQL provisioning
- **WHEN** Terraform applies the postgres module with `var.environment = "dev"`
- **THEN** a PostgreSQL Flexible Server named `pg-odin-dev-westeurope` is created
- **AND** SKU is `B_Standard_B1ms`
- **AND** storage is 32 GB with auto-grow disabled (dev cost control)
- **AND** public network access is disabled

#### Scenario: Database initialization
- **WHEN** the PostgreSQL server is created
- **THEN** a database named `synapseflow` SHALL be created
- **AND** an admin user SHALL be configured with credentials stored in Key Vault

### Requirement: Azure Cache for Redis
The system SHALL provision an Azure Cache for Redis with Basic C0 SKU (250 MB) for the dev environment. The cache SHALL connect via private endpoint only.

#### Scenario: Redis provisioning
- **WHEN** Terraform applies the redis module with `var.environment = "dev"`
- **THEN** a Redis cache named `redis-odin-dev-westeurope` is created
- **AND** SKU is `Basic` with family `C` and capacity `0`
- **AND** minimum TLS version is 1.2
- **AND** public network access is disabled

#### Scenario: Connection string in Key Vault
- **WHEN** Redis is provisioned
- **THEN** the primary connection string SHALL be stored in Key Vault as secret `redis-connection-string`

### Requirement: Variable-driven SKU selection
Both modules SHALL accept a `sku_tier` variable that maps to environment-appropriate SKUs. This allows future environments to specify larger SKUs without modifying module code.

#### Scenario: SKU override for prod
- **WHEN** `var.sku_tier = "standard"`
- **THEN** PostgreSQL SHALL use `GP_Standard_D2s_v3` and Redis SHALL use `Standard C1`
