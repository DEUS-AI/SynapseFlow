## ADDED Requirements

### Requirement: VNet with isolated subnets
The system SHALL provision an Azure Virtual Network with at least two subnets: one for AKS workloads (`subnet-aks`) and one for data service private endpoints (`subnet-data`). The VNet address space SHALL be `10.0.0.0/16`.

#### Scenario: VNet creation
- **WHEN** Terraform applies the networking module
- **THEN** a VNet named `vnet-odin-{env}-westeurope` is created with address space `10.0.0.0/16`
- **AND** `subnet-aks` is created with CIDR `10.0.0.0/20`
- **AND** `subnet-data` is created with CIDR `10.0.16.0/24`

### Requirement: Network Security Groups
The system SHALL attach NSGs to each subnet restricting inbound traffic. The `subnet-data` NSG SHALL deny all inbound traffic except from `subnet-aks` CIDR.

#### Scenario: Data subnet isolation
- **WHEN** a request originates from outside `subnet-aks`
- **THEN** the NSG on `subnet-data` SHALL deny the connection

#### Scenario: AKS to data subnet allowed
- **WHEN** a pod in `subnet-aks` connects to a private endpoint in `subnet-data`
- **THEN** the connection SHALL be allowed

### Requirement: Private endpoints for managed services
The system SHALL create private endpoints for Azure Database for PostgreSQL and Azure Cache for Redis within `subnet-data`. Each private endpoint SHALL have a corresponding Private DNS Zone linked to the VNet.

#### Scenario: PostgreSQL private endpoint resolution
- **WHEN** an AKS pod resolves the PostgreSQL FQDN
- **THEN** DNS SHALL resolve to the private endpoint IP within `subnet-data`
- **AND** traffic SHALL NOT traverse the public internet

#### Scenario: Redis private endpoint resolution
- **WHEN** an AKS pod resolves the Redis FQDN
- **THEN** DNS SHALL resolve to the private endpoint IP within `subnet-data`

### Requirement: Module outputs
The networking module SHALL output `vnet_id`, `subnet_aks_id`, `subnet_data_id`, and private DNS zone IDs for consumption by dependent modules.

#### Scenario: Downstream module wiring
- **WHEN** the AKS module references `module.networking.subnet_aks_id`
- **THEN** the output SHALL contain the correct Azure resource ID
