# k8s

Homelab Kubernetes cluster running on k3s. Managed via GitOps with Argo CD.

## What's running

| Service | URL | Description |
|---|---|---|
| Gitea | https://gitea.home.bearl.me | Git server (hosts this repo) |
| Argo CD | https://argocd.home.bearl.me | GitOps continuous delivery |
| Step CA | https://step-ca.home.bearl.me | Internal ACME certificate authority |
| ingress-nginx | — | Ingress controller (LoadBalancer) |
| cert-manager | — | Automatic TLS certificate provisioning |

## Repo structure

```
argocd/
├── root-app.yaml           # Bootstrap app — manages all child apps
└── apps/                   # One Application manifest per service
workloads/                  # Kubernetes manifests for each service
scripts/                    # Backup and restore scripts
docs/                       # Guides and reference
```

## Quick start

See the [Deployment Guide](docs/deployment-guide.md) for full setup instructions.

## Documentation

- [Deployment Guide](docs/deployment-guide.md) — Full setup from bare metal to working cluster
- [Mullvad + k3s Setup](docs/mullvad-k3s-setup.md) — Running k3s alongside Mullvad VPN on Fedora
