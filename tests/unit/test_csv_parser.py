"""Unit tests: csv_parser formats + error paths."""

import pytest

from reign.exceptions import CSVParseError
from reign.services.csv_parser import parse_csv

BCA = "Tanggal,Keterangan,Mutasi\n15/04/2026,STARBUCKS,-75.000\n16/04/2026,GAJI,+15.000.000\n"
MANDIRI = "Tanggal Transaksi,Description,Debit,Credit\n15/04/2026,KOPI,75000,\n16/04/2026,GAJI,,15000000\n"
JENIUS = "Date,Description,Amount\n2026-04-15,KOPI,-75000\n2026-04-16,GAJI,15000000\n"
BRI = "Tanggal,Uraian,Debit,Kredit,Saldo\n15/04/2026,TRSF E-BANKING,500000,,10000000\n16/04/2026,SETORAN,,2000000,12000000\n"
BNI = "Tanggal,Keterangan,Debit,Kredit,Saldo\n15-Apr-2026,QRIS PAY,150000,,9850000\n16-Apr-2026,GAJI MASUK,,15000000,24850000\n"


def test_parse_bca():
    fmt, rows = parse_csv(BCA)
    assert fmt == "bca"
    assert len(rows) == 2
    assert rows[0]["description"] == "STARBUCKS"
    assert rows[1]["amount"] > 0


def test_parse_mandiri():
    fmt, rows = parse_csv(MANDIRI)
    assert fmt == "mandiri"
    assert len(rows) == 2
    assert rows[0]["amount"] < 0
    assert rows[1]["amount"] > 0


def test_parse_jenius():
    fmt, rows = parse_csv(JENIUS)
    assert fmt == "jenius"
    assert len(rows) == 2


def test_parse_bri():
    fmt, rows = parse_csv(BRI)
    assert fmt == "bri"
    assert len(rows) == 2
    assert rows[0]["amount"] < 0
    assert rows[1]["amount"] > 0
    assert rows[0]["date"] == "2026-04-15"


def test_parse_bni():
    fmt, rows = parse_csv(BNI)
    assert fmt == "bni"
    assert len(rows) == 2
    assert rows[0]["amount"] < 0
    assert rows[1]["amount"] > 0


def test_parse_bri_skips_bad_rows():
    bad = "Tanggal,Uraian,Debit,Kredit,Saldo\nnot-a-date,XXX,,,\n15/04/2026,OK,100000,,0\n"
    fmt, rows = parse_csv(bad)
    assert fmt == "bri"
    assert len(rows) == 1


def test_parse_bni_skips_bad_rows():
    bad = "Tanggal,Keterangan,Debit,Kredit,Saldo\n32-XXX-2026,XXX,1,,0\n15-Apr-2026,OK,,50000,0\n"
    fmt, rows = parse_csv(bad)
    assert fmt == "bni"
    assert len(rows) == 1


def test_parse_unknown_format_raises():
    with pytest.raises(CSVParseError):
        parse_csv("foo,bar\n1,2\n")


def test_parse_empty_header_raises():
    with pytest.raises(CSVParseError):
        parse_csv("")


def test_parse_csv_bytes_input():
    fmt, rows = parse_csv(BCA.encode("utf-8"))
    assert fmt == "bca"
    assert len(rows) == 2


def test_parse_bca_skips_bad_rows():
    bad = "Tanggal,Keterangan,Mutasi\nnot-a-date,XXX,abc\n15/04/2026,OK,-1000\n"
    fmt, rows = parse_csv(bad)
    assert fmt == "bca"
    assert len(rows) == 1
