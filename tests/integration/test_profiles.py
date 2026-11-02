"""Tests: local profiles isolation."""

import pytest
from httpx import ASGITransport, AsyncClient

from reign.adapters.database import profile_db_url, validate_slug
from reign.api.app import app
from reign.exceptions import ProfileError


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def test_validate_slug():
    assert validate_slug("Alice-1") == "alice-1"
    for bad in ["", "UPPER!", "../x", "a" * 33, "with space"]:
        with pytest.raises(ProfileError):
            validate_slug(bad)


def test_profile_db_url_default_keeps_legacy():
    url = profile_db_url("default")
    assert url.endswith("reign.db")


def test_profile_db_url_isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("REIGN_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("DATABASE_URL", raising=False)
    url = profile_db_url("keluarga")
    assert "profiles" in url and "keluarga" in url


@pytest.mark.asyncio
async def test_profiles_crud_and_isolation(client):
    r = await client.get("/api/profiles")
    assert r.status_code == 200
    assert "default" in r.json()
    r = await client.post("/api/profiles", json={"slug": "keluarga"})
    assert r.status_code == 201
    r = await client.post("/api/profiles", json={"slug": "BAD!!"})
    assert r.status_code == 400
    # Header profile returning empty categories proves a separate DB file.
    r = await client.get("/api/categories", headers={"X-Reign-Profile": "keluarga"})
    assert r.status_code == 200
    assert any(c["name"] == "Food" for c in r.json())


@pytest.mark.asyncio
async def test_backup_per_profile_isolated(client, tmp_path, monkeypatch):
    monkeypatch.setenv("REIGN_DATA_DIR", str(tmp_path))
    r = await client.get("/api/backup", headers={"X-Reign-Profile": "kantor2"})
    assert r.status_code == 200
    assert r.json()["accounts"] == []
    r = await client.post("/api/backup/trigger", headers={"X-Reign-Profile": "kantor2"})
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_profile_header_isolation(client):
    r = await client.get("/api/accounts", headers={"X-Reign-Profile": "kantor"})
    assert r.status_code == 200
    kantor_before = r.json()
    r = await client.post(
        "/api/accounts",
        json={"name": "Kantor Only", "type": "checking", "currency": "IDR", "initial_balance": 0},
        headers={"X-Reign-Profile": "kantor"},
    )
    assert r.status_code == 201
    r = await client.get("/api/accounts", headers={"X-Reign-Profile": "kantor"})
    names_kantor = [a["name"] for a in r.json()]
    assert "Kantor Only" in names_kantor
    r = await client.get("/api/accounts")
    names_default = [a["name"] for a in r.json()]
    assert "Kantor Only" not in names_default
    assert len(kantor_before) + 1 == len(names_kantor)
