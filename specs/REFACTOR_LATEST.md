# Refactor Plan — Reign (all scopes, breaking allowed)

Status: interview done. Testing: fix 3 red tests first (in-memory DB fixture), then new tests per module. Order: executor bebas pilih urutan (user: "kerjakan semuanya sampai selesai"). Breaking API changes allowed — update `app.js` sekalian.

HARD GATE (plan-refactor): perilaku kini didokum & kenapa salah ada di tiap Problem; invariant yang harus dipertahankan dicantum di tiap Commits (baris "Invariant:").

## Problem Statement

Reign v0.2.0 jalan sebagai local-first finance tracker (FastAPI + SQLite + Vanilla JS, ~3000 baris backend), tapi fondasinya rapuh di 4 sisi sekaligus: (1) **security** — CORS `*` + credential, CSV/JSON upload tanpa limit dibaca full ke memori, restore menghapus tabel tanpa backup field lengkap, XSS via `innerHTML` + data CSV mentah; (2) **arsitektur** — duplikasi serialisasi backup & eager-load query, repository gemuk, validasi string bebas (currency/type), error mapping manual per route, settings logic ganda; (3) **test & kualitas** — 3/4 test merah (`no such table`), ruff 8 error + 27 file unformatted, CI opsional pakai Python salah; (4) **performa & DB** — tanpa indeks, N-query di budgets/trends, `timedelta(30 hari)` untuk aritmetika bulan, net-worth salah (cuma initial_balance). Spec/plan beku di v1.0 sementara kode sudah v0.2.0. User minta semuanya dibereskan sampai selesai, boleh breaking.

## Solution

Refactor bertahap 8 fase (A–H): hijaukan test dulu (fixture DB), kunci pintu (security), rapikan rumah (arsitektur + Enum + error handler), betulkan angka (domain + tanggal + indeks), rapikan frontend (XSS + pecah app.js bila perlu), selaraskan dokumen (spec/plan hidup), keraskan CI, tutup dengan audit akhir. Tiap commit kecil, working, ada perintah verify. Kontrak API boleh berubah; `app.js` diupdate di fase yang sama (D4, E2).

## Commits

A. Test baseline hijau
1. `test: in-memory DB fixture + lifespan-free app` → verify: `uv run pytest -q -p no:cacheprovider --no-cov` (target 4/4 hijau). Invariant: 4 test lama tetap lolos tanpa ubah app lifespan.
2. `test: tambah unit csv_parser + categorizer + schemas` → verify: `uv run pytest -q` (target ≥15 test). Invariant: parser lama tetap terima format BCA/Mandiri/Jenius yang sudah jalan.
3. `test: integration backup/restore + transfer + budgets` → verify: `uv run pytest -q`. Invariant: response shape lama masih dipakai app.js sampai fase D.

B. Security hardening (B1–B6 boleh berurutan apa saja, tiap commit verify `uv run pytest -q` + manual curl)
4. `fix: CORS ketat (origin localhost saja, tanpa credentials wildcard)` → verify: `curl -H Origin:http://evil.test` ditolak; app lokal tetap jalan. Invariant: `http://localhost:8000` tetap boleh.
5. `fix: upload limits (CSV ≤5MB, JSON ≤10MB, ekstensi+content-type check, streaming read)` → verify: upload 6MB ditolak 413; CSV valid tetap masuk. Invariant: 2 CSV test lama tetap lolos.
6. `fix: validasi account_id/category_id exist + FK error jadi 404 terstruktur` → verify: import dengan account fiktif → 404, bukan 500. Invariant: import valid tidak berubah.
7. `fix: backup/restore aman (tutup kolom hilang: budgets/recurring/splits/notes/tags, guard transaksi, tanpa DELETE buta)` → verify: backup→restore round-trip diff sama. Invariant: file backup lama tetap bisa dibaca (migrasi defensif).
8. `fix: XSS frontend (escapeHtml utk description/tags/category, hindari innerHTML data mentah)` → verify: deskripsi `<img onerror>` tampil sebagai teks. Invariant: tampilan normal identik.
9. `fix: Pydantic ConfigDict + settings env desktop nyambung` → verify: tanpa deprecation warning; desktop mode baca DB benar. Invariant: `.env` lama tetap jalan.

C. Arsitektur backend
10. `refactor: Enum Currency/TxType/AccountType + Period value object` → verify: `uvx ruff check src` + pytest hijau. Invariant: nilai string lama ("IDR", "expense") tetap diterima (parse case-insensitive).
11. `refactor: global exception handlers (NotFound→404, CSVParse→422, Validation→400) + hapus try/except per route` → verify: pytest + curl 404/422 shape konsisten. Invariant: status code lama tidak berubah.
12. `refactor: TransactionRepository dipecah (Repo CRUD, BulkOps service, SummaryQueries)` → verify: pytest hijau. Invariant: hasil query identik (bandingkan snapshot test).
13. `refactor: hilangkan duplikasi serialisasi backup + eager-load helper` → verify: pytest hijau. Invariant: isi JSON backup identik key-per-key.
14. `refactor: satukan settings logic (satu module, bukan ganda)` → verify: pytest hijau. Invariant: key auto_backup_* lama tetap terbaca.
15. `refactor: ValidationError dipakai (bukan dead code) + hapus TransactionListParams mati` → verify: ruff + pytest hijau. Invariant: tidak ada route yang memakai yang dihapus.

