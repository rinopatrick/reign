"""Domain enums — typed boundaries for account/category/transaction/currency."""

from enum import StrEnum


class Currency(StrEnum):
    """Supported ledger currencies (spec: IDR, USD, AUD + common extras)."""

    IDR = "IDR"
    USD = "USD"
    AUD = "AUD"
    EUR = "EUR"
    SGD = "SGD"
    JPY = "JPY"
    GBP = "GBP"


class AccountType(StrEnum):
    """Kinds of accounts."""

    CHECKING = "checking"
    SAVINGS = "savings"
    CASH = "cash"
    INVESTMENT = "investment"
    CREDIT = "credit"
    WALLET = "wallet"
    OTHER = "other"


class CategoryType(StrEnum):
    """Kinds of categories."""

    INCOME = "income"
    EXPENSE = "expense"
    TRANSFER = "transfer"


class TxType(StrEnum):
    """Kinds of transactions."""

    INCOME = "income"
    EXPENSE = "expense"
    TRANSFER = "transfer"
