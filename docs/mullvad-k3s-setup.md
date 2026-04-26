# Running k3s with Mullvad VPN on Fedora Linux

## Problem

Mullvad VPN's kill switch uses nftables rules with a default `drop` policy on input, output, and forward chains. This blocks all k3s pod-to-pod and pod-to-service traffic, including DNS (CoreDNS on UDP/53), because the cluster network CIDRs (`10.42.0.0/16` for pods, `10.43.0.0/16` for services) are not recognized by Mullvad as allowed traffic.

Symptoms:
- CoreDNS is running but pods get "connection refused" or timeouts on DNS lookups
- TCP connections between pods may partially work while UDP is blocked
- `nft list ruleset` shows `DROP by policy` entries for pod traffic
- Disabling Mullvad immediately resolves all connectivity issues

## Solution

Mark k3s cluster traffic with Mullvad's split-tunneling connection tracking mark (`0x00000f41`) and meta mark (`0x6d6f6c65`) so it bypasses the VPN tunnel and firewall rules.

Reference: [Mullvad split tunneling with Linux (advanced)](https://mullvad.net/en/help/split-tunneling-with-linux-advanced)

### 1. Install the nftables rules

Copy the rules file to a system location:

```bash
sudo cp docs/mullvad-k3s-exclude.rules /etc/mullvad-k3s-exclude.rules
```

The rules file (`docs/mullvad-k3s-exclude.rules`) defines three chains:

- **excludeOutgoing** — marks host-originated traffic destined for pod/service CIDRs to bypass the tunnel
- **allowIncoming** — marks traffic from pod/service CIDRs so Mullvad's input chain doesn't drop it
- **allowForward** — marks forwarded traffic (pod-to-pod, pod-to-service) to pass through

### 2. Load the rules

```bash
sudo nft -f /etc/mullvad-k3s-exclude.rules
```

Verify they're loaded:

```bash
sudo nft list table inet excludeK3s
```

To remove them:

```bash
sudo nft delete table inet excludeK3s
```

### 3. Make it persistent across reboots

Create a systemd service:

```bash
sudo tee /etc/systemd/system/mullvad-k3s-exclude.service << 'EOF'
[Unit]
Description=nftables rules to exclude k3s traffic from Mullvad
Before=k3s.service
After=network-pre.target

[Service]
Type=oneshot
ExecStart=/usr/sbin/nft -f /etc/mullvad-k3s-exclude.rules
ExecStop=/usr/sbin/nft delete table inet excludeK3s
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable mullvad-k3s-exclude.service
```

### 4. Verify

With Mullvad connected:

```bash
# DNS should work from pods
kubectl run dnstest --image=busybox:1.36 --rm -it --restart=Never -- nslookup google.com

# All argocd pods should be healthy
kubectl get pods -n argocd
```

## Additional notes

### Argo CD NetworkPolicies

The Argo CD `stable` install manifest includes NetworkPolicies that can also interfere with pod traffic. If you see connectivity issues within the argocd namespace even after applying the nftables rules, remove them:

```bash
kubectl delete networkpolicies --all -n argocd
```

### systemd-resolved

Fedora uses `systemd-resolved` which listens on `127.0.0.53`. This address is not reachable from inside pods. k3s needs an upstream DNS resolver that pods can reach.

Configure `systemd-resolved` to also listen on the host's LAN IP:

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

Fedora's firewalld may also block pod traffic. Add the k3s interfaces and CIDRs to the trusted zone:

```bash
sudo firewall-cmd --add-interface=cni0 --zone=trusted --permanent
sudo firewall-cmd --add-source=10.42.0.0/16 --zone=trusted --permanent
sudo firewall-cmd --add-source=10.43.0.0/16 --zone=trusted --permanent
sudo firewall-cmd --add-masquerade --permanent
sudo firewall-cmd --reload
```

### Pod internet access

With these rules, pod-to-pod and pod-to-service traffic bypasses the VPN. Traffic from pods to the internet still goes through Mullvad. If pods need to reach external services without the VPN (e.g., pulling container images), add those destinations to the `K3S_NETWORKS` set in the rules file or create additional exclusion rules.