D. Domain & data benar (boleh breaking, update app.js sekalian)
16. `fix: net-worth = initial_balance + mutasi (bukan initial saja)` → verify: test dashboard dengan transaksi → balance benar. Invariant: currency filtering tetap per-currency.
17. `fix: aritmetika bulan dengan calendar (bukan timedelta 30 hari) di trends+forecast` → verify: test lintas Jan→Feb→Mar label benar. Invariant: shape ForecastResponse tetap sampai E2 bila belum dipecah.
18. `fix: forecast = proyeksi recurring future (bukan summary historis)` + update app.js → verify: forecast kosong tanpa recurring; ada recurring → angka proyeksi. Invariant: endpoint path tidak berubah kecuali diputuskan dipecah.
19. `feat: indeks DB (date, account_id, category_id, type) + pagination cursor` + update app.js → verify: EXPLAIN pakai indeks; 2000+ rows tetap responsif. Invariant: limit/offset lama tetap didukung selama transisi.
20. `fix: budgets spent via satu agregasi (bukan N query)` → verify: test N budget 1 query (assert via event listener). Invariant: angka spent identik.

E. Frontend
21. `refactor: pecah app.js per halaman (atau minimal modul ES) + hapus inline onclick kritis` → verify: semua halaman manual smoke (dashboard/tx/budget/backup). Invariant: semua tombol/fitur lama tetap ada.
22. `feat: kontrak API baru (bila D pecah endpoint) + app.js ikut` → verify: smoke penuh + pytest hijau. Invariant: tidak ada halaman blank/error console.

F. Dokumen hidup
23. `docs: spec.md v0.3 (scope aktual: transfer/split/recurring/goal/backup; bank didukung realistis)` → verify: tiap klaim ada test/implementasi rujukan.
24. `docs: plan.md status jujur (centang selesai, sisa dipindah ke map)` → verify: tidak ada `[ ]` untuk yang sudah rilis.

G. CI & kualitas
25. `ci: Python 3.12 + uv + ruff check && format --check && pytest --cov (gagal bila merah)` → verify: push trial / `act` lokal hijau.
26. `chore: ruff format seluruh repo + bereskan 8 ruff error + hapus per-file-ignore pemutih` → verify: `uvx ruff check src tests && uvx ruff format --check src tests` bersih.
27. `chore: ganti print→logging + hapus pycache dari tree` → verify: ruff + `git status` bersih.

H. Penutup
28. `audit: ulangi $code-review + $security-review penuh` → verify: nol hard violation, nol implemented-tapi-salah.
29. `release: bump 0.3.0 + changelog + tag` → verify: `uv run` + desktop smoke.

## Decision Document

- Modul dibangun/diubah: `tests/conftest.py` (fixture), `api/errors.py` baru (handler), `domain/enums.py` baru, `domain/period.py` baru, `adapters/repository.py` (pecah), `services/backup.py` baru (pindah dari routes), `api/routes/*` (tipis), `static/app.js` (escape + modul), `specs/*`, `.github/workflows/ci.yml`.
- Interface berubah (breaking allowed): net-worth response (angka berubah = benar), forecast shape (bila dipecah), pagination (cursor), error shape konsisten `{detail, code}`.
- Klarifikasi user: testing = fix merah lalu tulis baru; urutan = bebas asal tuntas; kontrak = boleh breaking + update app.js.
- Arsitektur: route tipis → service/repository; Enum strict di boundary, string di DB; backup service murni (testable tanpa HTTP).
- Skema/DB: tambah indeks; tambah kolom hanya bila perlu (tidak sebelum H); migrasi defensif untuk backup lama; `Alembic` dipertimbangkan di tiket (kini `create_all`).
- Kontrak: CORS localhost-only; upload 5/10MB; error JSON konsisten.

## Testing Decisions

- Test yang bagus: perilaku luar (HTTP/JSON/angka), bukan internals; fixture DB in-memory per-test; snapshot untuk agregasi.
- Modul dites: csv_parser, categorizer, schemas/Enum, backup round-trip, transfer, budgets-spent, dashboard-net-worth, trends/forecast tanggal, XSS escape (jsdom/manual), upload limits.
- Prior art: `tests/integration/test_end_to_end.py` (pola ASGITransport) dipertahankan + diperluas; `tests/unit/` baru diisi.

## Out of Scope

- Bank API integration, mobile app, LLM categorization (tetap out, sesuai spec).
- 4 format bank hilang (BRI/BNI/Blu/Jago) = fitur baru, bukan refactor — masuk tiket follow-up, bukan plan ini.
- Multi-user/auth penuh — di luar repo kini (single-user local); hanya hardening dasar (CORS/validasi) di plan ini.
- Migrasi Alembic penuh — diputuskan via tiket riset, tidak dipaksa di plan ini.

## Further Notes

- Estimasi: 29 commit kecil; tiap commit working + verify eksplisit.
- Risiko terbesar: restore merusak data user → mitigasi: backup otomatis sebelum restore + dry-run flag (diputuskan di eksekusi).
- Setelah plan ini: eksekusi via subagents paralel per fase + council review sebelum release.
