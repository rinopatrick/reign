"""End-to-end integration tests."""

import pytest
from httpx import ASGITransport, AsyncClient

from sovereign_ledger.api.app import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "healthy"


@pytest.mark.asyncio
async def test_categories_seeded(client):
    r = await client.get("/api/categories")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 10
    assert any(c["name"] == "Food" for c in data)


@pytest.mark.asyncio
async def test_create_account_and_transaction(client):
    # Create account
    r = await client.post("/api/accounts", json={"name": "Test", "type": "cash", "currency": "IDR", "initial_balance": 0})
    assert r.status_code == 201
    test_account = r.json()

    # Create transaction
    r = await client.post("/api/transactions", json={
        "date": "2026-04-15",
        "description": "COFFEE SHOP",
        "amount": -50000,
        "currency": "IDR",
        "account_id": test_account["id"],
    })
    assert r.status_code == 201
    tx = r.json()
    assert tx["description"] == "COFFEE SHOP"

    # Dashboard should reflect it
    r = await client.get("/api/dashboard/summary?currency=IDR")
    summary = r.json()
    assert float(summary["month_expense"]) < 0


@pytest.mark.asyncio
async def test_csv_import(client):
    # Get account
    r = await client.get("/api/accounts")
    accounts = r.json()
    account = next(a for a in accounts if a["name"] == "Cash")

    csv_content = b"Tanggal,Keterangan,Mutasi\n15/04/2026,STARBUCKS,-75.000\n16/04/2026,SALARY,+15.000.000\n"
    r = await client.post(
        f"/api/transactions/import?account_id={account['id']}",
        files={"file": ("test.csv", csv_content, "text/csv")},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["imported"] == 2

    # Check categorized
    r = await client.get("/api/transactions")
    txs = r.json()
    starbucks = next(t for t in txs if "STARBUCKS" in t["description"])
    assert starbucks["category"]["name"] == "Food"
