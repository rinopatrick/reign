# ADR-001: Tetap `create_all`, Tanpa Alembic (v0.4.0)

Status: accepted. Menutup #39 (tindak lanjut tiket riset #4).

## Konteks

Reign adalah aplikasi desktop single-user, SQLite file lokal, 8 tabel
(`accounts`, `categories`, `transactions`, `transaction_splits`, `budgets`,
`goals`, `recurring_transactions`, `app_settings`). Skema dibuat via
`Base.metadata.create_all` di lifespan app, pembuatan profil, dan fixture tests.
Tidak ada skema versioning, tidak ada migrasi destruktif sejauh ini.
Backup/restore JSON v2 menjadi jaring pengaman data.

## Opsi yang dipertimbangkan

1. **Alembic penuh** — autogenerate + revision chain + CLI migrate.
   Pro: standar industri untuk tim/server, riwayat eksplisit per perubahan.
   Kontra: overhead besar untuk pola rilis ini (skema hanya berubah
   additive: tambah tabel/kolom/indeks); async engine + multi-profil
   (satu DB per profil) membuat runner migrasi harus loop per profil;
   risiko salah operasi (downgrade) di tangan non-teknis lebih besar
   daripada manfaatnya.
2. **`create_all` + `schema_version` guard (dipilih)** — `create_all`
   sudah additive dan idempoten; tambah kunci `schema_version` di
   `app_settings` + pemeriksaan kompatibilitas saat startup:
   versi app yang dibutuhkan vs versi skema tersimpan.
   Pro: nol dependensi baru, nol langkah manual untuk user desktop,
   konsisten dengan profil multi-DB (guard berjalan per profil).
   Kontra: tidak bisa migrasi destruktif (rename/drop kolom) otomatis —
   kasus itu ditangani via backup → fresh DB → restore (jalur yang
   sudah diuji di `test_transfer_backup.py` dan `test_security.py`).

## Keputusan

Tetap `create_all`. Tambah:
- `SCHEMA_VERSION = 3` di `reign.domain.models` (naik tiap perubahan skema).
- `ensure_schema_version(session)`: tulis `schema_version` bila kosong,
  tolak startup (`RuntimeError` → 500 di lifespan dengan pesan jelas)
  bila DB lebih baru dari app (mencegah buka DB masa depan dengan
  app lama) — downgrade eksplisit hanya via backup/restore.
- Test: fresh DB dapat cap versi; DB versi masa depan ditolak.

## Konsekuensi

- Perubahan skema ke depan WAJIB additive (tambah tabel/kolom/indeks
  nullable atau ber-default) + naikkan `SCHEMA_VERSION` + catat di CHANGELOG.
- Bila suatu saat dibutuhkan migrasi destruktif, ADR ini dicabut dan
  Alembic diadopsi dengan runner per-profil.
