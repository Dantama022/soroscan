from django.db import migrations
import soroscan.ingest.fields

# PostgreSQL-only column conversion: ``ALTER TABLE ... TYPE bytea USING ...``
# is not valid SQL on SQLite (used by the test suite), so the raw statements
# run through RunPython where the vendor check happens at migration-apply
# time — the same pattern as 0054_contractevent_partitioning.py.


def payload_to_bytea(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return

    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            """
            DROP INDEX IF EXISTS ingest_contractevent_payload_gin;
            ALTER TABLE ingest_contractevent ALTER COLUMN payload TYPE bytea USING convert_to(payload::text, 'UTF8');
            """
        )


def payload_to_jsonb(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return

    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            """
            ALTER TABLE ingest_contractevent ALTER COLUMN payload TYPE jsonb USING convert_from(payload, 'UTF8')::jsonb;
            CREATE INDEX IF NOT EXISTS ingest_contractevent_payload_gin ON ingest_contractevent USING gin (payload);
            """
        )


class _AlterFieldNonPostgres(migrations.AlterField):
    """AlterField that only touches the database on non-Postgres backends.

    On Postgres the column conversion is done explicitly by the RunPython
    above (with a correct bytea <-> jsonb USING clause). Letting Django also
    run its own ALTER makes the reverse path fail: it executes first on the
    way back and emits ``"payload"::jsonb``, which Postgres cannot cast from
    bytea.
    """

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        if schema_editor.connection.vendor == "postgresql":
            return
        super().database_forwards(app_label, schema_editor, from_state, to_state)

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        if schema_editor.connection.vendor == "postgresql":
            return
        super().database_backwards(app_label, schema_editor, from_state, to_state)


class Migration(migrations.Migration):

    dependencies = [
        ('ingest', '0053_webhook_replay_job'),
    ]

    operations = [
        migrations.RunPython(payload_to_bytea, payload_to_jsonb),
        _AlterFieldNonPostgres(
            model_name='contractevent',
            name='payload',
            field=soroscan.ingest.fields.CompressedJSONField(help_text='Decoded event payload'),
        ),
    ]
