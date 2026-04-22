"""Global pytest fixtures."""

import pytest


@pytest.fixture
def sample_transactions() -> list[dict]:
    """Return sample transaction dicts for testing."""
    return [
        {
            "date": "2026-04-01",
            "description": "STARBUCKS INDONESIA",
            "amount": -75000.0,
            "currency": "IDR",
            "account_id": 1,
        },
        {
            "date": "2026-04-02",
            "description": "SALARY ACME CORP",
            "amount": 15000000.0,
            "currency": "IDR",
            "account_id": 1,
        },
    ]
