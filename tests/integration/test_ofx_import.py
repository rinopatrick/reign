"""Tests: OFX/QFX parser + import/preview routes."""

import pytest
from httpx import ASGITransport, AsyncClient

from reign.api.app import app
from reign.exceptions import CSVParseError
from reign.services.ofx_parser import parse_ofx

OFX_SAMPLE = b"""OFXHEADER:100
DATA:OFXSGML
VERSION:102
SECURITY:NONE
ENCODING:USASCII
CHARSET:1252
COMPRESSION:NONE
OLDFILEUID:NONE
NEWFILEUID:NONE

<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS>
<BANKACCTFROM><BANKID>001</BANKID><ACCTID>123</ACCTID><ACCTTYPE>CHECKING</ACCTTYPE></BANKACCTFROM>
<BANKTRANLIST><DTSTART>20260101</DTSTART><DTEND>20260430</DTEND>
<STMTTRN><TRNTYPE>DEBIT</TRNTYPE><DTPOSTED>20260415</DTPOSTED><TRNAMT>-75000</TRNAMT><FITID>1</FITID><NAME>STARBUCKS</NAME></STMTTRN>
<STMTTRN><TRNTYPE>CREDIT</TRNTYPE><DTPOSTED>20260416</DTPOSTED><TRNAMT>15000000</TRNAMT><FITID>2</FITID><NAME>SALARY</NAME></STMTTRN>
</BANKTRANLIST></STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>
"""


def test_parse_ofx():
    fmt, rows = parse_ofx(OFX_SAMPLE)
    assert fmt == "ofx"
    assert len(rows) == 2
    assert rows[0]["description"] == "STARBUCKS"
    assert rows[1]["amount"] > 0


def test_parse_ofx_invalid_raises():
    with pytest.raises(CSVParseError):
        parse_ofx(b"not an ofx file")


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_ofx_preview_and_import(client):
    r = await client.get("/api/accounts")
    acc = next(a for a in r.json() if a["name"] == "Cash")
    r = await client.post(
        "/api/transactions/import-ofx-preview",
        files={"file": ("stmt.ofx", OFX_SAMPLE, "application/x-ofx")},
    )
    assert r.status_code == 200
    assert r.json()["total"] == 2
    r = await client.post(
        f"/api/transactions/import-ofx?account_id={acc['id']}",
        files={"file": ("stmt.ofx", OFX_SAMPLE, "application/x-ofx")},
    )
    assert r.status_code == 200
    assert r.json()["imported"] == 2


@pytest.mark.asyncio
async def test_ofx_rejects_non_ofx(client):
    r = await client.post(
        "/api/transactions/import-ofx?account_id=1",
        files={"file": ("x.csv", b"a,b\n1,2", "text/csv")},
    )
    assert r.status_code == 400
