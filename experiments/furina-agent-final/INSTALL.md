# Memasang Furina Agent di Termux

Furina Agent adalah eksperimen terpisah dari aplikasi Furina utama. Core berjalan di Termux dan FurinaHub menjadi client Android untuk chat, pengaturan, update, media, dan kontrol perangkat yang memang diaktifkan pengguna.

## 1. Siapkan Termux

```bash
pkg update -y && pkg install -y curl
```

## 2. Pasang Furina Agent

```bash
curl -fsSL https://github.com/WynnDev-rill/furina/releases/download/furina-update-stable/furina-install.sh | bash
```

Bootstrap stabil mengunduh satu snapshot Core + bridge yang lengkap dan memverifikasi SHA-256 sebelum aktivasi atomik. Ia dapat dipakai untuk instalasi baru maupun pemulihan versi lama tanpa rantai patch perantara. Model dan data pengguna disimpan terpisah di `~/.furina-agent`, sehingga update Core tidak menghapus data atau model.

Saat instalasi/update interaktif, Termux menampilkan progress ringkas. Detail teknis tetap ditulis ke log agar layar tidak dipenuhi output dependency.

## 3. Jalankan

```bash
furina
```

FurinaHub tetap dapat dibuka ketika Core Termux sedang tidak aktif; fitur yang memerlukan Core akan menunjukkan status koneksi yang sebenarnya.

## Memperbarui

Core + runtime:

```bash
furina update
```

Jika updater normal rusak atau berhenti sebelum berjalan:

```bash
furina recover
```

Instalasi lama yang belum memiliki `furina recover` harus memakai pipe langsung—jangan menulis file ke `/tmp`, karena lokasi global itu bukan direktori temp yang valid untuk Termux:

```bash
curl -fsSL https://github.com/WynnDev-rill/furina/releases/download/furina-update-stable/furina-install.sh | bash
```

APK FurinaHub diperbarui dari **FurinaHub → Pengaturan → Pembaruan**. APK dan Core memiliki lifecycle terpisah agar kegagalan salah satunya tidak merusak yang lain.

## Mode kontrol Android

- **Normal** — default, tanpa Shizuku/root.
- **Shizuku** — opsional jika Shizuku tersedia dan aktif.
- **Root** — opsional untuk perangkat yang memang memiliki root.

Termux:API bukan syarat utama untuk kontrol Android melalui FurinaHub/Bridge.

## Plugin

Plugin memakai OpenConnector lokal. Jika diperlukan:

```bash
furina-openconnector status
furina-openconnector repair
furina-openconnector logs
```

Provider `no_auth` dapat dipakai langsung. Provider yang membutuhkan API key menggunakan key milik pengguna. OAuth self-hosted membutuhkan OAuth Client ID/Secret pengguna; hosted connector tidak menjadi dependency wajib Furina Agent.

## Pemeriksaan dan perbaikan

```bash
furina doctor
furina repair
furina recover
furina optimize
```

`furina optimize` digunakan untuk benchmark model lokal dan memilih konfigurasi CPU yang lebih sesuai; tidak dijalankan setiap startup.

## Lokasi data

```text
~/.furina-agent
```

Kode eksperimen berada di branch `experiment/furina-agent-termux` dan tidak ikut masuk ke APK Furina utama.
