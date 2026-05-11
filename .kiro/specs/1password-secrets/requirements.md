# Requirements Document

## Introduction

Integrate 1Password with the k3s cluster for secret management using the 1Password Connect Server and the 1Password Kubernetes Operator. This eliminates plain-text secrets from Git manifests, which is critical because the repository is mirrored to a public GitHub repo.

The 1Password Connect Server provides a REST API for accessing vault items. The 1Password Kubernetes Operator watches for `OnePasswordItem` custom resources and automatically creates/updates native Kubernetes Secrets from 1Password vault items. Together, they allow workloads to consume secrets without those secrets ever appearing in Git.

The Connect Server credentials (`1password-credentials.json`) represent the single bootstrap secret that must be applied manually via `kubectl`, since the operator cannot manage the secret it depends on to function.

## Glossary

- **Connect_Server**: The 1Password Connect Server, a containerized REST API that provides access to 1Password vault items (container images: `1password/connect-api` and `1password/connect-sync`)
- **Operator**: The 1Password Kubernetes Operator, a controller that watches `OnePasswordItem` custom resources and creates/updates native Kubernetes Secrets from 1Password vault data
- **OnePasswordItem**: A custom resource definition (CRD) that declares which 1Password vault item should be synced into a Kubernetes Secret
- **Connect_Credentials_Secret**: The Kubernetes Secret containing the `1password-credentials.json` file, required by the Connect_Server to authenticate with 1Password
- **Connect_Token_Secret**: The Kubernetes Secret containing the access token used by the Connect_Server and Operator to authorize API requests
- **ArgoCD_Application**: A custom resource that tells ArgoCD how to deploy and sync a set of Kubernetes manifests from a Git repository
- **Cluster**: The k3s Kubernetes cluster at `https://kubernetes.default.svc`
- **Vault_Item**: An item stored in a 1Password vault containing secret fields (passwords, keys, environment variables)

## Requirements

### Requirement 1: 1Password Connect Server Deployment

**User Story:** As a cluster operator, I want the 1Password Connect Server running on the cluster, so that the Operator can retrieve secrets from my 1Password vault.

#### Acceptance Criteria

1. THE Connect_Server SHALL be deployed as a Deployment in a dedicated namespace named `1password`
2. THE Connect_Server SHALL run two containers: `connect-api` and `connect-sync`
3. THE Connect_Server SHALL mount the Connect_Credentials_Secret as a file at the path expected by the connect-api container
4. THE Connect_Server SHALL read the access token from the Connect_Token_Secret
5. THE Connect_Server SHALL store sync data on a persistent or emptyDir volume shared between the two containers
6. THE Connect_Server SHALL define resource requests for CPU and memory on both containers
7. WHEN the Connect_Credentials_Secret is missing, THE Connect_Server SHALL fail to start with a clear error in pod events

### Requirement 2: 1Password Connect Server Service

**User Story:** As a cluster operator, I want the Connect Server accessible within the cluster, so that the Operator can communicate with it.

#### Acceptance Criteria

1. THE Service SHALL be named `onepassword-connect` in the `1password` namespace
2. THE Service SHALL route traffic to the Connect_Server on port 8080
3. THE Service SHALL be of type ClusterIP

### Requirement 3: 1Password Kubernetes Operator Deployment

**User Story:** As a cluster operator, I want the 1Password Operator running on the cluster, so that secrets are automatically synced from 1Password into Kubernetes Secrets.

#### Acceptance Criteria

1. THE Operator SHALL be deployed as a Deployment in the `1password` namespace
2. THE Operator SHALL be configured to connect to the Connect_Server via the in-cluster Service URL
3. THE Operator SHALL have RBAC permissions to watch `OnePasswordItem` resources across all namespaces
4. THE Operator SHALL have RBAC permissions to create, update, and delete Secrets in any namespace where a `OnePasswordItem` exists
5. THE Operator SHALL define resource requests for CPU and memory
6. WHEN the Connect_Server is unreachable, THE Operator SHALL retry with backoff and emit warning events on affected OnePasswordItem resources

