"""Tests: investment holdings CRUD + valuation."""

import pytest
from httpx import ASGITransport, AsyncClient

from reign.api.app import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_holdings_crud_and_valuation(client):
    r = await client.get("/api/accounts")
    acc = r.json()[0]
    r = await client.post(
        "/api/holdings",
        json={
            "symbol": "bbca",
            "name": "Bank BCA",
            "units": 100,
            "cost_basis": 9000,
            "current_price": 10000,
            "currency": "IDR",
            "account_id": acc["id"],
        },
    )
    assert r.status_code == 201
    h = r.json()
    assert h["symbol"] == "BBCA"
    assert float(h["value"]) == 100 * 10000
    assert float(h["pnl"]) == 100 * (10000 - 9000)
    r = await client.get("/api/holdings")
    assert any(x["id"] == h["id"] for x in r.json())
    r = await client.put(f"/api/holdings/{h['id']}", json={"current_price": 11000})
    assert float(r.json()["value"]) == 100 * 11000
    r = await client.put("/api/holdings/999999", json={"current_price": 1})
    assert r.status_code == 404
    r = await client.post(
        "/api/holdings",
        json={
            "symbol": "X",
            "units": 1,
            "cost_basis": 1,
            "current_price": 1,
            "currency": "IDR",
            "account_id": 999999,
        },
    )
    assert r.status_code == 404
    r = await client.delete(f"/api/holdings/{h['id']}")
    assert r.status_code == 200
    r = await client.delete(f"/api/holdings/{h['id']}")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_alert_above_and_below(client):
    r = await client.get("/api/accounts")
    acc = r.json()[0]
    r = await client.post(
        "/api/holdings",
        json={
            "symbol": "AL1",
            "units": 1,
            "cost_basis": 100,
            "current_price": 150,
            "currency": "IDR",
            "account_id": acc["id"],
            "alert_above": 120,
            "alert_below": 50,
        },
    )
    assert r.json()["alert"] is not None
    hid = r.json()["id"]
    r = await client.put(f"/api/holdings/{hid}", json={"current_price": 40})
    assert "bawah" in r.json()["alert"]
    r = await client.put(
        f"/api/holdings/{hid}",
        json={"current_price": 100, "alert_above": None, "alert_below": None},
    )
    assert r.json()["alert"] is None
