# 1Password Connect Server — Bootstrap Guide

## Prerequisites

- A 1Password account with a vault named **Kubernetes**
- `kubectl` configured to access the k3s cluster
- The `1password` namespace exists (ArgoCD creates it, or create manually with `kubectl create namespace 1password`)

## 1. Create the Connect Server in 1Password

1. Log in to the [1Password web UI](https://my.1password.com)
2. Go to **Integrations** → **Directory** → search for **Secrets Automation**
3. Choose **1Password Connect Server** and click **Set Up**
4. Name the server (e.g. `k3s-homelab`) and grant it access to the **Kubernetes** vault
5. Download the **1password-credentials.json** file — store it securely, you cannot download it again
6. Create an **Access Token** for the Connect Server and copy it

## 2. Create Bootstrap Secrets

Both secrets need the `IgnoreExtraneous` annotation so ArgoCD does not prune them during sync (they exist in the cluster but not in Git).

Create the namespace first (ArgoCD will adopt it later):

```bash
kubectl create namespace 1password
```

### op-credentials

```bash
kubectl create secret generic op-credentials \
  --namespace 1password \
  --from-file=1password-credentials.json \
  --dry-run=client -o yaml | \
  kubectl annotate -f - --local \
    argocd.argoproj.io/compare-options=IgnoreExtraneous \
    -o yaml | kubectl apply -f -
```

### onepassword-token

```bash
kubectl create secret generic onepassword-token \
  --namespace 1password \
  --from-literal=token=<your-access-token> \
  --dry-run=client -o yaml | \
  kubectl annotate -f - --local \
    argocd.argoproj.io/compare-options=IgnoreExtraneous \
    -o yaml | kubectl apply -f -
```

Replace `<your-access-token>` with the token copied in step 1.6.

## 3. Deployment Order

1. **Namespace** — created by ArgoCD (`CreateNamespace=true`) or manually
2. **Bootstrap secrets** — apply `op-credentials` and `onepassword-token` manually (above)
3. **ArgoCD syncs** the `1password` Application — deploys Connect Server, Operator, RBAC
4. **Connect Server starts** — authenticates with 1Password.com using the credentials file
5. **Operator starts** — connects to the Connect Server at `onepassword-connect.1password.svc.cluster.local:8080`
6. **OnePasswordItems resolve** — the Operator watches CRs in all namespaces and creates/updates Secrets

## 4. Vault Item Setup (Planka)

Create an item in the **Kubernetes** vault:

- **Item name:** `planka-secret`
- **Fields:**
  - `POSTGRES_DB` — database name (e.g. `planka`)
  - `POSTGRES_USER` — database user (e.g. `planka`)
  - `POSTGRES_PASSWORD` — database password
  - `SECRET_KEY` — Planka session secret (random string, 64+ chars)

The Operator resolves `vaults/Kubernetes/items/planka-secret` and creates a Kubernetes Secret named `planka-secret` in the `planka` namespace with these fields.

## Troubleshooting

| Symptom | Check |
|---------|-------|
| Connect Server in CrashLoopBackOff | `kubectl describe pod -n 1password` — likely missing `op-credentials` secret |
| Operator logs "connection refused" | Connect Server not ready yet — wait or check its logs |
| OnePasswordItem not producing a Secret | `kubectl describe onepassworditem -n planka` — look for Warning events |
| Secret fields empty | Verify the 1Password item field names match exactly (case-sensitive) |
