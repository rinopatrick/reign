"""OFX/QFX bank statement parser (ofxparse wrapper → internal row shape)."""

import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO

from ofxparse import OfxParser

from reign.exceptions import CSVParseError

logger = logging.getLogger("reign.ofx_parser")
CURRENCY_CODE_LEN = 3


def parse_ofx(content: bytes) -> tuple[str, list[dict]]:
    """Parse OFX/QFX bytes, return (\"ofx\", transactions).

    Row shape matches csv_parser output: date (ISO), description, amount, currency.
    Raises CSVParseError (mapped to 422 downstream) on invalid payloads.
    """
    try:
        ofx = OfxParser.parse(BytesIO(content))
    except Exception as e:
        raise CSVParseError(f"Invalid OFX/QFX file: {e}") from e
    try:
        account = ofx.account
        currency = (getattr(account, "currency", None) or "IDR").upper()
        raw = account.statement.transactions
    except Exception as e:
        raise CSVParseError(f"OFX/QFX has no statement transactions: {e}") from e

    out: list[dict] = []
    for t in raw:
        desc = (getattr(t, "payee", "") or "").strip() or (getattr(t, "memo", "") or "").strip()
        if not desc:
            desc = "OFX transaction"
        dt = getattr(t, "date", None)
        if isinstance(dt, datetime):
            day = dt.date()
        elif dt is not None:
            try:
                day = datetime(dt.year, dt.month, dt.day).date()
            except Exception:
                logger.debug("Skipping OFX transaction with bad date: %r", dt)
                continue
        else:
            continue
        try:
            amount = Decimal(str(t.amount))
        except (InvalidOperation, ValueError, TypeError):
            continue
        out.append(
            {
                "date": day.isoformat(),
                "description": desc,
                "amount": amount,
                "currency": currency if len(currency) == CURRENCY_CODE_LEN else "IDR",
            }
        )
    if not out:
        raise CSVParseError("OFX/QFX contains no parseable transactions")
    return "ofx", out
