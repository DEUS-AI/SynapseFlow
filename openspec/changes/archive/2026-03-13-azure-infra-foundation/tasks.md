## 1. Project Scaffolding

- [x] 1.1 Create directory structure: `infra/terraform/modules/`, `infra/terraform/environments/dev/`, `infra/k8s/base/`, `infra/k8s/overlays/dev/`, `scripts/`
- [x] 1.2 Create `infra/terraform/versions.tf` with required providers (`azurerm >= 4.0`, `azuread`, `random`) and Terraform version constraint (`>= 1.9`)
- [x] 1.3 Create `infra/terraform/environments/dev/backend.tf` with Azure Storage backend configuration (storage account `stodindevstate`, container `tfstate`, key `dev.terraform.tfstate`)
- [x] 1.4 Create `scripts/bootstrap-tf-state.sh` — idempotent script that creates the storage account and blob container via `az` CLI

## 2. Networking Module

- [x] 2.1 Create `infra/terraform/modules/networking/` with `main.tf`, `variables.tf`, `outputs.tf`
- [x] 2.2 Implement VNet (`vnet-odin-{env}-westeurope`, `10.0.0.0/16`) with `subnet-aks` (`10.0.0.0/20`) and `subnet-data` (`10.0.16.0/24`)
- [x] 2.3 Implement NSGs: deny all inbound on `subnet-data` except from `subnet-aks` CIDR
- [x] 2.4 Create Private DNS Zones for PostgreSQL (`privatelink.postgres.database.azure.com`) and Redis (`privatelink.redis.cache.windows.net`) linked to VNet
- [x] 2.5 Output `vnet_id`, `subnet_aks_id`, `subnet_data_id`, and private DNS zone IDs

## 3. AKS Cluster Module

- [x] 3.1 Create `infra/terraform/modules/aks/` with `main.tf`, `variables.tf`, `outputs.tf`
- [x] 3.2 Implement AKS cluster (`aks-odin-{env}-westeurope`) with free tier SKU, system-assigned managed identity, and latest stable Kubernetes version
- [x] 3.3 Configure default node pool: `Standard_B4ms`, `min_count=1`, `max_count=1` for dev (variables for future scaling)
- [x] 3.4 Enable Key Vault CSI driver add-on (`key_vault_secrets_provider`)
- [x] 3.5 Grant `AcrPull` role to AKS kubelet managed identity on ACR
- [x] 3.6 Output `cluster_id`, `kubelet_identity_object_id`, `kube_config`, `host`

## 4. Container Registry Module

- [x] 4.1 Create `infra/terraform/modules/acr/` with `main.tf`, `variables.tf`, `outputs.tf`
- [x] 4.2 Implement ACR (`acrodindev`) with Basic SKU, admin disabled
- [x] 4.3 Output `acr_login_server`, `acr_id`, `acr_name`

## 5. Managed Data Module (PostgreSQL + Redis)

- [x] 5.1 Create `infra/terraform/modules/postgres/` with `main.tf`, `variables.tf`, `outputs.tf`
- [x] 5.2 Implement PostgreSQL Flexible Server (`pg-odin-{env}-westeurope`): Burstable B1ms, PostgreSQL 16, 32 GB storage, public access disabled
- [x] 5.3 Create database `synapseflow` and admin user with `random_password` stored in Key Vault
- [x] 5.4 Create private endpoint in `subnet-data` with DNS zone association
- [x] 5.5 Create `infra/terraform/modules/redis/` with `main.tf`, `variables.tf`, `outputs.tf`
- [x] 5.6 Implement Redis (`redis-odin-{env}-westeurope`): Basic C0, TLS 1.2, public access disabled
- [x] 5.7 Create private endpoint in `subnet-data` with DNS zone association
- [x] 5.8 Store Redis connection string in Key Vault

## 6. Key Vault Module

- [x] 6.1 Create `infra/terraform/modules/keyvault/` with `main.tf`, `variables.tf`, `outputs.tf`
- [x] 6.2 Implement Key Vault (`kv-odin-{env}-westeurope`): RBAC authorization, soft delete 7 days, no purge protection (dev)
- [x] 6.3 Grant `Key Vault Secrets User` role to AKS kubelet managed identity
- [x] 6.4 Seed secrets: `pg-admin-password`, `pg-connection-string`, `redis-connection-string`, `rabbitmq-default-password` (auto-generated)
- [x] 6.5 Output `keyvault_id`, `keyvault_uri`, `keyvault_name`

## 7. Static Web App Module

- [x] 7.1 Create `infra/terraform/modules/static-web-app/` with `main.tf`, `variables.tf`, `outputs.tf`
- [x] 7.2 Implement Static Web App (`swa-odin-{env}-westeurope`): Free tier, store deployment token in Key Vault
- [x] 7.3 Output `swa_default_hostname`, `swa_id`

