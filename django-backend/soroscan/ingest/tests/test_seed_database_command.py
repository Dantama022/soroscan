"""Tests for the seed_database management command (issue #1945)."""

from __future__ import annotations

import json
from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError

from soroscan.ingest.management.commands import seed_database as seed_database_cmd
from soroscan.ingest.models import (
    AlertExecution,
    AlertRule,
    ContractEvent,
    Organization,
    OrganizationMembership,
    Team,
    TeamMembership,
    TrackedContract,
    WebhookDeliveryLog,
    WebhookSubscription,
)
from soroscan.ingest.tests.factories import UserFactory

User = get_user_model()


def _call_seed(*args, **kwargs):
    out = StringIO()
    err = StringIO()
    call_command("seed_database", *args, stdout=out, stderr=err, **kwargs)
    return out.getvalue(), err.getvalue()


def _minimal_fixture_payload():
    return {
        "organizations": [
            {
                "name": "Test Seed Org",
                "slug": "test-seed-org",
                "owner_email": "alice@example.com",
                "settings": {"plan": "pro"},
                "quota": 5000,
            }
        ],
        "teams": [
            {
                "name": "Core Team",
                "organization_slug": "test-seed-org",
                "created_by_email": "alice@example.com",
            }
        ],
        "users": [
            {
                "email": "alice@example.com",
                "password": "testpass123",
                "first_name": "Alice",
                "last_name": "Seed",
            },
            {
                "email": "bob@example.com",
                "password": "testpass123",
                "first_name": "Bob",
                "last_name": "Member",
            },
        ],
        "memberships": [
            {
                "user_email": "alice@example.com",
                "organization_slug": "test-seed-org",
                "role": "owner",
            },
            {
                "user_email": "bob@example.com",
                "organization_slug": "test-seed-org",
                "role": "member",
            },
        ],
        "team_memberships": [
            {
                "user_email": "alice@example.com",
                "team_name": "Core Team",
                "role": "admin",
            },
            {
                "user_email": "bob@example.com",
                "team_name": "Core Team",
                "role": "member",
            },
        ],
        "contracts": [
            {
                "contract_id": "C" + "A" * 55,
                "name": "Seeded Pool",
                "alias": "Pool",
                "description": "Seeded AMM pool",
                "owner_email": "alice@example.com",
                "organization_slug": "test-seed-org",
                "team_name": "Core Team",
                "abi_schema": {"events": [{"name": "swap", "params": ["amount"]}]},
                "event_filter_type": "none",
                "event_filter_list": [],
            }
        ],
        "events": {
            "per_contract": 4,
            "event_types": ["swap"],
            "days_back": 7,
        },
        "webhooks": [
            {
                "contract_id": "C" + "A" * 55,
                "event_type": "swap",
                "target_url": "https://example.com/hook",
                "timeout_seconds": 10,
                "retry_backoff_strategy": "exponential",
                "retry_backoff_seconds": 30,
                "signature_algorithm": "sha256",
            }
        ],
        "webhook_delivery_logs": {
            "per_webhook": 2,
            "status_codes": [200, 500],
        },
        "alert_rules": [
            {
                "contract_id": "C" + "A" * 55,
                "name": "Large Swap",
                "condition": {"op": "gt", "field": "amount", "value": 100},
                "channels": [{"type": "webhook", "target": "https://example.com/alert"}],
                "action_type": "webhook",
                "action_target": "https://example.com/alert",
            }
        ],
    }


