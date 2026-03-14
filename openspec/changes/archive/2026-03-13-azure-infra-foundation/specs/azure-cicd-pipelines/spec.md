## ADDED Requirements

### Requirement: OIDC federation for GitHub Actions
The system SHALL use Azure AD Workload Identity Federation to authenticate GitHub Actions workflows. No client secrets SHALL be stored in GitHub. The federation SHALL be scoped to the specific GitHub repository.

#### Scenario: OIDC authentication in workflow
- **WHEN** a GitHub Actions workflow requests an Azure token
- **THEN** it SHALL use the `azure/login` action with OIDC
- **AND** `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, and `AZURE_SUBSCRIPTION_ID` SHALL be stored as GitHub Actions variables (not secrets)

#### Scenario: Branch-scoped federation
- **WHEN** a workflow runs on a PR branch
- **THEN** OIDC SHALL authenticate for `terraform plan` (read-only)
- **AND** `terraform apply` SHALL only be authorized from the `main` branch

### Requirement: CI workflow with Terraform plan
The existing `ci.yml` SHALL be extended to run `terraform plan` on PRs that modify files under `infra/terraform/**`. The plan output SHALL be posted as a PR comment.

#### Scenario: Infra PR review
- **WHEN** a PR modifies files under `infra/terraform/`
- **THEN** CI SHALL run `terraform init` and `terraform plan`
- **AND** the plan output SHALL be posted as a comment on the PR

#### Scenario: Non-infra PR
- **WHEN** a PR does not modify files under `infra/terraform/`
- **THEN** the Terraform plan step SHALL be skipped

### Requirement: Infrastructure apply workflow
A `infra-apply.yml` workflow SHALL run `terraform apply` when changes to `infra/terraform/**` are merged to `main`. The apply SHALL require no manual approval for dev but SHALL support environment protection rules for future prod.

#### Scenario: Auto-apply on merge to main
- **WHEN** a PR with infra changes is merged to `main`
- **THEN** `terraform apply -auto-approve` SHALL execute for the dev environment

### Requirement: Container build and push workflow
A `build-push.yml` workflow SHALL build Docker images and push them to ACR when application code changes are merged to `main`. Images SHALL be tagged with the git commit SHA.

#### Scenario: Agent image build
- **WHEN** files under `src/` or `Dockerfile.agent` change on `main`
- **THEN** the workflow SHALL build the agent image using `Dockerfile.agent`
- **AND** push to `{acr_login_server}/synapseflow/agent:{git-sha}`
- **AND** also tag as `{acr_login_server}/synapseflow/agent:latest`

#### Scenario: Backend image build
- **WHEN** files under `src/` or `application/api/` change on `main`
- **THEN** the workflow SHALL build the backend image
- **AND** push to `{acr_login_server}/synapseflow/backend:{git-sha}`

### Requirement: Application deploy workflow
A `deploy.yml` workflow SHALL be triggered after `build-push.yml` completes. It SHALL update the AKS deployments to use the new image tags.

#### Scenario: Rolling update
- **WHEN** new images are pushed to ACR
- **THEN** the deploy workflow SHALL run `kubectl set image` or `kustomize edit set image` for each affected deployment
- **AND** wait for rollout to complete with `kubectl rollout status`

#### Scenario: Deploy failure rollback
- **WHEN** `kubectl rollout status` reports failure
- **THEN** the workflow SHALL run `kubectl rollout undo` on the failed deployment
- **AND** the workflow SHALL exit with failure status

### Requirement: Frontend deploy workflow
A `swa-deploy.yml` workflow SHALL deploy the Astro frontend to Azure Static Web Apps when files under `frontend/` change on `main`.

#### Scenario: Frontend deployment
- **WHEN** files under `frontend/` change on `main`
- **THEN** the workflow SHALL run `npm ci && npm run build` in `frontend/`
- **AND** deploy `frontend/dist/` to the Static Web App using the deployment token from Key Vault
