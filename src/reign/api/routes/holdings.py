"""Investment holdings API routes (v0.5.0)."""

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from reign.adapters.repository import AccountRepository
from reign.api.routes.profiles import profile_session
from reign.domain.enums import Currency
from reign.domain.models import Holding
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

    _v_currency = field_validator("currency", mode="before")(_norm_currency)


class HoldingOut(HoldingCreate):
    id: int
    value: Decimal
    pnl: Decimal


class HoldingUpdate(BaseModel):
    name: str | None = None
    units: Decimal | None = None
    cost_basis: Decimal | None = None
    current_price: Decimal | None = None
    currency: str | None = None

    _v_currency = field_validator("currency", mode="before")(_norm_currency_optional)


def _summarize(h: Holding) -> HoldingOut:
    value = (h.units or Decimal("0")) * (h.current_price or Decimal("0"))
    pnl = value - (h.units or Decimal("0")) * (h.cost_basis or Decimal("0"))
    return HoldingOut(
        id=h.id,
        symbol=h.symbol,
        name=h.name or "",
        units=h.units,
        cost_basis=h.cost_basis,
        current_price=h.current_price,
        currency=h.currency,
        account_id=h.account_id,
        value=value,
        pnl=pnl,
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
    h.current_price = price
    await session.commit()
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
            h.current_price = price
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
