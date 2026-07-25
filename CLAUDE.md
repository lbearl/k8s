# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

Homelab Kubernetes cluster (k3s) managed via GitOps with Argo CD. All changes to workloads go through git — push to `main` on Gitea, and Argo CD auto-syncs within seconds. No `kubectl apply` needed for day-to-day changes.

## Repo layout

```
argocd/
  root-app.yaml       # Bootstrap: apply once to start everything
  apps/               # One Application manifest per service
workloads/            # Kubernetes manifests, grouped by service
scripts/              # Manual backup/restore for Step CA
workers/              # Cloudflare Workers (email-to-planka)
docs/                 # Setup guides
```

## Adding a new service

1. Create `workloads/<service-name>/` with manifests (namespace, deployment, service, ingress, pvc as needed)
2. Add `argocd/apps/<service-name>.yaml` pointing at that path
3. Add an Ingress with `cert-manager.io/cluster-issuer: step-ca-issuer` for auto-TLS
4. Add the hostname to `workloads/coredns-custom/configmap.yaml` (in-cluster DNS)
5. Add the hostname to `/etc/hosts` on the host machine
6. Commit and push

## Secrets management

Secrets come from 1Password via the 1Password Operator. The pattern:

1. Create a `OnePasswordItem` CR referencing `vaults/k8s/items/<item-name>`
2. The operator creates a Kubernetes Secret with the same name in the same namespace
3. Deployments reference it via `secretKeyRef`

The 1Password bootstrap secrets (`op-credentials`, `onepassword-token`) are applied manually once — they have `argocd.argoproj.io/compare-options=IgnoreExtraneous` so Argo CD never prunes them.

## TLS / certificates

- cert-manager + Step CA (internal ACME CA at `step-ca.home.bearl.me`)
- All Ingresses use `ingressClassName: nginx` and the annotation `cert-manager.io/cluster-issuer: step-ca-issuer`
- The `caBundle` in `workloads/cluster-issuer/cluster-issuer.yaml` is environment-specific (base64 of Step CA root cert)

## Ingress pattern

```yaml
metadata:
  annotations:
    cert-manager.io/cluster-issuer: step-ca-issuer
spec:
  ingressClassName: nginx
  tls:
    - hosts: [example.home.bearl.me]
      secretName: example-tls
```

## Stateful services

Services with databases (n8n, planka) use dedicated postgres Deployments in the same namespace with a ClusterIP service and a PVC. Postgres credentials come from 1Password via OnePasswordItem. Use `strategy: Recreate` for single-replica stateful deployments.

## Backups

CronJobs in `workloads/backups/` write to NAS (`192.168.1.246:/volume1/k8s-backups`) via direct NFS mounts. To trigger manually:

```bash
kubectl create job --from=cronjob/<job-name> <job-name>-manual -n <namespace>
kubectl logs -f job/<job-name>-manual -n <namespace>
```

Step CA can also be backed up from a local machine:

```bash
./scripts/backup-step-ca.sh       # to backups/step-ca/<timestamp>/
./scripts/restore-step-ca.sh <backup-dir>
```

## Environment-specific values

These must be updated per deployment — do not hardcode the values from this repo:

| Value | File |
|---|---|
| Step CA `caBundle` | `workloads/cluster-issuer/cluster-issuer.yaml` |
| CoreDNS ingress ClusterIP | `workloads/coredns-custom/configmap.yaml` |
| NAS IP for backups | `workloads/backups/*.yaml` |

## Useful kubectl commands

```bash
# Check all Argo CD app health
kubectl get applications -n argocd

# Check all TLS certs
kubectl get certificates --all-namespaces

# Force Argo CD to sync immediately
argocd app sync <app-name>

# Watch pod status across all namespaces
kubectl get pods --all-namespaces -w
```
