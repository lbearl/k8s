# Requirements Document

## Introduction

Deploy Planka, an open-source kanban board application, as a new service on the existing k3s cluster. Planka will be managed via ArgoCD following the established GitOps pattern and made accessible at `planka.home.bearl.me` with TLS termination provided by cert-manager and step-ca.

Planka requires a PostgreSQL database backend. The deployment will follow the same structural conventions as existing workloads (e.g., Gitea): dedicated namespace, Deployment, Service, Ingress, and PersistentVolumeClaim manifests stored under `workloads/planka/`, with an ArgoCD Application defined in `argocd/apps/planka.yaml`.

## Glossary

- **Planka**: An open-source kanban board application (container image: `ghcr.io/plankanban/planka`)
- **PostgreSQL**: A relational database used as the backend data store for Planka
- **ArgoCD_Application**: A custom resource that tells ArgoCD how to deploy and sync a set of Kubernetes manifests from a Git repository
- **Cluster**: The k3s Kubernetes cluster at `https://kubernetes.default.svc`
- **Ingress**: A Kubernetes Ingress resource that routes external HTTP/HTTPS traffic to a Service
- **ClusterIssuer**: The cert-manager ClusterIssuer named `step-ca-issuer` that provisions TLS certificates via step-ca ACME
- **PVC**: A PersistentVolumeClaim providing durable storage for application data
- **Secret**: A Kubernetes Secret resource storing sensitive configuration values

## Requirements

### Requirement 1: ArgoCD Application Definition

**User Story:** As a cluster operator, I want Planka managed by ArgoCD, so that deployments are automated and follow the GitOps workflow.

#### Acceptance Criteria

1. THE ArgoCD_Application SHALL reference the source path `workloads/planka` in the Git repository `http://gitea-http.gitea.svc.cluster.local:3000/infra/k8s.git` on branch `main`
2. THE ArgoCD_Application SHALL target the destination namespace `planka` on the Cluster
3. THE ArgoCD_Application SHALL enable automated sync with self-heal and prune enabled
4. THE ArgoCD_Application SHALL include the `CreateNamespace=true` sync option
5. THE ArgoCD_Application SHALL include the `resources-finalizer.argocd.argoproj.io` finalizer

### Requirement 2: Namespace Isolation

**User Story:** As a cluster operator, I want Planka deployed in its own namespace, so that resources are isolated from other workloads.

#### Acceptance Criteria

1. THE Cluster SHALL contain a Namespace named `planka`

### Requirement 3: PostgreSQL Database Deployment

**User Story:** As a cluster operator, I want a PostgreSQL instance deployed alongside Planka, so that Planka has a persistent data store.

#### Acceptance Criteria

1. THE Cluster SHALL run a PostgreSQL Deployment in the `planka` namespace
2. THE PostgreSQL Deployment SHALL store data on a PVC with at least 2Gi of storage
3. THE PostgreSQL Deployment SHALL read database credentials from a Secret in the `planka` namespace
4. THE PostgreSQL Deployment SHALL define resource requests for CPU and memory

### Requirement 4: Planka Application Deployment

**User Story:** As a cluster operator, I want the Planka application deployed as a Kubernetes Deployment, so that it runs reliably on the cluster.

#### Acceptance Criteria

1. THE Planka Deployment SHALL run in the `planka` namespace using the `ghcr.io/plankanban/planka` container image
2. THE Planka Deployment SHALL connect to the PostgreSQL instance using credentials from the Secret in the `planka` namespace
3. THE Planka Deployment SHALL set the `BASE_URL` environment variable to `https://planka.home.bearl.me`
4. THE Planka Deployment SHALL set a `SECRET_KEY` environment variable sourced from the Secret
5. THE Planka Deployment SHALL define resource requests for CPU and memory
6. THE Planka Deployment SHALL use the `Recreate` deployment strategy
7. THE Planka Deployment SHALL store user-uploaded files on a PVC with at least 2Gi of storage

### Requirement 5: Service Exposure

**User Story:** As a cluster operator, I want a ClusterIP Service for Planka, so that the Ingress can route traffic to the application.

#### Acceptance Criteria

1. THE Service SHALL be named `planka` in the `planka` namespace
2. THE Service SHALL route traffic to the Planka Deployment on port 1337
3. THE Service SHALL be of type ClusterIP

### Requirement 6: Ingress and TLS

**User Story:** As a user, I want to access Planka at `planka.home.bearl.me` over HTTPS, so that my connection is secure.

#### Acceptance Criteria

1. THE Ingress SHALL route traffic for host `planka.home.bearl.me` to the `planka` Service on port 1337
2. THE Ingress SHALL use the `nginx` ingress class
3. THE Ingress SHALL request a TLS certificate from the ClusterIssuer named `step-ca-issuer` via the `cert-manager.io/cluster-issuer` annotation
4. THE Ingress SHALL store the TLS certificate in a Secret named `planka-tls`

### Requirement 7: Sensitive Configuration

**User Story:** As a cluster operator, I want database credentials and the application secret key stored in a Kubernetes Secret, so that sensitive values are not exposed in plain-text manifests.

#### Acceptance Criteria

1. THE Secret SHALL be named `planka-secret` in the `planka` namespace
2. THE Secret SHALL contain the PostgreSQL database name, username, and password
3. THE Secret SHALL contain the Planka `SECRET_KEY` value
4. IF the Secret is missing or incomplete, THEN THE Planka Deployment SHALL fail to start with a clear error indicating missing environment variables

### Requirement 8: Persistent Storage

**User Story:** As a cluster operator, I want Planka and PostgreSQL data persisted across pod restarts, so that no data is lost during redeployments.

#### Acceptance Criteria

1. THE PVC for PostgreSQL SHALL use the `ReadWriteOnce` access mode
2. THE PVC for Planka user uploads SHALL use the `ReadWriteOnce` access mode
3. WHEN a pod is restarted, THE Cluster SHALL remount the existing PVC data without data loss
