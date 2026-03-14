## ADDED Requirements

### Requirement: AKS cluster with free tier control plane
The system SHALL provision an AKS cluster using the free tier SKU for the control plane. The cluster SHALL be named `aks-odin-{env}-westeurope` and deployed into the AKS subnet.

#### Scenario: Cluster creation
- **WHEN** Terraform applies the AKS module
- **THEN** an AKS cluster is created with SKU tier `Free`
- **AND** Kubernetes version SHALL be the latest stable version supported by Azure
- **AND** the cluster SHALL use the `subnet-aks` from the networking module

### Requirement: Single node pool for dev
The system SHALL create a default node pool with VM size `Standard_B4ms` (4 vCPU, 16 GB RAM). The dev environment SHALL configure `min_count=1`, `max_count=1` (no autoscaling). The node pool SHALL use Azure Managed Disks.

#### Scenario: Dev node pool sizing
- **WHEN** `var.environment` is `dev`
- **THEN** the node pool SHALL have exactly 1 node of size `Standard_B4ms`
- **AND** enable_auto_scaling SHALL be `false`

#### Scenario: Future env scalability
- **WHEN** `var.environment` is `prod`
- **THEN** the module SHALL accept `vm_size`, `min_count`, and `max_count` as variables

### Requirement: Managed identity and ACR integration
The cluster SHALL use a system-assigned managed identity. The identity SHALL be granted `AcrPull` role on the Azure Container Registry to pull images without credentials.

#### Scenario: Image pull from ACR
- **WHEN** a pod spec references an image from the project ACR
- **THEN** AKS SHALL pull the image using its managed identity without imagePullSecrets

### Requirement: NGINX ingress controller
The system SHALL deploy the NGINX ingress controller add-on or Helm chart on the AKS cluster to expose the backend API.

#### Scenario: Ingress routing
- **WHEN** an Ingress resource is created in the `synapseflow-backend` namespace
- **THEN** NGINX SHALL route external HTTP(S) traffic to the backend service

### Requirement: Key Vault CSI driver
The AKS cluster SHALL enable the Azure Key Vault Provider for Secrets Store CSI Driver add-on.

#### Scenario: Secret mount
- **WHEN** a pod references a `SecretProviderClass` pointing to Key Vault
- **THEN** secrets SHALL be mounted as files or synced as Kubernetes secrets
