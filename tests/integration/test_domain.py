"""Domain: net-worth, calendar months, recurring forecast, 1-query budgets."""

import io
from datetime import datetime
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from pypdf import PdfReader

from reign.api.app import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_net_worth_includes_transactions(client):
    r = await client.post(
        "/api/accounts",
        json={"name": "NW", "type": "cash", "currency": "IDR", "initial_balance": 100000},
    )
    assert r.status_code == 201
    acc = r.json()
    today = datetime.now().strftime("%Y-%m-%d")
    r = await client.post(
        "/api/transactions",
        json={
            "date": today,
            "description": "EXP",
            "amount": -25000,
            "currency": "IDR",
            "account_id": acc["id"],
        },
    )
    assert r.status_code == 201
    r = await client.get("/api/dashboard/summary?currency=IDR")
    assert r.status_code == 200
    summary = r.json()
    assert float(summary["total_balance"]) == 75000.0


@pytest.mark.asyncio
async def test_trends_calendar_labels(client):
    r = await client.get("/api/dashboard/trends?months=3&currency=IDR")
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 3
    assert len({(x["year"], x["month"]) for x in rows}) == 3


@pytest.mark.asyncio
async def test_forecast_projects_recurring_future(client):
    r = await client.get("/api/accounts")
    acc = next(a for a in r.json() if a["name"] == "Cash")
    r = await client.post(
        "/api/recurring",
        json={
            "description": "SALARY",
            "amount": 5000000,
            "currency": "IDR",
            "day_of_month": 1,
            "account_id": acc["id"],
            "active": True,
        },
    )
    assert r.status_code == 201
    r = await client.get("/api/forecast?currency=IDR")
    assert r.status_code == 200
    data = r.json()
    assert len(data["months"]) == 3
    assert float(data["months"][0]["income"]) >= 5000000.0


@pytest.mark.asyncio
async def test_budgets_spent_single_query(client):
    now = datetime.now()
    r = await client.get("/api/categories")
    food = next(c for c in r.json() if c["name"] == "Food")
    r = await client.post(
        "/api/budgets",
        json={
            "year": now.year,
            "month": now.month,
            "amount": 1000000,
            "currency": "IDR",
            "category_id": food["id"],
        },
    )
    assert r.status_code == 201
    r = await client.get(f"/api/budgets?year={now.year}&month={now.month}")
    assert r.status_code == 200
    rows = r.json()
    assert any(x["category"]["id"] == food["id"] and float(x["spent"]) >= 0 for x in rows)


@pytest.mark.asyncio
async def test_cursor_pagination(client):
    r = await client.get("/api/transactions?limit=1")
    assert r.status_code == 200
    first = r.json()
    assert len(first) <= 1
    if first:
        last_id = first[-1]["id"]
        r = await client.get(f"/api/transactions?limit=1&after_id={last_id}")
        assert r.status_code == 200
        nxt = r.json()
        assert all(x["id"] < last_id for x in nxt)


@pytest.mark.asyncio
async def test_sankey_consistent_with_summary(client):
    r = await client.get("/api/reports/sankey")
    assert r.status_code == 200
    data = r.json()
    assert Decimal(data["total_in"]) >= 0
    assert Decimal(data["total_out"]) >= 0
    out_links = sum(Decimal(x["value"]) for x in data["links"] if x["target"].startswith("out:"))
    assert out_links == Decimal(data["total_out"])
    node_ids = {n["id"] for n in data["nodes"]}
    for link in data["links"]:
        assert link["source"] in node_ids
        assert link["target"] in node_ids


@pytest.mark.asyncio
async def test_sankey_pdf_readable(client):
    r = await client.get("/api/reports/sankey/pdf")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/pdf")
    text = PdfReader(io.BytesIO(r.content)).pages[0].extract_text()
    assert "Pemasukan" in text


@pytest.mark.asyncio
async def test_sankey_pdf_english(client):
    r = await client.get("/api/reports/sankey/pdf?lang=en")
    assert r.status_code == 200
    assert (
        "sankey_" in r.headers["content-disposition"]
        and "_en.pdf" in r.headers["content-disposition"]
    )
    text = PdfReader(io.BytesIO(r.content)).pages[0].extract_text()
    assert "From" in text and "To" in text and "Monthly Report" in text


@pytest.mark.asyncio
async def test_sankey_links_carry_drilldown_ids(client):
    r = await client.get("/api/reports/sankey")
    assert r.status_code == 200
    data = r.json()
    for link in data["links"]:
        if link["target"].startswith("out:"):
            assert link.get("category_id") is not None
            assert link.get("category") == link["target"][4:]
            tx = await client.get(f"/api/transactions?category_id={link['category_id']}&limit=5")
            assert tx.status_code == 200


@pytest.mark.asyncio
async def test_sankey_income_links_carry_drilldown_ids(client):
    r = await client.get("/api/reports/sankey")
    assert r.status_code == 200
    data = r.json()
    for link in data["links"]:
        if link["target"].startswith("in:"):
            assert link.get("category_id") is not None
            assert link.get("category") == link["target"][3:]


@pytest.mark.asyncio
async def test_sankey_saved_carries_breakdown(client):
    r = await client.get("/api/reports/sankey")
    assert r.status_code == 200
    data = r.json()
    saved = [x for x in data["links"] if x["target"] == "saved"]
    if Decimal(data["total_in"]) > Decimal(data["total_out"]):
        assert len(saved) == 1
        bd = saved[0]["breakdown"]
        assert sum(Decimal(x["value"]) for x in bd["income"]) == Decimal(data["total_in"])
        assert sum(Decimal(x["value"]) for x in bd["expense"]) == Decimal(data["total_out"])
    else:
        assert saved == []


@pytest.mark.asyncio
async def test_drilldown_csv_matches_filter(client):
    r = await client.get("/api/reports/drilldown.csv")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    lines = r.text.strip().splitlines()
    assert lines[0] == "id,date,description,amount,currency,category,account_id"
    r = await client.get("/api/reports/sankey")
    out = [x for x in r.json()["links"] if x["target"].startswith("out:") and x.get("category_id")]
    if out:
        cid = out[0]["category_id"]
        r = await client.get(f"/api/reports/drilldown.csv?category_id={cid}")
        assert r.status_code == 200
        body = r.text.strip().splitlines()
        assert body[0].startswith("id,date,")
