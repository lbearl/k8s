# Backups

CronJobs deployed to their respective namespaces using direct NFS mounts to the Synology NAS at 192.168.1.246:/volume1/k8s-backups.

| Job | Namespace | Schedule | Retention |
|-----|-----------|----------|-----------|
| gitea-backup | gitea | Daily 3:00am | 30 days |
| step-ca-backup | step-ca | Weekly Sun 3:00am | 90 days |
| n8n-postgres-backup | n8n | Daily 3:30am | 30 days |
| planka-postgres-backup | planka | Daily 3:30am | 30 days |
| paperless-postgres-backup | paperless | Daily 4:00am | 30 days |
| workout-tracker-postgres-backup | workout-tracker | Daily 3:45am | 30 days |

n8n workflows are backed up separately via an n8n workflow that commits to the `infra/n8n-backups` Gitea repo daily at 4:00am.
