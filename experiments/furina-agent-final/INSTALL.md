# Instalasi Furina Lite + FurinaHub

Panduan private build saat ini: Core `1.0.2`, FurinaHub `1.0.2`, dependency revision `2026.08.24-r42`.

## Instalasi baru

Gunakan Termux yang masih didukung, lalu jalankan:

```bash
pkg update -y && pkg install -y curl
curl -fsSL https://github.com/WynnDev-rill/furina/releases/download/furina-update-stable/furina-install.sh | bash
```

Bootstrap memverifikasi updater, lalu satu client `furina-update/1` menangani Core/bridge, dependency yang dibutuhkan, dan FurinaHub APK. Instalasi baru **tidak mengunduh model LLM lokal**.

Di sesi Termux interaktif, instalasi memakai tampilan **Furina By Wynn** dengan progress ringkas. Saat dipanggil dari FurinaHub, updater mengirim progress machine-readable agar APK menampilkan statusnya sendiri.

Setelah selesai:

```bash
furina
```

Menu utama hanya berisi **Chat**, **Provider & Model**, **Pengaturan**, dan **Exit**. Memory/Psyche tetap berjalan secara internal tetapi tidak ditampilkan sebagai menu pemeliharaan.

## Menyiapkan model chat

Buka:

```text
furina → Provider & Model
```

Pilihan routing hanya dua:

- **Online** — model/provider API yang tersedia dapat berganti otomatis di dalam jalur online sebelum jawaban terlihat. Setelah streaming jawaban mulai tampil, response tidak dipindah ke provider lain.
- **Local** — tepat satu model lokal yang sudah selesai diunduh dan dipilih.

Katalog lokal:

- **wifuGPT 1.7B Q4_K_M** — sekitar 1.03 GiB.
- **Qwen3 1.7B Heretic Q5_K_M** — sekitar 1.17 GiB.

Model yang belum ada menunjukkan **Unduh**. Setelah download selesai, ukuran, header GGUF dan SHA-256 diverifikasi; baru setelah itu tombol berubah menjadi **Pilih**. Model yang dipakai menunjukkan **Aktif**.

Unduhan dapat dilanjutkan setelah koneksi terputus. Membuka `furina` biasa tidak memuat model. Setelah **Local** dipilih, Furina mulai menyiapkan model terpilih di background. Jika chat dibuka lebih cepat, tampil status **Menyiapkan model lokal…** dan pesan tetap menunggu runtime yang sama; model sehat kemudian dipertahankan warm hingga sekitar 10 menit idle agar pesan berikutnya tidak memuat GGUF dari awal.

Local Performance V2 memakai context dasar 4096, cache-reuse dan Flash Attention secara capability-gated. Benchmark performa opsional membandingkan 4/5/6 thread pada model yang benar-benar terpasang. OpenCL/Vulkan hanya digunakan bila build backend khusus memang tersedia dan lolos benchmark; CPU tetap fallback. Model, quantization, sampling, dan budget jawaban tidak diturunkan untuk mengejar angka benchmark.

Baik chat Online maupun Local mengirim jawaban secara streaming. Chunk pertama langsung ditampilkan; chunk kecil berikutnya digabung dalam interval sangat pendek agar tampilan Termux/FurinaHub terasa lancar tanpa fake typing.

Migrasi menghapus file Deckard/Qwen lama yang memang dimiliki katalog Furina sebelumnya. File GGUF lain yang ditaruh pengguna sendiri tidak dihapus otomatis.

## Pengaturan

Kontrol yang jarang dipakai dipindahkan ke **Pengaturan** agar layar utama tetap sederhana:

- Identitas
- Kontrol perangkat
- Sistem
- Backup
- Update & Recovery

Mode kontrol Android tetap **Normal**, **Shizuku**, atau **Root**, tanpa eskalasi otomatis.

## Update

```bash
furina update
```

Jika Core dan APK sudah sesuai channel, updater memakai fast path dan tidak mengulang pekerjaan dependency/npm/Plugin yang berat.

Jika updater lokal rusak atau client hilang:

```bash
furina recover
```

Untuk memvalidasi ulang snapshot dan integrasi:

```bash
furina repair
```

Instalasi lama yang belum memiliki `furina recover` dapat memakai bootstrap stabil yang sama:

```bash
curl -fsSL https://github.com/WynnDev-rill/furina/releases/download/furina-update-stable/furina-install.sh | bash
```

## FurinaHub APK

Saat channel memiliki APK baru, updater mengunduh APK terverifikasi dan membuka Android Package Installer. Versi baru baru dianggap terpasang setelah FurinaHub yang baru benar-benar dijalankan dan mengonfirmasi bundle ke Termux.

FurinaHub memakai katalog model dan runtime yang sama dengan Termux. Download/pilih/hapus model dari FurinaHub memengaruhi Core yang sama; status model juga tetap **Unduh**, **Pilih**, atau **Aktif**. Memilih model Local dari FurinaHub juga memulai persiapan background yang sama. Memory/Psyche tetap digunakan oleh Core tetapi direct navigation-nya disembunyikan.

## Hapus seluruh Furina dari Termux

```bash
hapus furina
```

Perintah ini meminta konfirmasi `HAPUS` lalu menghapus seluruh data Furina di Termux, termasuk percakapan, memory, provider secret, model lokal, backup, runtime dan launcher Furina. Tindakan ini tidak dapat dipulihkan tanpa backup.

Yang **tidak** dihapus:

- paket Termux bersama seperti Python/Git/Node;
- konfigurasi Termux global yang bukan milik Furina;
- APK FurinaHub yang sudah terpasang di Android.

Untuk penghapusan non-interaktif yang disengaja:

```bash
hapus furina --yes
```

## Plugin

OpenConnector bersifat lokal dan opsional. Runtime direkonsiliasi saat instalasi/repair benar-benar memerlukannya; no-op update tidak mengulang setup tersebut.

Pemeriksaan manual tetap tersedia:

```bash
furina-openconnector status
furina-openconnector repair
furina-openconnector logs
```

## Data

Semua data pengguna berada di:

```text
~/.furina-agent/
```

Update Core/bridge normal tidak menghapus percakapan, memory, provider secret, model lokal, personalization, shared moments, atau konfigurasi pengguna. Hanya `hapus furina` yang melakukan penghapusan penuh dari Termux.
