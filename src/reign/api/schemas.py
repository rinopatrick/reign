"""Pydantic request/response schemas."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from reign.domain.enums import AccountType, CategoryType, Currency, TxType

_Date = date


def _norm_currency(v: str) -> str:
    return Currency(str(v).upper()).value


def _norm_account_type(v: str) -> str:
    return AccountType(str(v).lower()).value


def _norm_category_type(v: str) -> str:
    return CategoryType(str(v).lower()).value


def _norm_tx_type(v: str) -> str:
    return TxType(str(v).lower()).value


class AccountCreate(BaseModel):
    name: str
    type: str = "checking"
    currency: str = "IDR"
    initial_balance: Decimal = Decimal("0")

    _v_currency = field_validator("currency", mode="before")(_norm_currency)
    _v_type = field_validator("type", mode="before")(_norm_account_type)


class AccountOut(AccountCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int


class CategoryCreate(BaseModel):
    name: str
    type: str = "expense"
    color: str | None = "#718096"
    keywords: str | None = ""

    _v_type = field_validator("type", mode="before")(_norm_category_type)


class CategoryOut(CategoryCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int


class SplitCreate(BaseModel):
    category_id: int
    amount: Decimal
    description: str | None = None


class SplitOut(SplitCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    category: CategoryOut | None = None


class TransactionCreate(BaseModel):
    date: date
    description: str
    amount: Decimal
    currency: str = "IDR"
    notes: str | None = ""
    tags: str | None = ""
    transaction_type: str = "expense"
    account_id: int
    category_id: int | None = None
    splits: list[SplitCreate] | None = None

    _v_currency = field_validator("currency", mode="before")(_norm_currency)
    _v_type = field_validator("transaction_type", mode="before")(_norm_tx_type)


class TransactionOut(TransactionCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    is_deleted: bool = False
    is_reconciled: bool = False
    created_at: datetime
    category: CategoryOut | None = None
    splits: list[SplitOut] = []


class TransferCreate(BaseModel):
    from_account_id: int
    to_account_id: int
    amount: Decimal
    currency: str = "IDR"
    date: date
    description: str | None = "Transfer"

    _v_currency = field_validator("currency", mode="before")(_norm_currency)


class BudgetCreate(BaseModel):
    year: int
    month: int
    amount: Decimal
    currency: str = "IDR"
    category_id: int
    rollover: bool = False

    _v_currency = field_validator("currency", mode="before")(_norm_currency)


class BudgetOut(BudgetCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    spent: Decimal | None = None
    category: CategoryOut | None = None


class CategoryTotal(BaseModel):
    name: str
    total: Decimal


class DashboardSummary(BaseModel):
    total_accounts: int
    total_balance: Decimal
    month_income: Decimal
    month_expense: Decimal
    month_net: Decimal
    currency: str


class TrendPoint(BaseModel):
    label: str
    year: int
    month: int
    income: Decimal
    expense: Decimal
    net: Decimal


class GoalCreate(BaseModel):
    name: str
    target_amount: Decimal
    current_amount: Decimal = Decimal("0")
    currency: str = "IDR"

    _v_currency = field_validator("currency", mode="before")(_norm_currency)


class GoalOut(GoalCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime


class RecurringCreate(BaseModel):
    description: str
    amount: Decimal
    currency: str = "IDR"
    day_of_month: int = Field(ge=1, le=31)
    account_id: int
    category_id: int | None = None
    active: bool = True

    _v_currency = field_validator("currency", mode="before")(_norm_currency)


class RecurringOut(RecurringCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    last_generated: date | None = None
    category: CategoryOut | None = None


class ForecastMonth(BaseModel):
    label: str
    income: Decimal
    expense: Decimal
    net: Decimal


class ForecastResponse(BaseModel):
    months: list[ForecastMonth]
    recurring: list[RecurringOut]


class BulkIds(BaseModel):
    ids: list[int]


class BulkUpdate(BaseModel):
    ids: list[int]
    category_id: int | None = None
    date: _Date | None = None


class CSVImportResponse(BaseModel):
    imported: int
    skipped: int
    message: str


class ReconcileMatch(BaseModel):
    index: int
    transaction_id: int
    description: str
    score: float
    date_gap_days: int


class ReconcileUnmatched(BaseModel):
    index: int
    row: dict
    reason: str


class ReconcileTotals(BaseModel):
    statement_rows: int
    matched: int
    unmatched: int


class ReconcileResult(BaseModel):
    matched: list[ReconcileMatch]
    unmatched: list[ReconcileUnmatched]
    marked_reconciled: int
    totals: ReconcileTotals


class TransactionListParams(BaseModel):
    """GET /api/transactions filter bundle (keeps route signature small)."""

    account_id: int | None = None
    category_id: int | None = None
    start_date: _Date | None = None
    end_date: _Date | None = None
    q: str | None = None
    tag: str | None = None
    limit: int = Field(default=500, ge=1, le=2000)
    offset: int = Field(default=0, ge=0)
    after_id: int | None = Field(default=None, ge=1)
