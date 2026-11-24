# Incident Response Playbooks

Machine-readable alert → action mappings live in
`django-backend/soroscan/ingest/services/incident_playbooks.py`.

| Alert | Prometheus rule | Automated actions | Playbook |
|-------|-----------------|-------------------|----------|
| Event ingestion lag | `SoroScanEventIngestionLag` | send_alert, pause_contract | [event-ingestion-lag.md](./event-ingestion-lag.md) |
| Webhook delivery failure burst | `SoroScanWebhookFailureBurst` | send_alert, disable_webhooks | [webhook-delivery-failure-burst.md](./webhook-delivery-failure-burst.md) |
| DB connection pool exhausted | `SoroScanDbPoolExhausted` | send_alert | [database-connection-pool-exhausted.md](./database-connection-pool-exhausted.md) |
| RPC endpoint unavailable | `SoroScanRpcEndpointUnavailable` | send_alert, pause_contract | [rpc-endpoint-unavailable.md](./rpc-endpoint-unavailable.md) |
| Celery queue backlog | `SoroScanCeleryQueueBacklog` | send_alert | [celery-queue-backlog.md](./celery-queue-backlog.md) |

## Operational runbooks

These are exercised on a schedule rather than triggered by a single alert:

| Procedure | Cadence | Runbook |
|-----------|---------|---------|
| Disaster recovery and restore drill | Quarterly drill, monthly verification | [disaster-recovery-restore-drill.md](./disaster-recovery-restore-drill.md) |

Remediation rules are evaluated every 5 minutes by
`evaluate_remediation_rules`. Seed defaults with:

```bash
python manage.py seed_incident_playbooks
```
