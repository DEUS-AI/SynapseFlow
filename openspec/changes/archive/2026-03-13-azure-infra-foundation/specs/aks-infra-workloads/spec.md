## ADDED Requirements

### Requirement: Neo4j deployment via Helm
The system SHALL deploy Neo4j to the `synapseflow-infra` namespace using the official Neo4j Helm chart. The deployment SHALL include the APOC plugin, pin the chart version, and use a PersistentVolumeClaim with Azure Managed Disk for data persistence.

#### Scenario: Neo4j pod running
- **WHEN** Helm installs the Neo4j chart with dev values
- **THEN** a single Neo4j pod SHALL be running in `synapseflow-infra`
- **AND** APOC plugin SHALL be loaded and available
- **AND** Neo4j SHALL be accessible at `neo4j.synapseflow-infra.svc.cluster.local:7687`

#### Scenario: Neo4j resource limits (dev)
- **WHEN** the dev overlay is applied
- **THEN** Neo4j requests SHALL be `250m CPU / 1Gi RAM`
- **AND** limits SHALL be `1000m CPU / 3Gi RAM`

#### Scenario: Data persistence
- **WHEN** the Neo4j pod is restarted or the node is replaced
- **THEN** all graph data SHALL be preserved via the PersistentVolumeClaim

### Requirement: RabbitMQ deployment via Helm
The system SHALL deploy RabbitMQ to the `synapseflow-infra` namespace using the Bitnami RabbitMQ Helm chart. The management UI SHALL be accessible within the cluster.

#### Scenario: RabbitMQ pod running
- **WHEN** Helm installs the RabbitMQ chart with dev values
- **THEN** a single RabbitMQ pod SHALL be running in `synapseflow-infra`
- **AND** AMQP SHALL be accessible at `rabbitmq.synapseflow-infra.svc.cluster.local:5672`
- **AND** management UI SHALL be accessible at port `15672`

#### Scenario: RabbitMQ credentials
- **WHEN** RabbitMQ is deployed
- **THEN** the default user password SHALL be sourced from Key Vault secret `rabbitmq-default-password`

### Requirement: FalkorDB deployment
The system SHALL deploy FalkorDB as a single-pod Deployment in `synapseflow-infra` using the `falkordb/falkordb:latest` image with a PersistentVolumeClaim.

#### Scenario: FalkorDB pod running
- **WHEN** the Kustomize base is applied
- **THEN** FalkorDB SHALL be accessible at `falkordb.synapseflow-infra.svc.cluster.local:6379`

#### Scenario: FalkorDB resource limits (dev)
- **WHEN** the dev overlay is applied
- **THEN** FalkorDB requests SHALL be `100m CPU / 256Mi RAM`

### Requirement: Qdrant deployment
The system SHALL deploy Qdrant as a single-pod Deployment in `synapseflow-infra` using the `qdrant/qdrant:latest` image with a PersistentVolumeClaim.

#### Scenario: Qdrant pod running
- **WHEN** the Kustomize base is applied
- **THEN** Qdrant SHALL be accessible at `qdrant.synapseflow-infra.svc.cluster.local:6333` (HTTP) and `:6334` (gRPC)

#### Scenario: Qdrant resource limits (dev)
- **WHEN** the dev overlay is applied
- **THEN** Qdrant requests SHALL be `100m CPU / 256Mi RAM`

### Requirement: Namespace and resource quotas
The `synapseflow-infra` namespace SHALL have a ResourceQuota limiting total resource consumption for dev.

#### Scenario: Quota enforcement
- **WHEN** total resource requests in `synapseflow-infra` exceed `2000m CPU / 6Gi RAM`
- **THEN** new pod scheduling SHALL be rejected
