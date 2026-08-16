# Memasang Furina Agent di Termux

Furina Agent adalah eksperimen terpisah dari aplikasi Furina utama. Core berjalan di Termux dan dapat memakai FurinaHub/Furina Bridge untuk kontrol Android. Instalasi ini tidak memasukkan Furina Agent ke APK Furina utama.

> Furina Agent masih eksperimental. Core Termux dan APK FurinaHub memiliki lifecycle update terpisah agar kegagalan salah satu tidak merusak yang lain.

## 1. Siapkan Termux

Buka Termux lalu jalankan:

```bash
pkg update -y && pkg install -y curl
```

## 2. Pasang Furina Agent

Jalankan installer resmi dari branch eksperimen:

```bash
curl -fsSL https://raw.githubusercontent.com/WynnDev-rill/furina/experiment/furina-agent-termux/experiments/furina-agent-final/install.sh | bash
```

Installer menyiapkan Core dan runtime yang diperlukan ke `~/.furina-agent`, melakukan validasi sebelum aktivasi, dan mempertahankan model/data secara terpisah dari Core.

## 3. Jalankan Furina

```bash
furina
```

FurinaHub adalah client Android untuk Core tersebut. Izin Android seperti Accessibility tetap dikelola dari FurinaHub/Bridge, bukan dari updater Core.

## Mode kontrol Android

- **Normal** — mode default; tidak membutuhkan Shizuku atau root.
- **Shizuku** — opsional; pilih hanya jika Shizuku tersedia dan aktif.
- **Root** — opsional; pilih hanya pada perangkat yang memang memiliki akses root.

Termux:API bukan syarat utama untuk kontrol Android melalui Furina Bridge.

## Memperbarui

Untuk memperbarui Core dan runtime Furina Agent:

```bash
furina update
```

`furina update` adalah jalur canonical untuk **Core + dependency/runtime**. Pada instalasi yang sudah ada, perintah ini tidak memasang ulang atau menurunkan versi APK FurinaHub.

Update APK dilakukan dari **FurinaHub → Pengaturan → Update FurinaHub**. Core Termux dan APK Android dapat diperbaiki atau di-rollback secara independen.

## Plugin

Plugin memakai OpenConnector lokal di Termux. RC48 memeriksa endpoint kesehatan resmi `/v1/health`; launcher akan mencoba memperbaiki dependency sekali secara otomatis bila runtime gagal start.

Pemeriksaan manual jika diperlukan:

```bash
furina-openconnector status
furina-openconnector repair
furina-openconnector logs
```

Provider `no_auth` langsung dapat digunakan. Provider dengan API key, seperti GitHub, dapat dihubungkan dengan key dari FurinaHub. Untuk provider OAuth seperti Gmail, OpenConnector self-hosted membutuhkan OAuth Client ID/Secret milik pengguna; ini batasan OpenConnector self-hosted, bukan error FurinaHub. Hosted connector dapat menyediakan managed OAuth, tetapi sengaja tidak dijadikan dependency wajib Furina Agent.

## Pemeriksaan dan perbaikan

```bash
furina doctor
furina repair
furina optimize
```

`furina optimize` digunakan untuk benchmark model lokal pada perangkat dan memilih konfigurasi CPU yang lebih sesuai; tidak dijalankan setiap startup.

## Lokasi data

```text
~/.furina-agent
```

Data Furina Agent ini terpisah dari source dan instalasi APK Furina utama.

## Pemisahan dari Furina utama

Kode eksperimen berada di branch `experiment/furina-agent-termux`. Installer di atas juga mengambil file dari branch tersebut, bukan dari `main`. Menambahkan tautan dokumentasi Furina Agent ke README repository utama tidak membuat kode Agent ikut masuk ke build APK Furina utama.
