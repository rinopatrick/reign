"""Security: CORS, upload limits, FK 404, restore dry-run + snapshot."""

import io
import json

import pytest
from httpx import ASGITransport, AsyncClient

from reign.api.app import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_cors_rejects_foreign_origin(client):
    r = await client.get("/health", headers={"Origin": "http://evil.test"})
    assert "access-control-allow-origin" not in {k.lower() for k in r.headers}


@pytest.mark.asyncio
async def test_cors_allows_localhost(client):
    r = await client.get("/health", headers={"Origin": "http://localhost:8000"})
    assert r.headers.get("access-control-allow-origin") == "http://localhost:8000"


@pytest.mark.asyncio
async def test_transaction_fk_404(client):
    r = await client.post(
        "/api/transactions",
        json={
            "date": "2026-11-01",
            "description": "NOPE",
            "amount": -1000,
            "currency": "IDR",
            "account_id": 999999,
        },
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_import_fk_404(client):
    csv_content = b"Tanggal,Keterangan,Mutasi\n15/04/2026,X,-1000\n"
    r = await client.post(
        "/api/transactions/import?account_id=999999",
        files={"file": ("test.csv", csv_content, "text/csv")},
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_import_rejects_non_csv(client):
    r = await client.post(
        "/api/transactions/import?account_id=1",
        files={"file": ("evil.exe", b"MZ", "application/octet-stream")},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_import_rejects_oversize(client):
    big = b"Tanggal,Keterangan,Mutasi\n" + b"15/04/2026,X,-1000\n" * 300000
    r = await client.post(
        "/api/transactions/import?account_id=1",
        files={"file": ("big.csv", io.BytesIO(big), "text/csv")},
    )
    assert r.status_code == 413


@pytest.mark.asyncio
async def test_restore_rejects_bad_json(client):
    r = await client.post(
        "/api/restore", files={"file": ("bad.json", b"not json", "application/json")}
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_restore_rejects_bad_fk(client):
    bad = {"accounts": [], "categories": [], "transactions": [{"id": 1, "date": "2026-01-01", "description": "X", "amount": 1, "account_id": 999}]}
    r = await client.post(
        "/api/restore",
        files={"file": ("bad.json", io.BytesIO(json.dumps(bad).encode()), "application/json")},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_restore_dry_run_and_snapshot(client):
    r = await client.get("/api/backup")
    assert r.status_code == 200
    data = r.json()
    assert "budgets" in data and "recurring" in data and "splits" in data
    payload = json.dumps(data).encode()
    r = await client.post(
        "/api/restore?dry_run=true",
        files={"file": ("b.json", io.BytesIO(payload), "application/json")},
    )
    assert r.status_code == 200
    assert r.json()["message"] == "Dry run OK"
    r = await client.post(
        "/api/restore",
        files={"file": ("b.json", io.BytesIO(payload), "application/json")},
    )
    assert r.status_code == 200
    assert "snapshot" in r.json()
