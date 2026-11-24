"""Tests for the ``verify_source`` action on ``TrackedContractViewSet`` (issue #1703).

These cover the four acceptance criteria:

  * ``placeholder_hash`` no longer appears in the codebase path exercised here.
  * The hash is computed from the actual uploaded source file (SHA-256).
  * A mismatch against an existing verification is rejected with 409.
  * The happy path records a real, caller-supplied bytecode hash.
"""
from __future__ import annotations

import hashlib
from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from soroscan.ingest.models import (
    ContractSource,
    ContractVerification,
)
from soroscan.ingest.tests.factories import TrackedContractFactory, UserFactory


pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SOURCE_BYTES = b"// SPDX-License-Identifier: MIT\npub fn hello() {}\n"
SOURCE_SHA256 = hashlib.sha256(SOURCE_BYTES).hexdigest()
BYTECODE_HASH_A = "a" * 64
BYTECODE_HASH_B = "b" * 64


def _make_contract_with_source(user, *, contract_id=None):
    """Create a contract owned by *user* with one uploaded source row."""
    kwargs = {"owner": user}
    if contract_id:
        kwargs["contract_id"] = contract_id
    contract = TrackedContractFactory(**kwargs)

    upload = SimpleUploadedFile(
        "contract.rs",
        BytesIO(SOURCE_BYTES).read(),
        content_type="text/plain",
    )
    ContractSource.objects.create(
        contract=contract,
        source_file=upload,
        uploaded_by=user,
    )
    return contract


def _verify_url(contract):
    return f"/api/ingest/contracts/{contract.pk}/verify_source/"


# ---------------------------------------------------------------------------
# Malformed / missing bytecode_hash
# ---------------------------------------------------------------------------

class TestVerifySourceInputValidation:
    def test_placeholder_hash_constant_does_not_exist_in_view_module(self):
        """Regression guard for #1703: no `placeholder_hash` literal remains."""
        from soroscan.ingest import views as views_module

        source = open(views_module.__file__, "r", encoding="utf-8").read()
        assert "placeholder_hash" not in source

    def test_rejects_missing_bytecode_hash(self):
        user = UserFactory()
        contract = _make_contract_with_source(user)

        client = APIClient()
        client.force_authenticate(user=user)
        resp = client.post(_verify_url(contract), data={}, format="json")

        assert resp.status_code == 400
        assert "bytecode_hash is required" in resp.json()["detail"]
        assert not ContractVerification.objects.filter(contract=contract).exists()

    def test_rejects_malformed_bytecode_hash(self):
        user = UserFactory()
        contract = _make_contract_with_source(user)

        client = APIClient()
        client.force_authenticate(user=user)
        for bad in ["not-a-hash", "ABC" * 10, "Z" * 64, "a" * 63, "a" * 65]:
            resp = client.post(
                _verify_url(contract),
                data={"bytecode_hash": bad},
                format="json",
            )
            assert resp.status_code == 400, f"hash={bad!r} should have been rejected"
            assert "64-character" in resp.json()["detail"] or "hex" in resp.json()["detail"]

        assert not ContractVerification.objects.filter(contract=contract).exists()


# ---------------------------------------------------------------------------
# Happy path — real source hash is computed, real bytecode hash is stored
# ---------------------------------------------------------------------------

class TestVerifySourceHappyPath:
    def test_records_real_source_hash_and_bytecode_hash(self):
        user = UserFactory()
        contract = _make_contract_with_source(user)

        client = APIClient()
        client.force_authenticate(user=user)
        resp = client.post(
            _verify_url(contract),
            data={"bytecode_hash": BYTECODE_HASH_A, "compiler_version": "1.78.0"},
            format="json",
        )

        assert resp.status_code == 200, resp.json()

        body = resp.json()
        # Real bytecode hash stored on the model row
        assert body["bytecode_hash"] == BYTECODE_HASH_A
        # Real source hash computed from the uploaded file is included in the
        # response (proves what was uploaded)
        assert body["source_hash"] == SOURCE_SHA256
        # No placeholder anywhere
        assert body["bytecode_hash"] != "placeholder_hash"

        verification = ContractVerification.objects.get(contract=contract)
        assert verification.status == ContractVerification.Status.VERIFIED
        assert verification.bytecode_hash == BYTECODE_HASH_A
        assert verification.compiler_version == "1.78.0"
        assert verification.error_message == ""


# ---------------------------------------------------------------------------
# Mismatch against an existing verification is rejected
# ---------------------------------------------------------------------------

class TestVerifySourceMismatch:
    def test_conflicting_bytecode_hash_returns_409(self):
        user = UserFactory()
        contract = _make_contract_with_source(user)

        # Seed an existing verification with hash A.
        ContractVerification.objects.create(
            contract=contract,
            source=contract.sources.first(),
            status=ContractVerification.Status.VERIFIED,
            bytecode_hash=BYTECODE_HASH_A,
            compiler_version="1.78.0",
        )

        client = APIClient()
        client.force_authenticate(user=user)
        resp = client.post(
            _verify_url(contract),
            data={"bytecode_hash": BYTECODE_HASH_B},
            format="json",
        )

        assert resp.status_code == 409
        body = resp.json()
        assert body["existing_bytecode_hash"] == BYTECODE_HASH_A
        assert body["supplied_bytecode_hash"] == BYTECODE_HASH_B

        # Original verification untouched
        verification = ContractVerification.objects.get(contract=contract)
        assert verification.bytecode_hash == BYTECODE_HASH_A

    def test_force_true_allows_replacing_the_hash(self):
        user = UserFactory()
        contract = _make_contract_with_source(user)

        ContractVerification.objects.create(
            contract=contract,
            source=contract.sources.first(),
            status=ContractVerification.Status.VERIFIED,
            bytecode_hash=BYTECODE_HASH_A,
        )

        client = APIClient()
        client.force_authenticate(user=user)
        resp = client.post(
            _verify_url(contract),
            data={"bytecode_hash": BYTECODE_HASH_B, "force": True},
            format="json",
        )

        assert resp.status_code == 200
        assert resp.json()["bytecode_hash"] == BYTECODE_HASH_B
        assert (
            ContractVerification.objects.get(contract=contract).bytecode_hash
            == BYTECODE_HASH_B
        )


# ---------------------------------------------------------------------------
# Preconditions
# ---------------------------------------------------------------------------

class TestVerifySourcePreconditions:
    def test_returns_400_when_no_source_uploaded(self):
        user = UserFactory()
        contract = TrackedContractFactory(owner=user)

        client = APIClient()
        client.force_authenticate(user=user)
        resp = client.post(
            _verify_url(contract),
            data={"bytecode_hash": BYTECODE_HASH_A},
            format="json",
        )

        assert resp.status_code == 400
        assert "No source uploaded" in resp.json()["detail"]