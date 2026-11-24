"""Restore constraints and indexes lost when ingest_contractevent was partitioned.

Migration 0054_contractevent_partitioning rebuilt the table with
``CREATE TABLE ... (LIKE ...) PARTITION BY RANGE (timestamp)``, which copies
defaults and CHECK constraints only. The primary key, the unique dedupe
constraint, both foreign keys and every index were silently dropped, so
re-ingesting an event produced a duplicate row.

PostgreSQL requires every unique/primary key on a partitioned table to
include the partition key, so the restored constraints are:

* primary key        (id, timestamp)
* unique constraint  (contract_id, ledger, event_index, timestamp)

``timestamp`` is the ledger close time, so it is identical for a re-ingested
event and the dedupe guarantee is preserved.

Inbound foreign keys from other tables to ``ingest_contractevent(id)`` cannot be
restored (a partitioned table can only be referenced via a key that includes
the partition key); Django's delete collector enforces them in the ORM.

Postgres-only and idempotent; a no-op on other backends.
"""

from django.db import migrations

FORWARD_SQL = """
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'ingest_contractevent'::regclass AND contype = 'p'
    ) THEN
        ALTER TABLE ingest_contractevent ADD PRIMARY KEY (id, "timestamp");
    END IF;

    -- Remove pre-existing duplicates (keep the lowest id) so the unique
    -- constraint can be created on databases that already ingested twice.
    DELETE FROM ingest_contractevent a
    USING ingest_contractevent b
    WHERE a.contract_id = b.contract_id
      AND a.ledger = b.ledger
      AND a.event_index = b.event_index
      AND a."timestamp" = b."timestamp"
      AND a.id > b.id;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'ingest_contractevent'::regclass
          AND conname = 'unique_contract_ledger_event_index'
    ) THEN
        ALTER TABLE ingest_contractevent
            ADD CONSTRAINT unique_contract_ledger_event_index
            UNIQUE (contract_id, ledger, event_index, "timestamp");
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'ingest_contractevent'::regclass
          AND conname = 'ingest_contractevent_contract_id_fk'
    ) THEN
        ALTER TABLE ingest_contractevent
            ADD CONSTRAINT ingest_contractevent_contract_id_fk
            FOREIGN KEY (contract_id) REFERENCES ingest_trackedcontract(id)
            DEFERRABLE INITIALLY DEFERRED;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'ingest_contractevent'::regclass
          AND conname = 'ingest_contractevent_invocation_id_fk'
    ) THEN
        ALTER TABLE ingest_contractevent
            ADD CONSTRAINT ingest_contractevent_invocation_id_fk
            FOREIGN KEY (invocation_id) REFERENCES ingest_contractinvocation(id)
            ON DELETE SET NULL
            DEFERRABLE INITIALLY DEFERRED;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS ingest_cont_contrac_07c066_idx ON ingest_contractevent (contract_id, event_type, "timestamp");
CREATE INDEX IF NOT EXISTS ingest_cont_contrac_3666e0_idx ON ingest_contractevent (contract_id, "timestamp");
CREATE INDEX IF NOT EXISTS ingest_cont_contrac_c5f862_idx ON ingest_contractevent (contract_id, ledger, event_index);
CREATE INDEX IF NOT EXISTS ingest_cont_invocat_123230_idx ON ingest_contractevent (invocation_id);
CREATE INDEX IF NOT EXISTS ingest_cont_ledger_dde0a1_idx ON ingest_contractevent (ledger);
CREATE INDEX IF NOT EXISTS ingest_cont_signatu_39e92a_idx ON ingest_contractevent (signature_status);
CREATE INDEX IF NOT EXISTS ingest_cont_tx_hash_24128c_idx ON ingest_contractevent (tx_hash);
CREATE INDEX IF NOT EXISTS ingest_contractevent_event_type_idx ON ingest_contractevent (event_type);
CREATE INDEX IF NOT EXISTS ingest_contractevent_payload_hash_idx ON ingest_contractevent (payload_hash);
CREATE INDEX IF NOT EXISTS ingest_contractevent_timestamp_idx ON ingest_contractevent ("timestamp");
CREATE INDEX IF NOT EXISTS ingest_contractevent_validation_status_idx ON ingest_contractevent (validation_status);
CREATE INDEX IF NOT EXISTS ingest_contractevent_decoding_status_idx ON ingest_contractevent (decoding_status);
CREATE INDEX IF NOT EXISTS ingest_contractevent_status_idx ON ingest_contractevent (status);
"""


def restore(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    # Only act when the table is actually partitioned.
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "SELECT 1 FROM pg_partitioned_table WHERE partrelid = 'ingest_contractevent'::regclass"
        )
        if cursor.fetchone() is None:
            return
        cursor.execute(FORWARD_SQL)


class Migration(migrations.Migration):

    dependencies = [
        ("ingest", "0057_contractevent_restore_id_sequence"),
    ]

    operations = [
        migrations.RunPython(restore, migrations.RunPython.noop),
    ]
