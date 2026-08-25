# Instalasi Furina Termux

Private build saat ini: Core `1.1.16`, dependency revision `2026.08.25-r66`. FurinaHub tidak didistribusikan oleh installer/updater untuk sementara; source dan rilis lamanya tidak dihapus.

## Instalasi baru

```bash
pkg update -y && pkg install -y curl
curl -fsSL https://github.com/WynnDev-rill/furina/releases/download/furina-update-stable/furina-install.sh | bash
furina
```

Bootstrap memverifikasi updater dan memastikan `llama-cpp` tersedia, tetapi tidak mengunduh model LLM. Semua GGUF hanya diunduh dari **Provider & Model**.

## Personalisasi

Buka **Personalisasi** di menu utama Termux.

Ada 20 toggle independen: Tsundere, Yandere, Kuudere, Dandere, Deredere, Himedere, Kamidere, Sadodere, Mayadere, Bakadere, Hajidere, Darudere, Shundere, Utsudere, Bodere, Hiyakasudere, Nyandere, Oujodere, Genki girl, dan Onee-san type. Klik untuk aktif, klik lagi untuk nonaktif. Tidak ada batas jumlah kombinasi.

Core mengompilasi kombinasi ke facet perilaku yang ringkas; nama trope tidak dilempar sebagai daftar panjang ke model. Kombinasi besar tetap dipakai secara kontekstual.

## Model lokal

Tiga pilihan tetap tersedia:

- **wifuGPT 1.7B Q4_K_M** — ~1.03 GiB.
- **Qwen3 1.7B Heretic Q5_K_M** — ~1.17 GiB.
- **Qwen3 4B Instruct 2507 Uncensored Q4_K_M** — ~2.50 GB, Quality.

Status model: **Unduh → Kelola → Aktif**. Model yang sudah diunduh dapat dipilih atau dihapus dari menu yang sama. Menghapus model aktif menghentikan runtime lalu memindahkan routing ke Online sebelum file dihapus. Local tidak memiliki fallback diam-diam ke Online saat inferensi.

Download mendukung resume dan wajib lolos verifikasi GGUF + SHA-256. Model 4B tidak pernah diunduh otomatis oleh install/update.

## Percakapan dan memori 1.1.16

Grounded Dialogue State memisahkan ucapan user yang faktual dari wording Furina sendiri. Balasan Furina sebelumnya hanya dibawa ke turn baru jika user memang merujuknya untuk koreksi, klarifikasi, atau acknowledgement. Pergantian topik tidak membawa motif/kalimat balasan lama ke prompt Local.

Semua balasan conversational tetap dibuat oleh model yang dipilih. Adaptive pacing hanya memberi target kedalaman/panjang secara abstrak; tidak ada canned social response atau rewrite isi jawaban.

Setiap proses Termux memulai thread jangka pendek baru, tetapi ucapan user dari thread lama langsung masuk indeks SQLite FTS5. Saat pesan baru membutuhkan konteks lama, Core mencari indeks dan memasukkan maksimal empat kutipan relevan—bukan seluruh riwayat. Konsolidasi AI tetap memutuskan fakta, preferensi, tujuan, atau pola mana yang layak menjadi memori terstruktur.

## Update Termux

```bash
furina update
```

Perintah ini memeriksa stable channel dan mengganti Core Termux secara atomik. Ia tidak mengunduh APK atau membuka installer Android.

Recovery tetap tersedia:

```bash
furina recover
furina repair
```

Conversation, memory, provider secrets, pilihan sifat, local models, dan personalisasi lain di `~/.furina-agent/` tidak diganti oleh update normal.

## Hapus Furina dari Termux

```bash
hapus furina
```

Menghapus data/runtime/model/launcher Furina dari Termux setelah konfirmasi, tetapi tidak menghapus shared Termux packages atau APK lama yang mungkin masih terpasang di Android.
