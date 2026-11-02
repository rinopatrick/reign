"""Investment holdings API routes (v0.5.0)."""

from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from reign.adapters.repository import AccountRepository
from reign.api.routes.profiles import profile_session
from reign.domain.enums import Currency
from reign.domain.models import Holding, PriceAlert, PricePoint
from reign.exceptions import NotFoundError
from reign.services.market import fetch_price, resolve_yahoo_symbol

router = APIRouter()


def _norm_currency(v: str) -> str:
    return Currency(str(v).upper()).value


def _norm_currency_optional(v):
    return None if v is None else _norm_currency(v)


class HoldingCreate(BaseModel):
    symbol: str = Field(min_length=1, max_length=20)
    name: str = ""
    units: Decimal = Decimal("0")
    cost_basis: Decimal = Decimal("0")
    current_price: Decimal = Decimal("0")
    currency: str = "IDR"
    account_id: int
    alert_above: Decimal | None = None
    alert_below: Decimal | None = None

    _v_currency = field_validator("currency", mode="before")(_norm_currency)


class HoldingOut(HoldingCreate):
    id: int
    value: Decimal
    pnl: Decimal
    alert: str | None = None


class HoldingUpdate(BaseModel):
    name: str | None = None
    units: Decimal | None = None
    cost_basis: Decimal | None = None
    current_price: Decimal | None = None
    currency: str | None = None
    alert_above: Decimal | None = None
    alert_below: Decimal | None = None

    _v_currency = field_validator("currency", mode="before")(_norm_currency_optional)


def _summarize(h: Holding) -> HoldingOut:
    value = (h.units or Decimal("0")) * (h.current_price or Decimal("0"))
    pnl = value - (h.units or Decimal("0")) * (h.cost_basis or Decimal("0"))
    alert = None
    price = h.current_price or Decimal("0")
    if h.alert_above is not None and price >= h.alert_above:
        alert = f"Target atas tercapai: {price} >= {h.alert_above}"
    elif h.alert_below is not None and price <= h.alert_below:
        alert = f"Target bawah tercapai: {price} <= {h.alert_below}"
    return HoldingOut(
        id=h.id,
        symbol=h.symbol,
        name=h.name or "",
        units=h.units,
        cost_basis=h.cost_basis,
        current_price=h.current_price,
        currency=h.currency,
        account_id=h.account_id,
        alert_above=h.alert_above,
        alert_below=h.alert_below,
        value=value,
        pnl=pnl,
        alert=alert,
    )


@router.get("", response_model=list[HoldingOut])
async def list_holdings(
    account_id: int | None = None, session: AsyncSession = Depends(profile_session)
):
    stmt = select(Holding).options(selectinload(Holding.account)).order_by(Holding.symbol)
    if account_id is not None:
        stmt = stmt.where(Holding.account_id == account_id)
    rows = (await session.execute(stmt)).scalars().all()
    return [_summarize(h) for h in rows]


