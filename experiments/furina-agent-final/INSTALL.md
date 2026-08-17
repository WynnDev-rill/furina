# Memasang Furina Agent di Termux

Furina Agent adalah eksperimen terpisah dari aplikasi Furina utama. Core berjalan di Termux dan dapat memakai FurinaHub/Furina Bridge untuk kontrol Android. Instalasi ini tidak memasukkan Furina Agent ke APK Furina utama.

> Furina Agent masih eksperimental. Core Termux dan APK FurinaHub memiliki lifecycle update terpisah agar kegagalan salah satu tidak merusak yang lain.

## 1. Siapkan Termux

Buka Termux lalu jalankan:

```bash
pkg update -y && pkg install -y curl
```

## 2. Pasang Furina Agent

Gunakan bootstrap CDN berikut. Bootstrap ini sengaja tidak bergantung pada `raw.githubusercontent.com`, sehingga tetap dapat dipakai jika endpoint raw GitHub sedang terkena HTTP 429 atau timeout:

```bash
curl -fsSL https://cdn.jsdelivr.net/gh/WynnDev-rill/furina@experiment/furina-agent-termux/experiments/furina-agent-final/install.sh | bash
```

Installer kemudian memiliki fallback otomatis melalui beberapa jalur update dan tetap melakukan verifikasi integritas sebelum menerapkan file. Installer menyiapkan Core dan runtime yang diperlukan ke `~/.furina-agent`, serta mempertahankan model/data secara terpisah dari Core.

Jika instalasi lama gagal melakukan `furina update` dengan pesan `HTTP 429`, `Too Many Requests`, atau timeout, jalankan perintah bootstrap CDN di atas **sekali**. Runtime `r17` akan memasang updater resilien; setelah itu `furina update` kembali menjadi jalur normal.

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

Mulai runtime `2026.08.17-r17`, `furina update` memakai transport multi-jalur. Ia mencoba endpoint raw GitHub, CDN jsDelivr, lalu jalur raw GitHub web sebagai fallback, dengan timeout dan retry terbatas. File yang diperoleh tetap divalidasi sebelum dijalankan.

`furina update` adalah jalur canonical untuk **Core + dependency/runtime**. Pada instalasi yang sudah ada, perintah ini tidak memasang ulang atau menurunkan versi APK FurinaHub.

Update APK dilakukan dari **FurinaHub → Pengaturan → Pembaruan**. FurinaHub Android RC36 juga memakai fallback beberapa jalur untuk metadata update, sehingga HTTP 429 pada satu endpoint tidak langsung menggagalkan pemeriksaan versi.

> Jika APK yang terpasang masih RC35 atau lebih lama dan updater di dalam APK itu sedang terkena HTTP 429, pasang RC36 satu kali dari release GitHub. Setelah RC36 aktif, pemeriksaan update berikutnya sudah memakai transport fallback baru.

## Plugin

Plugin memakai OpenConnector lokal di Termux. Runtime memeriksa endpoint kesehatan resmi `/v1/health`; launcher akan mencoba memperbaiki dependency sekali secara otomatis bila runtime gagal start.

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
