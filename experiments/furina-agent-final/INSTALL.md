# Instalasi Furina Lite + FurinaHub

Panduan ini untuk private final build: Core `1.0.0`, FurinaHub `1.0.0`, dependency revision `2026.08.23-r40`.

## Instalasi baru

Gunakan Termux yang masih didukung, lalu jalankan:

```bash
pkg update -y && pkg install -y curl
curl -fsSL https://github.com/WynnDev-rill/furina/releases/download/furina-update-stable/furina-install.sh | bash
```

Bootstrap hanya bertugas menemukan dan memverifikasi updater. Setelah itu satu client `furina-update/1` menangani snapshot Core/bridge, dependency yang benar-benar diperlukan, dan FurinaHub APK.

Di sesi Termux interaktif, instalasi memakai tampilan yang sama dengan Furina Lite: header **Furina By Wynn**, garis pemisah hijau, persentase, dan satu status aktif. Saat dipanggil dari FurinaHub, output berubah otomatis ke progress machine-readable agar APK dapat menampilkan statusnya sendiri.

Jalankan Furina:

```bash
furina
```

## Update

```bash
furina update
```

Jika Core dan APK sudah sesuai channel, updater berhenti lewat fast path setelah pemeriksaan metadata dan tidak menjalankan pemeriksaan npm/Plugin yang berat.

Jika update lokal rusak atau client hilang:

```bash
furina recover
```

Untuk memvalidasi ulang snapshot, integrasi Termux, Plugin runtime dan bridge:

```bash
furina repair
```

Instalasi lama yang belum memiliki `furina recover` dapat memakai installer stabil yang sama:

```bash
curl -fsSL https://github.com/WynnDev-rill/furina/releases/download/furina-update-stable/furina-install.sh | bash
```

Jangan menyimpan bootstrap ke `/tmp` Android global. Installer/recovery memakai direktori internal Furina dan temporary directory Termux yang valid.

## FurinaHub APK

Saat bundle baru memiliki APK yang belum dikonfirmasi, updater mengunduh APK terverifikasi dan membuka Android Package Installer. Bundle APK baru dianggap terpasang hanya setelah FurinaHub versi baru benar-benar dijalankan dan mengirim konfirmasi kembali ke Termux.

FurinaHub juga dapat memulai pemeriksaan update dari **Pengaturan → Pembaruan**; jalurnya tetap client yang sama dengan `furina update`.

## Kontrol Android

- **Normal** — default, tanpa privilege tambahan.
- **Shizuku** — opsional setelah readiness check berhasil.
- **Root** — opsional pada perangkat root.

Tidak ada eskalasi otomatis dari Normal ke Shizuku/root.

## Plugin

OpenConnector bersifat lokal dan opsional pada level produk. Runtime-nya direkonsiliasi saat instalasi/repair Core memang membutuhkannya; no-op update tidak mengulang pekerjaan tersebut.

Pemeriksaan manual:

```bash
furina-openconnector status
furina-openconnector repair
furina-openconnector logs
```

## Diagnostik

```bash
furina doctor
furina repair
furina recover
furina optimize
```

`furina optimize` hanya untuk benchmark/tuning model lokal, bukan bagian startup normal.

## Data

Semua data pengguna berada di:

```text
~/.furina-agent/
```

Update Core/bridge tidak menghapus percakapan, memory, provider secret, model lokal, personalization, shared moments, atau konfigurasi pengguna.
