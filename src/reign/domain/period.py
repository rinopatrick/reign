"""Calendar-correct month period value object."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date as _date

from reign.domain.enums import Currency

MIN_YEAR = 1970
MAX_YEAR = 2200
MONTHS_PER_YEAR = 12


@dataclass(frozen=True)
class Period:
    """A (year, month, currency) triple travelling together through queries."""

    year: int
    month: int
    currency: Currency = Currency.IDR

    def __post_init__(self) -> None:
        if not MIN_YEAR <= self.year <= MAX_YEAR:
            raise ValueError(f"year out of range: {self.year}")
        if not 1 <= self.month <= MONTHS_PER_YEAR:
            raise ValueError(f"month out of range: {self.month}")

    @classmethod
    def from_raw(cls, year: int, month: int, currency: str = "IDR") -> Period:
        """Parse raw query params; raises ValueError on bad input."""
        return cls(year=year, month=month, currency=Currency(str(currency).upper()))

    def add_months(self, delta: int) -> Period:
        """Calendar-correct month arithmetic (no timedelta-30-days drift)."""
        total = (self.year * MONTHS_PER_YEAR + (self.month - 1)) + delta
        year, month0 = divmod(total, MONTHS_PER_YEAR)
        return Period(year=year, month=month0 + 1, currency=self.currency)

    def label(self) -> str:
        """Short label like 'Nov 2026'."""
        return _date(self.year, self.month, 1).strftime("%b %Y")

    def as_currency_str(self) -> str:
        """Plain currency code for SQLAlchemy filters."""
        return self.currency.value
