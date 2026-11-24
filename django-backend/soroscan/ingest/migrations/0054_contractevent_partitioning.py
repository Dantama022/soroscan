"""Partition ingest_contractevent by (timestamp, ledger_sequence) on Postgres.

Uses RunPython (not RunSQL) so the vendor check happens at migration-apply
time rather than unconditionally — this keeps the migration a no-op on
non-Postgres backends (e.g. SQLite in tests), matching the pattern used in
0044_contractevent_payload_compression.py.
"""

from django.db import migrations


def partition_contractevent(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return

    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            """
            DROP TABLE IF EXISTS ingest_contractevent_old CASCADE;
            -- 1. Rename existing table
            ALTER TABLE ingest_contractevent RENAME TO ingest_contractevent_old;

            -- 2. Create the new partitioned table (by timestamp range)
            CREATE TABLE ingest_contractevent (
                LIKE ingest_contractevent_old INCLUDING DEFAULTS INCLUDING CONSTRAINTS
            ) PARTITION BY RANGE ("timestamp");

            -- Ensure sequence for id primary key
            CREATE SEQUENCE IF NOT EXISTS ingest_contractevent_id_seq;
            ALTER TABLE ingest_contractevent ALTER COLUMN id SET DEFAULT nextval('ingest_contractevent_id_seq');
            DO $$
            BEGIN
                BEGIN
                    ALTER SEQUENCE ingest_contractevent_id_seq OWNED BY ingest_contractevent.id;
                EXCEPTION WHEN OTHERS THEN
                    NULL;
                END;
            END $$;

            -- 3. Create initial active partitions and default partition
            CREATE TABLE ingest_contractevent_y2026m08 PARTITION OF ingest_contractevent
                FOR VALUES FROM ('2026-08-01 00:00:00+00') TO ('2026-09-01 00:00:00+00');

            CREATE TABLE ingest_contractevent_y2026m09 PARTITION OF ingest_contractevent
                FOR VALUES FROM ('2026-09-01 00:00:00+00') TO ('2026-10-01 00:00:00+00');

            CREATE TABLE ingest_contractevent_default PARTITION OF ingest_contractevent DEFAULT;

            -- 4. Migrate data
            INSERT INTO ingest_contractevent SELECT * FROM ingest_contractevent_old;

            -- Update sequence value to max existing id
            SELECT setval('ingest_contractevent_id_seq', COALESCE((SELECT MAX(id) FROM ingest_contractevent), 1));

            -- 5. Drop old temporary table
            DROP TABLE IF EXISTS ingest_contractevent_old CASCADE;
            """
        )


