# Running k3s with Mullvad VPN on Fedora Linux

## Problem

Mullvad VPN's kill switch uses nftables rules with a default `drop` policy on input, output, and forward chains. This blocks k3s pod traffic in two ways:

1. **Intra-cluster traffic** — pod-to-pod and pod-to-service communication is blocked because Mullvad doesn't recognize the cluster CIDRs as allowed.
2. **Pod internet traffic** — forwarded packets from pods to the internet go through the physical interface (not `wg0-mullvad`), so Mullvad's forward chain drops them. This cannot be fixed with packet marks alone because routing decisions for forwarded traffic are made before the forward hook.

Symptoms:
- CoreDNS is running but pods get "connection refused" or timeouts on DNS lookups
- Pods can resolve DNS but HTTP requests to external hosts time out
- `nft list ruleset` shows `DROP by policy` entries for pod traffic
- Disabling Mullvad immediately resolves all connectivity issues

## Solution

Two-part fix:

1. **Insert accept rules into Mullvad's own `inet mullvad` table** for the k3s pod CIDR (`10.42.0.0/16`). This allows forwarded pod traffic through Mullvad's firewall. Pod internet traffic will bypass the VPN tunnel and go out the physical interface.

2. **Create a separate `inet excludeK3s` table** that marks intra-cluster traffic with Mullvad's split-tunnel marks (`ct mark 0x00000f41`, `meta mark 0x6d6f6c65`) so it bypasses the tunnel routing.

