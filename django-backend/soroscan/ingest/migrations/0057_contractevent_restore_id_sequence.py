"""Restore the ``id`` sequence default on the partitioned ingest_contractevent.

Migration 0054 (partitioning) pointed the new table's ``id`` default at the
sequence owned by the old table, then ran ``DROP TABLE ... CASCADE`` on the
old table, which dropped the sequence *and* the default. On PostgreSQL every
INSERT without an explicit id then failed with a NOT NULL violation.

This migration is idempotent: it (re)creates the sequence, advances it past
the highest existing id, re-attaches the default and ownership. It is a no-op
on non-PostgreSQL backends (where 0054 did nothing either).
"""

from django.db import migrations


def restore_id_sequence(apps, schema_editor):
    connection = schema_editor.connection
    if connection.vendor != "postgresql":
        return

    with connection.cursor() as cursor:
        # Only act if the table exists and is missing its default.
        cursor.execute(
            """
            SELECT column_default
            FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = 'ingest_contractevent'
              AND column_name = 'id'
            """
        )
        row = cursor.fetchone()
        if row is None or row[0]:
            return

        cursor.execute("CREATE SEQUENCE IF NOT EXISTS ingest_contractevent_id_seq")
        cursor.execute(
            """
            SELECT setval(
                'ingest_contractevent_id_seq',
                COALESCE((SELECT MAX(id) FROM ingest_contractevent), 0) + 1,
                false
            )
            """
        )
        cursor.execute(
            "ALTER TABLE ingest_contractevent ALTER COLUMN id "
            "SET DEFAULT nextval('ingest_contractevent_id_seq')"
        )
        cursor.execute(
            "ALTER SEQUENCE ingest_contractevent_id_seq OWNED BY ingest_contractevent.id"
        )


class Migration(migrations.Migration):
    dependencies = [
        ("ingest", "0056_contractevent_ledger_timestamp_index"),
    ]

    operations = [
        migrations.RunPython(restore_id_sequence, migrations.RunPython.noop),
    ]
