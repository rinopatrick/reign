"""CSV bank statement parser with auto-format detection."""

import csv
from collections.abc import Callable
from datetime import datetime
from decimal import Decimal, InvalidOperation
from io import StringIO

from reign.exceptions import CSVParseError

BankFormat = tuple[Callable[[list[str]], bool], Callable[[list[dict]], list[dict]]]


def _detect_bca(header: list[str]) -> bool:
    return (
        any("Tanggal" in h for h in header)
        and any("Keterangan" in h for h in header)
        and any("Mutasi" in h for h in header)
    )


def _clean_idr_amount(raw: str) -> str:
    """Normalize Indonesian-formatted numbers (1.234.567,89 -> 1234567.89)."""
    return raw.strip().replace(".", "").replace(",", ".")


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
        out.append(
            {
                "date": dt.date().isoformat(),
                "description": desc,
                "amount": amount,
                "currency": "IDR",
            }
        )
    return out


def _detect_bri(header: list[str]) -> bool:
    # BRI and BNI share the same columns (Tanggal + desc + Debit/Kredit).
    # Disambiguation happens by date style, probed in _parse_bri_bni below:
    # dd/MM/yyyy -> bri, dd-MMM-yyyy -> bni.
    has_date = "Tanggal" in header
    has_desc = any(k in ("Uraian", "Keterangan", "Description") for k in header)
    has_dr_cr = "Debit" in header and "Kredit" in header
    return has_date and has_desc and has_dr_cr and "Tanggal Transaksi" not in header


def _parse_bri(rows: list[dict]) -> list[dict]:
    return _parse_bri_bni(rows, "%d/%m/%Y")


def _parse_bri_bni(rows: list[dict], date_fmt: str) -> list[dict]:
    """Shared BRI/BNI body: same columns, only the date style differs."""
    out: list[dict] = []
    for row in rows:
        date_str = row.get("Tanggal", "").strip()
        desc = next(
            (row.get(k, "").strip() for k in ("Uraian", "Keterangan", "Description") if k in row),
            "",
        )
        debit = _clean_idr_amount(row.get("Debit", ""))
        credit = _clean_idr_amount(row.get("Kredit", ""))
        if not date_str:
            continue
        try:
            dt = datetime.strptime(date_str, date_fmt)
        except ValueError:
            continue
        amount = Decimal("0")
        if debit:
            amount = -Decimal(debit)
        elif credit:
            amount = Decimal(credit)
        else:
            continue
        out.append(
            {
                "date": dt.date().isoformat(),
                "description": desc,
                "amount": amount,
                "currency": "IDR",
            }
        )
    return out


def _parse_bni(rows: list[dict]) -> list[dict]:
    return _parse_bri_bni(rows, "%d-%b-%Y")


def _detect_blu(header: list[str]) -> bool:
    # Blu by BCA Digital export: Tanggal + Keterangan + Debit/Kredit (+ optional
    # reference columns like No/ID Transaksi). Disambiguated from BRI/BNI by the
    # presence of a reference column; from BCA by the Debit/Kredit pair.
    has_date = "Tanggal" in header
    has_desc = any(k in ("Keterangan", "Uraian", "Description") for k in header)
    has_dr_cr = "Debit" in header and "Kredit" in header
    has_ref = any(
        k in header for k in ("No", "No.", "ID", "ID Transaksi", "No Referensi", "Referensi")
    )
    return has_date and has_desc and has_dr_cr and has_ref and "Tanggal Transaksi" not in header


def _parse_blu(rows: list[dict]) -> list[dict]:
    return _parse_bri_bni(rows, "%d/%m/%Y")


