"""Tests for the ``registerContract`` GraphQL mutation (issue #1700).

Covers:
  * Malformed ``contractId`` values are rejected with a clear GraphQL error.
  * Duplicate registration returns a clear error instead of an
    unhandled ``IntegrityError`` (no 500 / no raw DB exception in the message).
  * A valid, unique ``contractId`` still registers successfully.
"""
from __future__ import annotations

import pytest
from stellar_sdk import StrKey

from soroscan.ingest.models import TrackedContract
from soroscan.ingest.tests.factories import TrackedContractFactory, UserFactory


pytestmark = pytest.mark.django_db


REGISTER_MUTATION = """
    mutation RegisterContract($contractId: String!, $name: String!) {
        registerContract(contractId: $contractId, name: $name) {
            contractId
            name
        }
    }
"""

# A real StrKey-encoded contract address (valid CRC16 checksum). A bare
# "C" + "A" * 55 is only regex-valid and is rejected by StrKey validation.
VALID_CONTRACT_ID = StrKey.encode_contract(bytes(32))


def _register(schema, contract_id: str, name: str = "Test Contract"):
    from django.test import RequestFactory

    request = RequestFactory().post("/graphql")
    request.user = UserFactory()
    return schema.execute_sync(
        REGISTER_MUTATION,
        variable_values={"contractId": contract_id, "name": name},
        context_value=type("Ctx", (), {"request": request})(),
    )


# ---------------------------------------------------------------------------
# Malformed contract IDs
# ---------------------------------------------------------------------------

class TestMalformedContractId:
    @pytest.mark.parametrize(
        "bad_id",
        [
            "",                              # empty
            "   ",                           # whitespace only
            "ABC123",                        # too short, wrong prefix
            "G" + "A" * 55,                  # wrong prefix (G is an account, not contract)
            "C" + "a" * 55,                  # lowercase is not Base32
            "C" + "1" * 55,                  # '1' is not in the Base32 alphabet
            "C" + "A" * 54,                  # too short by one
            "C" + "A" * 56,                  # too long by one
            "CABC!@#$" + "A" * 48,           # invalid chars
        ],
    )
    def test_rejects_malformed_contract_id(self, bad_id):
        from soroscan.ingest.schema import schema

        result = _register(schema, bad_id)

        # No data returned for the mutation, exactly one error
        assert result.data is None or result.data.get("registerContract") is None
        assert result.errors, f"Expected a GraphQL error for contract_id={bad_id!r}"
        message = result.errors[0].message.lower()
        assert "invalid contractid" in message or "must not be empty" in message

        # Nothing was persisted
        assert TrackedContract.objects.count() == 0

    def test_strips_surrounding_whitespace_before_validation(self):
        """``'  <valid>  '`` is normalised and accepted (whitespace isn't format)."""
        from django.test import RequestFactory

        from soroscan.ingest.schema import schema

        user = UserFactory()
        rf = RequestFactory()
        request = rf.post("/graphql")
        request.user = user

        result = schema.execute_sync(
            REGISTER_MUTATION,
            variable_values={"contractId": f"  {VALID_CONTRACT_ID}  ", "name": "Whitespace"},
            context_value=type("Ctx", (), {"request": request})(),
        )

        assert result.errors is None, result.errors
        assert result.data["registerContract"]["contractId"] == VALID_CONTRACT_ID


# ---------------------------------------------------------------------------
# Duplicate registration
# ---------------------------------------------------------------------------

class TestDuplicateRegistration:
    def test_duplicate_returns_clean_graphql_error(self):
        """A second registration of the same contract ID yields a clean error.

        Asserts:
          * No ``IntegrityError`` leaks to the client.
          * The error message names the conflict (mentions "already" or
            "unique"/"exists").
          * The original row is untouched (count still 1).
        """
        from django.test import RequestFactory

        from soroscan.ingest.schema import schema

        user = UserFactory()
        TrackedContractFactory(contract_id=VALID_CONTRACT_ID, owner=user)

        rf = RequestFactory()
        request = rf.post("/graphql")
        request.user = user

        result = schema.execute_sync(
            REGISTER_MUTATION,
            variable_values={"contractId": VALID_CONTRACT_ID, "name": "Second attempt"},
            context_value=type("Ctx", (), {"request": request})(),
        )

        assert result.data is None or result.data.get("registerContract") is None
        assert result.errors, "Expected a GraphQL error on duplicate registration"

        message = result.errors[0].message.lower()
        # Friendly, explicit error — not a raw DB traceback
        assert "already" in message or "unique" in message or "exists" in message
        # And definitely not a raw IntegrityError string
        assert "integrityerror" not in message
        assert "duplicate key" not in message

        # Only the original row exists
        assert TrackedContract.objects.filter(contract_id=VALID_CONTRACT_ID).count() == 1


# ---------------------------------------------------------------------------
# Happy path — ensure the new validation didn't break normal registration
# ---------------------------------------------------------------------------

class TestValidRegistration:
    def test_valid_contract_id_registers_successfully(self):
        from django.test import RequestFactory

        from soroscan.ingest.schema import schema

        user = UserFactory()
        rf = RequestFactory()
        request = rf.post("/graphql")
        request.user = user

        result = schema.execute_sync(
            REGISTER_MUTATION,
            variable_values={"contractId": VALID_CONTRACT_ID, "name": "Happy Path"},
            context_value=type("Ctx", (), {"request": request})(),
        )

        assert result.errors is None, result.errors
        assert result.data["registerContract"]["contractId"] == VALID_CONTRACT_ID
        assert result.data["registerContract"]["name"] == "Happy Path"
        assert TrackedContract.objects.filter(contract_id=VALID_CONTRACT_ID).exists()