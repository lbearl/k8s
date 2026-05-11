# Requirements Document

## Introduction

Deploy n8n (workflow automation platform) and OpenClaw (personal AI assistant gateway) as new services on the existing k3s cluster. Both services will be managed via ArgoCD following the established GitOps pattern, accessible over HTTPS on the `home.bearl.me` domain, and use 1Password Connect for secret management.

n8n is an extensible workflow automation tool that will initially integrate with Planka (the existing kanban board) and expand to orchestrate additional services over time. It requires a PostgreSQL database for workflow and credential persistence.

OpenClaw is a personal AI assistant gateway — a Node.js application that connects to cloud AI providers via OpenRouter and bridges to messaging channels (WhatsApp, Telegram, Slack, Discord, etc.). It uses file-based storage for configuration and workspace data, requires no database, and runs as a non-root user (node, UID 1000). OpenRouter provides a unified API for accessing multiple LLM providers (Claude, GPT, Gemini, etc.) with automatic model routing and fallbacks.

Both services follow the established workload conventions: dedicated namespaces, Deployments, Services, Ingresses, PVCs, and 1Password-managed secrets stored under `workloads/{app-name}/` with ArgoCD Applications in `argocd/apps/`.

## Glossary

- **n8n**: An open-source workflow automation platform (container image: `docker.n8n.io/n8nio/n8n`)
- **OpenClaw**: A personal AI assistant gateway that connects to cloud AI providers via OpenRouter and bridges to messaging channels (container image: `ghcr.io/openclaw/openclaw:latest`)
- **OpenRouter**: A unified LLM API gateway (openrouter.ai) that routes requests to multiple AI providers; OpenClaw uses it via the `OPENROUTER_API_KEY` environment variable
- **ArgoCD_Application**: A custom resource that tells ArgoCD how to deploy and sync a set of Kubernetes manifests from a Git repository
- **Cluster**: The k3s Kubernetes cluster at `https://kubernetes.default.svc`
- **Ingress**: A Kubernetes Ingress resource that routes external HTTP/HTTPS traffic to a Service
- **ClusterIssuer**: The cert-manager ClusterIssuer named `step-ca-issuer` that provisions TLS certificates via step-ca
- **PVC**: A PersistentVolumeClaim providing durable storage for application data
- **OnePasswordItem**: A custom resource that syncs secrets from 1Password vaults into Kubernetes Secrets via the 1Password Connect operator
- **PostgreSQL**: A relational database used as the backend data store for n8n
- **Planka_API**: The REST API exposed by the Planka kanban board at `http://planka.planka.svc.cluster.local:1337`

## Requirements

### Requirement 1: n8n ArgoCD Application Definition

**User Story:** As a cluster operator, I want n8n managed by ArgoCD, so that deployments are automated and follow the GitOps workflow.

#### Acceptance Criteria

1. THE ArgoCD_Application SHALL reference the source path `workloads/n8n` in the Git repository `http://gitea-http.gitea.svc.cluster.local:3000/infra/k8s.git` on branch `main`
2. THE ArgoCD_Application SHALL target the destination namespace `n8n` on the Cluster
3. THE ArgoCD_Application SHALL enable automated sync with self-heal and prune enabled
4. THE ArgoCD_Application SHALL include the `CreateNamespace=true` sync option
5. THE ArgoCD_Application SHALL include the `resources-finalizer.argocd.argoproj.io` finalizer

### Requirement 2: OpenClaw ArgoCD Application Definition

**User Story:** As a cluster operator, I want OpenClaw managed by ArgoCD, so that deployments are automated and follow the GitOps workflow.

#### Acceptance Criteria

1. THE ArgoCD_Application SHALL reference the source path `workloads/openclaw` in the Git repository `http://gitea-http.gitea.svc.cluster.local:3000/infra/k8s.git` on branch `main`
2. THE ArgoCD_Application SHALL target the destination namespace `openclaw` on the Cluster
3. THE ArgoCD_Application SHALL enable automated sync with self-heal and prune enabled
4. THE ArgoCD_Application SHALL include the `CreateNamespace=true` sync option
5. THE ArgoCD_Application SHALL include the `resources-finalizer.argocd.argoproj.io` finalizer

### Requirement 3: n8n Namespace Isolation

**User Story:** As a cluster operator, I want n8n deployed in its own namespace, so that resources are isolated from other workloads.

#### Acceptance Criteria

1. THE Cluster SHALL contain a Namespace named `n8n`

### Requirement 4: OpenClaw Namespace Isolation

**User Story:** As a cluster operator, I want OpenClaw deployed in its own namespace, so that resources are isolated from other workloads.

#### Acceptance Criteria

1. THE Cluster SHALL contain a Namespace named `openclaw`

### Requirement 5: n8n PostgreSQL Database Deployment

**User Story:** As a cluster operator, I want a PostgreSQL instance deployed alongside n8n, so that n8n has a persistent data store for workflows and credentials.

#### Acceptance Criteria

