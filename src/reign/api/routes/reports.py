"""Report generation routes."""

import asyncio
import csv
import dataclasses
import io
from datetime import date, datetime
from decimal import Decimal
from io import BytesIO

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from reign.adapters.database import get_session_factory, validate_slug
from reign.adapters.repository import (
    HoldingRepository,
    TransactionListFilter,
    TransactionRepository,
)
from reign.api.routes.profiles import profile_session
from reign.domain.period import Period
from reign.services.pdf_generator import (
    MonthlyReportInput,
    generate_holdings_report,
    generate_monthly_report,
    generate_sankey_report,
)

router = APIRouter()


@dataclasses.dataclass
class MonthlyParams:
    """Bundled monthly-report query params (keeps the endpoint signature small)."""

    year: int | None = None
    month: int | None = None
    currency: str = "IDR"
    lang: str = "id"


@router.get("/monthly")
async def monthly_report(
    request: Request,
    params: MonthlyParams = Depends(),
    session: AsyncSession = Depends(profile_session),
):
    profile = validate_slug(request.headers.get("x-reign-profile", "") or "default")
    now = datetime.now()
    year = params.year or now.year
    month = params.month or now.month
    currency = params.currency
    lang = params.lang if params.lang in ("id", "en") else "id"

    tx_repo = TransactionRepository(session)
    summary = await tx_repo.get_summary(year, month, currency)
    category_rows = await tx_repo.get_category_totals(year, month, currency)

    pdf_bytes = generate_monthly_report(
        MonthlyReportInput(
            year=year,
            month=month,
            currency=currency,
            summary=summary,
            category_totals=category_rows,
            profile=profile,
            lang=lang,
        )
    )

    filename = f"report_{profile}_{year}{month:02d}_{currency}_{lang}.pdf"
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


_SANKEY_CACHE: dict[tuple, tuple] = {}
_SANKEY_VERSION: dict[str, int] = {}


def bump_sankey_cache(profile: str) -> None:
    """Invalidate cached Sankey payloads for one profile."""
    _SANKEY_VERSION[profile] = _SANKEY_VERSION.get(profile, 0) + 1


def _neighbor_months(year: int, month: int) -> list[tuple[int, int]]:
    """Previous and next calendar months for prefetch."""
    base = Period(year=year, month=month)
    prev = base.add_months(-1)
    nxt = base.add_months(1)
    return [(prev.year, prev.month), (nxt.year, nxt.month)]


async def _prefetch_neighbors(
    slug: str, year: int, month: int, currency: str, version: int
) -> None:
    """Fill the cache for neighbor months. Never raises. Own session per prefetch."""
    try:
        for y, m in _neighbor_months(year, month):
            key = (slug, y, m, currency, version)
            if key in _SANKEY_CACHE:
                continue
            async with get_session_factory(slug)() as session:
                _SANKEY_CACHE[key] = await _compute_sankey(session, y, m, currency)
    except Exception:  # noqa: S110 — best-effort warmup only
        pass


@router.get("/sankey")
async def sankey(
    request: Request,
    year: int | None = None,
    month: int | None = None,
    currency: str = "IDR",
    session: AsyncSession = Depends(profile_session),
):
    """Cash-flow Sankey nodes/links: income categories -> expense categories + remainder."""
    slug = validate_slug(request.headers.get("x-reign-profile", "") or "default")
    now = datetime.now()
    year = year or now.year
    month = month or now.month
    version = _SANKEY_VERSION.get(slug, 0)
    key = (slug, year, month, currency, version)
    if key in _SANKEY_CACHE:
        return JSONResponse(content=_SANKEY_CACHE[key], headers={"X-Cache": "HIT"})
    data = await _compute_sankey(session, year, month, currency)
    _SANKEY_CACHE[key] = data
    prefetch_task = asyncio.create_task(_prefetch_neighbors(slug, year, month, currency, version))
    prefetch_task.add_done_callback(lambda t: t.exception())
    return JSONResponse(content=data, headers={"X-Cache": "MISS"})


