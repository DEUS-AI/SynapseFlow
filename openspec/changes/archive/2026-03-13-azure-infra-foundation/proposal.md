## Why

SynapseFlow has no Infrastructure as Code — all infrastructure runs via local docker-compose files with hardcoded credentials and no path to cloud deployment. The project needs a reproducible, secure, cost-controlled Azure deployment to move beyond local development. Starting with a `dev` environment establishes the foundation for future staging/prod environments.

## What Changes

- Add Terraform modules for Azure infrastructure: networking (VNet, subnets, NSGs, private endpoints), AKS cluster, Azure Container Registry, Azure Database for PostgreSQL Flexible Server, Azure Cache for Redis, Azure Key Vault, and Azure Static Web Apps
- Add a FinOps module with Azure Cost Management budgets and alerts ($100/month ceiling for dev)
- Add Terraform state backend configuration using Azure Storage
- Add GitHub Actions OIDC federation for passwordless Azure authentication from CI/CD
- Add Kustomize base manifests and dev overlay for deploying Neo4j (Helm), RabbitMQ (Helm), FalkorDB, and Qdrant as AKS workloads
- Add GitHub Actions workflows for infrastructure plan/apply and application build/deploy pipelines
- **BREAKING**: Production deployments will require Azure subscription access and Terraform state storage — local docker-compose remains for local development only

## Capabilities

### New Capabilities

- `azure-networking`: VNet, subnets (AKS + data), NSGs, and private endpoints for Postgres and Redis. Provides network isolation and secure connectivity between managed services and AKS workloads.
- `azure-aks-cluster`: AKS cluster provisioning with free tier control plane, single B4ms node pool for dev, managed identity, ACR integration, and cluster autoscaler configuration.
- `azure-managed-data`: Azure Database for PostgreSQL Flexible Server (Burstable B1ms) and Azure Cache for Redis (Basic C0) with private endpoint connectivity and Key Vault secret storage.
- `azure-container-registry`: ACR (Basic tier) with managed identity pull access from AKS. Image build and push lifecycle.
- `azure-keyvault-secrets`: Key Vault for all secrets (DB passwords, API keys, connection strings) with AKS CSI driver integration for pod-level secret injection via managed identity.
- `azure-static-web-app`: Azure Static Web Apps (Free tier) for hosting the Astro frontend with Azure-provided domain and HTTPS.
- `azure-finops`: Cost Management budget with threshold alerts (50%, 80%, 100%), resource tagging strategy (env, service, cost-center), and dev auto-shutdown recommendations.
- `azure-tf-state`: Terraform remote state backend using Azure Storage Account with blob container, state locking, and encryption at rest.
- `aks-infra-workloads`: Kustomize manifests for deploying Neo4j (Helm chart), RabbitMQ (Helm chart), FalkorDB, and Qdrant as AKS pods in a dedicated `synapseflow-infra` namespace with dev-appropriate resource limits.
- `aks-app-deployment`: Kustomize manifests for deploying the 4 agent containers (synapseflow-agents namespace), backend API with ingress (synapseflow-backend namespace), and Helm values/overlays per environment.
- `azure-cicd-pipelines`: GitHub Actions workflows for CI (lint/test/tf-plan on PR), infrastructure apply (tf-apply on merge), container build+push to ACR, and application deploy to AKS. Uses OIDC federation — no stored secrets.

### Modified Capabilities

_(none — this is greenfield infrastructure, no existing spec behavior changes)_

## Impact

- **New directory**: `infra/terraform/` with modules, environments, and backend config
- **New directory**: `infra/k8s/` with Kustomize base/overlays and Helm values
- **Modified**: `.github/workflows/` — new workflow files for infra and deploy pipelines; existing `ci.yml` enhanced with tf-plan step
- **Dependencies**: Terraform CLI, `az` CLI, `kubectl`, `helm`, `kustomize` added to CI runner
- **Azure resources created**: Resource Group (existing RG-ODINDATA-DEV), VNet, AKS, ACR, PostgreSQL, Redis, Key Vault, Static Web App, Storage Account (state), Cost Management budget
- **Naming convention**: `{service}-odin-dev-westeurope` (e.g., `aks-odin-dev-westeurope`, `kv-odin-dev-westeurope`)
- **Subscription**: `7e4ea88f-473d-4e71-ab25-6b8e2ac614fa`, Tenant: `f34bb8b2-7e71-417a-afa5-91015b15c7ef`, Region: `westeurope`
- **Budget**: $100/month for dev environment
- **Auth**: GitHub OIDC → Azure AD App Registration with Contributor role on RG
