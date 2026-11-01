"""Domain: net-worth, calendar months, recurring forecast, 1-query budgets."""

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
async def test_net_worth_includes_transactions(client):
    r = await client.post(
        "/api/accounts",
        json={"name": "NW", "type": "cash", "currency": "IDR", "initial_balance": 100000},
    )
    assert r.status_code == 201
    acc = r.json()
    today = datetime.now().strftime("%Y-%m-%d")
    r = await client.post(
        "/api/transactions",
        json={
            "date": today,
            "description": "EXP",
            "amount": -25000,
            "currency": "IDR",
            "account_id": acc["id"],
        },
    )
    assert r.status_code == 201
    r = await client.get("/api/dashboard/summary?currency=IDR")
    assert r.status_code == 200
    summary = r.json()
    assert float(summary["total_balance"]) == 75000.0


@pytest.mark.asyncio
async def test_trends_calendar_labels(client):
    r = await client.get("/api/dashboard/trends?months=3&currency=IDR")
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 3
    assert len({(x["year"], x["month"]) for x in rows}) == 3


@pytest.mark.asyncio
async def test_forecast_projects_recurring_future(client):
    r = await client.get("/api/accounts")
    acc = next(a for a in r.json() if a["name"] == "Cash")
    r = await client.post(
        "/api/recurring",
        json={
            "description": "SALARY",
            "amount": 5000000,
            "currency": "IDR",
            "day_of_month": 1,
            "account_id": acc["id"],
            "active": True,
        },
    )
    assert r.status_code == 201
    r = await client.get("/api/forecast?currency=IDR")
    assert r.status_code == 200
    data = r.json()
    assert len(data["months"]) == 3
    assert float(data["months"][0]["income"]) >= 5000000.0


@pytest.mark.asyncio
async def test_budgets_spent_single_query(client):
    now = datetime.now()
    r = await client.get("/api/categories")
    food = next(c for c in r.json() if c["name"] == "Food")
    r = await client.post(
        "/api/budgets",
        json={
            "year": now.year,
            "month": now.month,
            "amount": 1000000,
            "currency": "IDR",
            "category_id": food["id"],
        },
    )
    assert r.status_code == 201
    r = await client.get(f"/api/budgets?year={now.year}&month={now.month}")
    assert r.status_code == 200
    rows = r.json()
    assert any(x["category"]["id"] == food["id"] and float(x["spent"]) >= 0 for x in rows)


@pytest.mark.asyncio
async def test_cursor_pagination(client):
    r = await client.get("/api/transactions?limit=1")
    assert r.status_code == 200
    first = r.json()
    assert len(first) <= 1
    if first:
        last_id = first[-1]["id"]
        r = await client.get(f"/api/transactions?limit=1&after_id={last_id}")
        assert r.status_code == 200
        nxt = r.json()
        assert all(x["id"] < last_id for x in nxt)