1. THE Cluster SHALL run a PostgreSQL Deployment in the `n8n` namespace
2. THE PostgreSQL Deployment SHALL store data on a PVC with at least 5Gi of storage
3. THE PostgreSQL Deployment SHALL read database credentials from a Secret named `n8n-secret` in the `n8n` namespace
4. THE PostgreSQL Deployment SHALL define resource requests for CPU and memory
5. THE PostgreSQL Deployment SHALL use the `Recreate` deployment strategy
6. THE PostgreSQL Deployment SHALL use the `postgres:16` container image

### Requirement 6: n8n Application Deployment

**User Story:** As a cluster operator, I want the n8n application deployed as a Kubernetes Deployment, so that it runs reliably on the cluster and can orchestrate workflows.

#### Acceptance Criteria

1. THE n8n Deployment SHALL run in the `n8n` namespace using the `docker.n8n.io/n8nio/n8n` container image
2. THE n8n Deployment SHALL connect to the PostgreSQL instance using credentials from the Secret named `n8n-secret`
3. THE n8n Deployment SHALL set the `WEBHOOK_URL` environment variable to `https://n8n.home.bearl.me/`
4. THE n8n Deployment SHALL set the `N8N_EDITOR_BASE_URL` environment variable to `https://n8n.home.bearl.me/`
5. THE n8n Deployment SHALL configure PostgreSQL as the database backend via the `DB_TYPE` environment variable set to `postgresdb`
6. THE n8n Deployment SHALL store workflow data files on a PVC with at least 5Gi of storage
7. THE n8n Deployment SHALL define resource requests for CPU and memory
8. THE n8n Deployment SHALL use the `Recreate` deployment strategy
9. THE n8n Deployment SHALL set an encryption key for credentials via the `N8N_ENCRYPTION_KEY` environment variable sourced from the Secret

### Requirement 7: n8n Service Exposure

**User Story:** As a cluster operator, I want a ClusterIP Service for n8n, so that the Ingress can route traffic to the application.

#### Acceptance Criteria

1. THE Service SHALL be named `n8n` in the `n8n` namespace
2. THE Service SHALL route traffic to the n8n Deployment on port 5678
3. THE Service SHALL be of type ClusterIP

### Requirement 8: n8n Ingress and TLS

**User Story:** As a user, I want to access n8n at `n8n.home.bearl.me` over HTTPS, so that my connection is secure.

#### Acceptance Criteria

1. THE Ingress SHALL route traffic for host `n8n.home.bearl.me` to the `n8n` Service on port 5678
2. THE Ingress SHALL use the `nginx` ingress class
3. THE Ingress SHALL request a TLS certificate from the ClusterIssuer named `step-ca-issuer` via the `cert-manager.io/cluster-issuer` annotation
4. THE Ingress SHALL store the TLS certificate in a Secret named `n8n-tls`
5. THE Ingress SHALL set `nginx.ingress.kubernetes.io/proxy-body-size` to at least `50m` to support large webhook payloads

### Requirement 9: n8n Secret Management

**User Story:** As a cluster operator, I want n8n secrets managed via 1Password Connect, so that sensitive values are securely synced from the 1Password vault.

#### Acceptance Criteria

1. THE OnePasswordItem SHALL be named `n8n-secret` in the `n8n` namespace
2. THE OnePasswordItem SHALL reference the item path `vaults/k8s/items/n8n-secret`
3. THE synced Secret SHALL contain the PostgreSQL database name, username, and password
4. THE synced Secret SHALL contain the n8n `N8N_ENCRYPTION_KEY` value
5. IF the Secret is missing or incomplete, THEN THE n8n Deployment SHALL fail to start with a clear error indicating missing environment variables

### Requirement 10: OpenClaw Application Deployment

**User Story:** As a cluster operator, I want the OpenClaw application deployed as a Kubernetes Deployment, so that the AI assistant gateway runs reliably on the cluster.

#### Acceptance Criteria

1. THE OpenClaw Deployment SHALL run in the `openclaw` namespace using the `ghcr.io/openclaw/openclaw:latest` container image
2. THE OpenClaw Deployment SHALL run the container command `node dist/index.js gateway --bind lan --port 18789`
3. THE OpenClaw Deployment SHALL set the `OPENCLAW_GATEWAY_BIND` environment variable to `lan`
4. THE OpenClaw Deployment SHALL set the `OPENCLAW_GATEWAY_PORT` environment variable to `18789`
5. THE OpenClaw Deployment SHALL set the `NODE_ENV` environment variable to `production`
6. THE OpenClaw Deployment SHALL set the `OPENCLAW_GATEWAY_TOKEN` environment variable sourced from the Secret named `openclaw-secret`
7. THE OpenClaw Deployment SHALL set the `OPENROUTER_API_KEY` environment variable sourced from the Secret named `openclaw-secret`
8. THE OpenClaw Deployment SHALL mount a PVC at `/home/node/.openclaw` for configuration and session data
9. THE OpenClaw Deployment SHALL mount a PVC or subPath at `/home/node/.openclaw/workspace` for agent workspace files
10. THE OpenClaw Deployment SHALL run as non-root user with UID 1000
11. THE OpenClaw Deployment SHALL define resource requests for CPU and memory
12. THE OpenClaw Deployment SHALL use the `Recreate` deployment strategy
13. THE OpenClaw Deployment SHALL expose container port 18789 for the gateway and container port 18790 for the bridge

