"""Statement reconciliation — match bank-statement rows to ledger transactions.

Matching rule (explicit, auditable):
- same account_id,
- not soft-deleted, not already reconciled,
- abs(amount) equal (Decimal exact),
- abs(date difference) <= tolerance_days (default 2),
- description similarity: normalized token overlap >= 0.3 OR one contains the other.

Best match wins per statement row (highest score, then smallest date gap).
Each ledger transaction matches at most one statement row (greedy by score).
"""

import logging
from datetime import date
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from reign.adapters.repository import TransactionListFilter, TransactionRepository

logger = logging.getLogger("reign.reconcile")
MIN_DESC_SCORE = 0.3
DEFAULT_TOLERANCE_DAYS = 2
MIN_TOKEN_LEN = 2


def _normalize(text: str) -> set[str]:
    tokens = set()
    for raw in (text or "").lower().replace("/", " ").replace("-", " ").split():
        t = "".join(c for c in raw if c.isalnum())
        if len(t) > MIN_TOKEN_LEN:
            tokens.add(t)
    return tokens


def _desc_score(a: str, b: str) -> float:
    ta, tb = _normalize(a), _normalize(b)
    if not ta or not tb:
        return 0.0
    al, bl = a.lower(), b.lower()
    if al in bl or bl in al:
        return 1.0
    inter = len(ta & tb)
    union = len(ta | tb)
    return inter / union if union else 0.0


async def reconcile_statement(
    session: AsyncSession,
    account_id: int,
    statement_rows: list[dict],
    *,
    tolerance_days: int = DEFAULT_TOLERANCE_DAYS,
    auto_mark: bool = False,
) -> dict:
    """Match statement rows to ledger transactions. Optionally mark matched reconciled."""
    repo = TransactionRepository(session)
    filters = TransactionListFilter(account_id=account_id, limit=2000)
    ledger = [t for t in await repo.list(filters) if not t.is_reconciled]

    used: set[int] = set()
    matched: list[dict] = []
    unmatched: list[dict] = []

    for idx, row in enumerate(statement_rows):
        try:
            row_date = date.fromisoformat(str(row["date"]))
            row_amount = abs(Decimal(str(row["amount"])))
        except Exception:
            logger.debug("Skipping invalid statement row %d", idx)
            unmatched.append({"index": idx, "row": row, "reason": "invalid row"})
            continue
        best = None
        best_key = None
        for tx in ledger:
            if tx.id in used:
                continue
            try:
                tx_amount = abs(Decimal(str(tx.amount)))
            except Exception:
                logger.debug("Skipping ledger tx %s with bad amount", getattr(tx, "id", "?"))
                continue
            if tx_amount != row_amount:
                continue
            gap = abs((tx.date - row_date).days)
            if gap > tolerance_days:
                continue
            score = _desc_score(tx.description, str(row.get("description", "")))
            key = (score, -gap)
            if score < MIN_DESC_SCORE:
                continue
            if best is None or key > best_key:
                best, best_key = tx, key
        if best is None:
            unmatched.append({"index": idx, "row": row, "reason": "no match"})
            continue
        used.add(best.id)
        matched.append(
            {
                "index": idx,
                "transaction_id": best.id,
                "description": best.description,
                "score": round(best_key[0], 3),
                "date_gap_days": -best_key[1],
            }
        )

    marked = 0
    if auto_mark and matched:
        ids = [m["transaction_id"] for m in matched]
        await repo.bulk_reconcile(ids)
        marked = len(ids)

    return {
        "matched": matched,
        "unmatched": unmatched,
        "marked_reconciled": marked,
        "totals": {
            "statement_rows": len(statement_rows),
            "matched": len(matched),
            "unmatched": len(unmatched),
        },
    }