### Requirement 4: ArgoCD Application for 1Password Components

**User Story:** As a cluster operator, I want the 1Password Connect Server and Operator managed by ArgoCD, so that they follow the same GitOps workflow as all other workloads.

#### Acceptance Criteria

1. THE ArgoCD_Application SHALL reference the source path `workloads/1password` in the Git repository on branch `main`
2. THE ArgoCD_Application SHALL target the destination namespace `1password` on the Cluster
3. THE ArgoCD_Application SHALL enable automated sync with self-heal and prune enabled
4. THE ArgoCD_Application SHALL include the `CreateNamespace=true` sync option
5. THE ArgoCD_Application SHALL include the `resources-finalizer.argocd.argoproj.io` finalizer

### Requirement 5: Bootstrap Credentials Secret

**User Story:** As a cluster operator, I want a documented manual bootstrap process for the Connect credentials, so that the one secret the operator cannot self-manage is applied securely.

#### Acceptance Criteria

1. THE Connect_Credentials_Secret SHALL be created manually via `kubectl` in the `1password` namespace before the Connect_Server starts
2. THE Connect_Credentials_Secret SHALL contain the `1password-credentials.json` file as a data key
3. THE Connect_Token_Secret SHALL be created manually via `kubectl` in the `1password` namespace containing the access token
4. THE ArgoCD_Application SHALL ignore the Connect_Credentials_Secret and Connect_Token_Secret during prune operations so that manually-created secrets are not deleted by ArgoCD sync

### Requirement 6: OnePasswordItem Custom Resource for Planka

**User Story:** As a cluster operator, I want the Planka secret replaced with a OnePasswordItem reference, so that Planka credentials are sourced from 1Password instead of stored in Git.

#### Acceptance Criteria

1. THE OnePasswordItem SHALL be created in the `planka` namespace referencing the corresponding Vault_Item
2. WHEN the Operator processes the OnePasswordItem, THE Operator SHALL create a Kubernetes Secret named `planka-secret` in the `planka` namespace
3. THE generated Secret SHALL contain the same keys as the original plain-text Secret: `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, and `SECRET_KEY`
4. WHEN the Vault_Item is updated in 1Password, THE Operator SHALL update the Kubernetes Secret within its polling interval
5. THE plain-text `secret.yaml` manifest SHALL be removed from the `workloads/planka/` directory

### Requirement 7: Operator Polling and Sync Behavior

**User Story:** As a cluster operator, I want the Operator to periodically sync secrets from 1Password, so that rotated credentials are propagated to the cluster without manual intervention.

#### Acceptance Criteria

1. THE Operator SHALL poll for Vault_Item changes at a configurable interval (default: 600 seconds)
2. WHEN a Vault_Item field value changes in 1Password, THE Operator SHALL update the corresponding Kubernetes Secret within one polling interval
3. THE Operator SHALL preserve the Secret name and namespace defined in the OnePasswordItem resource
4. IF a referenced Vault_Item does not exist in 1Password, THEN THE Operator SHALL emit a warning event on the OnePasswordItem resource and not create a Secret

### Requirement 8: RBAC and Security

**User Story:** As a cluster operator, I want the Operator and Connect Server running with least-privilege permissions, so that the blast radius of a compromise is minimized.

#### Acceptance Criteria

1. THE Operator SHALL run with a dedicated ServiceAccount in the `1password` namespace
2. THE Operator ServiceAccount SHALL have ClusterRole permissions scoped only to `onepassworditems` and `secrets` resources
3. THE Connect_Server SHALL run with a dedicated ServiceAccount in the `1password` namespace
4. THE Connect_Server containers SHALL run as non-root users
5. THE Operator container SHALL run as a non-root user

