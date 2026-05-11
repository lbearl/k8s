# Implementation Plan: n8n & OpenClaw Deployment

## Overview

Create Kubernetes manifests and ArgoCD Applications to deploy n8n (with PostgreSQL) and OpenClaw on the existing k3s cluster. Tasks are organized by workload — n8n first (namespace, secrets, database layer, application layer, networking), then OpenClaw (namespace, secrets, storage, application, networking), and finally the ArgoCD Applications that reference the workload directories. Each manifest file is its own sub-task. All files follow the established conventions mirroring the Planka workload structure.

## Tasks

- [x] 1. Create n8n namespace and secret management
  - [x] 1.1 Create `workloads/n8n/namespace.yaml`
    - Define a Namespace resource named `n8n`
    - _Requirements: 3.1_
  - [x] 1.2 Create `workloads/n8n/onepassworditem.yaml`
    - Define a OnePasswordItem named `n8n-secret` in namespace `n8n`
    - Reference item path `vaults/k8s/items/n8n-secret`
    - This will sync a Secret containing `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, and `N8N_ENCRYPTION_KEY`
    - _Requirements: 9.1, 9.2, 9.3, 9.4_

- [x] 2. Create n8n PostgreSQL storage and deployment
  - [x] 2.1 Create `workloads/n8n/postgres-pvc.yaml`
    - Define a PVC named `n8n-postgres-data` in namespace `n8n`
    - 5Gi capacity, ReadWriteOnce access mode
    - _Requirements: 5.2, 16.1_
  - [x] 2.2 Create `workloads/n8n/postgres-deployment.yaml`
    - Define a Deployment named `n8n-postgres` in namespace `n8n`
    - Use `postgres:16` image, single replica, Recreate strategy
    - Mount `n8n-postgres-data` PVC at `/var/lib/postgresql/data`
    - Read `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` from Secret `n8n-secret`
    - Define resource requests for CPU and memory
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_
  - [x] 2.3 Create `workloads/n8n/postgres-service.yaml`
    - Define a ClusterIP Service named `n8n-postgres` in namespace `n8n`
    - Route traffic to pods with label `app: n8n-postgres` on port 5432
    - _Requirements: 5.1, 14.1_

- [x] 3. Create n8n application storage and deployment
  - [x] 3.1 Create `workloads/n8n/pvc.yaml`
    - Define a PVC named `n8n-data` in namespace `n8n`
    - 5Gi capacity, ReadWriteOnce access mode
    - _Requirements: 6.6, 16.2_
  - [x] 3.2 Create `workloads/n8n/deployment.yaml`
    - Define a Deployment named `n8n` in namespace `n8n`
    - Use `docker.n8n.io/n8nio/n8n` image, single replica, Recreate strategy
    - Mount `n8n-data` PVC at `/home/node/.n8n`
    - Set literal env vars: `DB_TYPE=postgresdb`, `DB_POSTGRESDB_HOST=n8n-postgres`, `DB_POSTGRESDB_PORT=5432`, `WEBHOOK_URL=https://n8n.home.bearl.me/`, `N8N_EDITOR_BASE_URL=https://n8n.home.bearl.me/`, `N8N_COMMUNITY_PACKAGES_ENABLED=true`, `GENERIC_TIMEZONE=America/Chicago`
    - Read `DB_POSTGRESDB_DATABASE`, `DB_POSTGRESDB_USER`, `DB_POSTGRESDB_PASSWORD`, `N8N_ENCRYPTION_KEY` from Secret `n8n-secret`
    - Define resource requests for CPU and memory
    - Expose container port 5678
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8, 6.9, 18.1, 18.2, 18.3_

- [x] 4. Create n8n Service and Ingress
  - [x] 4.1 Create `workloads/n8n/service.yaml`
    - Define a ClusterIP Service named `n8n` in namespace `n8n`
    - Route traffic to pods with label `app: n8n` on port 5678
    - _Requirements: 7.1, 7.2, 7.3_
  - [x] 4.2 Create `workloads/n8n/ingress.yaml`
    - Define an Ingress named `n8n` in namespace `n8n`
    - Use `nginx` ingress class
    - Annotate with `cert-manager.io/cluster-issuer: step-ca-issuer`
    - Annotate with `nginx.ingress.kubernetes.io/proxy-body-size: "50m"`
    - TLS for host `n8n.home.bearl.me` stored in secret `n8n-tls`
    - Route path `/` (Prefix) to service `n8n` on port 5678
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

- [x] 5. Checkpoint - Verify n8n manifests
  - Ensure all n8n YAML manifests are syntactically valid and consistent. Ask the user if questions arise.

