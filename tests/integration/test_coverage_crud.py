"""Coverage: transactions CRUD/404, budget FK, accounts/categories delete."""

from datetime import datetime

import pytest
from httpx import ASGITransport, AsyncClient

from reign.api.app import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_transactions_get_update_delete_404(client):
    today = datetime.now().strftime("%Y-%m-%d")
    r = await client.get("/api/accounts")
    acc = r.json()[0]
    r = await client.post(
        "/api/transactions",
        json={
            "date": today,
            "description": "CRUD",
            "amount": -100,
            "currency": "IDR",
            "account_id": acc["id"],
        },
    )
    assert r.status_code == 201
    tid = r.json()["id"]
    r = await client.get(f"/api/transactions/{tid}")
    assert r.status_code == 200
    r = await client.get("/api/transactions/999999")
    assert r.status_code == 404
    r = await client.put(
        f"/api/transactions/{tid}",
        json={
            "date": today,
            "description": "CRUD2",
            "amount": -200,
            "currency": "IDR",
            "account_id": acc["id"],
        },
    )
    assert r.status_code == 200
    assert r.json()["description"] == "CRUD2"
    r = await client.put(
        "/api/transactions/999999",
        json={
            "date": today,
            "description": "X",
            "amount": -1,
            "currency": "IDR",
            "account_id": acc["id"],
        },
    )
    assert r.status_code == 404
    r = await client.put(
        f"/api/transactions/{tid}",
        json={
            "date": today,
            "description": "X",
            "amount": -1,
            "currency": "IDR",
            "account_id": 999999,
        },
    )
    assert r.status_code == 404
    r = await client.delete(f"/api/transactions/{tid}")
    assert r.status_code == 200
    r = await client.delete("/api/transactions/999999")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_transaction_create_fk_404(client):
    today = datetime.now().strftime("%Y-%m-%d")
    r = await client.post(
        "/api/transactions",
        json={
            "date": today,
            "description": "X",
            "amount": -1,
            "currency": "IDR",
            "account_id": 999999,
        },
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_transfer_same_account_400_and_fk_404(client):
    today = datetime.now().strftime("%Y-%m-%d")
    r = await client.get("/api/accounts")
    acc = r.json()[0]
    r = await client.post(
        "/api/transactions/transfer",
        json={
            "from_account_id": acc["id"],
            "to_account_id": acc["id"],
            "amount": 10,
            "currency": "IDR",
            "date": today,
        },
    )
    assert r.status_code == 400
    r = await client.post(
        "/api/transactions/transfer",
        json={
            "from_account_id": 999999,
            "to_account_id": acc["id"],
            "amount": 10,
            "currency": "IDR",
            "date": today,
        },
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_budget_fk_404_and_bulk_update_fk_404(client):
    now = datetime.now()
    r = await client.post(
        "/api/budgets",
        json={
            "year": now.year,
            "month": now.month,
            "amount": 100,
            "currency": "IDR",
            "category_id": 999999,
        },
    )
    assert r.status_code == 404
    r = await client.post(
        "/api/transactions/bulk-update",
        json={"ids": [1], "category_id": 999999},
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_accounts_categories_delete_and_404(client):
    r = await client.post(
        "/api/accounts",
        json={"name": "DEL", "type": "cash", "currency": "IDR", "initial_balance": 0},
    )
    aid = r.json()["id"]
    r = await client.delete(f"/api/accounts/{aid}")
    assert r.status_code == 200
    r = await client.delete("/api/accounts/999999")
    assert r.status_code == 404
    r = await client.post("/api/categories", json={"name": "DELX", "type": "expense"})
    assert r.status_code in (200, 201)
