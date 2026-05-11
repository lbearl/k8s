# Tasks

## Task 1: Create namespace and service accounts

- [x] 1.1 Create `workloads/1password/namespace.yaml` with Namespace `1password`
- [x] 1.2 Create `workloads/1password/connect-serviceaccount.yaml` with ServiceAccount `onepassword-connect` in namespace `1password`
- [x] 1.3 Create `workloads/1password/operator-serviceaccount.yaml` with ServiceAccount `onepassword-operator` in namespace `1password`

## Task 2: Create RBAC resources

- [x] 2.1 Create `workloads/1password/clusterrole.yaml` with ClusterRole `onepassword-operator` granting permissions on `onepassworditems`, `secrets`, `events`, and `deployments`
- [x] 2.2 Create `workloads/1password/clusterrolebinding.yaml` binding ClusterRole `onepassword-operator` to ServiceAccount `onepassword-operator` in namespace `1password`

## Task 3: Create Connect Server deployment and service

- [x] 3.1 Create `workloads/1password/connect-deployment.yaml` with Deployment `onepassword-connect` containing `connect-api` and `connect-sync` containers, shared emptyDir volume, credentials mount, token env var, bus peer configuration, security context (runAsUser: 999, runAsNonRoot: true), and resource requests
- [x] 3.2 Create `workloads/1password/connect-service.yaml` with ClusterIP Service `onepassword-connect` on port 8080

## Task 4: Create Operator deployment

- [x] 4.1 Create `workloads/1password/operator-deployment.yaml` with Deployment `onepassword-operator` using image `1password/onepassword-operator:1.8.0`, env vars for `OP_CONNECT_HOST`, `POLLING_INTERVAL`, `OP_CONNECT_TOKEN` (from secret), leader-elect args, security context (runAsNonRoot: true), and resource requests

## Task 5: Create ArgoCD Application

- [x] 5.1 Create `argocd/apps/1password.yaml` with Application targeting `workloads/1password`, automated sync with selfHeal and prune, CreateNamespace=true sync option, resources-finalizer, and ignoreDifferences for bootstrap secrets

## Task 6: Create OnePasswordItem for Planka and remove plain-text secret

- [x] 6.1 Create `workloads/planka/onepassworditem.yaml` with OnePasswordItem `planka-secret` in namespace `planka` referencing the vault item path
- [x] 6.2 Remove `workloads/planka/secret.yaml` (plain-text secret replaced by operator-managed secret)

## Task 7: Create bootstrap documentation

- [x] 7.1 Create `workloads/1password/README.md` documenting the bootstrap process: creating the 1Password Connect Server in the 1Password web UI, saving the credentials file, creating the `op-credentials` and `onepassword-token` secrets with the `IgnoreExtraneous` annotation, and the expected deployment order
