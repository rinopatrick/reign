"""Tests: investment holdings CRUD + valuation."""

import io

import pytest
from httpx import ASGITransport, AsyncClient
from pypdf import PdfReader

from reign.api.app import app
from reign.services import notify as notify_module


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


@pytest.mark.asyncio
async def test_allocation_sums_to_total(client):
    r = await client.get("/api/accounts")
    acc = r.json()[0]
    for sym, units, price in (("AA", 1, 100), ("BB", 3, 100)):
        r = await client.post(
            "/api/holdings",
            json={
                "symbol": sym,
                "units": units,
                "cost_basis": 1,
                "current_price": price,
                "currency": "IDR",
                "account_id": acc["id"],
            },
        )
        assert r.status_code == 201
    r = await client.get("/api/holdings/allocation")
    assert r.status_code == 200
    data = r.json()
    mine = {s["symbol"]: s for s in data["slices"] if s["symbol"] in ("AA", "BB")}
    assert set(mine) == {"AA", "BB"}
    assert float(mine["AA"]["value"]) + float(mine["BB"]["value"]) == 400.0
    assert mine["BB"]["weight"] / mine["AA"]["weight"] == pytest.approx(3.0)


@pytest.mark.asyncio
async def test_holdings_pdf_report(client):
    r = await client.get("/api/reports/holdings")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/pdf")
    assert "holdings_default" in r.headers["content-disposition"]
    assert r.content[:5] == b"%PDF-"


@pytest.mark.asyncio
async def test_push_vapid_key_unconfigured(client, monkeypatch):
    monkeypatch.setattr("reign.api.routes.holdings.vapid_configured", lambda: False)
    r = await client.get("/api/holdings/push/vapid-key")
    assert r.status_code == 200
    assert r.json()["configured"] is False


@pytest.mark.asyncio
async def test_push_subscribe_roundtrip(client):
    sub = {
        "endpoint": "https://push.example/abc123",
        "p256dh": "cDI1NmRoLWtleQ",
        "auth": "YXV0aC1rZXk",
    }
    r = await client.post("/api/holdings/push/subscribe", json=sub)
    assert r.status_code == 200
    r = await client.post("/api/holdings/push/unsubscribe", json=sub)
    assert r.status_code == 200
    assert r.json()["message"] == "Push subscription removed"


@pytest.mark.asyncio
async def test_push_noop_without_vapid(monkeypatch):
    monkeypatch.setattr(notify_module.settings, "vapid_private_key", "")
    monkeypatch.setattr(notify_module.settings, "vapid_public_key", "")
    assert notify_module.vapid_configured() is False

    class FakeSession:
        async def execute(self, *_args, **_kwargs):
            raise AssertionError("must not query DB without VAPID")

    assert await notify_module.send_push_alerts(FakeSession(), "t", "b") == 0
    assert notify_module.send_webpush("e", "p", "a", "t", "b") is False


@pytest.mark.asyncio
async def test_push_send_mocked(monkeypatch):
    monkeypatch.setattr(notify_module.settings, "vapid_private_key", "priv")
    monkeypatch.setattr(notify_module.settings, "vapid_public_key", "pub")
    calls = []

    class FakeSub:
        endpoint = "https://push.example/x"
        p256dh = "p"
        auth = "a"

    class FakeResult:
        def scalars(self):
            class S:
                def all(self):
                    return [FakeSub()]

            return S()

    class FakeSession:
        async def execute(self, *_args, **_kwargs):
            return FakeResult()

    monkeypatch.setattr(notify_module, "send_webpush", lambda *a: calls.append(a) or True)
    assert await notify_module.send_push_alerts(FakeSession(), "t", "b") == 1
    assert calls


@pytest.mark.asyncio
async def test_holdings_pdf_bilingual(client):
    for lang, marker in (("id", "Portofolio"), ("en", "Portfolio")):
        r = await client.get(f"/api/reports/holdings?lang={lang}")
        assert r.status_code == 200
        text = PdfReader(io.BytesIO(r.content)).pages[0].extract_text()
        assert marker in text