def _detect_seabank(header: list[str]) -> bool:
    # SeaBank export: Tanggal + Keterangan/Description + Debit/Kredit (+ optional
    # No. Transaksi / Transaction No column). Marker keeps BRI/BNI from matching.
    has_date = "Tanggal" in header
    has_desc = any(k in ("Keterangan", "Description", "Uraian") for k in header)
    has_dr_cr = "Debit" in header and "Kredit" in header
    has_ref = any(
        k in header
        for k in ("No Transaksi", "No. Transaksi", "Transaction No", "Transaction ID", "Ref")
    )
    return has_date and has_desc and has_dr_cr and has_ref and "Tanggal Transaksi" not in header


def _parse_seabank(rows: list[dict]) -> list[dict]:
    return _parse_bri_bni(rows, "%d/%m/%Y")


def _detect_cimb(header: list[str]) -> bool:
    # CIMB Niaga (OCTO/BizChannel) export: English headers with Reference number.
    has_date = "Transaction Date" in header or "Value Date" in header
    has_desc = any(k in ("Description", "Transaction Description", "Details") for k in header)
    has_dr_cr = "Debit" in header and "Credit" in header
    has_ref = any(k in header for k in ("Reference", "Ref No", "Reference No", "Cheque"))
    return has_date and has_desc and has_dr_cr and has_ref


def _parse_cimb(rows: list[dict]) -> list[dict]:
    out: list[dict] = []
    for row in rows:
        date_str = row.get("Transaction Date", "") or row.get("Value Date", "")
        date_str = date_str.strip()
        desc = next(
            (
                row.get(k, "").strip()
                for k in ("Description", "Transaction Description", "Details")
                if k in row
            ),
            "",
        )
        debit = _clean_idr_amount(row.get("Debit", ""))
        credit = _clean_idr_amount(row.get("Credit", ""))
        if not date_str:
            continue
        dt = _parse_flexible_date(date_str)
        if not dt:
            continue
        if debit:
            amount = -Decimal(debit)
        elif credit:
            amount = Decimal(credit)
        else:
            continue
        out.append(
            {
                "date": dt.date().isoformat(),
                "description": desc,
                "amount": amount,
                "currency": "IDR",
            }
        )
    return out


def _detect_danamon(header: list[str]) -> bool:
    # Danamon export: Tanggal Transaksi/Tanggal + Keterangan + Debet/Kredit
    # (Indonesian spelling) and/or Cabang column. "Debet" distinguishes Mandiri.
    has_date = any(k in ("Tanggal Transaksi", "Tanggal") for k in header)
    has_desc = any(k in ("Keterangan", "Uraian", "Description") for k in header)
    has_dr_cr = ("Debet" in header and "Kredit" in header) or (
        "Debit" in header and "Cabang" in header
    )
    return has_date and has_desc and has_dr_cr


def _parse_danamon(rows: list[dict]) -> list[dict]:
    out: list[dict] = []
    for row in rows:
        date_str = row.get("Tanggal Transaksi", "") or row.get("Tanggal", "")
        date_str = date_str.strip()
        desc = next(
            (row.get(k, "").strip() for k in ("Keterangan", "Uraian", "Description") if k in row),
            "",
        )
        debit = _clean_idr_amount(row.get("Debet", "") or row.get("Debit", ""))
        credit = _clean_idr_amount(row.get("Kredit", "") or row.get("Credit", ""))
        if not date_str:
            continue
        dt = _parse_flexible_date(date_str)
        if not dt:
            continue
        if debit:
            amount = -Decimal(debit)
        elif credit:
            amount = Decimal(credit)
        else:
            continue
        out.append(
            {
                "date": dt.date().isoformat(),
                "description": desc,
                "amount": amount,
                "currency": "IDR",
            }
        )
    return out


def _detect_jago(header: list[str]) -> bool:
    # Bank Jago pocket export: Tanggal + a Jago-specific marker (Detail/Mutasi/
    # Nominal/Jumlah). The marker requirement keeps BNI/BRI headers from matching.
    has_date = "Tanggal" in header
    has_jago_marker = any(
        k in header
        for k in (
            "Detail",
            "Detail Transaksi",
            "Mutasi",
            "Mutation",
            "Tipe",
            "Type",
            "CR/DB",
            "DB/CR",
            "Nominal",
            "Jumlah",
        )
    )
    return has_date and has_jago_marker


