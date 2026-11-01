# Code Review — Reign (full working tree, gabungan spec.md + plan.md + README)

Fixed point: seluruh codebase di `main` @ `a91c8fe` (working tree clean). Bukan diff sempit, karena main single-branch dan user minta cakupan penuh.
Spec: `docs/plan/spec.md` + `docs/plan/plan.md` + `README.md` (ketiganya dipakai, inkonsistensi dicatat).
Metode $code-review: dua axis paralel (Standards + Spec). Agregasi di bawah tanpa re-rank lintas axis.

---

## Standards

Standards source yang ditemukan di repo: `pyproject.toml` (`[tool.ruff]`, `[tool.pytest.ini_options]`), `pyproject.toml requires-python >=3.12`, `.env.example`, `.gitignore`, `.github/workflows/ci.yml`. Tidak ada `CODING_STANDARDS.md` / `CONTRIBUTING.md` — aturan tertulis praktis = konfigurasi ruff + pytest. Baseline smell Fowler (12 smell, judgement call, repo override menang) dipakai sebagai lensa kedua.

Temuan per file/hunk:

1. **Ruff check gagal — 8 error (hard violation vs config sendiri).** Bukti: `uvx ruff check src tests` → `RUF006` (`app.py:35` `asyncio.create_task` tanpa referensi, task bisa di-GC), `PTH123` (`backup.py:76` `open()` → `Path.open()`), `PLR0917` (`transactions.py:30` 9 positional > 5), `PLC0415` import di dalam fungsi (`transactions.py:77-78`, `desktop.py:25,47,59`, `forecast.py`, `budgets.py` via heuristik per-file-ignore hanya memutihkan sebagian). Ini hard violation: repo mengkonfigurasi aturan ini lalu melanggarnya.

2. **Ruff format gagal — 27 file unformatted (hard violation).** Bukti: `uvx ruff format --check src tests` → semua route, `schemas.py`, `config.py`, `models.py`, `csv_parser.py`, dst. "would be reformatted". Artinya tidak ada format gate yang jalan sebelum commit.

3. **Speculative Generality / Dead code.** `schemas.py: TransactionListParams` didefinisikan tapi tidak dipakai di mana pun (route pakai query params inline). `models.py: AppSetting` + `settings.py: _get_or_create` vs `backup.py: _get_setting/_set_setting` = duplikasi logika settings 2x dengan perilaku beda (satu commit-on-create, satu tidak). `exceptions.py: ValidationError` tidak pernah di-raise/di-catch.

4. **Duplicated Code (judgement call).** Serialisasi backup JSON ditulis 2x identik di `backup.py: do_auto_backup` dan `export_backup` (accounts/categories/transactions/goals dict-building). Restore me-`DELETE` 5 tabel tapi backup hanya menulis 4 (budgets hilang, splits/notes/tags tidak ikut). Query `select(Transaction).options(selectinload...)` diulang di 4 tempat (`transactions.py: get_transaction`, `repository.py: create/update`). Pola `try/except NotFoundError → HTTPException(404)` diulang di 5 route files tanpa exception handler global.

5. **Shotgun Surgery / Divergent Change (judgement call).** Satu perubahan logis "tambah field transaksi" menyentuh `models.py` + `schemas.py` (2 versi: Create/Out) + `transactions.py` (create/update/get/export) + `repository.py` (list/create/update) + `backup.py` (export/import) + `app.js` (render + modal) — 6 file tanpa lapisan mapping terpusat. Sebaliknya `TransactionRepository` divergen: satu class mengurus CRUD + soft-delete + bulk ops + transfer + summary + trends + category totals + search.

6. **Primitive Obsession + Data Clumps (judgement call).** `type: str` (account/category/transaction), `currency: str` (bebas isi apa saja, tidak divalidasi), `transaction_type: str`, `tags: str` CSV mentah, `month/year: int` tanpa range check. Clump `(year, month, currency)` travelling bersama di `get_summary/get_category_totals/get_monthly_trends/dashboard/forecast/reports`. Seharusnya `Currency`/`TxType` Enum + `Period` value object.

7. **Feature Envy (judgement call).** `budgets.py: list_budgets` mengambil alih hitung `spent` dengan loop `get_category_totals` per budget (N query). Ini logika agregasi milik repository/service, bukan route. Sama untuk `forecast.py` (loop tanggal + timedelta) dan `dashboard.py summary` (net worth = sum `initial_balance` tanpa transaksi — angka salah secara domain).

8. **Message Chains (judgement call).** `app.js` mengakses `tx.category.name`, `tx.splits[].category.color`, `s.category.name` dalam template string tanpa guard konsisten — frontend mengasumsikan shape backend dalam-dalam (rapuh terhadap breaking change, relevan karena user mengizinkan breaking).

9. **Mysterious Name (judgement call).** `Transaction.tags` = string koma (bukan relasi). `Budget.spent` = atribut tempel dinamis di route, bukan kolom/model. `REIGN_BACKUPS_DIR` env dibaca di `desktop.py` tapi tidak pernah dibaca di `backup.py` (hardcode `./backups`). `settings.py` memakai `AsyncSessionLocal` import langsung, bukan `get_session`.

10. **CI tidak menegakkan standar (hard violation proses).** `ci.yml` pakai Python 3.11 padahal `requires-python >=3.12`, install via `pip install -e .` (bukan `uv`), lint/test dibungkus `if command -v` / opsional — selalu hijau walau ruff merah dan test merah. Ditambah `pyproject.toml` per-file-ignore yang memutihkan `PLR0913/E712/PLC0415/ERA001/PLR0912` di file paling bermasalah = standar diturunkan agar lolos, bukan kode diperbaiki.

