## ADDED Requirements

### Requirement: Agent deployments
The system SHALL deploy four agent containers (data_architect, data_engineer, knowledge_manager, medical_assistant) as separate Deployments in the `synapseflow-agents` namespace. Each agent SHALL use the `synapseflow/agent` image from ACR with the `--role` and `--port` arguments matching the existing docker-compose configuration.

#### Scenario: All agents running
- **WHEN** the Kustomize base + dev overlay is applied
- **THEN** four agent pods SHALL be running in `synapseflow-agents`
- **AND** each SHALL have a ClusterIP Service for A2A communication
- **AND** data_architect SHALL listen on port 8001, data_engineer on 8002, knowledge_manager on 8003, medical_assistant on 8004

#### Scenario: Agent environment variables
- **WHEN** an agent pod starts
- **THEN** environment variables SHALL be injected from Key Vault via SecretProviderClass
- **AND** `NEO4J_URI` SHALL point to `bolt://neo4j.synapseflow-infra.svc.cluster.local:7687`
- **AND** `RABBITMQ_URL` SHALL point to `amqp://guest:{password}@rabbitmq.synapseflow-infra.svc.cluster.local:5672/`
- **AND** `DEPLOYMENT_MODE` SHALL be `distributed`
- **AND** `AGENT_CONFIG_PATH` SHALL be `/app/config/agents.distributed.yaml`

#### Scenario: Agent resource limits (dev)
- **WHEN** the dev overlay is applied
- **THEN** each agent SHALL request `100m CPU / 256Mi RAM` with limits `500m CPU / 512Mi RAM`

### Requirement: Backend API deployment
The system SHALL deploy the backend API as a Deployment in the `synapseflow-backend` namespace using the `synapseflow/backend` image from ACR. The backend SHALL be exposed via an NGINX Ingress resource.

#### Scenario: Backend pod running
- **WHEN** the Kustomize base + dev overlay is applied
- **THEN** one backend pod SHALL be running with uvicorn on port 8000
- **AND** it SHALL be accessible via ClusterIP Service

#### Scenario: Ingress exposure
- **WHEN** the Ingress resource is applied
- **THEN** the backend SHALL be accessible at the Azure-provided ingress URL on HTTPS
- **AND** the path `/` SHALL route to the backend service on port 8000

### Requirement: ConfigMap for distributed agent config
The system SHALL create a ConfigMap containing the `agents.distributed.yaml` configuration file, mounted into each agent pod at `/app/config/`.

#### Scenario: Config mount
- **WHEN** an agent pod starts
- **THEN** `/app/config/agents.distributed.yaml` SHALL contain the distributed deployment configuration
- **AND** agent URLs SHALL reference Kubernetes internal DNS names (e.g., `http://data-architect.synapseflow-agents.svc.cluster.local:8001`)

### Requirement: Network policies
The system SHALL deploy NetworkPolicy resources restricting pod-to-pod traffic.

#### Scenario: Agent isolation
- **WHEN** an external pod outside `synapseflow-backend` attempts to reach an agent
- **THEN** the connection SHALL be denied by NetworkPolicy

#### Scenario: Backend to agent access
- **WHEN** the backend pod sends a request to an agent ClusterIP
- **THEN** the connection SHALL be allowed
