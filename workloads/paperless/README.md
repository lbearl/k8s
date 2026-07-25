# Paperless-ngx

Document management with OCR at `https://paperless.home.bearl.me`.

## Prerequisites

1. **1Password item** `paperless-secret` in vault `k8s` with fields:
   - `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`
   - `PAPERLESS_SECRET_KEY` — `openssl rand -hex 32`
   - `PAPERLESS_ADMIN_USER`, `PAPERLESS_ADMIN_PASSWORD` — used only on first startup

2. **CoreDNS entry** for `paperless.home.bearl.me` (configured)

## n8n Integration

### Setup: generate an API token

In Paperless: Settings → API Tokens → Create. Store it in 1Password under `paperless-secret` field `PAPERLESS_API_TOKEN`, then reference it in n8n as a credential.

The in-cluster API base URL is:
```
http://paperless.paperless.svc.cluster.local:8000/api
```

### Uploading a document from n8n

Use an **HTTP Request** node:

| Field | Value |
|---|---|
| Method | `POST` |
| URL | `http://paperless.paperless.svc.cluster.local:8000/api/documents/post_document/` |
| Authentication | Header Auth — `Authorization: Token <your-token>` |
| Body Content Type | `Form-Data/Multipart` |
| Field: `document` | Binary file data (from previous node) |
| Field: `title` _(optional)_ | Document title string |
| Field: `correspondent` _(optional)_ | Correspondent name |
| Field: `tags` _(optional)_ | Comma-separated tag names |

### Common workflow: email attachment → Paperless

Trigger: **Email Read (IMAP)** node watching an inbox  
→ **Loop Over Items** (for each attachment)  
→ **HTTP Request** POST to `post_document/` with `{{ $binary.attachment }}`  
→ **Move/delete** the email

### Querying documents from n8n

```
GET /api/documents/?query=invoice&page=1
GET /api/documents/<id>/download/
GET /api/correspondents/
GET /api/tags/
```

Full API reference: `https://paperless.home.bearl.me/api/` (browsable when logged in).

## Backups

PostgreSQL is backed up daily at 4:00am to the NAS (`/volume1/k8s-backups/paperless-postgres/`). **The `paperless-data` PVC is not backed up.** This PVC contains the original/archived document files — if it is lost, documents are unrecoverable even with a Postgres restore (the DB holds metadata only). Options:
- Keep source documents in a second location (email, scanner software, etc.) so they can be re-ingested
- Add a PVC snapshot or rsync job to the NAS if losing ingested originals is unacceptable

To trigger a manual backup:
```bash
kubectl create job --from=cronjob/paperless-postgres-backup paperless-postgres-backup-manual -n paperless
kubectl logs -f job/paperless-postgres-backup-manual -n paperless
```