11. **Logging via `print` (minor).** `backup.py:112,114`, `desktop.py:72,76,83` pakai `print`, bukan `logging` yang sudah disediakan `logging.py: setup_logging`.

**Ringkasan Standards:** 11 temuan (3 hard: ruff check, ruff format, CI non-enforcing; 8 judgement-call smells). Terburuk: **CI + lint gate fiktif** — 8 ruff error + 27 file unformatted + 3 test gagal tetap bisa merge karena CI opsional.

---

## Spec

Acuan gabungan: `spec.md` (MVP v1.0: 7 must-have + acceptance criteria), `plan.md` (Phase 1-4 + verification), `README.md` (fitur aktual v0.2.0).

**(a) Yang diminta tapi hilang/parsial:**

- `spec.md` acceptance #1: "upload BCA/Mandiri CSV dalam 3 detik" — hanya BCA/Mandiri/Jenius + generic yang ada; **BRI, BNI, Blu, Jago (4 dari 7 bank) hilang**. Tidak ada bukti timing 3 detik.
- `spec.md` acceptance #2: "dashboard <1s untuk 1000 transaksi" — tidak ada pagination nyata (limit 2000 tanpa cursor), tidak ada indeks DB selain PK/FK (`models.py` tanpa `Index`), `get_monthly_trends` pakai `timedelta(days=30*i)` yang menggeser bulan secara salah. Klaim performa tanpa dasar.
- `plan.md` Phase 3: seluruh frontend direncanakan **Next.js 14 + shadcn/ui + Recharts**, realita **Vanilla JS + Tailwind CDN + Chart.js** (`index.html: script cdn.tailwindcss.com`, `app.js` 1468 baris). Penyimpangan stack tanpa update spec/plan.
- `spec.md` MVP "multi-currency IDR/USD/AUD" — parsial: currency string bebas tanpa validasi (`schemas.py` semua `currency: str = "IDR"`), tanpa konversi/FX, agregasi per-currency terpisah tapi net worth hanya sum `initial_balance` (`dashboard.py`) tanpa mutasi transaksi.
- `plan.md` verification "coverage >80%" — tidak ada `tests/unit/` terisi (direktori kosong), hanya 1 file integration dengan 4 test, 3 di antaranya **gagal** (`no such table: accounts` — lifespan seeding tidak jalan di test, tidak ada fixture DB). Pintu verifikasi runtuh total.

**(b) Scope creep (ada di kode, tidak diminta spec/plan):**

- Transfers multi-akun, splits, notes/tags, recurring + forecast 3-bulan, goals, calendar heatmap, budget alerts, CSV preview, export CSV/JSON, backup/restore + scheduler, dark mode, keyboard shortcuts, templates localStorage, bulk edit/reconcile — semuanya fitur README v0.2.0 yang **tidak ada di spec.md MVP** (spec bahkan menulis "Recurring: out of scope"). Bukan bug, tapi spec/plan kedaluwarsa: dokumen beku di v1.0 sedangkan kode sudah v0.2.0.
- Inkonsistensi antar dokumen: `spec.md` klaim Python 3.13, `pyproject` `>=3.12`, CI `3.11`. `plan.md` status semua `[ ] Not Started` padahal fitur sudah rilis.

**(c) Terlihat implemented tapi implementasi salah:**

- `dashboard.py: total_balance` = sum `initial_balance` saja → net worth salah (transaksi diabaikan). `spec.md` core value "net worth" gagal domain.
- `repository.py: get_monthly_trends` — `timedelta(days=30)` untuk mundur bulan: label `"%b %Y"` bisa duplikat/loncat di bulan 28/31 hari. `forecast.py` maju `timedelta(days=30*i)` masalah sama + memproyeksikan bulan lalu/past sebagai forecast (seharusnya future dari recurring, bukan summary historis).
- `backup.py: import_backup` — `DELETE FROM` tanpa FK order aman + tanpa transaksi guard eksplisit per tabel; restore menulis ulang PK implisit (ID lama dipetakan tapi `Transaction.id` tidak di-restore → relasi split rusak, `budgets`/`recurring`/`app_settings` tidak di-backup tapi ikut dihapus sebagian). Restore parsial = data loss.
- `transactions.py: import_csv` — validasi hanya ekstensi `.csv`, tanpa batas ukuran/floor (file 500MB bisa OOM: `await file.read()` full di memori 2x: import + preview). `account_id` tidak diverifikasi exist (FK error mentah ke user). Duplikat import tidak dideteksi (re-upload = dobel data).
- `config.py: class Config` deprecated Pydantic v2 (`PydanticDeprecatedSince20` warning muncul di tiap run test). `desktop.py` set `DATABASE_URL` padahal settings membaca `database_url` → env tidak nyambung di desktop mode; `REIGN_BACKUPS_DIR` tidak dibaca backup.py.

**Ringkasan Spec:** ~6 missing/parsial, ~14 scope-creep items (dokumen kedaluwarsa), 5 implemented-tapi-salah (net worth, trends/forecast tanggal, restore, import CSV). Terburuk: **test merah + dokumen beku** — 3/4 test gagal dan plan.md masih `[ ] Not Started` sehingga tidak ada definisi "selesai" yang hidup.

---

## Agregat satu baris

Standards: 11 temuan, terburuk CI/lint gate fiktif. Spec: ~11 temuan, terburuk 3/4 test gagal + net-worth salah + restore berisiko data-loss.