### Requirement 11: OpenClaw Service Exposure

**User Story:** As a cluster operator, I want a ClusterIP Service for OpenClaw, so that the Ingress can route traffic to the gateway.

#### Acceptance Criteria

1. THE Service SHALL be named `openclaw` in the `openclaw` namespace
2. THE Service SHALL route traffic to the OpenClaw Deployment on port 18789
3. THE Service SHALL be of type ClusterIP

### Requirement 12: OpenClaw Ingress and TLS

**User Story:** As a user, I want to access OpenClaw at `openclaw.home.bearl.me` over HTTPS, so that my connection is secure.

#### Acceptance Criteria

1. THE Ingress SHALL route traffic for host `openclaw.home.bearl.me` to the `openclaw` Service on port 18789
2. THE Ingress SHALL use the `nginx` ingress class
3. THE Ingress SHALL request a TLS certificate from the ClusterIssuer named `step-ca-issuer` via the `cert-manager.io/cluster-issuer` annotation
4. THE Ingress SHALL store the TLS certificate in a Secret named `openclaw-tls`

### Requirement 13: OpenClaw Secret Management

**User Story:** As a cluster operator, I want OpenClaw secrets managed via 1Password Connect, so that sensitive values are securely synced from the 1Password vault.

#### Acceptance Criteria

1. THE OnePasswordItem SHALL be named `openclaw-secret` in the `openclaw` namespace
2. THE OnePasswordItem SHALL reference the item path `vaults/k8s/items/openclaw-secret`
3. THE synced Secret SHALL contain the `OPENCLAW_GATEWAY_TOKEN` value for gateway authentication
4. THE synced Secret SHALL contain the `OPENROUTER_API_KEY` value for AI provider connectivity via OpenRouter
5. IF the Secret is missing or incomplete, THEN THE OpenClaw Deployment SHALL fail to start with a clear error indicating missing environment variables

### Requirement 14: n8n Network Access to Planka

**User Story:** As a workflow designer, I want n8n to reach the Planka API, so that I can build automations that create and manage kanban cards.

#### Acceptance Criteria

1. THE n8n Deployment SHALL be able to reach the Planka_API at `http://planka.planka.svc.cluster.local:1337` via cluster-internal DNS
2. WHEN n8n sends an HTTP request to the Planka_API, THE Cluster SHALL route the request without requiring additional NetworkPolicy exceptions

### Requirement 15: OpenClaw Outbound Internet Access

**User Story:** As a user, I want OpenClaw to reach cloud AI provider APIs, so that the gateway can relay requests to services like Claude and OpenAI.

#### Acceptance Criteria

1. THE OpenClaw Deployment SHALL be able to reach the OpenRouter API at `https://openrouter.ai/api/` and any downstream AI provider endpoints
2. THE Cluster SHALL allow outbound internet traffic from the `openclaw` namespace without requiring additional NetworkPolicy exceptions
3. IF an AI provider endpoint is unreachable, THEN THE OpenClaw application SHALL return an error to the connected messaging channel indicating the provider is unavailable

### Requirement 16: n8n Persistent Storage

**User Story:** As a cluster operator, I want n8n data persisted across pod restarts, so that workflows and execution history are not lost during redeployments.

#### Acceptance Criteria

1. THE PVC for n8n PostgreSQL SHALL use the `ReadWriteOnce` access mode
2. THE PVC for n8n workflow files SHALL use the `ReadWriteOnce` access mode
3. WHEN a pod is restarted, THE Cluster SHALL remount the existing PVC data without data loss

### Requirement 17: OpenClaw Persistent Storage

**User Story:** As a cluster operator, I want OpenClaw data persisted across pod restarts, so that configuration, sessions, and workspace files are not lost during redeployments.

#### Acceptance Criteria

1. THE PVC for OpenClaw configuration and sessions SHALL be mounted at `/home/node/.openclaw` with `ReadWriteOnce` access mode and at least 2Gi of storage
2. THE PVC for OpenClaw workspace SHALL be mounted at `/home/node/.openclaw/workspace` with `ReadWriteOnce` access mode and at least 5Gi of storage
3. WHEN a pod is restarted, THE Cluster SHALL remount the existing PVC data without data loss
4. THE PVCs SHALL be writable by UID 1000 (the node user)

### Requirement 18: n8n Extensibility Configuration

**User Story:** As a workflow designer, I want n8n configured for future extensibility, so that I can add new integrations and community nodes without redeployment.

#### Acceptance Criteria

1. THE n8n Deployment SHALL mount the workflow data PVC at `/home/node/.n8n` to support community node installation
2. THE n8n Deployment SHALL set `N8N_COMMUNITY_PACKAGES_ENABLED` environment variable to `true`
3. THE n8n Deployment SHALL set the `GENERIC_TIMEZONE` environment variable to `America/Chicago`
