"""Tests: profile export/import (sync/copy between profiles)."""

import pytest
from httpx import ASGITransport, AsyncClient

from reign.api.app import app


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