Reference: [Mullvad split tunneling with Linux (advanced)](https://mullvad.net/en/help/split-tunneling-with-linux-advanced)

**Important**: Pod internet traffic will NOT go through the VPN. If you need pods to be anonymous, this approach won't work — you'd need a more complex setup with network namespaces.

### 1. Install the files

```bash
sudo cp docs/mullvad-k3s-exclude.rules /etc/mullvad-k3s-exclude.rules
sudo cp docs/mullvad-k3s-exclude.service /etc/systemd/system/mullvad-k3s-exclude.service
sudo systemctl daemon-reload
sudo systemctl enable mullvad-k3s-exclude.service
```

### 2. Apply the rules

```bash
sudo systemctl start mullvad-k3s-exclude.service
```

Or manually:

```bash
sudo nft -f /etc/mullvad-k3s-exclude.rules
sudo nft insert rule inet mullvad forward ip saddr 10.42.0.0/16 accept
sudo nft insert rule inet mullvad forward ip daddr 10.42.0.0/16 accept
sudo nft insert rule inet mullvad input ip saddr 10.42.0.0/16 accept
sudo nft insert rule inet mullvad output ip daddr 10.42.0.0/16 accept
```

### 3. Verify

```bash
kubectl run nettest --image=busybox:1.36 --rm -it --restart=Never -- wget -qO /dev/null --timeout=5 http://1.1.1.1
```

### 4. After Mullvad reconnects

Mullvad recreates its `inet mullvad` table on reconnect, wiping the inserted rules. A systemd path unit watches for tunnel changes and re-applies them automatically.

Install the watcher:

```bash
sudo cp docs/mullvad-k3s-watcher.path docs/mullvad-k3s-watcher.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now mullvad-k3s-watcher.path
```

The watcher monitors `/sys/class/net/wg0-mullvad` — when Mullvad recreates the WireGuard interface, it waits 3 seconds for Mullvad to finish writing its nftables rules, then re-inserts ours.

Verify it's running:

```bash
systemctl status mullvad-k3s-watcher.path
```

To test, reconnect Mullvad and check the rules were re-applied:

```bash
mullvad reconnect
sleep 5
sudo nft list chain inet mullvad forward | grep "10.42.0.0/16"
```

If the watcher fails for any reason, re-apply manually:

```bash
sudo systemctl restart mullvad-k3s-exclude.service
```

## Additional Fedora configuration

### systemd-resolved

Fedora uses `systemd-resolved` which listens on `127.0.0.53`. This address is not reachable from inside pods. Configure it to also listen on the host's LAN IP:

```bash
sudo mkdir -p /etc/systemd/resolved.conf.d
echo -e "[Resolve]\nDNSStubListenerExtra=192.168.1.88" | sudo tee /etc/systemd/resolved.conf.d/k3s.conf
sudo systemctl restart systemd-resolved
```

Then point k3s at it:

```bash
echo "nameserver 192.168.1.88" | sudo tee /etc/rancher/k3s/resolv.conf
```

Add `--resolv-conf=/etc/rancher/k3s/resolv.conf` to the k3s server flags via `sudo systemctl edit k3s`:

```ini
[Service]
ExecStart=
ExecStart=/usr/local/bin/k3s server --disable=traefik --resolv-conf=/etc/rancher/k3s/resolv.conf
```

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl restart k3s
```

### firewalld

Add the k3s interfaces and CIDRs to the trusted zone:

```bash
sudo firewall-cmd --add-interface=cni0 --zone=trusted --permanent
sudo firewall-cmd --add-source=10.42.0.0/16 --zone=trusted --permanent
sudo firewall-cmd --add-source=10.43.0.0/16 --zone=trusted --permanent
sudo firewall-cmd --add-masquerade --permanent
sudo firewall-cmd --reload
```

### Argo CD NetworkPolicies

The Argo CD `stable` install manifest includes NetworkPolicies that restrict pod communication. Remove them:

```bash
kubectl delete networkpolicies --all -n argocd
```

## Troubleshooting

### Symptoms of Mullvad rules being wiped

When Mullvad reconnects (or the system reboots and services start in the wrong order), the inserted rules in `inet mullvad` are lost. This causes:

- **Image pull failures** — containerd cannot reach container registries (ghcr.io, docker.io, etc.) because outbound traffic from the host is blocked by Mullvad's output chain. Pods will show `ErrImagePull` or `ImagePullBackOff`.
- **cert-manager ACME failures** — If cert-manager needs to reach step-ca via the service CIDR (`10.43.0.0/16`), the request is dropped. Certificates will stay in `Issuing` state and challenges will time out.
- **Pod-to-service communication breaks** — DNS lookups and service-to-service calls fail with timeouts.

### Quick diagnosis

```bash
# Check if the rules are present in Mullvad's table
sudo nft list chain inet mullvad forward | grep -c "10.42.0.0/16"
# Should return 2 (one for saddr, one for daddr)

sudo nft list chain inet mullvad forward | grep -c "10.43.0.0/16"
# Should return 2

# Check if the excludeK3s table exists
sudo nft list table inet excludeK3s
```

### Quick fix

```bash
sudo systemctl restart mullvad-k3s-exclude.service
```

### After fixing rules — recovering stuck workloads

Once the nftables rules are re-applied:

1. **Stuck image pulls** — Delete the pod to force a re-pull:
   ```bash
   kubectl delete pod -n <namespace> <pod-name>
   ```

2. **Stuck certificate issuance** — Delete the failed CertificateRequest and Order to force cert-manager to retry:
   ```bash
   kubectl delete certificaterequest -n <namespace> --all
   kubectl delete order -n <namespace> --all
   ```
   Or simply delete and recreate the Certificate resource. cert-manager will re-issue automatically.

3. **Verify recovery**:
   ```bash
   kubectl get pods -A | grep -v Running
   kubectl get certificates -A
   ```

### Deploying new workloads checklist

When deploying a new workload that pulls images from external registries:

1. Verify Mullvad rules are active: `sudo nft list chain inet mullvad forward | grep "10.42.0.0/16"`
2. If rules are missing, re-apply: `sudo systemctl restart mullvad-k3s-exclude.service`
3. Optionally pre-pull the image on the node: `sudo k3s crictl pull <image>`
4. Consider setting `imagePullPolicy: IfNotPresent` for images that may be pre-loaded or rarely change
5. After deploying, verify certificates are issued: `kubectl get certificates -n <namespace>`
