"""Tests: market price mapping + refresh endpoints (mocked network)."""

from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

import reign.api.routes.holdings as holdings_route
import reign.services.market as market_module
from reign.api.app import app
from reign.services.market import resolve_yahoo_symbol


def test_resolve_yahoo_symbol():
    assert resolve_yahoo_symbol("bbca") == "BBCA.JK"
    assert resolve_yahoo_symbol("BBCA.JK") == "BBCA.JK"
    assert resolve_yahoo_symbol("AAPL") == "AAPL.JK"
    assert resolve_yahoo_symbol("") == ""


class _Resp:
    def raise_for_status(self):
        pass

    def json(self):
        return {"chart": {"result": [{"meta": {"regularMarketPrice": 10250}, "indicators": {}}]}}


class _Client:
    async def get(self, url, **_kw):
        assert "BBCA.JK" in url
        return _Resp()

    async def aclose(self):
        pass


@pytest.mark.asyncio
async def test_fetch_price_mocked(monkeypatch):
    monkeypatch.setattr(market_module.httpx, "AsyncClient", lambda **_kw: _Client())
    assert await market_module.fetch_price("BBCA") == Decimal("10250")


class _FailClient:
    async def get(self, _url, **_kw):
        raise ValueError("boom")

    async def aclose(self):
        pass


@pytest.mark.asyncio
async def test_fetch_price_unavailable(monkeypatch):
    monkeypatch.setattr(market_module.httpx, "AsyncClient", lambda **_kw: _FailClient())
    assert await market_module.fetch_price("XXXX") is None


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_refresh_endpoints_mocked(client, monkeypatch):
    async def fake_price(_symbol):
        return Decimal("11000")

    monkeypatch.setattr(holdings_route, "fetch_price", fake_price)
    monkeypatch.setattr(market_module, "fetch_price", fake_price)

    r = await client.get("/api/accounts")
    acc = r.json()[0]
    r = await client.post(
        "/api/holdings",
        json={
            "symbol": "BBCA",
            "units": 10,
            "cost_basis": 9000,
            "current_price": 9000,
            "currency": "IDR",
            "account_id": acc["id"],
        },
    )
    hid = r.json()["id"]
    r = await client.post(f"/api/holdings/{hid}/refresh")
    assert r.status_code == 200
    assert r.json()["current_price"] == "11000.00"
    r = await client.post("/api/holdings/refresh-all")
    assert r.status_code == 200
    assert r.json()[0]["current_price"] == "11000.00"
    r = await client.get("/api/holdings/market/lookup?symbol=bbca")
    assert r.status_code == 200
    assert r.json()["yahoo_symbol"] == "BBCA.JK"
    r = await client.post("/api/holdings/999999/refresh")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_refresh_unavailable_502(client, monkeypatch):
    async def fake_none(_symbol):
        return None

    monkeypatch.setattr(holdings_route, "fetch_price", fake_none)

    r = await client.get("/api/accounts")
    acc = r.json()[0]
    r = await client.post(
        "/api/holdings",
        json={
            "symbol": "ZZZ9",
            "units": 1,
            "cost_basis": 1,
            "current_price": 1,
            "currency": "IDR",
            "account_id": acc["id"],
        },
    )
    hid = r.json()["id"]
    r = await client.post(f"/api/holdings/{hid}/refresh")
    assert r.status_code == 502


@pytest.mark.asyncio
async def test_history_recorded_on_refresh(client, monkeypatch):
    prices = iter([Decimal("10000"), Decimal("10100")])

    async def fake_seq(_symbol):
        return next(prices)

    monkeypatch.setattr(holdings_route, "fetch_price", fake_seq)

    r = await client.get("/api/accounts")
    acc = r.json()[0]
    r = await client.post(
        "/api/holdings",
        json={
            "symbol": "BBCA",
            "units": 10,
            "cost_basis": 9000,
            "current_price": 9000,
            "currency": "IDR",
            "account_id": acc["id"],
        },
    )
    hid = r.json()["id"]
    await client.post(f"/api/holdings/{hid}/refresh")
    await client.post(f"/api/holdings/{hid}/refresh")
    r = await client.get(f"/api/holdings/{hid}/history?limit=10")
    assert r.status_code == 200
    pts = r.json()["points"]
    assert [p["price"] for p in pts] == [10000.0, 10100.0]
    r = await client.get("/api/holdings/999999/history")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_alert_center_flow(client, monkeypatch):
    async def fake_price(_symbol):
        return Decimal("120.0")

    monkeypatch.setattr(holdings_route, "fetch_price", fake_price)
    r = await client.get("/api/accounts")
    acc = r.json()[0]
    r = await client.post(
        "/api/holdings",
        json={
            "symbol": "AL2",
            "units": 1,
            "cost_basis": 100,
            "current_price": 100,
            "currency": "IDR",
            "account_id": acc["id"],
            "alert_above": 110,
        },
    )
    assert r.status_code == 201
    r = await client.post(f"/api/holdings/{r.json()['id']}/refresh")
    assert r.status_code == 200
    r = await client.get("/api/holdings/alerts/list")
    assert r.status_code == 200
    assert len(r.json()) >= 1
    assert all(
        a["direction"] == "above" for a in r.json() if a["holding_id"] == r.json()[0]["holding_id"]
    )
    r = await client.get("/api/holdings/alerts/unread-count")
    assert r.json()["unread"] >= 1
    aid = (await client.get("/api/holdings/alerts/list")).json()[0]["id"]
    r = await client.post(f"/api/holdings/alerts/{aid}/read")
    assert r.status_code == 200
    assert r.json()["is_read"] is True
    r = await client.post("/api/holdings/alerts/read-all")
    assert r.json()["marked"] >= 0
