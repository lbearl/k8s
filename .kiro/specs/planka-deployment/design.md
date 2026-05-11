# Design Document: Planka Deployment

## Overview

This design describes the Kubernetes manifests and ArgoCD configuration required to deploy Planka (an open-source kanban board) with a PostgreSQL backend on the existing k3s cluster. The deployment follows the established GitOps pattern: manifests live in `workloads/planka/`, an ArgoCD Application in `argocd/apps/planka.yaml` syncs them, and TLS is handled by cert-manager with the existing `step-ca-issuer` ClusterIssuer.

The design mirrors the Gitea workload structure — dedicated namespace, Deployment(s), Service, Ingress, PVC(s), and a Secret for sensitive values.

## Architecture

```mermaid
graph TD
    subgraph ArgoCD
        RootApp[root-app] --> PlankaApp[argocd/apps/planka.yaml]
    end

    subgraph planka namespace
        PlankaApp -->|syncs| NS[Namespace: planka]
        PlankaApp -->|syncs| SecretRes[Secret: planka-secret]
        PlankaApp -->|syncs| PG_PVC[PVC: planka-postgres-data]
        PlankaApp -->|syncs| PG_Deploy[Deployment: planka-postgres]
        PlankaApp -->|syncs| Planka_PVC[PVC: planka-uploads]
        PlankaApp -->|syncs| Planka_Deploy[Deployment: planka]
        PlankaApp -->|syncs| SVC[Service: planka]
        PlankaApp -->|syncs| ING[Ingress: planka]

        PG_Deploy -->|mounts| PG_PVC
        PG_Deploy -->|reads| SecretRes
        Planka_Deploy -->|mounts| Planka_PVC
        Planka_Deploy -->|reads| SecretRes
        Planka_Deploy -->|connects to| PG_Deploy
        SVC -->|routes to| Planka_Deploy
        ING -->|routes to| SVC
    end

    User[Browser] -->|HTTPS planka.home.bearl.me| ING
    CertMgr[cert-manager] -->|provisions TLS| ING
```

### Design Decisions

1. **Single-pod PostgreSQL** — Planka is a low-traffic internal tool. A single-replica PostgreSQL Deployment with a PVC is sufficient; no need for an operator or HA setup.
2. **Recreate strategy for both Deployments** — Both Planka and PostgreSQL use `ReadWriteOnce` PVCs, which cannot be mounted by two pods simultaneously. `Recreate` avoids stuck rollouts.
3. **Shared Secret** — One Secret (`planka-secret`) holds both PostgreSQL credentials and the Planka `SECRET_KEY`. This keeps the manifest count low and simplifies references.
4. **Placeholder Secret in Git** — The Secret manifest will contain placeholder values. The operator must replace them before the first sync (or use sealed-secrets/external-secrets in the future). This matches the current cluster pattern where secrets are managed manually.

## Components and Interfaces

### File Layout

```
argocd/apps/planka.yaml          # ArgoCD Application
workloads/planka/
├── namespace.yaml               # Namespace
├── secret.yaml                  # Secret (placeholder values)
├── postgres-pvc.yaml            # PVC for PostgreSQL data
├── postgres-deployment.yaml     # PostgreSQL Deployment
├── pvc.yaml                     # PVC for Planka user uploads
├── deployment.yaml              # Planka Deployment
├── service.yaml                 # ClusterIP Service
└── ingress.yaml                 # Ingress with TLS
```

### Component Details

| Component | Resource | Name | Purpose |
|-----------|----------|------|---------|
| ArgoCD App | `Application` | `planka` | Syncs `workloads/planka` to the cluster |
| Namespace | `Namespace` | `planka` | Resource isolation |
| Secret | `Secret` | `planka-secret` | DB credentials + Planka SECRET_KEY |
| PostgreSQL PVC | `PersistentVolumeClaim` | `planka-postgres-data` | 2Gi RWO storage for DB |
| PostgreSQL | `Deployment` | `planka-postgres` | PostgreSQL 16 single-replica |
| Planka PVC | `PersistentVolumeClaim` | `planka-uploads` | 2Gi RWO storage for uploads |
| Planka | `Deployment` | `planka` | Planka application |
| Service | `Service` | `planka` | ClusterIP on port 1337 |
| Ingress | `Ingress` | `planka` | TLS termination, routes to Service |

### Inter-Component Communication

