"""Tests: statement reconciliation (match, mismatch, auto-mark)."""

import pytest
from httpx import ASGITransport, AsyncClient

from reign.api.app import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _seed_tx(client, acc_id, desc, amount, date):
    r = await client.post(
        "/api/transactions",
        json={
            "date": date,
            "description": desc,
            "amount": amount,
            "currency": "IDR",
            "account_id": acc_id,
        },
    )
    assert r.status_code == 201
    return r.json()


@pytest.mark.asyncio
async def test_reconcile_match_and_unmatched(client):
    r = await client.get("/api/accounts")
    acc = r.json()[0]
    await _seed_tx(client, acc["id"], "STARBUCKS COFFEE", -75000, "2026-04-15")
    csv_content = b"Tanggal,Keterangan,Mutasi\n15/04/2026,STARBUCKS,-75.000\n16/04/2026,UNKNOWN SHOP,-999999\n"
    r = await client.post(
        f"/api/transactions/reconcile-statement?account_id={acc['id']}",
        files={"file": ("stmt.csv", csv_content, "text/csv")},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["totals"]["matched"] == 1
    assert data["totals"]["unmatched"] == 1
    assert data["marked_reconciled"] == 0


@pytest.mark.asyncio
async def test_reconcile_auto_mark(client):
    r = await client.get("/api/accounts")
    acc = r.json()[0]
    tx = await _seed_tx(client, acc["id"], "KOPI KENANGAN", -20000, "2026-05-01")
    csv_content = b"Tanggal,Keterangan,Mutasi\n02/05/2026,KOPI KENANGAN,-20.000\n"
    r = await client.post(
        f"/api/transactions/reconcile-statement?account_id={acc['id']}&auto_mark=true",
        files={"file": ("stmt.csv", csv_content, "text/csv")},
    )
    assert r.status_code == 200
    assert r.json()["marked_reconciled"] == 1
    r = await client.get(f"/api/transactions/{tx['id']}")
    assert r.json()["is_reconciled"] is True


@pytest.mark.asyncio
async def test_reconcile_rejects(client):
    r = await client.post(
        "/api/transactions/reconcile-statement?account_id=1",
        files={"file": ("x.txt", b"nope", "text/plain")},
    )
    assert r.status_code == 400
    r = await client.post(
        "/api/transactions/reconcile-statement?account_id=999999",
        files={"file": ("s.csv", b"Tanggal,Keterangan,Mutasi\n", "text/csv")},
    )
    assert r.status_code == 404
    r = await client.post(
        "/api/transactions/reconcile-statement?account_id=1&tolerance_days=99",
        files={"file": ("s.csv", b"Tanggal,Keterangan,Mutasi\n", "text/csv")},
    )
    assert r.status_code == 400