def _jago_amount_from_mutation(row: dict, mut: str, amt_key, debit_key, credit_key):
    """Amount from CR/DB mutation marker; None when unusable."""
    raw = row.get(amt_key or debit_key or credit_key or "", "")
    value = abs(_clean_decimal(raw))
    if value == 0:
        return None
    if mut in ("CR", "CREDIT", "C", "MASUK", "KREDIT"):
        return value
    if mut in ("DB", "DEBIT", "D", "KELUAR", "DEBET"):
        return -value
    return None


def _jago_amount_plain(row: dict, amt_key, debit_key, credit_key):
    """Amount from signed amount or Debit/Kredit columns; None when unusable."""
    if amt_key:
        try:
            amount = Decimal(_clean_idr_amount(row.get(amt_key, "")))
        except InvalidOperation:
            return None
        return amount if amount != 0 else None
    if debit_key or credit_key:
        debit = _clean_idr_amount(row.get(debit_key, "") if debit_key else "")
        credit = _clean_idr_amount(row.get(credit_key, "") if credit_key else "")
        if debit:
            return -Decimal(debit)
        if credit:
            return Decimal(credit)
    return None


def _parse_jago(rows: list[dict]) -> list[dict]:
    out: list[dict] = []
    keys = list(rows[0].keys()) if rows else []
    date_key = next((k for k in keys if "tanggal" in k.lower() or "date" in k.lower()), "Tanggal")
    desc_keys = [
        k for k in ("Detail", "Detail Transaksi", "Keterangan", "Description") if k in keys
    ]
    mut_key = next(
        (k for k in keys if k in ("Mutasi", "Mutation", "Tipe", "Type", "CR/DB", "DB/CR")), None
    )
    amt_key = next((k for k in keys if "amount" in k.lower() or k in ("Nominal", "Jumlah")), None)
    debit_key = next((k for k in keys if k.lower() == "debit"), None)
    credit_key = next((k for k in keys if k.lower() in ("kredit", "credit")), None)
    for row in rows:
        date_str = row.get(date_key, "").strip()
        desc = next((row.get(k, "").strip() for k in desc_keys), "")
        if not date_str or not desc:
            continue
        dt = _parse_flexible_date(date_str)
        if not dt:
            continue
        amount = None
        mut = row.get(mut_key, "").strip().upper() if mut_key else ""
        if mut:
            amount = _jago_amount_from_mutation(row, mut, amt_key, debit_key, credit_key)
        else:
            amount = _jago_amount_plain(row, amt_key, debit_key, credit_key)
        if amount is None or amount == 0:
            continue
        out.append(
            {
                "date": dt.date().isoformat(),
                "description": desc,
                "amount": amount,
                "currency": "IDR",
            }
        )
    return out


def _clean_decimal(raw: str) -> Decimal:
    try:
        return Decimal(_clean_idr_amount(raw or ""))
    except InvalidOperation:
        return Decimal("0")


def _detect_mandiri(header: list[str]) -> bool:
    return "Tanggal Transaksi" in header and "Description" in header and "Debit" in header


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
        out.append(
            {
                "date": dt.date().isoformat(),
                "description": desc,
                "amount": amount,
                "currency": "IDR",
            }
        )
    return out


def _detect_jenius(header: list[str]) -> bool:
    return "Date" in header and "Description" in header and "Amount" in header


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
        out.append(
            {
                "date": dt.date().isoformat(),
                "description": desc,
                "amount": amount,
                "currency": "IDR",
            }
        )
    return out


def _detect_generic(header: list[str]) -> bool:
    # Fallback: has date, description, and some amount-like column
    h_lower = [h.lower() for h in header]
    has_date = any(k in h_lower for k in ("date", "tanggal"))
    has_desc = any(k in h_lower for k in ("description", "keterangan", "narrative", "remarks"))
    has_amount = any(k in h_lower for k in ("amount", "debit", "credit", "mutasi"))
    return has_date and has_desc and has_amount


