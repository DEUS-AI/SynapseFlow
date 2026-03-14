## Context

SynapseFlow currently runs entirely on local docker-compose with two compose files (`docker-compose.services.yml` for core services + agents, `docker-compose.memory.yml` for Redis + Qdrant). Credentials are hardcoded, there is no remote state, and no CI/CD deploys infrastructure. The existing `Dockerfile.agent` (Python 3.11-slim with uv) is production-ready and forms the base for AKS agent deployments.

The target is a single `dev` environment in Azure (`westeurope`, subscription `7e4ea88f`, RG `RG-ODINDATA-DEV`) with a hard $100/month ceiling. This forces aggressive cost optimization: free tiers where available, burstable SKUs, single-node AKS, and no HA.

## Goals / Non-Goals

**Goals:**
- Fully reproducible Azure infrastructure via Terraform — `terraform apply` creates a working dev environment from scratch
- All secrets in Key Vault, injected into pods via CSI driver — zero secrets in env vars, GitHub secrets, or Terraform state
- Private networking for all data services (Postgres, Redis accessed only via private endpoints inside VNet)
- GitHub Actions pipelines that authenticate via OIDC (no stored service principal secrets)
- Reusable Terraform modules that accept a `var.environment` to support future staging/prod without rewriting
- Stay under $100/month for the dev environment

**Non-Goals:**
- Multi-region deployment or geo-redundancy
- HA or zone-redundant configurations (dev only)
- Migrating away from RabbitMQ to Azure Service Bus (keep RabbitMQ on AKS)
- Replacing FalkorDB or Qdrant with Azure-native services
- Production hardening (WAF, DDoS protection, Azure Defender)
- Custom domain or DNS configuration (use Azure-provided domains)
- Terraform module registry publication

## Decisions

### D1: Single AKS node (B4ms) over multiple smaller nodes

**Decision**: Use 1x Standard_B4ms (4 vCPU, 16 GB RAM) node instead of 2x B2ms nodes.

**Rationale**: A single 16 GB node avoids the overhead of running kubelet, kube-proxy, and system pods on two nodes (~1.5 GB system overhead per node). With 9 application pods + system pods, a single B4ms gives ~13 GB usable vs ~13 GB across two B2ms but with worse scheduling flexibility. Cost is identical (~$60/mo), but single node simplifies networking and avoids cross-node traffic.

**Alternatives considered**:
- 2x B2ms (8 GB each): Same cost, worse memory efficiency due to double system overhead
- 1x D2s_v5: Better performance but ~$70/mo, pushes budget
- Spot instances: ~$18/mo but eviction kills stateful workloads (Neo4j, RabbitMQ)

**Trade-off**: Single point of failure — acceptable for dev. Prod would use 2+ nodes with pod anti-affinity.

### D2: Private endpoints for managed services, AKS workloads on internal DNS

**Decision**: Postgres and Redis connect to AKS via private endpoints in a dedicated `subnet-data`. AKS-hosted services (Neo4j, RabbitMQ, FalkorDB, Qdrant) use ClusterIP services and internal DNS.

**Rationale**: Private endpoints ensure no public internet exposure for data services. AKS internal DNS (`<service>.<namespace>.svc.cluster.local`) provides service discovery without external load balancers. Agent-to-agent A2A calls stay cluster-internal.

**Alternatives considered**:
- Public endpoints with firewall rules: Simpler TF but violates security requirement
- VNet injection for Postgres/Redis: Not available on burstable tiers

### D3: Kustomize + Helm hybrid over pure Helm or pure Kustomize

**Decision**: Use Kustomize for application manifests (agents, backend, infra pods) with overlays per environment. Use Helm for third-party charts (Neo4j, RabbitMQ) with values files managed alongside Kustomize overlays.

**Rationale**: Kustomize handles simple deployment/service/ingress manifests cleanly without templating complexity. Neo4j and RabbitMQ have official Helm charts with dozens of configurable options — reimplementing as raw manifests would be error-prone. The hybrid approach gives us `helm template | kubectl apply` for third-party and `kustomize build | kubectl apply` for our own workloads.

**Alternatives considered**:
- Pure Helm: Over-engineered for simple deployment manifests
- Pure Kustomize: Would need to vendor/maintain Neo4j and RabbitMQ manifests manually
- Helmfile: Additional tool dependency with marginal benefit for 2 charts

### D4: GitHub OIDC federation over service principal secrets

**Decision**: Use Azure AD Workload Identity Federation with GitHub Actions OIDC tokens. No client secrets stored anywhere.

**Rationale**: OIDC federation eliminates secret rotation, reduces attack surface, and follows Azure/GitHub best practices. The federation trust is scoped to the specific GitHub repo and branch patterns (`main` for apply, `*` for plan).

