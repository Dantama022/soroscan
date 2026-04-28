from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("ingest", "0033_trackedcontract_metadata"),
    ]

    operations = [
        migrations.CreateModel(
            name="ContractSource",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "source_file",
                    models.FileField(
                        help_text="Uploaded source file (Rust code or tarball)",
                        upload_to="contract_sources/",
                    ),
                ),
                (
                    "abi_json",
                    models.JSONField(
                        blank=True,
                        help_text="ABI JSON extracted from source or uploaded separately",
                        null=True,
                    ),
                ),
                ("uploaded_at", models.DateTimeField(auto_now_add=True)),
                (
                    "contract",
                    models.ForeignKey(
                        help_text="Contract this source belongs to",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="sources",
                        to="ingest.trackedcontract",
                    ),
                ),
                (
                    "uploaded_by",
                    models.ForeignKey(
                        help_text="User who uploaded this source",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="uploaded_sources",
                        to="auth.user",
                    ),
                ),
            ],
            options={
                "ordering": ["-uploaded_at"],
            },
        ),
        migrations.CreateModel(
            name="ContractVerification",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("verified", "Verified"),
                            ("failed", "Failed"),
                        ],
                        default="pending",
                        help_text="Verification status",
                        max_length=16,
                    ),
                ),
                (
                    "bytecode_hash",
                    models.CharField(
                        help_text="SHA256 hash of the deployed bytecode",
                        max_length=64,
                    ),
                ),
                (
                    "compiler_version",
                    models.CharField(
                        blank=True,
                        help_text="Compiler version used to produce the bytecode",
                        max_length=100,
                    ),
                ),
                (
                    "verified_at",
                    models.DateTimeField(blank=True, null=True),
                ),
                (
                    "error_message",
                    models.TextField(
                        blank=True,
                        help_text="Error message if verification failed",
                    ),
                ),
                (
                    "contract",
                    models.OneToOneField(
                        help_text="Contract being verified",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="verification",
                        to="ingest.trackedcontract",
                    ),
                ),
                (
                    "source",
                    models.ForeignKey(
                        help_text="Source used for verification",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="verifications",
                        to="ingest.contractsource",
                    ),
                ),
            ],
            options={
                "ordering": ["-verified_at"],
            },
        ),
        migrations.AddIndex(
            model_name="contractsource",
            index=models.Index(fields=["contract", "uploaded_at"], name="ingest_cont_contract__a5c2e8_idx"),
        ),
    ]