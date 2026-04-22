"""CSV bank statement parser with auto-format detection."""

import csv
from collections.abc import Callable
from datetime import datetime
from decimal import Decimal, InvalidOperation
from io import StringIO

from sovereign_ledger.exceptions import CSVParseError

# Format: (detector, parser)
BankFormat = tuple[Callable[[list[str]], bool], Callable[[list[dict]], list[dict]]]


def _detect_bca(header: list[str]) -> bool:
    return any("Tanggal" in h for h in header) and any("Keterangan" in h for h in header) and any("Mutasi" in h for h in header)


def _parse_bca(rows: list[dict]) -> list[dict]:
    out: list[dict] = []
    for row in rows:
        date_str = row.get("Tanggal", "").strip()
        desc = row.get("Keterangan", "").strip()
        mutasi = row.get("Mutasi", "").strip().replace(".", "").replace(",", ".")
        if not date_str or not mutasi:
            continue
        try:
            dt = datetime.strptime(date_str, "%d/%m/%Y")
            amount = Decimal(mutasi)
        except (ValueError, InvalidOperation):
            continue
        out.append({
            "date": dt.date().isoformat(),
            "description": desc,
            "amount": amount,
            "currency": "IDR",
        })
    return out


def _detect_mandiri(header: list[str]) -> bool:
    return any("Tanggal Transaksi" in h or "Description" in h for h in header)


def _parse_mandiri(rows: list[dict]) -> list[dict]:
    out: list[dict] = []
    for row in rows:
        date_str = row.get("Tanggal Transaksi", "").strip()
        desc = row.get("Description", "").strip()
        debit = row.get("Debit", "").strip().replace(".", "").replace(",", ".")
        credit = row.get("Credit", "").strip().replace(".", "").replace(",", ".")
        if not date_str:
            continue
        try:
            dt = datetime.strptime(date_str, "%d/%m/%Y")
        except ValueError:
            continue
        amount = Decimal("0")
        if debit:
            amount = -Decimal(debit)
        elif credit:
            amount = Decimal(credit)
        else:
            continue
        out.append({
            "date": dt.date().isoformat(),
            "description": desc,
            "amount": amount,
            "currency": "IDR",
        })
    return out


def _detect_jenius(header: list[str]) -> bool:
    return any("Date" in h and "Description" in h and "Amount" in h for h in header)


def _parse_jenius(rows: list[dict]) -> list[dict]:
    out: list[dict] = []
    for row in rows:
        date_str = row.get("Date", "").strip()
        desc = row.get("Description", "").strip()
        amount_str = row.get("Amount", "").strip().replace(",", "")
        if not date_str or not amount_str:
            continue
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            amount = Decimal(amount_str)
        except (ValueError, InvalidOperation):
            continue
        out.append({
            "date": dt.date().isoformat(),
            "description": desc,
            "amount": amount,
            "currency": "IDR",
        })
    return out


def _detect_generic(header: list[str]) -> bool:
    # Fallback: has date, description, and some amount-like column
    h_lower = [h.lower() for h in header]
    has_date = any(k in h_lower for k in ("date", "tanggal"))
    has_desc = any(k in h_lower for k in ("description", "keterangan", "narrative", "remarks"))
    has_amount = any(k in h_lower for k in ("amount", "debit", "credit", "mutasi"))
    return has_date and has_desc and has_amount


def _parse_generic(rows: list[dict]) -> list[dict]:
    out: list[dict] = []
    if not rows:
        return out
    keys = list(rows[0].keys())
    date_key = next((k for k in keys if "date" in k.lower() or "tanggal" in k.lower()), None)
    desc_key = next((k for k in keys if any(x in k.lower() for x in ("desc", "keterangan", "narrative"))), None)
    amt_key = next((k for k in keys if "amount" in k.lower()), None)
    debit_key = next((k for k in keys if "debit" in k.lower()), None)
    credit_key = next((k for k in keys if "credit" in k.lower()), None)

    for row in rows:
        date_str = row.get(date_key, "").strip() if date_key else ""
        desc = row.get(desc_key, "").strip() if desc_key else ""
        if not date_str or not desc:
            continue
        # Try multiple date formats
        dt = None
        for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%m/%d/%Y", "%d-%m-%Y"):
            try:
                dt = datetime.strptime(date_str, fmt)
                break
            except ValueError:
                continue
        if not dt:
            continue

        amount = Decimal("0")
        if amt_key:
            amt_clean = row.get(amt_key, "").strip().replace(",", "")
            try:
                amount = Decimal(amt_clean)
            except InvalidOperation:
                continue
        elif debit_key or credit_key:
            debit = row.get(debit_key, "").strip().replace(",", "").replace(".", "") if debit_key else ""
            credit = row.get(credit_key, "").strip().replace(",", "").replace(".", "") if credit_key else ""
            try:
                if debit:
                    amount = -Decimal(debit)
                elif credit:
                    amount = Decimal(credit)
                else:
                    continue
            except InvalidOperation:
                continue
        else:
            continue

        out.append({
            "date": dt.date().isoformat(),
            "description": desc,
            "amount": amount,
            "currency": "IDR",
        })
    return out


BANK_FORMATS: list[tuple[str, Callable, Callable]] = [
    ("bca", _detect_bca, _parse_bca),
    ("mandiri", _detect_mandiri, _parse_mandiri),
    ("jenius", _detect_jenius, _parse_jenius),
    ("generic", _detect_generic, _parse_generic),
]


def parse_csv(content: str | bytes) -> tuple[str, list[dict]]:
    """Parse bank CSV and return (detected_format, transactions)."""
    if isinstance(content, bytes):
        content = content.decode("utf-8", errors="replace")
    f = StringIO(content)
    try:
        sample = f.read(4096)
        f.seek(0)
        dialect = csv.Sniffer().sniff(sample, delimiters=",;	")
    except csv.Error:
        dialect = csv.excel
        f.seek(0)

    reader = csv.DictReader(f, dialect=dialect)
    if not reader.fieldnames:
        raise CSVParseError("CSV has no header row")

    header = list(reader.fieldnames)
    rows = list(reader)

    for name, detector, parser in BANK_FORMATS:
        if detector(header):
            return name, parser(rows)

    raise CSVParseError(f"Unknown CSV format. Headers: {header}")