@router.post("", response_model=HoldingOut, status_code=201)
async def create_holding(data: HoldingCreate, session: AsyncSession = Depends(profile_session)):
    try:
        await AccountRepository(session).get(data.account_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    h = Holding(**data.model_dump())
    h.symbol = h.symbol.upper()
    session.add(h)
    await session.commit()
    await session.refresh(h)
    return _summarize(h)


@router.put("/{holding_id}", response_model=HoldingOut)
async def update_holding(
    holding_id: int, data: HoldingUpdate, session: AsyncSession = Depends(profile_session)
):
    h = await session.get(Holding, holding_id)
    if not h:
        raise HTTPException(status_code=404, detail=f"Holding {holding_id} not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(h, key, value)
    if h.symbol:
        h.symbol = h.symbol.upper()
    await session.commit()
    await session.refresh(h)
    return _summarize(h)


async def _apply_price(
    session: AsyncSession, h: Holding, price: Decimal, *, commit: bool = True
) -> None:
    """Set current price + append a history point (single place, used by routes)."""
    h.current_price = price
    session.add(PricePoint(holding_id=h.id, price=price, currency=h.currency or "IDR"))
    await _fire_alert_if_hit(session, h, price)
    if commit:
        await session.commit()


async def _fire_alert_if_hit(session: AsyncSession, h: Holding, price: Decimal) -> None:
    """Fire-once alert used by routes and the background scheduler.

    Dedup: at most one unread row per (holding, direction). Re-arming happens
    automatically once the price leaves the trigger zone and crosses again,
    because firing marks nothing persistent besides the alert row itself:
    a new row is only added when no unread row exists for that direction.
    """
    direction = None
    target = None
    if h.alert_above is not None and price >= h.alert_above:
        direction, target = "above", h.alert_above
    elif h.alert_below is not None and price <= h.alert_below:
        direction, target = "below", h.alert_below
    if direction is None:
        return
    existing = await session.execute(
        select(PriceAlert)
        .where(PriceAlert.holding_id == h.id)
        .where(PriceAlert.direction == direction)
        .where(PriceAlert.is_read.is_(False))
        .limit(1)
    )
    if existing.scalars().first() is not None:
        return
    session.add(
        PriceAlert(
            holding_id=h.id,
            direction=direction,
            price=price,
            target=target,
            currency=h.currency or "IDR",
        )
    )


@router.get("/{holding_id}/history")
async def holding_history(
    holding_id: int, *, limit: int = 60, session: AsyncSession = Depends(profile_session)
):
    """Price history (newest last, capped)."""
    h = await session.get(Holding, holding_id)
    if not h:
        raise HTTPException(status_code=404, detail=f"Holding {holding_id} not found")
    stmt = (
        select(PricePoint)
        .where(PricePoint.holding_id == holding_id)
        .order_by(PricePoint.at.desc(), PricePoint.id.desc())
        .limit(max(1, min(limit, 365)))
    )
    rows = (await session.execute(stmt)).scalars().all()
    pts = [
        {"price": float(p.price), "at": p.at.isoformat() if p.at else None} for p in reversed(rows)
    ]
    return {"holding_id": holding_id, "symbol": h.symbol, "points": pts}


@router.delete("/{holding_id}")
async def delete_holding(holding_id: int, session: AsyncSession = Depends(profile_session)):
    h = await session.get(Holding, holding_id)
    if not h:
        raise HTTPException(status_code=404, detail=f"Holding {holding_id} not found")
    await session.delete(h)
    await session.commit()
    return {"message": "Holding deleted"}


@router.post("/{holding_id}/refresh", response_model=HoldingOut)
async def refresh_holding(holding_id: int, session: AsyncSession = Depends(profile_session)):
    """Refresh one holding's price from the market. 404 when unknown."""
    h = await session.get(Holding, holding_id)
    if not h:
        raise HTTPException(status_code=404, detail=f"Holding {holding_id} not found")
    price = await fetch_price(h.symbol)
    if price is None:
        raise HTTPException(status_code=502, detail=f"Market price unavailable for {h.symbol}")
    await _apply_price(session, h, price)
    await session.refresh(h)
    return _summarize(h)


@router.post("/refresh-all", response_model=list[HoldingOut])
async def refresh_all_holdings(session: AsyncSession = Depends(profile_session)):
    """Refresh all holdings' prices; entries without a quote keep their price."""
    stmt = select(Holding).options(selectinload(Holding.account)).order_by(Holding.symbol)
    rows = (await session.execute(stmt)).scalars().all()
    out: list[HoldingOut] = []
    for h in rows:
        price = await fetch_price(h.symbol)
        if price is not None:
            await _apply_price(session, h, price, commit=False)
    await session.commit()
    for h in rows:
        await session.refresh(h)
        out.append(_summarize(h))
    return out


@router.get("/market/lookup")
async def market_lookup(symbol: str):
    """Preview Yahoo symbol mapping + latest price without saving."""
    price = await fetch_price(symbol)
    if price is None:
        raise HTTPException(status_code=502, detail=f"Market price unavailable for {symbol}")
    return {"symbol": symbol.upper(), "yahoo_symbol": resolve_yahoo_symbol(symbol), "price": price}


class AlertOut(BaseModel):
    id: int
    holding_id: int
    symbol: str
    direction: str
    price: Decimal
    target: Decimal
    currency: str
    is_read: bool
    at: datetime | None


def _alert_out(a: PriceAlert, symbol: str) -> AlertOut:
    return AlertOut(
        id=a.id,
        holding_id=a.holding_id,
        symbol=symbol,
        direction=a.direction,
        price=a.price,
        target=a.target,
        currency=a.currency,
        is_read=a.is_read,
        at=a.at,
    )


@router.get("/alerts/list", response_model=list[AlertOut])
async def list_alerts(
    *, unread_only: bool = False, session: AsyncSession = Depends(profile_session)
):
    """Alert center feed, newest first."""
    stmt = (
        select(PriceAlert, Holding.symbol)
        .join(Holding, Holding.id == PriceAlert.holding_id)
        .order_by(PriceAlert.id.desc())
        .limit(200)
    )
    if unread_only:
        stmt = stmt.where(PriceAlert.is_read.is_(False))
    rows = (await session.execute(stmt)).all()
    return [_alert_out(a, sym) for a, sym in rows]


@router.get("/alerts/unread-count")
async def unread_alert_count(session: AsyncSession = Depends(profile_session)):
    """Unread count for the header badge."""
    n = (
        await session.execute(
            select(func.count()).select_from(PriceAlert).where(PriceAlert.is_read.is_(False))
        )
    ).scalar_one()
    return {"unread": int(n)}


class AllocationSlice(BaseModel):
    symbol: str
    value: Decimal
    weight: float


class AllocationResponse(BaseModel):
    total: Decimal
    slices: list[AllocationSlice]


@router.get("/allocation", response_model=AllocationResponse)
async def allocation(session: AsyncSession = Depends(profile_session)):
    """Portfolio allocation by symbol (weights sum to 1 when total > 0)."""
    rows = (await session.execute(select(Holding))).scalars().all()
    items = []
    for h in rows:
        value = (h.units or Decimal("0")) * (h.current_price or Decimal("0"))
        items.append((h.symbol, value))
    total = sum((v for _, v in items), Decimal("0"))
    slices = [
        AllocationSlice(
            symbol=s,
            value=v,
            weight=float(v / total) if total > 0 else 0.0,
        )
        for s, v in sorted(items, key=lambda kv: kv[1], reverse=True)
    ]
    return AllocationResponse(total=total, slices=slices)


@router.post("/alerts/{alert_id}/read", response_model=AlertOut)
async def mark_alert_read(alert_id: int, session: AsyncSession = Depends(profile_session)):
    a = await session.get(PriceAlert, alert_id)
    if not a:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")
    a.is_read = True
    await session.commit()
    h = await session.get(Holding, a.holding_id)
    return _alert_out(a, h.symbol if h else "?")


@router.post("/alerts/read-all")
async def mark_all_alerts_read(session: AsyncSession = Depends(profile_session)):
    res = await session.execute(select(PriceAlert).where(PriceAlert.is_read.is_(False)))
    rows = res.scalars().all()
    for a in rows:
        a.is_read = True
    await session.commit()
    return {"marked": len(rows)}
