"""Tests: profile export/import (sync/copy between profiles)."""

import io
import json
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from reign.adapters.database import get_session_factory, init_db
from reign.api.app import app
from reign.api.routes import backup as backup_module
from reign.services.settings import set_setting


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_profile_export_shape(client):
    r = await client.get("/api/profiles/export")
    assert r.status_code == 200
    payload = r.json()
    assert payload["kind"] == "reign-profile"
    assert payload["profile"] == "default"
    assert "backup" in payload
    assert "accounts" in payload["backup"]


@pytest.mark.asyncio
async def test_profile_import_clones_data(client):
    r = await client.post(
        "/api/accounts",
        json={"name": "SYNC_SRC", "type": "cash", "currency": "IDR", "initial_balance": 0},
    )
    assert r.status_code == 201
    r = await client.post("/api/profiles/import", json={"slug": "syncdst"})
    assert r.status_code == 200
    body = r.json()
    assert body["from"] == "default"
    assert body["to"] == "syncdst"
    assert "snapshot" in body
    r = await client.get("/api/accounts", headers={"X-Reign-Profile": "syncdst"})
    assert any(a["name"] == "SYNC_SRC" for a in r.json())


@pytest.mark.asyncio
async def test_profile_import_rejects(client):
    r = await client.post("/api/profiles/import", json={"slug": "BAD!!"})
    assert r.status_code == 400
    r = await client.post("/api/profiles/import", json={"slug": "default"})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_backup_history_lists_archives(client, tmp_path, monkeypatch):
    monkeypatch.setenv("REIGN_DATA_DIR", str(tmp_path))
    r = await client.get("/api/backup/history", headers={"X-Reign-Profile": "hist1"})
    assert r.status_code == 200
    assert r.json() == []
    r = await client.post("/api/profiles", json={"slug": "hist1"})
    assert r.status_code in (200, 201)
    payload = json.dumps({"accounts": [], "categories": [], "transactions": []}).encode()
    r = await client.post(
        "/api/restore",
        headers={"X-Reign-Profile": "hist1"},
        files={"file": ("b.json", io.BytesIO(payload), "application/json")},
    )
    assert r.status_code == 200
    r = await client.get("/api/backup/history", headers={"X-Reign-Profile": "hist1"})
    names = [x["name"] for x in r.json()]
    assert any(n.startswith("reign_prerestore_") for n in names)


@pytest.mark.asyncio
async def test_run_backup_cycle_skips_when_disabled(client):
    assert await backup_module.run_backup_cycle("cycle-disabled-1") is None


@pytest.mark.asyncio
async def test_run_backup_cycle_creates_then_skips_same_day(client, tmp_path, monkeypatch):
    monkeypatch.setenv("REIGN_DATA_DIR", str(tmp_path))
    slug = "cycle1"
    await init_db(slug)
    async with get_session_factory(slug)() as s:
        await set_setting(s, "auto_backup_enabled", "true")
        await set_setting(s, "auto_backup_interval_days", "1")
    first = await backup_module.run_backup_cycle(slug)
    assert first is not None
    assert Path(first).name.startswith("reign_auto_")
    assert await backup_module.run_backup_cycle(slug) is None