GENERIC_DATE_FORMATS = ("%d/%m/%Y", "%Y-%m-%d", "%m/%d/%Y", "%d-%m-%Y")


def _parse_flexible_date(date_str: str):
    """Try known date formats, return datetime or None."""
    for fmt in GENERIC_DATE_FORMATS:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None


def _parse_generic_amount(row: dict, amt_key, debit_key, credit_key):
    """Return Decimal amount or None when the row has no usable amount."""
    try:
        if amt_key:
            amt_clean = row.get(amt_key, "").strip().replace(",", "")
            return Decimal(amt_clean)
        if debit_key or credit_key:
            debit = (
                row.get(debit_key, "").strip().replace(",", "").replace(".", "")
                if debit_key
                else ""
            )
            credit = (
                row.get(credit_key, "").strip().replace(",", "").replace(".", "")
                if credit_key
                else ""
            )
            if debit:
                return -Decimal(debit)
            if credit:
                return Decimal(credit)
    except InvalidOperation:
        pass
    return None


def _generic_keys(rows: list[dict]):
    """Detect date/desc/amount column keys for the generic fallback."""
    keys = list(rows[0].keys())
    date_key = next((k for k in keys if "date" in k.lower() or "tanggal" in k.lower()), None)
    desc_key = next(
        (k for k in keys if any(x in k.lower() for x in ("desc", "keterangan", "narrative"))), None
    )
    amt_key = next((k for k in keys if "amount" in k.lower()), None)
    debit_key = next((k for k in keys if "debit" in k.lower()), None)
    credit_key = next((k for k in keys if "credit" in k.lower()), None)
    return date_key, desc_key, amt_key, debit_key, credit_key


def _parse_generic(rows: list[dict]) -> list[dict]:
    out: list[dict] = []
    if not rows:
        return out
    date_key, desc_key, amt_key, debit_key, credit_key = _generic_keys(rows)
    for row in rows:
        date_str = row.get(date_key, "").strip() if date_key else ""
        desc = row.get(desc_key, "").strip() if desc_key else ""
        if not date_str or not desc:
            continue
        dt = _parse_flexible_date(date_str)
        if not dt:
            continue
        amount = _parse_generic_amount(row, amt_key, debit_key, credit_key)
        if amount is None:
            continue
        out.append(
            {
                "date": dt.date().isoformat(),
                "description": desc,
                "amount": amount,
                "currency": "IDR",
            }
        )
    return out


def _bni_date_style(rows: list[dict]) -> bool:
    """True when the first parseable dated row uses BNI's dd-MMM-yyyy style."""
    for row in rows:
        date_str = row.get("Tanggal", "").strip()
        if not date_str:
            continue
        try:
            datetime.strptime(date_str, "%d-%b-%Y")
            return True
        except ValueError:
            pass
        try:
            datetime.strptime(date_str, "%d/%m/%Y")
            return False
        except ValueError:
            continue
    return False


BANK_FORMATS: list[tuple[str, Callable, Callable]] = [
    ("bca", _detect_bca, _parse_bca),
    ("mandiri", _detect_mandiri, _parse_mandiri),
    ("jenius", _detect_jenius, _parse_jenius),
    ("blu", _detect_blu, _parse_blu),
    ("jago", _detect_jago, _parse_jago),
    ("seabank", _detect_seabank, _parse_seabank),
    ("cimb", _detect_cimb, _parse_cimb),
    ("danamon", _detect_danamon, _parse_danamon),
    ("bri", _detect_bri, _parse_bri),
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
            if name == "bri" and _bni_date_style(rows):
                return "bni", _parse_bni(rows)
            return name, parser(rows)

    raise CSVParseError(f"Unknown CSV format. Headers: {header}")
