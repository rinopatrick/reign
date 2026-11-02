"""Unit tests: uploads, settings service, pdf generator, period edges."""

from decimal import Decimal

import pytest
from fastapi import HTTPException

from reign.domain.period import Period
from reign.services.pdf_generator import MonthlyReportInput, generate_monthly_report
from reign.services.uploads import read_limited_upload


class FakeUpload:
    def __init__(self, chunks: list[bytes]):
        self._chunks = list(chunks)

    async def read(self, _size: int = -1):
        if not self._chunks:
            return b""
        return self._chunks.pop(0)


@pytest.mark.asyncio
async def test_read_limited_upload_ok():
    data = await read_limited_upload(FakeUpload([b"ab", b"cd", b""]), 10, "X")
    assert data == b"abcd"


@pytest.mark.asyncio
async def test_read_limited_upload_413():
    with pytest.raises(HTTPException) as ei:
        await read_limited_upload(FakeUpload([b"123456"]), 5, "CSV")
    assert ei.value.status_code == 413


def test_generate_monthly_report_pdf_bytes():
    pdf = generate_monthly_report(
        MonthlyReportInput(
            year=2026,
            month=11,
            summary={"income": Decimal("100"), "expense": Decimal("-40"), "net": Decimal("60")},
            category_totals=[("Food", Decimal("-40"))],
        )
    )
    assert pdf[:5] == b"%PDF-"


def test_generate_monthly_report_empty_categories():
    pdf = generate_monthly_report(MonthlyReportInput(year=2026, month=1, currency="USD"))
    assert pdf[:5] == b"%PDF-"


def test_period_add_months_year_boundary():
    p = Period(year=2026, month=12, currency="IDR")
    nxt = p.add_months(1)
    assert (nxt.year, nxt.month) == (2027, 1)
    prev = p.add_months(-12)
    assert (prev.year, prev.month) == (2025, 12)


def test_period_invalid_rejected():
    with pytest.raises(ValueError):
        Period(year=2026, month=13)
    with pytest.raises(ValueError):
        Period.from_raw(2026, 0, "IDR")
    with pytest.raises(ValueError):
        Period.from_raw(2026, 1, "XXX")
