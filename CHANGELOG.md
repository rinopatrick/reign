# Changelog — Reign

## v0.6.0 — Harga pasar otomatis + peringatan + sinkron profil (2026-11-02)

- Harga pasar otomatis Yahoo Finance: mapping BBCA->BBCA.JK, refresh per-holding + semua, lookup (PR #56)
- Isolasi profil di semua route + bukti tulis-baca lintas profil (PR #55)
- Riwayat harga append-only + scheduler harian + sparkline + endpoint history (PR #60)
- Alert target naik/turun + badge UI + SCHEMA_VERSION 5 (PR #61)
- Sinkronisasi profil: export per-profil, clone antar-profil, auto-init DB (PR #57)
- Suite: 88 passed, coverage 85 persen, ruff bersih, JS valid

## v0.5.0 — Investments, more banks, per-profile backup/PDF, desktop tests (2026-11-02)

- Investment holdings + valuation + UI (PR #50) — menutup roadmap Investment/Stock tracking
- Parser SeaBank + CIMB Niaga + Danamon + 3 unit tests (PR #51)
- Backup/restore/trigger + PDF report per profil + auto-init DB profil (PR #52)
- Desktop helpers teruji: resolve_port, wait_for_server, _spawn_server + 6 unit tests (PR #53)
- Coverage naik, suite hijau

## v0.4.0 — Bank coverage + reconciliation + PWA + profiles (2026-11-02)

- Parser BRI + BNI (disambiguasi gaya tanggal) dan Blu + Jago (marker khas, CR/DB + signed amount) — PR #41, #44
- OFX/QFX import + preview + validasi 400/413/422 — PR #42
- Coverage 69% → 81% (goals/recurring/settings CRUD+404, reports, backup trigger, transactions/budgets FK) — PR #43
- Rekonsiliasi statement vs ledger (match amount + toleransi tanggal + skor deskripsi, auto-mark, tombol UI) — PR #45
- PWA: manifest, service worker offline-shell + network-first API 5s, ikon SVG, theme-color — PR #46
- Multi-user local profiles (1 DB per profil, validasi slug, auto-init, /api/profiles, header X-Reign-Profile, switcher UI) — PR #47
- ADR-001: tetap `create_all` + `schema_version` guard, tolak DB lebih baru — PR #48
- Suite: 67 passed, ruff check + format bersih, JS valid

## v0.3.0 — Production hardening (2026-11-01)

Full autonomous hardening of the v0.2.0 codebase (fases A–H, goal `mvxpogxs-eukkty`).
30 tests green, ruff check + format clean, CI hard gates.

### Security (fase B)
- CORS locked to `http://localhost:8000` + `http://127.0.0.1:8000`, no credentials wildcard
- Uploads streamed in 1MB chunks with 413 caps (CSV 5MB, JSON 10MB)
- FK validation → structured 404 (transactions, import, transfer, update, bulk, budget, recurring)
- Backup v2: full payload (accounts/categories/transactions+splits/budgets/goals/recurring/notes/tags/flags), dry-run, pre-restore snapshot, FK validation, rollback on failure
- XSS: global `escapeHtml` + `safeColor` + `textContent` for status; verified with `<img onerror>` payload (renders as escaped text, `hasImg=false`)
- Settings allowlist + 256-char cap; desktop env vars + logging (no `print` in app code)

### Architecture (fase C)
- Typed boundaries: `Currency`/`AccountType`/`CategoryType`/`TxType` enums with 422/400 on invalid values
- `Period` calendar-correct month arithmetic (replaces 30-day `timedelta` drift)
- Global exception handlers with consistent JSON shape; scheduler task reference (RUF006)
- `TransactionListFilter` dataclass (kills PLR0913); settings/uploads/restore services; thin routes
- Split 400-line `import_backup` into `services/restore.py` helpers; generic CSV parser split
- Ruff check + format clean with zero `src/` per-file ignores (only documented global ignores + test-only ignores)

### Domain & data (fase D)
- Net worth = initial balances + transaction totals (was initial only)
- Trends + forecast use calendar months; forecast projects active recurring future (not historical summary)
- Budgets spent via single `get_spent_map` aggregation (was N queries)
- 6 transaction indexes (EXPLAIN confirms `SEARCH USING INDEX`); cursor pagination `after_id` + `limit/offset` compat
- `TrendPoint` gains `year`/`month` (additive, `app.js` compatible)

### Frontend (fase E)
- XSS sweep of all user-data interpolations; `node --check` clean
- Browser smoke: Dashboard/Transactions/Accounts/Budgets/Forecast/Settings render, `No page errors`

### Docs (fase F)
- `docs/plan/spec.md` v0.3 + `docs/plan/plan.md` v0.3 (living docs, every claim references a test)

### CI & quality (fase G)
- CI: Python 3.12 + `uv sync --dev`, hard gates (`ruff check`, `ruff format --check`, `pytest --cov`)
- `host` configurable (default `127.0.0.1`, was hardcoded `0.0.0.0`); `.pi/` + WAL files ignored

### Verification
- `uv run pytest -q -p no:cacheprovider --no-cov` → 30 passed, 0 failed
- `uvx ruff check src tests` + `uvx ruff format --check src tests` → clean
- `node --check src/reign/static/app.js` → ok
- Browser: all key pages render, console clean, XSS escaped
