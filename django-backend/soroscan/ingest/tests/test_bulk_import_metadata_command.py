"""Tests for the bulk_import_metadata management command (issue #1945)."""

from __future__ import annotations

import json
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from soroscan.ingest.models import ContractMetadata
from soroscan.ingest.tests.factories import ContractMetadataFactory, TrackedContractFactory


def _call_bulk_import(*args, **kwargs):
    out = StringIO()
    err = StringIO()
    call_command(
        "bulk_import_metadata",
        *args,
        stdout=out,
        stderr=err,
        **kwargs,
    )
    return out.getvalue(), err.getvalue()


def _valid_row(contract_id: str, **overrides) -> dict:
    row = {
        "contract_id": contract_id,
        "name": "Contract Meta",
        "description": "Metadata description",
        "tags": ["defi"],
        "documentation_url": "https://docs.example.com/contract",
        "github_repo": "https://github.com/org/contract",
        "team_email": "team@example.com",
    }
    row.update(overrides)
    return row


@pytest.mark.django_db
class TestBulkImportMetadataCommand:
    def test_imports_and_updates_from_csv_file(self, tmp_path):
        c_create = TrackedContractFactory()
        c_update = TrackedContractFactory()
        ContractMetadataFactory(contract=c_update, name="Old Name", description="Old desc")

        csv_file = tmp_path / "metadata.csv"
        csv_file.write_text(
            "contract_id,name,description,tags,documentation_url,github_repo,team_email\n"
            f'{c_create.contract_id},DEX Pool,Liquidity pool,"defi,amm",https://docs.example.com/dex,https://github.com/org/dex,dex@example.com\n'
            f"{c_update.contract_id},Updated Name,New desc,token,https://docs.example.com/u,https://github.com/org/u,u@example.com\n",
            encoding="utf-8",
        )

        out, _ = _call_bulk_import("--input", str(csv_file))

        assert "Mode:                         live" in out
        assert "Created:                      1" in out
        assert "Updated:                      1" in out
        assert "Errors:                       0" in out

        created_meta = ContractMetadata.objects.get(contract=c_create)
        assert created_meta.name == "DEX Pool"
        assert created_meta.description == "Liquidity pool"
        assert created_meta.tags == ["defi", "amm"]
        assert created_meta.documentation_url == "https://docs.example.com/dex"
        assert created_meta.github_repo == "https://github.com/org/dex"
        assert created_meta.team_email == "dex@example.com"

        updated_meta = ContractMetadata.objects.get(contract=c_update)
        assert updated_meta.name == "Updated Name"
        assert updated_meta.description == "New desc"
        assert updated_meta.tags == ["token"]

    @pytest.mark.parametrize(
        "payload_builder",
        [
            lambda cid: [_valid_row(cid, name="List Meta", tags=["a", "b"])],
            lambda cid: {"metadata": [_valid_row(cid, name="List Meta", tags=["a", "b"])]},
            lambda cid: {"items": [_valid_row(cid, name="List Meta", tags=["a", "b"])]},
            lambda cid: {"contracts": [_valid_row(cid, name="List Meta", tags=["a", "b"])]},
        ],
    )
    def test_imports_supported_json_shapes(self, tmp_path, payload_builder):
        contract = TrackedContractFactory()
        json_file = tmp_path / "metadata.json"
        json_file.write_text(json.dumps(payload_builder(contract.contract_id)), encoding="utf-8")

        out, _ = _call_bulk_import("--input", str(json_file))

        assert "Created:                      1" in out
        meta = ContractMetadata.objects.get(contract=contract)
        assert meta.name == "List Meta"
        assert meta.tags == ["a", "b"]

    def test_defaults_blank_name_to_contract_id(self, tmp_path):
        contract = TrackedContractFactory()
        json_file = tmp_path / "blank_name.json"
        json_file.write_text(
            json.dumps([_valid_row(contract.contract_id, name="")]),
            encoding="utf-8",
        )

        _call_bulk_import("--input", str(json_file))

        meta = ContractMetadata.objects.get(contract=contract)
        assert meta.name == contract.contract_id

    def test_stdin_input_raises_attribute_error_under_current_impl(self):
        # bulk_import_metadata._load_input references self.stdin, which Django
        # BaseCommand does not define (only self.stdout/self.stderr exist).
        with pytest.raises(AttributeError, match="stdin"):
            _call_bulk_import("--input", "-", "--format", "json")

    def test_stdin_without_format_raises_command_error(self):
        with pytest.raises(CommandError, match="format is required"):
            _call_bulk_import("--input", "-")

    def test_dry_run_does_not_persist_changes(self, tmp_path):
        contract = TrackedContractFactory()
        json_file = tmp_path / "dry.json"
        json_file.write_text(
            json.dumps([{"contract_id": contract.contract_id, "name": "Dry Run"}]),
            encoding="utf-8",
        )

        out, _ = _call_bulk_import("--input", str(json_file), "--dry-run")

        assert "Mode:                         dry-run" in out
        assert "Created:                      1" in out
        assert not ContractMetadata.objects.filter(contract=contract).exists()

    def test_writes_report_file(self, tmp_path):
        contract = TrackedContractFactory()
        json_file = tmp_path / "data.json"
        json_file.write_text(
            json.dumps([_valid_row(contract.contract_id, name="Reported")]),
            encoding="utf-8",
        )
        report_file = tmp_path / "reports" / "import-report.json"

        out, _ = _call_bulk_import("--input", str(json_file), "--report", str(report_file))

        assert f"Report written to {report_file}" in out
        report = json.loads(report_file.read_text(encoding="utf-8"))
        assert report["mode"] == "live"
        assert report["created"] == 1
        assert report["errors"] == 0

    def test_rollback_on_missing_contract_leaves_no_partial_writes(self, tmp_path):
        contract = TrackedContractFactory()
        unknown_id = "C" + "Z" * 55
        json_file = tmp_path / "partial.json"
        json_file.write_text(
            json.dumps(
                [
                    _valid_row(contract.contract_id, name="Should Roll Back"),
                    _valid_row(unknown_id, name="Missing"),
                ]
            ),
            encoding="utf-8",
        )

        with pytest.raises(CommandError, match="TrackedContract not found"):
            _call_bulk_import("--input", str(json_file), "--on-error", "rollback")

        assert not ContractMetadata.objects.filter(contract=contract).exists()

    def test_rollback_on_validation_error_leaves_no_partial_writes(self, tmp_path):
        c1 = TrackedContractFactory()
        c2 = TrackedContractFactory()
        json_file = tmp_path / "invalid_row.json"
        json_file.write_text(
            json.dumps(
                [
                    _valid_row(c1.contract_id, name="Valid First"),
                    _valid_row(c2.contract_id, name="x" * 257),
                ]
            ),
            encoding="utf-8",
        )

        with pytest.raises(CommandError, match="name exceeds max length of 256"):
            _call_bulk_import("--input", str(json_file))

        assert not ContractMetadata.objects.filter(contract=c1).exists()
        assert not ContractMetadata.objects.filter(contract=c2).exists()

    def test_skip_mode_persists_valid_rows_and_reports_errors(self, tmp_path):
        c1 = TrackedContractFactory()
        c_bad = TrackedContractFactory()
        c2 = TrackedContractFactory()
        unknown_id = "C" + "Z" * 55
        json_file = tmp_path / "mixed.json"
        json_file.write_text(
            json.dumps(
                [
                    _valid_row(c1.contract_id, name="First Valid"),
                    _valid_row(unknown_id, name="No Contract"),
                    _valid_row(c_bad.contract_id, name="x" * 257),
                    _valid_row(c2.contract_id, name="Second Valid"),
                ]
            ),
            encoding="utf-8",
        )

        out, _ = _call_bulk_import("--input", str(json_file), "--on-error", "skip")

        assert "Created:                      2" in out
        assert "Skipped (no contract):        1" in out
        assert "Skipped (on error):           1" in out
        assert "Errors:                       1" in out
        assert f"Row 2 ({unknown_id}): TrackedContract not found" in out
        assert f"Row 3 ({c_bad.contract_id}): name exceeds max length of 256" in out

        assert ContractMetadata.objects.get(contract=c1).name == "First Valid"
        assert ContractMetadata.objects.get(contract=c2).name == "Second Valid"
        assert not ContractMetadata.objects.filter(contract=c_bad).exists()

    def test_omitting_optional_url_fields_raises_not_null_error_under_current_impl(self, tmp_path):
        """metadata_bulk_import maps empty optional URLs/email to None despite NOT NULL columns."""
        contract = TrackedContractFactory()
        json_file = tmp_path / "omit_urls.json"
        json_file.write_text(
            json.dumps([{"contract_id": contract.contract_id, "name": "Minimal"}]),
            encoding="utf-8",
        )

        with pytest.raises(CommandError, match="NOT NULL constraint failed"):
            _call_bulk_import("--input", str(json_file), "--on-error", "rollback")

    def test_missing_file_raises_command_error(self, tmp_path):
        missing = tmp_path / "missing.json"

        with pytest.raises(CommandError, match="Cannot read input file"):
            _call_bulk_import("--input", str(missing))

    @pytest.mark.parametrize(
        "filename,content,error_match",
        [
            ("bad.txt", "{}", "Cannot detect format"),
            ("bad.json", "{not-json", "JSON parse error"),
            ("bad_root.json", '"just a string"', "JSON must be an array"),
            ("bad.csv", "name,description\nFoo,Bar\n", "contract_id"),
            ("empty.csv", "", "contract_id"),
        ],
    )
    def test_invalid_inputs_raise_command_error(self, tmp_path, filename, content, error_match):
        path = tmp_path / filename
        path.write_text(content, encoding="utf-8")

        with pytest.raises(CommandError, match=error_match):
            _call_bulk_import("--input", str(path))

    def test_empty_json_list_exits_gracefully(self, tmp_path):
        path = tmp_path / "empty.json"
        path.write_text("[]", encoding="utf-8")

        out, _ = _call_bulk_import("--input", str(path))

        assert "No metadata rows to import." in out