## 8. FinOps Module

- [x] 8.1 Create `infra/terraform/modules/finops/` with `main.tf`, `variables.tf`, `outputs.tf`
- [x] 8.2 Implement Cost Management budget (`budget-odin-{env}`): $100 monthly, scoped to RG
- [x] 8.3 Configure notification thresholds at 50%, 80%, 100% with email alerts
- [x] 8.4 Implement default tags map (`environment`, `service`, `cost-center`, `managed-by`) passed to all modules

## 9. Monitoring Module

- [x] 9.1 Create `infra/terraform/modules/monitoring/` with `main.tf`, `variables.tf`, `outputs.tf`
- [x] 9.2 Implement Log Analytics Workspace and link to AKS cluster for container insights

## 10. Environment Composition (dev)

- [x] 10.1 Create `infra/terraform/environments/dev/main.tf` composing all modules with dev-specific variables
- [x] 10.2 Create `infra/terraform/environments/dev/variables.tf` and `terraform.tfvars` with dev values (B4ms, B1ms, Basic C0, $100 budget)
- [x] 10.3 Verify `terraform init` succeeds with Azure Storage backend
- [x] 10.4 Verify `terraform plan` completes without errors
- [x] 10.5 Verify `terraform apply` provisions all resources within $100/month estimate

## 11. Kubernetes Manifests — Infrastructure Workloads

- [x] 11.1 Create `infra/k8s/base/namespaces.yaml` defining `synapseflow-infra`, `synapseflow-agents`, `synapseflow-backend` with resource quotas
- [x] 11.2 Create Neo4j Helm values at `infra/k8s/base/neo4j/values.yaml`: single core, APOC plugin, PVC with Azure Managed Disk, resource requests `250m/1Gi`
- [x] 11.3 Create RabbitMQ Helm values at `infra/k8s/base/rabbitmq/values.yaml`: single replica, password from Key Vault, resource requests `100m/256Mi`
- [x] 11.4 Create FalkorDB base deployment + service + PVC at `infra/k8s/base/falkordb/`
- [x] 11.5 Create Qdrant base deployment + service + PVC at `infra/k8s/base/qdrant/`
- [x] 11.6 Create `infra/k8s/base/kustomization.yaml` referencing all base resources
- [x] 11.7 Create dev overlay at `infra/k8s/overlays/dev/` with resource limit patches for all infra pods

## 12. Kubernetes Manifests — Application Deployments

- [x] 12.1 Create agent deployments (data_architect, data_engineer, knowledge_manager, medical_assistant) at `infra/k8s/base/agents/` with ClusterIP services
- [x] 12.2 Create ConfigMap with `agents.distributed.yaml` adapted for Kubernetes DNS names
- [x] 12.3 Create SecretProviderClass resources for `synapseflow-agents` and `synapseflow-backend` namespaces mapping Key Vault secrets
- [x] 12.4 Create backend API deployment + ClusterIP service at `infra/k8s/base/backend/`
- [x] 12.5 Create NGINX Ingress resource for backend at `infra/k8s/base/backend/ingress.yaml`
- [x] 12.6 Create NetworkPolicy resources: agents reachable only from backend, infra reachable from agents and backend
- [x] 12.7 Create dev overlay at `infra/k8s/overlays/dev/` with resource limit patches for agent and backend pods

## 13. GitHub Actions — OIDC and CI

- [x] 13.1 Document OIDC setup instructions in `infra/README.md`: App Registration, federated credentials, role assignment
- [x] 13.2 Update `.github/workflows/ci.yml` to add Terraform plan step for PRs touching `infra/terraform/**`
- [x] 13.3 Create `.github/workflows/infra-apply.yml`: authenticate via OIDC, `terraform apply -auto-approve` on merge to main (path filter: `infra/terraform/**`)

## 14. GitHub Actions — Build and Deploy

- [x] 14.1 Create `.github/workflows/build-push.yml`: build `synapseflow/agent` and `synapseflow/backend` images, push to ACR with git SHA tag (path filter: `src/**`, `Dockerfile*`)
- [x] 14.2 Create `.github/workflows/deploy.yml`: triggered after build-push, `kubectl set image` or `kustomize edit set image` for affected deployments, `kubectl rollout status` with rollback on failure
- [x] 14.3 Create `.github/workflows/swa-deploy.yml`: `npm ci && npm run build` in `frontend/`, deploy `frontend/dist/` to Static Web App (path filter: `frontend/**`)

## 15. Frontend Configuration

- [x] 15.1 Create `frontend/staticwebapp.config.json` with proxy rule routing `/api/*` to AKS backend ingress URL
