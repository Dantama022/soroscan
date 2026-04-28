from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ingest", "0032_apikey_team_alter_contractmetadata_id_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="trackedcontract",
            name="metadata",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text="Custom attributes for storing contract metadata (team, owner, cost center, etc.)",
            ),
        ),
    ]