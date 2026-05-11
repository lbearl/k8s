# Implementation Plan: Planka Deployment

## Overview

Create Kubernetes manifests and an ArgoCD Application to deploy Planka with a PostgreSQL backend on the existing k3s cluster. Each task produces one or more YAML files following the established conventions (mirroring the Gitea workload structure). Tasks are ordered so that foundational resources (namespace, secret) come first, then the database layer, then the application layer, and finally networking.

## Tasks

- [x] 1. Create the ArgoCD Application manifest
  - Create `argocd/apps/planka.yaml` defining an ArgoCD Application named `planka`
  - Source: `http://gitea-http.gitea.svc.cluster.local:3000/infra/k8s.git`, branch `main`, path `workloads/planka`
  - Destination: `https://kubernetes.default.svc`, namespace `planka`
  - Enable automated sync with selfHeal and prune
  - Include `CreateNamespace=true` sync option and `resources-finalizer.argocd.argoproj.io` finalizer
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

- [x] 2. Create namespace and secret manifests
  - [x] 2.1 Create `workloads/planka/namespace.yaml`
    - Define a Namespace resource named `planka`
    - _Requirements: 2.1_
  - [x] 2.2 Create `workloads/planka/secret.yaml`
    - Define a Secret named `planka-secret` in namespace `planka`
    - Include placeholder keys: `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `SECRET_KEY`
    - Add a comment noting that values must be replaced before first sync
    - _Requirements: 7.1, 7.2, 7.3_

- [x] 3. Create PostgreSQL storage and deployment
  - [x] 3.1 Create `workloads/planka/postgres-pvc.yaml`
    - Define a PVC named `planka-postgres-data` in namespace `planka`
    - 2Gi capacity, ReadWriteOnce access mode
    - _Requirements: 3.2, 8.1_
  - [x] 3.2 Create `workloads/planka/postgres-deployment.yaml`
    - Define a Deployment named `planka-postgres` in namespace `planka`
    - Use `postgres:16` image, single replica, Recreate strategy
    - Mount `planka-postgres-data` PVC at `/var/lib/postgresql/data`
    - Read `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` from `planka-secret`
    - Define resource requests for CPU and memory
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

- [x] 4. Checkpoint - Verify foundational manifests
  - Ensure all YAML files created so far are valid. Ask the user if questions arise.

- [x] 5. Create Planka application storage and deployment
  - [x] 5.1 Create `workloads/planka/pvc.yaml`
    - Define a PVC named `planka-uploads` in namespace `planka`
    - 2Gi capacity, ReadWriteOnce access mode
    - _Requirements: 4.7, 8.2_
  - [x] 5.2 Create `workloads/planka/deployment.yaml`
    - Define a Deployment named `planka` in namespace `planka`
    - Use `ghcr.io/plankanban/planka` image, single replica, Recreate strategy
    - Set `BASE_URL` to `https://planka.home.bearl.me`
    - Construct `DATABASE_URL` from secret values: `postgresql://$(POSTGRES_USER):$(POSTGRES_PASSWORD)@planka-postgres:5432/$(POSTGRES_DB)`
    - Read `SECRET_KEY` from `planka-secret`
    - Mount `planka-uploads` PVC with subPaths for `/app/public/user-avatars` and `/app/private/attachments`
    - Define resource requests for CPU and memory
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7_

- [x] 6. Create Service and Ingress
  - [x] 6.1 Create `workloads/planka/service.yaml`
    - Define a ClusterIP Service named `planka` in namespace `planka`
    - Route traffic to pods with label `app: planka` on port 1337
    - _Requirements: 5.1, 5.2, 5.3_
  - [x] 6.2 Create `workloads/planka/ingress.yaml`
    - Define an Ingress named `planka` in namespace `planka`
    - Use `nginx` ingress class
    - Annotate with `cert-manager.io/cluster-issuer: step-ca-issuer`
    - TLS for host `planka.home.bearl.me` stored in secret `planka-tls`
    - Route path `/` (Prefix) to service `planka` on port 1337
    - _Requirements: 6.1, 6.2, 6.3, 6.4_

- [x] 7. Final checkpoint - Validate all manifests
  - Ensure all YAML manifests are syntactically valid and consistent. Ask the user if questions arise.

## Notes

- All manifests are declarative YAML — no application code or property-based tests apply.
- The Secret contains placeholder values that must be replaced with real credentials before the first ArgoCD sync.
- The file structure mirrors the existing Gitea workload for consistency.
- Each task references specific acceptance criteria from the requirements document for traceability.
