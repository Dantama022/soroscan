# Operations Runbooks

Operational procedures for running SoroScan in production. Each guide includes
the checks and commands needed to verify a successful outcome.

| Runbook | Use when |
|---------|----------|
| [Contract pause and suspension](./contract_pause.md) | An incident, contract upgrade, or maintenance window requires pausing ingestion. |
| [Data retention and event archival](./DATA_RETENTION.md) | Events must be archived to S3, pruned, or restored from an archived batch. |
| [Disaster recovery and restore drill](../deployment/playbooks/disaster-recovery-restore-drill.md) | Restoring PostgreSQL or the contract registry, or running the scheduled restore drill. |

Alert-driven incident playbooks live in
[`docs/deployment/playbooks/`](../deployment/playbooks/README.md). Deployment,
monitoring, and backup guidance lives in
[`docs/deployment/`](../deployment/README.md).
