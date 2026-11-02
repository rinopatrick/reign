"""Tests: market price mapping + refresh endpoints (mocked network)."""

import urllib.request
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

import reign.api.routes.holdings as holdings_route
import reign.config
import reign.services.market as market_module
from reign.api.app import app
from reign.services import notify as notify_module
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


@pytest.mark.asyncio
async def test_notify_channels_off_by_default(monkeypatch):
    monkeypatch.setattr(reign.config.settings, "alert_smtp_host", "", raising=False)
    monkeypatch.setattr(reign.config.settings, "alert_webhook_url", "", raising=False)
    assert notify_module.smtp_configured() is False
    assert notify_module.webhook_configured() is False
    assert notify_module.notify_email("t", "b") is False
    assert notify_module.notify_webhook("t", "b") is False
    result = notify_module.notify_alert_fired("BBCA", "above", 1, 2, 3)
    assert result == {"email": False, "webhook": False}


@pytest.mark.asyncio
async def test_notify_webhook_success(monkeypatch):
    monkeypatch.setattr(reign.config.settings, "alert_webhook_url", "http://x/hook", raising=False)

    class FakeResp:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(urllib.request, "urlopen", lambda _req, **_kw: FakeResp())
    assert notify_module.notify_webhook("t", "b") is True


@pytest.mark.asyncio
async def test_fetch_price_live_or_skip():
    """Live Yahoo Finance check; skipped gracefully when offline/blocked."""
    pytest.importorskip("httpx")
    try:
        price = await market_module.fetch_price("BBCA")
    except Exception:
        pytest.skip("network unavailable for live price check")
    if price is None:
        pytest.skip("Yahoo Finance blocked or symbol unknown")
    assert price > 0
