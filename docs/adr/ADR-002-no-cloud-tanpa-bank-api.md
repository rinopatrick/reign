# ADR-002: No Cloud, No Bank API Sync

Status: accepted.

## Konteks

Setiap rilis bank-sync menggoda koneksi API bank langsung. Produk ini berjanji local-first sejak README: tanpa cloud, tanpa langganan, tanpa kebocoran data. Janji itu selama ini hanya berupa prosa.

## Keputusan

Reign tidak akan mengambil kredensial bank dan tidak akan memanggil API bank. Sinkronisasi berarti impor ulang file statement manual ditambah preview read-only dan dedupe fingerprint. Semua data tetap di SQLite lokal per profil.

## Konsekuensi

- Impor otomatis penuh tetap out of scope selamanya, bukan sekadar ditunda.
- Format bank baru ditambah sebagai detector CSV/OFX lokal, bukan integrasi API.
- Bila suatu hari keputusan ini dicabut, ADR ini dicabut eksplisit beserta alasan keamanannya.