_UNPARTITION_SQL = """
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'ingest_contractevent_old') THEN
        DROP TABLE IF EXISTS ingest_contractevent CASCADE;
        ALTER TABLE ingest_contractevent_old RENAME TO ingest_contractevent;
    ELSE
        -- Detach the id sequence so dropping the partitioned table keeps it.
        ALTER SEQUENCE IF EXISTS ingest_contractevent_id_seq OWNED BY NONE;

        CREATE TABLE ingest_contractevent_unpart (
            LIKE ingest_contractevent INCLUDING DEFAULTS INCLUDING CONSTRAINTS
        );
        INSERT INTO ingest_contractevent_unpart SELECT * FROM ingest_contractevent;
        DROP TABLE ingest_contractevent CASCADE;
        ALTER TABLE ingest_contractevent_unpart RENAME TO ingest_contractevent;
        ALTER SEQUENCE IF EXISTS ingest_contractevent_id_seq OWNED BY ingest_contractevent.id;
        ALTER TABLE ingest_contractevent ALTER COLUMN id SET DEFAULT nextval('ingest_contractevent_id_seq');

        -- LIKE does not copy keys or indexes: restore the pre-partitioning
        -- schema (names match what earlier migrations expect to find).
        -- Deduplicate first so the narrower unique key can be created.
        DELETE FROM ingest_contractevent a USING ingest_contractevent b
        WHERE a.contract_id = b.contract_id AND a.ledger = b.ledger
          AND a.event_index = b.event_index AND a.id > b.id;

        ALTER TABLE ingest_contractevent ADD CONSTRAINT ingest_contractevent_pkey PRIMARY KEY (id);
        ALTER TABLE ingest_contractevent ADD CONSTRAINT unique_contract_ledger_event_index
            UNIQUE (contract_id, ledger, event_index);
        ALTER TABLE ingest_contractevent ADD CONSTRAINT ingest_contractevent_contract_id_eaf17dc4_fk_ingest_tr
            FOREIGN KEY (contract_id) REFERENCES ingest_trackedcontract(id) DEFERRABLE INITIALLY DEFERRED;
        ALTER TABLE ingest_contractevent ADD CONSTRAINT ingest_contractevent_invocation_id_eafb481d_fk_ingest_co
            FOREIGN KEY (invocation_id) REFERENCES ingest_contractinvocation(id) DEFERRABLE INITIALLY DEFERRED;
        CREATE INDEX ingest_cont_contrac_07c066_idx ON ingest_contractevent (contract_id, event_type, "timestamp");
        CREATE INDEX ingest_cont_contrac_3666e0_idx ON ingest_contractevent (contract_id, "timestamp");
        CREATE INDEX ingest_cont_contrac_c5f862_idx ON ingest_contractevent (contract_id, ledger, event_index);
        CREATE INDEX ingest_cont_invocat_123230_idx ON ingest_contractevent (invocation_id);
        CREATE INDEX ingest_cont_ledger_dde0a1_idx ON ingest_contractevent (ledger);
        CREATE INDEX ingest_cont_signatu_39e92a_idx ON ingest_contractevent (signature_status);
        CREATE INDEX ingest_cont_tx_hash_24128c_idx ON ingest_contractevent (tx_hash);
        CREATE INDEX ingest_contractevent_contract_id_eaf17dc4 ON ingest_contractevent (contract_id);
        CREATE INDEX ingest_contractevent_decoding_status_c0ec4743 ON ingest_contractevent (decoding_status);
        CREATE INDEX ingest_contractevent_decoding_status_c0ec4743_like ON ingest_contractevent (decoding_status varchar_pattern_ops);
        CREATE INDEX ingest_contractevent_event_type_6d979220 ON ingest_contractevent (event_type);
        CREATE INDEX ingest_contractevent_event_type_6d979220_like ON ingest_contractevent (event_type varchar_pattern_ops);
        CREATE INDEX ingest_contractevent_invocation_id_eafb481d ON ingest_contractevent (invocation_id);
        CREATE INDEX ingest_contractevent_ledger_4d1fe2c5 ON ingest_contractevent (ledger);
        CREATE INDEX ingest_contractevent_payload_hash_3e22777d ON ingest_contractevent (payload_hash);
        CREATE INDEX ingest_contractevent_payload_hash_3e22777d_like ON ingest_contractevent (payload_hash varchar_pattern_ops);
        CREATE INDEX ingest_contractevent_signature_status_c7eba2d8 ON ingest_contractevent (signature_status);
        CREATE INDEX ingest_contractevent_signature_status_c7eba2d8_like ON ingest_contractevent (signature_status varchar_pattern_ops);
        CREATE INDEX ingest_contractevent_timestamp_5145059d ON ingest_contractevent ("timestamp");
        CREATE INDEX ingest_contractevent_validation_status_9b0b90b3 ON ingest_contractevent (validation_status);
        CREATE INDEX ingest_contractevent_validation_status_9b0b90b3_like ON ingest_contractevent (validation_status varchar_pattern_ops);
    END IF;
END $$;
"""


def unpartition_contractevent(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return

    with schema_editor.connection.cursor() as cursor:
        cursor.execute(_UNPARTITION_SQL)


class Migration(migrations.Migration):

    dependencies = [
        ('ingest', '0053_webhook_replay_job'),
    ]

    operations = [
        migrations.RunPython(partition_contractevent, unpartition_contractevent),
    ]