async def _compute_sankey(session: AsyncSession, year: int, month: int, currency: str) -> dict:
    """Uncached Sankey payload (shared by the endpoint and the PDF export)."""
    tx_repo = TransactionRepository(session)
    income_cats = await tx_repo.get_income_by_category(year, month, currency)
    expense_cats = await tx_repo.get_category_totals(year, month, currency)
    cat_ids = await tx_repo.get_category_id_map()
    total_in = sum((Decimal(str(v)) for _, v in income_cats), Decimal("0"))
    total_out = sum((abs(Decimal(str(v))) for _, v in expense_cats), Decimal("0"))
    remainder = total_in - total_out
    nodes = [{"id": "income", "label": "Pemasukan"}]
    nodes += [{"id": f"in:{name}", "label": name} for name, _ in income_cats]
    nodes += [{"id": f"out:{name}", "label": name} for name, _ in expense_cats]
    if remainder > 0:
        nodes.append({"id": "saved", "label": "Sisa"})
    links = [
        {
            "source": "income",
            "target": f"in:{name}",
            "value": str(Decimal(str(v))),
            "category_id": cat_ids.get(name),
            "category": name,
        }
        for name, v in income_cats
    ]
    links += [
        {
            "source": "income",
            "target": f"out:{name}",
            "value": str(abs(Decimal(str(v)))),
            "category_id": cat_ids.get(name),
            "category": name,
        }
        for name, v in expense_cats
    ]
    if remainder > 0:
        links.append(
            {
                "source": "income",
                "target": "saved",
                "value": str(remainder),
                "breakdown": {
                    "income": [
                        {"category": name, "value": str(Decimal(str(v)))} for name, v in income_cats
                    ],
                    "expense": [
                        {"category": name, "value": str(abs(Decimal(str(v))))}
                        for name, v in expense_cats
                    ],
                },
            }
        )
    return {
        "year": year,
        "month": month,
        "currency": currency,
        "total_in": str(total_in),
        "total_out": str(total_out),
        "nodes": nodes,
        "links": links,
    }


@router.get("/sankey/pdf")
async def sankey_pdf(
    year: int | None = None,
    month: int | None = None,
    currency: str = "IDR",
    lang: str = "id",
    session: AsyncSession = Depends(profile_session),
):
    """Sankey cash-flow PDF for the active month."""
    now = datetime.now()
    data = await _compute_sankey(session, year or now.year, month or now.month, currency)
    pdf_bytes = generate_sankey_report(data, lang=lang if lang in ("id", "en") else "id")
    filename = f"sankey_{data['year']}{int(data['month']):02d}_{lang}.pdf"
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/drilldown.csv")
async def drilldown_csv(
    request: Request,
    category_id: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    session: AsyncSession = Depends(profile_session),
):
    """CSV export of the drill-down filter (category + date range)."""
    txs = await TransactionRepository(session).list(
        TransactionListFilter(
            category_id=category_id, start_date=start_date, end_date=end_date, limit=5000
        )
    )
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["id", "date", "description", "amount", "currency", "category", "account_id"])
    for t in txs:
        cat = getattr(t.category, "name", "") if getattr(t, "category", None) else ""
        writer.writerow(
            [
                t.id,
                t.date.isoformat() if t.date else "",
                t.description,
                t.amount,
                t.currency,
                cat,
                t.account_id,
            ]
        )
    slug = validate_slug(request.headers.get("x-reign-profile", "") or "default")
    filename = f"drilldown_{slug}_{start_date or 'all'}_{end_date or 'all'}.csv"
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/holdings")
async def holdings_report(
    request: Request, lang: str = "id", session: AsyncSession = Depends(profile_session)
):
    """Holdings portfolio PDF for the active profile."""
    lang = lang if lang in ("id", "en") else "id"
    profile = validate_slug(request.headers.get("x-reign-profile", "") or "default")
    repo = HoldingRepository(session)
    rows = await repo.list()
    items = [
        {
            "symbol": h.symbol,
            "units": str(h.units),
            "cost_basis": str(h.cost_basis),
            "current_price": str(h.current_price),
            "value": str((h.units or Decimal("0")) * (h.current_price or Decimal("0"))),
            "currency": h.currency,
        }
        for h in rows
    ]
    pdf_bytes = generate_holdings_report(items, profile=profile, lang=lang)
    filename = f"holdings_{profile}_{lang}.pdf"
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
