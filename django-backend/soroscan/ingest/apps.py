from django.apps import AppConfig


class IngestConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "soroscan.ingest"
    verbose_name = "SoroScan Ingest"

    def ready(self):
        import soroscan.ingest.signals  # noqa: F401 — registers signal handlers
        from soroscan.ingest.telemetry import configure_tracing
        from soroscan.operational_metrics import register_operational_collector
        from soroscan.shutdown import register_shutdown_handlers

        configure_tracing()
        register_operational_collector()
        register_shutdown_handlers()