**Setup required (manual one-time)**:
1. Create Azure AD App Registration
2. Add federated credential for GitHub repo (`repo:user/SynapseFlow:ref:refs/heads/main`)
3. Grant App Registration `Contributor` role on `RG-ODINDATA-DEV`
4. Store `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID` as GitHub Actions variables (not secrets — they're not sensitive)

### D5: Terraform module structure — flat modules over nested module composition

**Decision**: Each Azure resource type gets one module (e.g., `modules/aks/`, `modules/postgres/`). The environment root (`environments/dev/main.tf`) composes these modules directly.

**Rationale**: Flat modules are easier to understand, test, and reuse. Nested module hierarchies (e.g., a `platform` module that wraps `aks` + `networking`) add indirection without value at this scale. Each module exposes outputs that other modules consume via the environment root.

```
environments/dev/main.tf
  ├── module "networking"    → modules/networking/
  ├── module "aks"           → modules/aks/         (depends on networking)
  ├── module "acr"           → modules/acr/
  ├── module "postgres"      → modules/postgres/    (depends on networking)
  ├── module "redis"         → modules/redis/       (depends on networking)
  ├── module "keyvault"      → modules/keyvault/    (depends on aks)
  ├── module "static_web"    → modules/static-web-app/
  ├── module "finops"        → modules/finops/
  └── module "monitoring"    → modules/monitoring/
```

### D6: Terraform state in Azure Storage over Terraform Cloud or local state

**Decision**: Use an Azure Storage Account with blob container for remote state, with state locking via blob lease.

**Rationale**: Keeps everything in Azure (no third-party dependency). Free within storage account limits. State locking prevents concurrent applies. The storage account is created manually (or via a bootstrap script) before the first `terraform init` — it's the one resource not managed by Terraform itself.

**Naming**: `stodindevstate` (storage accounts are globally unique, alphanumeric, max 24 chars).

### D7: Three Kubernetes namespaces for workload isolation

**Decision**: Split workloads into `synapseflow-infra` (Neo4j, RabbitMQ, FalkorDB, Qdrant), `synapseflow-agents` (4 agent pods), and `synapseflow-backend` (API + ingress).

**Rationale**: Namespace isolation enables per-namespace resource quotas, network policies, and RBAC. Agents can be restarted independently of infrastructure services. The backend ingress is isolated from internal-only agent services.

Network policies:
- `synapseflow-agents` → can reach `synapseflow-infra` services + managed data (Postgres, Redis)
- `synapseflow-backend` → can reach `synapseflow-agents` + `synapseflow-infra`
- `synapseflow-infra` → no outbound restrictions (Neo4j needs bolt, RabbitMQ needs AMQP)
- External ingress → only `synapseflow-backend` via nginx ingress controller

### D8: Resource limits strategy for dev — tight requests, generous limits

**Decision**: Set low resource requests (to fit on single B4ms) with higher limits for burst.

```
Pod Resource Budget (B4ms: 4 vCPU, 16 GB — ~13 GB usable):

Service              Requests (CPU/Mem)    Limits (CPU/Mem)
────────────────────────────────────────────────────────────
Neo4j                250m / 1Gi            1000m / 3Gi
RabbitMQ             100m / 256Mi          500m  / 512Mi
FalkorDB             100m / 256Mi          500m  / 1Gi
Qdrant               100m / 256Mi          500m  / 1Gi
data_architect       100m / 256Mi          500m  / 512Mi
data_engineer        100m / 256Mi          500m  / 512Mi
knowledge_manager    100m / 256Mi          500m  / 512Mi
medical_assistant    100m / 256Mi          500m  / 512Mi
backend API          100m / 256Mi          500m  / 512Mi
────────────────────────────────────────────────────────────
Total requests:      1200m / 3Gi           (well within capacity)
```

### D9: CI/CD pipeline separation — infra and app as independent workflows

**Decision**: Separate GitHub Actions workflows: `infra-plan.yml` (on PR), `infra-apply.yml` (on merge, `infra/terraform/**` paths), `build-push.yml` (on merge, `src/**` or `Dockerfile*` paths), `deploy.yml` (triggered after build-push, deploys to AKS).

**Rationale**: Infrastructure changes are infrequent and high-risk — they need plan/review/apply gates. Application deployments are frequent and lower-risk. Separating them prevents infrastructure re-applies on every code push and allows independent rollback.

**Flow**:
```
PR (any file)        → ci.yml (lint, test)
PR (infra/**)        → ci.yml + infra-plan.yml (tf plan, comment on PR)
Merge (infra/**)     → infra-apply.yml (tf apply)
Merge (src/**)       → build-push.yml (docker build, push ACR)
                         └→ deploy.yml (kubectl rollout to AKS)
Merge (frontend/**)  → swa-deploy.yml (build Astro, deploy to Static Web App)
```

## Risks / Trade-offs

**[Single node failure]** → Acceptable for dev. All pods restart automatically via AKS. Data services (Neo4j, RabbitMQ) use PersistentVolumeClaims with Azure Disk — data survives node replacement. Prod would use multi-node with pod disruption budgets.

**[$100 budget is extremely tight]** → No headroom for experiments or temporary scale-up. Mitigation: Cost Management alerts at 50% and 80% provide early warning. Auto-shutdown (AKS node scale to 0 at night) could save ~40% but requires manual start in the morning — recommend as optional.

**[Terraform state bootstrap chicken-and-egg]** → The storage account for TF state can't be managed by TF itself. Mitigation: Provide a `scripts/bootstrap-tf-state.sh` that creates the storage account via `az` CLI before first `terraform init`.

**[Neo4j Helm chart complexity]** → The official Neo4j Helm chart has many options and version-specific quirks (e.g., APOC plugin loading). Mitigation: Pin Helm chart version, document tested values, include APOC plugin init container.

**[Private endpoint DNS resolution]** → AKS pods need to resolve private endpoint FQDNs. Mitigation: Enable Azure Private DNS Zone integration with AKS VNet. Terraform handles this via `azurerm_private_dns_zone_virtual_network_link`.

**[OIDC federation scope]** → The federated credential is scoped to the repo. If the repo is renamed or transferred, OIDC breaks. Mitigation: Document the federation setup, include in runbook.

## Open Questions

1. **AKS node auto-shutdown**: Should we implement nightly scale-to-zero (saves ~40% cost) or keep the node running 24/7 for $60/mo? Scale-to-zero means 3-5 min cold start each morning.
2. **ACR name**: Must be globally unique. Proposed: `acrodindev`. Acceptable?
3. **Existing RG**: Is `RG-ODINDATA-DEV` already created in Azure, or should Terraform create it?
4. **Frontend build**: Does the Astro frontend need any environment-specific variables at build time (e.g., API URL), or can it discover the backend at runtime?
