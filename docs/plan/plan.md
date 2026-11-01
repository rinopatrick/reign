# Plan — Reign v0.3 (living, jujur)

**Status:** [x] Implemented + hardened (fases A–E goal `mvxpogxs-eukkty`)
**Track:** reign

> Plan v1.0 lama ([ ] Not Started semua, frontend Next.js) sudah kedaluwarsa dan digantikan dokumen ini. Stack aktual: Vanilla JS + Tailwind CDN + Chart.js (bukan Next.js).

---

## Phase 1: Scaffold & Database — [x] Done
- [x] Task 1.1: uv project, src layout, ruff + pytest — `pyproject.toml` (`ruff check` + `format --check` bersih)
- [x] Task 1.2: Schema accounts/categories/transactions(+splits)/budgets/goals/recurring/app_settings — `src/reign/domain/models.py` + indeks 6 kolom
- [x] Task 1.3: SQLAlchemy models (Alembic diputuskan TIDAK — `create_all`, lihat tiket riset #4)
- [x] Task 1.4: Repository layer + `get_spent_map` 1-query + `get_balance_total` + cursor — `src/reign/adapters/repository.py`
- [x] Task 1.5: Seed 10 categories + demo Cash — `src/reign/utils/seed.py`, fixture `_clean_db`

## Phase 2: Backend API — [x] Done
- [x] Task 2.1: FastAPI factory + config (ConfigDict, `cors_origins`, limits, `backups_dir`) + logging + error handler global — `app.py`, `config.py`, `api/errors.py`
- [x] Task 2.2: Accounts CRUD (+FK 404) — `routes/accounts.py`
- [x] Task 2.3: Categories CRUD — `routes/categories.py`
- [x] Task 2.4: Transactions CRUD + filter + `limit/offset/after_id` + transfer + bulk + export CSV/JSON — `routes/transactions.py`, `schemas.TransactionListParams`
- [x] Task 2.5: CSV upload streaming 1MB chunk + 413 + preview — `services/uploads.py`, `test_security.py`
- [x] Task 2.6: Auto-categorization keyword — `services/categorizer.py`, `tests/unit/test_categorizer.py`
- [x] Task 2.7: Dashboard net-worth benar + categories + trends kalender — `routes/dashboard.py`, `test_domain.py`
- [x] Task 2.8: Budget CRUD + progress 1-query — `routes/budgets.py`, `test_budgets_spent_single_query`
- [x] Goals CRUD, Recurring CRUD, Forecast recurring-future, Reports PDF, Settings allowlist, Backup v2 — masing-masing route + tests

## Phase 3: Frontend — [x] Done (Vanilla JS, bukan Next.js)
- [x] Task 3.1: Shell `index.html` + Tailwind CDN + Chart.js (pengganti Next.js/shadcn/Recharts yang tidak pernah ada)
- [x] Task 3.2–3.7: Layout + Accounts + Transactions + Dashboard + Budgets + Categories + Goals + Forecast + Calendar + Recurring + Settings — `app.js` (~1470 baris), smoke browser fase E (semua render, `No page errors`)
- [x] XSS tuntas: `escapeHtml` + `safeColor` + `textContent` — payload `<img onerror>` tampil sebagai teks (`hasImg=false`)

## Phase 4: PDF & Polish — [x] Done
- [x] Task 4.1–4.2: ReportLab monthly + endpoint — `services/pdf_generator.py`, `routes/reports.py`
- [x] Task 4.3: Parser BCA/Mandiri/Jenius + generic — `services/csv_parser.py`, 7 unit tests
- [x] Task 4.4: Integration CSV → dashboard → backup/restore + domain + security — 30 tests hijau
- [x] Task 4.5: README + `.env.example` (README versi 0.2.0 badge; bump 0.3.0 di fase H)

## Verification — [x] Hijau
- [x] `uv run pytest -q -p no:cacheprovider --no-cov` → 30 passed, 0 failed
- [x] `uvx ruff check src tests` + `uvx ruff format --check src tests` bersih
- [x] `node --check src/reign/static/app.js` ok
- [x] Browser: Dashboard/Transactions/Accounts/Budgets/Forecast/Settings render, console bersih, XSS escaped
- [ ] Coverage >80% terukur — BELUM: `pytest --cov` belum dijalankan di gate (masuk fase G)
- [ ] CI keras hijau — BELUM: `ci.yml` masih Python 3.11 + pip + opsional (masuk fase G)

## Sisa ke fase G–H (dipindah, bukan di sini)
- G: `ci.yml` Python 3.12 + uv + gates wajib (ruff check, format --check, pytest --cov), hapus per-file-ignore pemutih, `print` → logging tuntas (`desktop.py` selesai, `backup.py` selesai), `git status` bersih
- H: audit ulang + screenshot/log per halaman + tag 0.3.0 + changelog + issues #1–#6
