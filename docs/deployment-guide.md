# Deployment Guide

This guide walks through deploying the full stack from scratch on a fresh machine running k3s.

## Prerequisites

- A Linux host (tested on Fedora)
- `kubectl` and `argocd` CLI installed
- A domain you control (this repo uses `*.home.bearl.me`)

## 1. Install k3s

```bash
curl -sfL https://get.k3s.io | INSTALL_K3S_EXEC="--disable=traefik" sh -
```

Traefik is disabled because we deploy ingress-nginx via Argo CD instead.

Set up kubeconfig for non-root access:

```bash
mkdir -p ~/.kube
sudo cp /etc/rancher/k3s/k3s.yaml ~/.kube/config
sudo chown $(id -u):$(id -g) ~/.kube/config
chmod 600 ~/.kube/config
echo 'export KUBECONFIG=~/.kube/config' >> ~/.bashrc
export KUBECONFIG=~/.kube/config
```

### Fedora-specific: systemd-resolved

Pods can't reach `127.0.0.53` (the default stub resolver). Expose it on the host's LAN IP:

```bash
HOST_IP=$(hostname -I | awk '{print $1}')
sudo mkdir -p /etc/systemd/resolved.conf.d
echo -e "[Resolve]\nDNSStubListenerExtra=${HOST_IP}" | sudo tee /etc/systemd/resolved.conf.d/k3s.conf
sudo systemctl restart systemd-resolved
```

Point k3s at it:

```bash
echo "nameserver ${HOST_IP}" | sudo tee /etc/rancher/k3s/resolv.conf
sudo systemctl edit k3s
```

In the editor:

```ini
[Service]
ExecStart=
ExecStart=/usr/local/bin/k3s server --disable=traefik --resolv-conf=/etc/rancher/k3s/resolv.conf
```

```bash
sudo systemctl daemon-reload
sudo systemctl restart k3s
```

### Fedora-specific: firewalld

```bash
sudo firewall-cmd --add-interface=cni0 --zone=trusted --permanent
sudo firewall-cmd --add-source=10.42.0.0/16 --zone=trusted --permanent
sudo firewall-cmd --add-source=10.43.0.0/16 --zone=trusted --permanent
sudo firewall-cmd --add-masquerade --permanent
sudo firewall-cmd --reload
```

### Optional: Mullvad VPN coexistence

See [docs/mullvad-k3s-setup.md](mullvad-k3s-setup.md).

## 2. Install Argo CD

```bash
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml --server-side
kubectl wait --for=condition=Ready pods --all -n argocd --timeout=300s
```

## 3. Deploy Gitea

```bash
kubectl apply -f workloads/gitea/namespace.yaml
kubectl apply -f workloads/gitea/
kubectl wait --for=condition=Ready pod -l app=gitea -n gitea --timeout=120s
```

Access Gitea to create the initial admin user and repository:

```bash
kubectl port-forward svc/gitea-http -n gitea 3000:3000
```

Open http://localhost:3000 and:
1. Create an admin account
2. Create an organization called `infra`
3. Create a repository called `k8s` under that org

## 4. Push this repo to Gitea

```bash
git remote add origin http://localhost:3000/infra/k8s.git
git push -u origin main
```

(Stop the port-forward after pushing.)

## 5. Deploy Step CA

```bash
kubectl apply -f workloads/step-ca/step-ca.yaml
kubectl wait --for=condition=Ready pod -l app=step-ca -n step-ca --timeout=120s
```

## 6. Register Gitea in Argo CD and bootstrap

```bash
ARGOCD_PASS=$(kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d)
kubectl port-forward svc/argocd-server -n argocd 8080:443 &

argocd login localhost:8080 --username admin --password "$ARGOCD_PASS" --insecure

argocd repo add http://gitea-http.gitea.svc.cluster.local:3000/infra/k8s.git \
  --username <gitea-user> --password <gitea-pass>

kubectl apply -f argocd/root-app.yaml
```

Argo CD will now deploy all child apps: ingress-nginx, cert-manager, CoreDNS custom config, the Argo CD ingress, and the cluster issuer.

Wait for ingress-nginx and cert-manager to come up:

```bash
kubectl wait --for=condition=Ready pods --all -n ingress-nginx --timeout=300s
kubectl wait --for=condition=Ready pods --all -n cert-manager --timeout=300s
```

## 7. Rotate the Argo CD admin password

The initial admin password is auto-generated and stored in a Kubernetes secret. Change it immediately:

```bash
argocd account update-password \
  --current-password "$ARGOCD_PASS" \
  --new-password '<your-new-password>'
```

Then delete the initial secret (it's no longer needed and Argo CD will not regenerate it):

```bash
kubectl delete secret argocd-initial-admin-secret -n argocd
```

You can stop the port-forward to `argocd-server` now. Once the Argo CD ingress and TLS are working (after steps below), access it at `https://argocd.home.bearl.me` instead.

## 8. Configure the ClusterIssuer

The ClusterIssuer needs the Step CA root certificate. Update it:

```bash
CA_BUNDLE=$(kubectl exec -n step-ca deploy/step-ca -- cat /home/step/certs/root_ca.crt | base64 -w0)
sed -i "s|caBundle:.*|caBundle: ${CA_BUNDLE}|" workloads/cluster-issuer/cluster-issuer.yaml
kubectl apply -f workloads/cluster-issuer/cluster-issuer.yaml
```

Verify it registered:

```bash
kubectl get clusterissuer step-ca-issuer -o jsonpath='{.status.conditions[0].message}'
# Should print: The ACME account was registered with the ACME server
```

## 9. Configure in-cluster DNS

Update the CoreDNS custom config with the ingress-nginx ClusterIP so pods can resolve `*.home.bearl.me`:

```bash
INGRESS_IP=$(kubectl get svc ingress-nginx-controller -n ingress-nginx -o jsonpath='{.spec.clusterIP}')
```

Edit `workloads/coredns-custom/configmap.yaml` and replace the IP in the `hosts` block with the value of `$INGRESS_IP`. Add entries for each hostname:

```
10.43.x.x gitea.home.bearl.me
10.43.x.x argocd.home.bearl.me
10.43.x.x step-ca.home.bearl.me
```

Apply and restart CoreDNS:

```bash
kubectl apply -f workloads/coredns-custom/configmap.yaml
kubectl rollout restart deployment coredns -n kube-system
```

## 10. Commit and push

```bash
git add -A
git commit -m "Configure ClusterIssuer and CoreDNS for this environment"
git push
```

## 11. Host DNS and CA trust

Point `*.home.bearl.me` at the ingress LoadBalancer IP on your host (and any other machines on your network):

```bash
EXTERNAL_IP=$(kubectl get svc ingress-nginx-controller -n ingress-nginx -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
echo "${EXTERNAL_IP}  gitea.home.bearl.me argocd.home.bearl.me step-ca.home.bearl.me" | sudo tee -a /etc/hosts
```

Trust the Step CA root certificate:

```bash
kubectl cp step-ca/$(kubectl get pod -n step-ca -l app=step-ca -o jsonpath='{.items[0].metadata.name}'):/home/step/certs/root_ca.crt ./root_ca.crt

# Fedora/RHEL:
sudo cp root_ca.crt /etc/pki/ca-trust/source/anchors/step-ca-root.crt
sudo update-ca-trust

# Debian/Ubuntu:
# sudo cp root_ca.crt /usr/local/share/ca-certificates/step-ca-root.crt
# sudo update-ca-certificates
```

Firefox uses its own certificate store — import `root_ca.crt` via Settings → Privacy & Security → Certificates → View Certificates → Import.

## 12. Verify

- https://gitea.home.bearl.me — Gitea with valid TLS
- https://argocd.home.bearl.me — Argo CD with valid TLS
- `kubectl get certificates --all-namespaces` — all should show `READY: True`
- `kubectl get applications -n argocd` — all should show `Synced` / `Healthy`

## Architecture

```
argocd/
├── root-app.yaml                 # Bootstrap: apply once, manages everything below
└── apps/
    ├── ingress-nginx.yaml        # Helm chart (LoadBalancer)
    ├── cert-manager.yaml         # Helm chart
    ├── gitea.yaml                # → workloads/gitea/
    ├── step-ca.yaml              # → workloads/step-ca/
    ├── argocd-ingress.yaml       # → workloads/argocd-ingress/
    ├── cluster-issuer.yaml       # → workloads/cluster-issuer/
    └── coredns-custom.yaml       # → workloads/coredns-custom/
workloads/
├── gitea/                        # gitea.home.bearl.me
├── step-ca/                      # Internal ACME CA
├── argocd-ingress/               # argocd.home.bearl.me
├── cluster-issuer/               # Connects cert-manager → Step CA
└── coredns-custom/               # In-cluster *.home.bearl.me DNS
```

All changes after initial bootstrap go through git → push to Gitea → Argo CD auto-syncs.

## Adding a new service

1. Create manifests in `workloads/<service-name>/`
2. Include an Ingress with the annotation `cert-manager.io/cluster-issuer: step-ca-issuer`
3. Add a child Application in `argocd/apps/<service-name>.yaml`
4. Add the hostname to `workloads/coredns-custom/configmap.yaml`
5. Add the hostname to `/etc/hosts` on your machine
6. Commit and push — Argo CD handles the rest

## Backups

Automated backups run as Kubernetes CronJobs and write to a Synology NAS (`192.168.1.246:/volume1/k8s-backups`) via NFS.

### What's backed up

| Data | Schedule | Retention | NAS path |
|---|---|---|---|
| Gitea (repos, DB, config) | Daily at 3am | 30 days | `/volume1/k8s-backups/gitea/` |
| Step CA (keys, certs, config) | Weekly Sunday 3am | 90 days | `/volume1/k8s-backups/step-ca/<timestamp>/` |

Argo CD and other services are stateless — their state is in git (this repo) and Kubernetes CRDs, both of which are reconstructed from the repo on redeploy.

### Prerequisites

Enable NFS on the Synology:
1. DSM → Control Panel → File Services → NFS → Enable NFS
2. Create shared folder `k8s-backups`
3. NFS Permissions: allow `192.168.1.0/24`, squash all users to admin

Install NFS client on the k3s server node:

```bash
# Fedora
sudo dnf install nfs-utils

# Ubuntu
sudo apt install nfs-common
```

### Manual backup

Trigger a backup immediately:

```bash
# Gitea
kubectl create job --from=cronjob/gitea-backup gitea-backup-manual -n gitea
kubectl logs -f job/gitea-backup-manual -n gitea

# Step CA
kubectl create job --from=cronjob/step-ca-backup step-ca-backup-manual -n step-ca
kubectl logs -f job/step-ca-backup-manual -n step-ca
```

### Manual backup (Step CA — from local machine)

The `scripts/backup-step-ca.sh` script extracts Step CA keys and config from the running pod to a local directory. Use this for an initial backup or before major changes:

```bash
./scripts/backup-step-ca.sh
```

Output goes to `backups/step-ca/<timestamp>/` (git-ignored). Store the `secrets/` subdirectory somewhere secure (encrypted USB, password manager).

### Restoring Gitea

```bash
# Scale down Gitea
kubectl scale deployment gitea -n gitea --replicas=0

# Copy the backup from the NAS and extract
# (adjust the filename to the backup you want to restore)
scp nas:/volume1/k8s-backups/gitea/gitea-backup-XXXXXXXX-XXXXXX.tar.gz .
tar xzf gitea-backup-*.tar.gz

# Restore the database and repos into the PVC
# (details depend on what's in the dump — see Gitea docs)
kubectl scale deployment gitea -n gitea --replicas=1
```

### Restoring Step CA

Use the restore script to recreate Kubernetes Secrets from a backup:

```bash
./scripts/restore-step-ca.sh backups/step-ca/<timestamp>
# Or from the NAS copy:
./scripts/restore-step-ca.sh /mnt/nas-backup/step-ca/<timestamp>

kubectl rollout restart deployment step-ca -n step-ca
```

### Disaster recovery (full cluster rebuild)

1. Install k3s (step 1 of this guide)
2. Install Argo CD (step 2)
3. Restore Step CA secrets: `./scripts/restore-step-ca.sh <backup-dir>`
4. Deploy Gitea, restore from NAS backup
5. Push this repo to Gitea
6. Register repo in Argo CD and apply root app (step 6)
7. Complete steps 7–12

## Environment-specific values

These values are specific to each deployment and must be updated:

| Value | Location | How to get it |
|---|---|---|
| Step CA root cert (caBundle) | `workloads/cluster-issuer/cluster-issuer.yaml` | `kubectl exec -n step-ca deploy/step-ca -- cat /home/step/certs/root_ca.crt \| base64 -w0` |
| Ingress ClusterIP | `workloads/coredns-custom/configmap.yaml` | `kubectl get svc ingress-nginx-controller -n ingress-nginx -o jsonpath='{.spec.clusterIP}'` |
| Host LAN IP | `/etc/hosts`, systemd-resolved config | `hostname -I \| awk '{print $1}'` |
| NAS IP | `workloads/backups/gitea-backup.yaml`, `step-ca-backup.yaml` | NFS server address for backup storage |

## Adding worker nodes

k3s supports mixed-architecture clusters. You can add amd64 and arm64 nodes to the same cluster — container images just need to be multi-arch (most popular images are). The kubelet on each node pulls the correct architecture variant automatically.

### Get the join token

On the server node:

```bash
sudo cat /var/lib/rancher/k3s/server/node-token
```

### Join a Fedora node

```bash
# Install k3s agent
curl -sfL https://get.k3s.io | K3S_URL=https://<server-ip>:6443 K3S_TOKEN=<token> sh -
```

Configure firewalld to allow cluster traffic:

```bash
sudo firewall-cmd --add-interface=cni0 --zone=trusted --permanent
sudo firewall-cmd --add-source=10.42.0.0/16 --zone=trusted --permanent
sudo firewall-cmd --add-source=10.43.0.0/16 --zone=trusted --permanent
sudo firewall-cmd --add-masquerade --permanent
sudo firewall-cmd --reload
```

If the node runs systemd-resolved, expose the stub listener on its LAN IP so local pods can resolve DNS:

```bash
NODE_IP=$(hostname -I | awk '{print $1}')
sudo mkdir -p /etc/systemd/resolved.conf.d
echo -e "[Resolve]\nDNSStubListenerExtra=${NODE_IP}" | sudo tee /etc/systemd/resolved.conf.d/k3s.conf
sudo systemctl restart systemd-resolved
```

If the node runs Mullvad VPN, apply the nftables exclusion rules (see [mullvad-k3s-setup.md](mullvad-k3s-setup.md)).

### Join an Ubuntu/Debian node (including Raspberry Pi)

```bash
# Install k3s agent
curl -sfL https://get.k3s.io | K3S_URL=https://<server-ip>:6443 K3S_TOKEN=<token> sh -
```

Ubuntu uses `ufw` instead of firewalld. Allow cluster traffic:

```bash
sudo ufw allow from 10.42.0.0/16
sudo ufw allow from 10.43.0.0/16
sudo ufw allow 6443/tcp    # k3s API server
sudo ufw allow 8472/udp    # flannel VXLAN
sudo ufw allow 10250/tcp   # kubelet metrics
sudo ufw allow 51820/udp   # flannel WireGuard (if using WireGuard backend)
```

If the node runs systemd-resolved (Ubuntu 18.04+), apply the same stub listener fix as Fedora above.

### Raspberry Pi notes

- Use a 64-bit OS (Ubuntu Server 24.04 arm64 or Raspberry Pi OS 64-bit). k3s does not support 32-bit.
- Ensure cgroups are enabled. For Raspberry Pi OS, add to `/boot/firmware/cmdline.txt`:
  ```
  cgroup_memory=1 cgroup_enable=memory
  ```
  Then reboot.
- If an image is amd64-only, the pod will fail on arm64 nodes with an exec format error. Pin it to amd64 nodes with a nodeSelector:
  ```yaml
  nodeSelector:
    kubernetes.io/arch: amd64
  ```

### Verify the node joined

From the server:

```bash
kubectl get nodes -o wide
```

You should see the new node with `Ready` status and its architecture listed under `ARCH`.