@pytest.mark.django_db
class TestSeedDatabaseCommand:
    def test_seeds_from_custom_fixture_with_expected_relationships(self, tmp_path):
        fixture_path = tmp_path / "custom.json"
        fixture_path.write_text(json.dumps(_minimal_fixture_payload()), encoding="utf-8")

        out, _ = _call_seed("--fixture", str(fixture_path))

        assert "Database seeded successfully." in out
        assert User.objects.filter(email__in=["alice@example.com", "bob@example.com"]).count() == 2

        org = Organization.objects.get(slug="test-seed-org")
        assert org.owner.email == "alice@example.com"
        assert org.quota == 5000

        team = Team.objects.get(slug="test-seed-org-core-team")
        assert team.organization == org
        assert team.created_by.email == "alice@example.com"

        assert OrganizationMembership.objects.filter(organization=org).count() == 2
        assert TeamMembership.objects.filter(team=team).count() == 2

        contract = TrackedContract.objects.get(contract_id="C" + "A" * 55)
        assert contract.owner.email == "alice@example.com"
        assert contract.organization == org
        assert contract.team == team
        assert contract.is_active is True

        events = ContractEvent.objects.filter(contract=contract)
        assert 1 <= events.count() <= 4

        webhook = WebhookSubscription.objects.get(contract=contract)
        assert webhook.target_url == "https://example.com/hook"
        assert WebhookDeliveryLog.objects.filter(subscription=webhook).count() == min(2, events.count())

        rule = AlertRule.objects.get(contract=contract, name="Large Swap")
        assert AlertExecution.objects.filter(rule=rule).count() == min(2, events.count())

    def test_default_run_falls_back_to_default_scenario_when_fixtures_dir_missing(self):
        # Note: seed_database.FIXTURES_DIR resolves to soroscan/fixtures rather than
        # django-backend/fixtures, so default invocation falls back to the built-in
        # default scenario unless --fixture is passed explicitly.
        out, _ = _call_seed()

        assert "Database seeded successfully." in out
        assert "Fixture file not found" in out
        assert Organization.objects.count() == 2
        assert Team.objects.count() == 2
        assert TrackedContract.objects.count() == 3
        assert WebhookSubscription.objects.count() == 2
        assert AlertRule.objects.count() == 1
        assert ContractEvent.objects.exists()

    def test_development_fixture_can_be_loaded_explicitly(self):
        dev_fixture = seed_database_cmd.Path(seed_database_cmd.__file__).resolve().parents[4] / "fixtures" / "development.json"
        out, _ = _call_seed("--fixture", str(dev_fixture))

        assert "Database seeded successfully." in out
        # development.json lists 3 orgs, but gamma-finance references owner
        # admin@gamma.example.com which is absent from its users list, so 2 are created.
        assert Organization.objects.count() == 2
        assert Team.objects.count() == 3
        assert TrackedContract.objects.count() == 5
        assert WebhookSubscription.objects.count() == 3
        assert AlertRule.objects.count() == 2
        assert ContractEvent.objects.exists()

    def test_scenarios_run_when_default_fixture_missing(self, monkeypatch, tmp_path):
        monkeypatch.setattr(seed_database_cmd, "FIXTURES_DIR", tmp_path)

        out, _ = _call_seed("--scenario", "minimal")

        assert "Fixture file not found" in out
        assert "minimal scenario" in out
        assert Organization.objects.filter(slug="minimal-org").exists()
        assert TrackedContract.objects.count() == 3
        assert ContractEvent.objects.count() == 0
        assert WebhookSubscription.objects.count() == 0
        assert AlertRule.objects.count() == 0

    @pytest.mark.parametrize("scenario", ["default", "webhook"])
    def test_non_minimal_scenarios_when_fixture_missing(self, monkeypatch, tmp_path, scenario):
        monkeypatch.setattr(seed_database_cmd, "FIXTURES_DIR", tmp_path)

        _call_seed("--scenario", scenario)

        assert Organization.objects.count() == 2
        assert Team.objects.count() == 2
        assert TrackedContract.objects.count() == 3
        assert WebhookSubscription.objects.count() == 2
        assert AlertRule.objects.count() == 1
        assert ContractEvent.objects.exists()

    @pytest.mark.django_db(transaction=True)
    def test_repeated_execution_behavior(self, tmp_path):
        """Users, orgs, teams, contracts use get_or_create; webhooks hit unique constraint (swallowed in autocommit); alert rules duplicate."""
        fixture_path = tmp_path / "repeat.json"
        fixture_path.write_text(json.dumps(_minimal_fixture_payload()), encoding="utf-8")

        _call_seed("--fixture", str(fixture_path))
        first_users = User.objects.count()
        first_orgs = Organization.objects.count()
        first_teams = Team.objects.count()
        first_contracts = TrackedContract.objects.count()
        first_webhooks = WebhookSubscription.objects.count()
        first_rules = AlertRule.objects.count()

        _call_seed("--fixture", str(fixture_path))

        assert User.objects.count() == first_users
        assert Organization.objects.count() == first_orgs
        assert Team.objects.count() == first_teams
        assert TrackedContract.objects.count() == first_contracts
        # WebhookSubscription has unique (target_url, contract) so second create fails and is caught.
        assert WebhookSubscription.objects.count() == first_webhooks
        # AlertRule has no unique constraint and uses .create(), so repeated run appends.
        assert AlertRule.objects.count() == first_rules * 2

    def test_clear_removes_example_com_seeded_data_only(self, tmp_path):
        fixture_path = tmp_path / "clear.json"
        fixture_path.write_text(json.dumps(_minimal_fixture_payload()), encoding="utf-8")

        staff_user = UserFactory(username="staff_keep", email="staff@example.com", is_staff=True)
        real_user = UserFactory(username="real_keep", email="real@soroscan.io", is_staff=False)

        _call_seed("--fixture", str(fixture_path))
        _call_seed("--fixture", str(fixture_path), "--clear")

        # --clear prevents duplicate webhooks/rules for @example.com fixtures.
        assert WebhookSubscription.objects.count() == 1
        assert AlertRule.objects.count() == 1
        assert User.objects.filter(pk=staff_user.pk).exists()
        assert User.objects.filter(pk=real_user.pk).exists()

    def test_invalid_json_fixture_raises_command_error(self, tmp_path):
        bad_file = tmp_path / "invalid.json"
        bad_file.write_text("{not valid json", encoding="utf-8")

        with pytest.raises(CommandError, match="Invalid JSON in fixture file"):
            call_command("seed_database", "--fixture", str(bad_file))

    def test_missing_fixture_file_raises_file_not_found(self, tmp_path):
        missing = tmp_path / "does_not_exist.json"

        with pytest.raises(FileNotFoundError):
            call_command("seed_database", "--fixture", str(missing))
