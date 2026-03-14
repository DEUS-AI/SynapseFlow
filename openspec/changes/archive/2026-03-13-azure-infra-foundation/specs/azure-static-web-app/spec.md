## ADDED Requirements

### Requirement: Static Web App for Astro frontend
The system SHALL provision an Azure Static Web App with Free tier SKU. The app SHALL use the Azure-provided domain (`*.azurestaticapps.net`) with automatic HTTPS.

#### Scenario: Static Web App provisioning
- **WHEN** Terraform applies the static-web-app module
- **THEN** a Static Web App named `swa-odin-{env}-westeurope` is created with Free SKU
- **AND** the deployment token is stored in Key Vault as `swa-deployment-token`

### Requirement: Astro static build output
The frontend SHALL be built using `npm run build` producing static files in `frontend/dist/`. The Static Web App SHALL serve these files with `app_location = "frontend"` and `output_location = "dist"`.

#### Scenario: Frontend deployment
- **WHEN** GitHub Actions deploys the frontend
- **THEN** the workflow SHALL use the `Azure/static-web-apps-deploy` action
- **AND** the built static files from `frontend/dist/` SHALL be deployed

#### Scenario: API proxy configuration
- **WHEN** the frontend makes API calls to `/api/*`
- **THEN** the Static Web App SHALL be configured with a `staticwebapp.config.json` proxy rule routing `/api/*` to the AKS backend ingress URL
