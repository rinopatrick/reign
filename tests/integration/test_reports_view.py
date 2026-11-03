"""Reports view: nav entry + renderReports wiring (v160)."""

import pytest
from httpx import ASGITransport, AsyncClient

from reign.api.app import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_reports_nav_present(client):
    r = await client.get("/")
    assert r.status_code == 200
    assert 'id="nav-reports"' in r.text
    assert "navigate('reports')" in r.text


@pytest.mark.asyncio
async def test_reports_view_wired(client):
    js = (await client.get("/static/app.js")).text
    assert "function renderReports" in js
    assert "'reports'" in js or '"reports"' in js
    assert "/api/reports/sankey" in js


@pytest.mark.asyncio
async def test_reports_period_change_refreshes_sankey(client):
    js = (await client.get("/static/app.js")).text
    assert "reports-month" in js and "reports-year" in js
    assert "onReportsPeriodChange" in js
    # Period change must refresh Sankey JSON (reused renderSankey path).
    idx = js.index("function onReportsPeriodChange")
    body = js[idx : idx + 600]
    assert "renderSankey()" in body
    assert "/api/reports/sankey" in js


@pytest.mark.asyncio
async def test_reports_period_single_source_of_truth(client):
    """One shared reportPeriod state drives Sankey JSON, CSV href, and monthly PDF href."""
    js = (await client.get("/static/app.js")).text
    assert "function reportPeriod" in js
    body = js[js.index("function reportPeriod") : js.index("function reportPeriod") + 800]
    assert "reports-month" in body and "reports-year" in body
    # Every consumer reads the one state, nobody reads selects directly.
    for consumer in ("renderSankey", "downloadDrilldownCsv", "downloadMonthlyPdf"):
        idx = js.index(f"function {consumer}")
        assert "reportPeriod()" in js[idx : idx + 600]
    assert "function sankeyPeriod" not in js
