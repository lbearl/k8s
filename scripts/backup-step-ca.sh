#!/bin/bash
# Backup Step CA keys, certs, and config from the running pod.
# Run this from the repo root. Outputs to backups/step-ca/<timestamp>/
#
# Usage: ./scripts/backup-step-ca.sh

set -euo pipefail

TIMESTAMP=$(date +%Y%m%d-%H%M%S)
BACKUP_DIR="backups/step-ca/${TIMESTAMP}"
POD=$(kubectl get pod -n step-ca -l app=step-ca -o jsonpath='{.items[0].metadata.name}')

echo "Backing up Step CA from pod ${POD}..."
mkdir -p "${BACKUP_DIR}/certs" "${BACKUP_DIR}/secrets" "${BACKUP_DIR}/config"

kubectl cp "step-ca/${POD}:/home/step/certs/root_ca.crt" "${BACKUP_DIR}/certs/root_ca.crt"
kubectl cp "step-ca/${POD}:/home/step/certs/intermediate_ca.crt" "${BACKUP_DIR}/certs/intermediate_ca.crt"
kubectl cp "step-ca/${POD}:/home/step/secrets/root_ca_key" "${BACKUP_DIR}/secrets/root_ca_key"
kubectl cp "step-ca/${POD}:/home/step/secrets/intermediate_ca_key" "${BACKUP_DIR}/secrets/intermediate_ca_key"
kubectl cp "step-ca/${POD}:/home/step/secrets/password" "${BACKUP_DIR}/secrets/password"
kubectl cp "step-ca/${POD}:/home/step/config/ca.json" "${BACKUP_DIR}/config/ca.json"
kubectl cp "step-ca/${POD}:/home/step/config/defaults.json" "${BACKUP_DIR}/config/defaults.json"

chmod 600 "${BACKUP_DIR}/secrets/"*

echo ""
echo "Backup complete: ${BACKUP_DIR}"
echo ""
echo "Files:"
find "${BACKUP_DIR}" -type f
echo ""
echo "IMPORTANT: Move the secrets/ directory to a secure location (encrypted USB, password manager, etc.)"
echo "           Do NOT commit it to git."
