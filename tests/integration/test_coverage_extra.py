"""Coverage: goals + recurring CRUD, settings allowlist, reports, backup trigger."""

from datetime import datetime

import pytest
from httpx import ASGITransport, AsyncClient

from reign.adapters.database import AsyncSessionLocal
from reign.api.app import app
from reign.domain.models import Transaction
from reign.services.categorizer import categorize_transactions
from reign.services.settings import get_setting, set_setting


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_goals_crud_and_404(client):
    r = await client.post(
        "/api/goals",
        json={"name": "G", "target_amount": 1000, "currency": "IDR"},
    )
    assert r.status_code == 201
    gid = r.json()["id"]
    r = await client.get("/api/goals")
    assert any(g["id"] == gid for g in r.json())
    r = await client.delete(f"/api/goals/{gid}")
    assert r.status_code == 200
    r = await client.delete("/api/goals/999999")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_recurring_crud_and_fk_404(client):
    r = await client.get("/api/accounts")
    acc = r.json()[0]
    r = await client.post(
        "/api/recurring",
        json={
            "description": "R",
            "amount": -5000,
            "currency": "IDR",
            "day_of_month": 1,
            "account_id": acc["id"],
        },
    )
    assert r.status_code == 201
    rid = r.json()["id"]
    r = await client.get("/api/recurring")
    assert any(x["id"] == rid for x in r.json())
    r = await client.post(
        "/api/recurring",
        json={
            "description": "BAD",
            "amount": 1,
            "currency": "IDR",
            "day_of_month": 1,
            "account_id": 999999,
        },
    )
    assert r.status_code == 404
    r = await client.delete(f"/api/recurring/{rid}")
    assert r.status_code == 200
    r = await client.delete("/api/recurring/999999")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_settings_allowlist_and_service(client):
    r = await client.get("/api/settings")
    assert r.status_code == 200
    r = await client.put("/api/settings/nope", json={"value": "x"})
    assert r.status_code == 400
    r = await client.put("/api/settings/theme", json={"value": "x" * 300})
    assert r.status_code == 400
    r = await client.put("/api/settings/theme", json={"value": "dark"})
    assert r.status_code == 200
    r = await client.get("/api/settings/theme")
    assert r.json()["value"] == "dark"
    async with AsyncSessionLocal() as s:
        assert await get_setting(s, "theme") == "dark"
        await set_setting(s, "theme", "light")
        assert await get_setting(s, "theme") == "light"


@pytest.mark.asyncio
async def test_reports_monthly_and_backup_trigger(client):
    now = datetime.now()
    r = await client.get(f"/api/reports/monthly?year={now.year}&month={now.month}&currency=IDR")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/pdf")
    r = await client.post("/api/backup/trigger")
    assert r.status_code == 200
    assert "message" in r.json()


@pytest.mark.asyncio
async def test_categorizer_skips_categorized():
    tx = Transaction(
        date=datetime.now().date(),
        description="STARBUCKS",
        amount=-1,
        currency="IDR",
        account_id=1,
        category_id=5,
    )
    async with AsyncSessionLocal() as s:
        await categorize_transactions(s, [tx])
    assert tx.category_id == 5


@pytest.mark.asyncio
async def test_reports_pdf_has_profile_header(client):
    now = datetime.now()
    r = await client.get(
        f"/api/reports/monthly?year={now.year}&month={now.month}&currency=IDR",
        headers={"X-Reign-Profile": "kantor"},
    )
    assert r.status_code == 200
    assert r.headers["content-disposition"].startswith("attachment; filename=report_kantor_")
    assert r.content[:5] == b"%PDF-"
