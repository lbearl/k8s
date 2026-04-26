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

Mullvad recreates its `inet mullvad` table on reconnect, wiping the inserted rules. Re-apply with:

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