- **Planka → PostgreSQL**: Planka connects via the Kubernetes DNS name `planka-postgres.planka.svc.cluster.local:5432` using credentials from `planka-secret`.
- **Ingress → Service → Planka**: External HTTPS traffic arrives at the Ingress, terminates TLS, and forwards to the `planka` Service on port 1337, which routes to the Planka pod.
- **cert-manager → Ingress**: cert-manager reads the `cert-manager.io/cluster-issuer` annotation and provisions a certificate stored in `planka-tls`.

## Data Models

### Secret Structure (`planka-secret`)

| Key | Description | Used By |
|-----|-------------|---------|
| `POSTGRES_DB` | Database name (e.g., `planka`) | PostgreSQL, Planka |
| `POSTGRES_USER` | Database username | PostgreSQL, Planka |
| `POSTGRES_PASSWORD` | Database password | PostgreSQL, Planka |
| `SECRET_KEY` | Planka session/encryption key | Planka |

### Environment Variable Mapping

**PostgreSQL Deployment:**
| Env Var | Source |
|---------|--------|
| `POSTGRES_DB` | `planka-secret` key `POSTGRES_DB` |
| `POSTGRES_USER` | `planka-secret` key `POSTGRES_USER` |
| `POSTGRES_PASSWORD` | `planka-secret` key `POSTGRES_PASSWORD` |

**Planka Deployment:**
| Env Var | Source |
|---------|--------|
| `BASE_URL` | Literal `https://planka.home.bearl.me` |
| `DATABASE_URL` | Constructed: `postgresql://$(POSTGRES_USER):$(POSTGRES_PASSWORD)@planka-postgres:5432/$(POSTGRES_DB)` |
| `SECRET_KEY` | `planka-secret` key `SECRET_KEY` |

### Persistent Volume Claims

| PVC Name | Capacity | Access Mode | Mount Path | Pod |
|----------|----------|-------------|------------|-----|
| `planka-postgres-data` | 2Gi | ReadWriteOnce | `/var/lib/postgresql/data` | planka-postgres |
| `planka-uploads` | 2Gi | ReadWriteOnce | `/app/public/user-avatars` + `/app/private/attachments` | planka |

> **Note:** Planka stores user avatars and attachments in separate directories. A single PVC mounted at `/app/private` with a subPath or a shared parent mount can cover both, but the simplest approach is to mount at `/app/public/user-avatars` and `/app/private/attachments` using subPaths from one PVC.

## Error Handling

### Missing Secret

If `planka-secret` does not exist or is missing keys, the Deployments will fail to schedule with `CreateContainerConfigError`. This is the standard Kubernetes behavior for `envFrom` / `secretKeyRef` with required keys — the pod stays in a pending/error state with a clear event message.

### PVC Not Bound

If the default StorageClass cannot provision a volume, the PVC remains in `Pending` state and the pod cannot start. The operator should verify that the cluster's default StorageClass (local-path on k3s) is functional.

### PostgreSQL Unavailable

If PostgreSQL is not ready when Planka starts, Planka will crash-loop. Kubernetes' restart policy (`Always`) will retry, and once PostgreSQL is healthy, Planka will connect on the next restart. No init-container dependency is strictly required for this low-traffic internal tool — the restart backoff is acceptable.

### ArgoCD Sync Failures

If manifests contain invalid YAML or reference non-existent resources, ArgoCD will report a sync failure in its UI/CLI. The operator resolves this by fixing the manifests in Git.

## Testing Strategy

### Why Property-Based Testing Does Not Apply

This feature consists entirely of declarative Kubernetes YAML manifests and an ArgoCD Application resource. There is no application code, no pure functions, and no input/output transformations to test. PBT is explicitly not appropriate for Infrastructure as Code.

### Recommended Testing Approach

1. **Schema Validation (CI)**
   - Use `kubeconform` or `kubeval` to validate all YAML manifests against Kubernetes OpenAPI schemas.
   - Validates that resource kinds, API versions, and field types are correct.

2. **Linting (CI)**
   - Use `kube-linter` to check for best-practice violations (missing resource requests, missing labels, etc.).

3. **Dry-Run Sync (Staging)**
   - Use `argocd app diff` or `argocd app sync --dry-run` to verify the manifests apply cleanly before merging.

4. **Integration Tests (Post-Deploy)**
   - Verify the ArgoCD Application reaches `Synced` and `Healthy` status.
   - Verify the Planka pod reaches `Running` state.
   - Verify HTTPS connectivity to `https://planka.home.bearl.me` returns a 200 response.
   - Verify PostgreSQL accepts connections from within the namespace.

5. **Manual Smoke Test**
   - Log in to Planka via the browser and create a board/card to confirm end-to-end functionality.