- [x] 6. Create OpenClaw namespace and secret management
  - [x] 6.1 Create `workloads/openclaw/namespace.yaml`
    - Define a Namespace resource named `openclaw`
    - _Requirements: 4.1_
  - [x] 6.2 Create `workloads/openclaw/onepassworditem.yaml`
    - Define a OnePasswordItem named `openclaw-secret` in namespace `openclaw`
    - Reference item path `vaults/k8s/items/openclaw-secret`
    - This will sync a Secret containing `OPENCLAW_GATEWAY_TOKEN` and `OPENROUTER_API_KEY`
    - _Requirements: 13.1, 13.2, 13.3, 13.4_

- [x] 7. Create OpenClaw storage
  - [x] 7.1 Create `workloads/openclaw/config-pvc.yaml`
    - Define a PVC named `openclaw-config` in namespace `openclaw`
    - 2Gi capacity, ReadWriteOnce access mode
    - _Requirements: 17.1_
  - [x] 7.2 Create `workloads/openclaw/workspace-pvc.yaml`
    - Define a PVC named `openclaw-workspace` in namespace `openclaw`
    - 5Gi capacity, ReadWriteOnce access mode
    - _Requirements: 17.2_

- [x] 8. Create OpenClaw application deployment
  - [x] 8.1 Create `workloads/openclaw/deployment.yaml`
    - Define a Deployment named `openclaw` in namespace `openclaw`
    - Use `ghcr.io/openclaw/openclaw:latest` image, single replica, Recreate strategy
    - Set container command: `node dist/index.js gateway --bind lan --port 18789`
    - Set literal env vars: `OPENCLAW_GATEWAY_BIND=lan`, `OPENCLAW_GATEWAY_PORT=18789`, `NODE_ENV=production`
    - Read `OPENCLAW_GATEWAY_TOKEN` and `OPENROUTER_API_KEY` from Secret `openclaw-secret`
    - Mount `openclaw-config` PVC at `/home/node/.openclaw`
    - Mount `openclaw-workspace` PVC at `/home/node/.openclaw/workspace`
    - Set security context: `runAsUser: 1000`, `runAsGroup: 1000`, `fsGroup: 1000`
    - Expose container ports 18789 (gateway) and 18790 (bridge)
    - Define resource requests for CPU and memory
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7, 10.8, 10.9, 10.10, 10.11, 10.12, 10.13, 17.1, 17.2, 17.4_

- [x] 9. Create OpenClaw Service and Ingress
  - [x] 9.1 Create `workloads/openclaw/service.yaml`
    - Define a ClusterIP Service named `openclaw` in namespace `openclaw`
    - Route traffic to pods with label `app: openclaw` on port 18789
    - _Requirements: 11.1, 11.2, 11.3_
  - [x] 9.2 Create `workloads/openclaw/ingress.yaml`
    - Define an Ingress named `openclaw` in namespace `openclaw`
    - Use `nginx` ingress class
    - Annotate with `cert-manager.io/cluster-issuer: step-ca-issuer`
    - TLS for host `openclaw.home.bearl.me` stored in secret `openclaw-tls`
    - Route path `/` (Prefix) to service `openclaw` on port 18789
    - _Requirements: 12.1, 12.2, 12.3, 12.4_

- [x] 10. Checkpoint - Verify OpenClaw manifests
  - Ensure all OpenClaw YAML manifests are syntactically valid and consistent. Ask the user if questions arise.

- [x] 11. Create ArgoCD Application manifests
  - [x] 11.1 Create `argocd/apps/n8n.yaml`
    - Define an ArgoCD Application named `n8n` in namespace `argocd`
    - Source: `http://gitea-http.gitea.svc.cluster.local:3000/infra/k8s.git`, branch `main`, path `workloads/n8n`
    - Destination: `https://kubernetes.default.svc`, namespace `n8n`
    - Enable automated sync with selfHeal and prune
    - Include `CreateNamespace=true` sync option and `resources-finalizer.argocd.argoproj.io` finalizer
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_
  - [x] 11.2 Create `argocd/apps/openclaw.yaml`
    - Define an ArgoCD Application named `openclaw` in namespace `argocd`
    - Source: `http://gitea-http.gitea.svc.cluster.local:3000/infra/k8s.git`, branch `main`, path `workloads/openclaw`
    - Destination: `https://kubernetes.default.svc`, namespace `openclaw`
    - Enable automated sync with selfHeal and prune
    - Include `CreateNamespace=true` sync option and `resources-finalizer.argocd.argoproj.io` finalizer
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

- [x] 12. Final checkpoint - Validate all manifests
  - Ensure all YAML manifests across both workloads and ArgoCD apps are syntactically valid and consistent. Ask the user if questions arise.

## Notes

- All manifests are declarative Kubernetes YAML — no application code or property-based tests apply.
- Secrets are managed via 1Password Connect (OnePasswordItem CRDs); no manual Secret creation needed.
- The file structure mirrors the existing Planka workload for consistency.
- ArgoCD Applications are created last since they reference the workload directories.
- Each task references specific acceptance criteria from the requirements document for traceability.
