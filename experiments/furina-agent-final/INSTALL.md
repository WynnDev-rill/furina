# Memasang Furina Agent di Termux

Furina Agent adalah eksperimen terpisah dari aplikasi Furina utama. Core berjalan di Termux dan dapat memakai Furina Bridge untuk kontrol Android. Instalasi ini tidak memasukkan Furina Agent ke APK Furina utama.

> Furina Agent masih eksperimental. Installer dan Bridge dapat berubah selama pengembangan.

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

Installer akan menyiapkan dependency yang diperlukan, memasang Core ke `~/.furina-agent`, melakukan validasi sebelum aktivasi, dan mempertahankan model/data secara terpisah dari Core.

## 3. Jalankan Furina

Setelah instalasi selesai:

```bash
furina
```

Jika Furina Bridge perlu dipasang atau diperbarui, installer akan mengarahkan ke APK resmi eksperimen. Buka Bridge dan aktifkan izin Android yang diperlukan untuk fitur kontrol perangkat.

## Mode kontrol Android

- **Normal** — mode default; tidak membutuhkan Shizuku atau root.
- **Shizuku** — opsional; pilih hanya jika Shizuku tersedia dan aktif.
- **Root** — opsional; pilih hanya pada perangkat yang memang memiliki akses root.

Termux:API bukan syarat utama untuk kontrol Android melalui Furina Bridge.

## Memperbarui

Untuk memperbarui Furina Agent:

```bash
furina update
```

Updater menggunakan staging/validation sebelum mengganti Core aktif dan mempertahankan model serta memory pada jalur update normal.

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
