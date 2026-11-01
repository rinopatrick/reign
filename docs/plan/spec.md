# Reign — Specification v0.3 (hardened, living doc)

## Overview
Local-first personal finance dashboard. Self-hosted, zero subscription. Single SQLite file, no cloud.

Status: implemented + hardened (fases A–E goal `mvxpogxs-eukkty`). Dokumen ini menggantikan spec v1.0 yang beku.

## Core Value Prop (verified)
1. Upload bank CSV → auto-categorize transactions — `tests/unit/test_csv_parser.py` (7), `tests/integration/test_end_to_end.py::test_csv_import`
2. Dashboard: net worth (initial + mutasi), cashflow, budgets, trends — `tests/integration/test_domain.py::test_net_worth_includes_transactions`, `test_trends_calendar_labels`
3. PDF report export (monthly) — `src/reign/services/pdf_generator.py`, route `/api/reports/monthly`
4. 100% offline — SQLite file, no cloud

## Tech Stack (actual, not aspirational)
- **Backend:** Python >=3.12, FastAPI 0.162, SQLAlchemy 2.0 (async), SQLite + aiosqlite, Pydantic v2
- **Frontend:** Vanilla JavaScript + Tailwind CDN + Chart.js (`src/reign/static/app.js`, ~1470 lines) — NOT Next.js (plan v1.0 salah, dikoreksi di sini)
- **PDF:** ReportLab
- **Task runner / package:** `uv`
- **Tests:** pytest, 30 tests hijau — `tests/unit/` + `tests/integration/` (csv_parser, categorizer, security, transfer/backup, domain)
- **Lint:** `uvx ruff check src tests` + `uvx ruff format --check src tests` bersih

## Scope v0.3 (implemented, tiap klaim ada rujukan)
### Must Have (done, tested)
- [x] CSV import BCA, Mandiri, Jenius + generic fallback — `src/reign/services/csv_parser.py`, `tests/unit/test_csv_parser.py`
- [x] Auto-categorization keyword rules — `src/reign/services/categorizer.py`, `tests/unit/test_categorizer.py`
- [x] CRUD accounts, categories, transactions (+ soft-delete, reconcile) — `src/reign/api/routes/`, `tests/integration/test_end_to_end.py`
- [x] Transfers multi-akun (linked debit/credit, excluded from summaries) — `test_transfer_and_backup.py`
- [x] Split transactions — model `TransactionSplit`, UI split modal
- [x] Notes, tags, tag-filtered search — model fields + `app.js` render + escape
- [x] Recurring transactions CRUD + 3-month forecast dari recurring future — `test_domain.py::test_forecast_projects_recurring_future`
- [x] Dashboard: net worth benar, cashflow bulanan, top categories, trend kalender — `test_net_worth_includes_transactions`, `test_trends_calendar_labels`
- [x] Budgeting + 1-query spent + overspend alerts — `test_budgets_spent_single_query`, `get_spent_map`
- [x] Goals CRUD — routes `/api/goals`
- [x] Calendar heatmap + day details — `app.js` renderCalendar
- [x] Budget alerts, dark mode, keyboard shortcuts, templates localStorage, quick add, bulk edit/reconcile, CSV preview 10 baris, export CSV/JSON — `app.js` (smoke browser fase E)
- [x] PDF monthly report — `pdf_generator.py`, route `/api/reports/monthly`
- [x] Backup v2 lengkap (accounts/categories/transactions+splits/budgets/goals/recurring/notes/tags/flags) + dry-run + snapshot pra-restore + validasi FK — `tests/integration/test_security.py`, `test_transfer_backup.py`
- [x] Security: CORS localhost-only tanpa credentials wildcard, upload streaming chunk 1MB + 413 (CSV 5MB, JSON 10MB), FK 404 terstruktur, settings allowlist, XSS `escapeHtml` + `safeColor` + `textContent` — `test_security.py` (9), smoke XSS fase E (`hasImg=false`)
- [x] Domain: `Period` calendar-correct, `Currency/AccountType/CategoryType/TxType` Enum + validator 422/400, indeks 6 kolom (EXPLAIN SEARCH USING INDEX terbukti), cursor `after_id` + `limit/offset` kompatibel
- [x] Arsitektur: error handler JSON konsisten, settings service tunggal, restore/upload/summary-query helpers terpisah, route tipis

### Explicitly supported banks (realistis)
- BCA (`Tanggal,Keterangan,Mutasi`), Mandiri (`Tanggal Transaksi,Debit,Credit`), Jenius (`Date,Description,Amount`), generic fallback (date-like + desc-like + amount/debit/credit). Bukti: `test_parse_bca/mandiri/jenius/generic`.

### Out of Scope (v0.3, tetap out — follow-up, bukan refactor)
- Bank API integration, mobile app / PWA, LLM categorization fallback, multi-user/auth penuh, migrasi Alembic penuh
- 4 format bank baru (BRI, BNI, Blu, Jago) — fitur baru, bukan bagian hardening ini
- OFX/QFX import, reconciliation with bank statements, investment/stock tracking — lihat Roadmap README (belum dikerjakan)

## Acceptance Criteria (terukur, terverifikasi)
1. CSV BCA/Mandiri/Jenius ter-parse + terkategorisasi — `pytest tests/unit/test_csv_parser.py tests/unit/test_categorizer.py` hijau
2. Net worth = initial + mutasi per currency — `test_net_worth_includes_transactions` (75000.0 dari 100000 − 25000)
3. Trends label kalender unik 3 bulan — `test_trends_calendar_labels`
4. Forecast = proyeksi recurring future (bukan summary historis) — `test_forecast_projects_recurring_future` (income ≥ 5000000)
5. Budgets spent 1 query konsisten — `test_budgets_spent_single_query`
6. Backup→restore round-trip + dry-run + snapshot — `test_security.py`, `test_transfer_backup.py`
7. Upload >limit → 413; FK fiktif → 404; Origin asing ditolak — `test_security.py` (9)
8. XSS payload tampil sebagai teks escaped, tidak ada elemen `img` — smoke browser fase E (`&lt;img...&gt;`, `hasImg=false`, `No page errors`)
9. `pytest -q` 0 failures (30 passed); `ruff check` + `ruff format --check` bersih; `node --check app.js` ok
10. Semua data di single SQLite file; backup JSON v2 lengkap

## Non-goals
- Tidak mengubah kontrak response secara diam-diam: perubahan aditif (TrendPoint +year/month, TransactionListParams +after_id) kompatibel dengan `app.js` lama.
- Tidak ada kredensial di repo; `.env.example` hanya placeholder.
