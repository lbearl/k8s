#!/bin/bash
# Restore Step CA from a backup by creating Kubernetes Secrets.
# The pod will mount these secrets instead of relying solely on the PVC.
#
# Usage: ./scripts/restore-step-ca.sh <backup-dir>
# Example: ./scripts/restore-step-ca.sh backups/step-ca/20260426-113800

set -euo pipefail

BACKUP_DIR="${1:?Usage: $0 <backup-dir>}"

if [ ! -f "${BACKUP_DIR}/secrets/root_ca_key" ]; then
    echo "Error: ${BACKUP_DIR}/secrets/root_ca_key not found"
    exit 1
fi

echo "Restoring Step CA secrets from ${BACKUP_DIR}..."

kubectl create namespace step-ca --dry-run=client -o yaml | kubectl apply -f -

kubectl create secret generic step-ca-certs -n step-ca \
    --from-file=root_ca.crt="${BACKUP_DIR}/certs/root_ca.crt" \
    --from-file=intermediate_ca.crt="${BACKUP_DIR}/certs/intermediate_ca.crt" \
    --dry-run=client -o yaml | kubectl apply -f -

kubectl create secret generic step-ca-keys -n step-ca \
    --from-file=root_ca_key="${BACKUP_DIR}/secrets/root_ca_key" \
    --from-file=intermediate_ca_key="${BACKUP_DIR}/secrets/intermediate_ca_key" \
    --from-file=password="${BACKUP_DIR}/secrets/password" \
    --dry-run=client -o yaml | kubectl apply -f -

kubectl create secret generic step-ca-config -n step-ca \
    --from-file=ca.json="${BACKUP_DIR}/config/ca.json" \
    --from-file=defaults.json="${BACKUP_DIR}/config/defaults.json" \
    --dry-run=client -o yaml | kubectl apply -f -

echo ""
echo "Secrets restored. Restart Step CA to pick them up:"
echo "  kubectl rollout restart deployment step-ca -n step-ca"
