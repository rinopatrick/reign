"""Integration: transfer + backup round-trip."""

import io
import json
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
async def test_transfer_and_backup_roundtrip(client):
    r = await client.post(
        "/api/accounts",
        json={"name": "A", "type": "cash", "currency": "IDR", "initial_balance": 0},
    )
    assert r.status_code == 201
    acc_a = r.json()
    r = await client.post(
        "/api/accounts",
        json={"name": "B", "type": "checking", "currency": "IDR", "initial_balance": 0},
    )
    assert r.status_code == 201
    acc_b = r.json()

    today = datetime.now().strftime("%Y-%m-%d")
    r = await client.post(
        "/api/transactions/transfer",
        json={
            "from_account_id": acc_a["id"],
            "to_account_id": acc_b["id"],
            "amount": 100000,
            "currency": "IDR",
            "date": today,
        },
    )
    assert r.status_code == 201

    r = await client.get("/api/backup")
    assert r.status_code == 200
    data = r.json()
    assert any(a["name"] == "A" for a in data["accounts"])
    assert len(data["transactions"]) >= 2

    payload = json.dumps(data).encode()
    r = await client.post(
        "/api/restore", files={"file": ("backup.json", io.BytesIO(payload), "application/json")}
    )
    assert r.status_code == 200
    assert r.json()["transactions"] >= 2


@pytest.mark.asyncio
async def test_import_preview_is_read_only(client):
    r = await client.get("/api/accounts")
    acc = r.json()[0]
    csv_body = "Tanggal,Keterangan,Mutasi\n15/04/2026,STARBUCKS JAKARTA,-75000\n"
    r = await client.post(
        "/api/transactions/import/preview",
        params={"account_id": acc["id"]},
        files={"file": ("bca.csv", io.BytesIO(csv_body.encode()), "text/csv")},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["format"] in ("bca", "generic")
    assert data["total"] == 1
    assert data["preview"][0]["description"] == "STARBUCKS JAKARTA"
    r = await client.get("/api/transactions?limit=100")
    assert all(t["description"] != "STARBUCKS JAKARTA" for t in r.json())
