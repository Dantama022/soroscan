"""Tests for the seed_incident_playbooks management command (issue #1945)."""

from __future__ import annotations

from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from soroscan.ingest.models import RemediationRule
from soroscan.ingest.services.incident_playbooks import default_remediation_rule_specs


def _call_playbooks(*args, **kwargs):
    out = StringIO()
    err = StringIO()
    call_command("seed_incident_playbooks", *args, stdout=out, stderr=err, **kwargs)
    return out.getvalue(), err.getvalue()


@pytest.mark.django_db
class TestSeedIncidentPlaybooksCommand:
    def test_creates_all_default_playbook_rules(self):
        specs = default_remediation_rule_specs()

        out, _ = _call_playbooks()

        assert f"created={len(specs)} updated=0 dry_run=False" in out
        assert RemediationRule.objects.count() == len(specs)

        for spec in specs:
            rule = RemediationRule.objects.get(name=spec["name"])
            assert rule.condition == spec["condition"]
            assert rule.actions == spec["actions"]
            assert rule.enabled is spec["enabled"]
            assert rule.grace_period_minutes == spec["grace_period_minutes"]
            assert rule.alert_type == spec["alert_type"]
            assert rule.dry_run is spec["dry_run"]
            assert rule.alert_target == ""
            assert f"Created {spec['name']}" in out

    def test_repeated_execution_updates_without_creating_duplicates(self):
        specs = default_remediation_rule_specs()
        _call_playbooks()

        rule = RemediationRule.objects.get(name=specs[0]["name"])
        rule.enabled = False
        rule.grace_period_minutes = 99
        rule.alert_target = "https://stale.example.com"
        rule.save()

        out, _ = _call_playbooks()

        assert RemediationRule.objects.count() == len(specs)
        assert f"created=0 updated={len(specs)} dry_run=False" in out

        rule.refresh_from_db()
        assert rule.enabled is True
        assert rule.grace_period_minutes == specs[0]["grace_period_minutes"]
        assert rule.alert_target == ""

    def test_dry_run_does_not_create_or_modify_rules(self):
        specs = default_remediation_rule_specs()

        out_create, _ = _call_playbooks("--dry-run")
        assert RemediationRule.objects.count() == 0
        assert "created=0 updated=0 dry_run=True" in out_create
        for spec in specs:
            assert f"[dry-run] would create {spec['name']}" in out_create

        # Seed once, mutate a rule, then verify --dry-run leaves DB untouched.
        _call_playbooks()
        target_rule = RemediationRule.objects.get(name=specs[0]["name"])
        target_rule.enabled = False
        target_rule.save()

        out_update, _ = _call_playbooks("--dry-run")
        assert "created=0 updated=0 dry_run=True" in out_update
        for spec in specs:
            assert f"[dry-run] would update {spec['name']}" in out_update

        target_rule.refresh_from_db()
        assert target_rule.enabled is False

    def test_unknown_option_raises_command_error(self):
        with pytest.raises(CommandError):
            call_command("seed_incident_playbooks", "--unknown-flag")
