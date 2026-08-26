# Instalasi Furina Termux

Private build saat ini: Core `1.1.18`, dependency revision `2026.08.26-r68`. FurinaHub tidak didistribusikan oleh installer/updater untuk sementara; source dan rilis lamanya tidak dihapus.

## Instalasi baru

```bash
pkg update -y && pkg install -y curl
curl -fsSL https://github.com/WynnDev-rill/furina/releases/download/furina-update-stable/furina-install.sh | bash
furina
```

Bootstrap memverifikasi updater dan memastikan `llama-cpp` tersedia, tetapi tidak mengunduh model LLM. Semua GGUF hanya diunduh dari **Provider & Model**.

## Personalisasi

Buka **Personalisasi** di menu utama Termux.

Ada 20 toggle independen: Tsundere, Yandere, Kuudere, Dandere, Deredere, Himedere, Kamidere, Sadodere, Mayadere, Bakadere, Hajidere, Darudere, Shundere, Utsudere, Bodere, Hiyakasudere, Nyandere, Oujodere, Genki girl, dan Onee-san type. Klik untuk aktif, klik lagi untuk nonaktif. Tidak ada batas jumlah kombinasi. Fresh install tidak memaksa trait apa pun; Identity Kernel Furina tetap aktif.

Core memilih satu sampai empat facet dari intent, emosi, hubungan, mode respons, dan state facet sebelumnya; nama trope tidak dilempar sebagai daftar panjang ke model. Hysteresis mencegah gaya berubah mendadak tanpa perubahan konteks.

## Model lokal

Tiga pilihan tetap tersedia:

- **wifuGPT 1.7B Q4_K_M** — ~1.03 GiB.
- **Qwen3 1.7B Heretic Q5_K_M** — ~1.17 GiB.
- **Qwen3 4B Instruct 2507 Uncensored Q4_K_M** — ~2.50 GB, Quality.

Status model: **Unduh → Kelola → Aktif**. Model yang sudah diunduh dapat dipilih atau dihapus dari menu yang sama. Jika model aktif adalah satu-satunya mesin chat yang siap, Furina memberi peringatan tegas sebelum penghapusan. Local tidak memiliki fallback diam-diam ke Online saat inferensi.

Download mendukung resume dan wajib lolos verifikasi GGUF + SHA-256. Model 4B tidak pernah diunduh otomatis oleh install/update.

## Percakapan dan memori 1.1.18

Grounded Dialogue State memisahkan ucapan user yang faktual dari wording Furina sendiri. Balasan Furina sebelumnya hanya dibawa ke turn baru jika user memang merujuknya untuk koreksi, klarifikasi, atau acknowledgement. Pergantian topik tidak membawa motif/kalimat balasan lama ke prompt Local.

Semua balasan conversational tetap dibuat oleh model yang dipilih. Response Rhythm Controller memberi target 1–6 gagasan: opini kasual biasanya dua, sedangkan audit nyata lima atau enam. Preferensi seperti “jawab ringkas” atau “jelaskan rinci” mengalahkan keputusan otomatis. Tidak ada canned social response atau rewrite isi jawaban.

Setiap proses Termux memulai thread jangka pendek baru. Core mengambil maksimal empat kutipan relevan memakai FTS5 dan, bila dikonfigurasi, reranking embedding multilingual lokal. Bukti lemah tidak memicu fallback pesan terbaru. Fakta eksplisit disimpan bersama `source_message_id`; inferensi AI yang lemah menjadi kandidat sampai mendapat bukti lain. Koreksi menautkan versi lama dan baru melalui relasi `replaces`, sedangkan relasi `evidence` dan `related` menjaga provenance tanpa database/framework berat.

## Update Termux

```bash
furina update
```

Perintah ini memeriksa stable channel dan mengganti Core Termux secara atomik. Ia tidak mengunduh APK atau membuka installer Android.

Recovery tetap tersedia:

```bash
furina recover
```

Conversation, memory, provider secrets, pilihan sifat, local models, dan personalisasi lain di `~/.furina-agent/` tidak diganti oleh update normal.

## Hapus Furina dari Termux

```bash
hapus furina
```

Menghapus data/runtime/model/launcher Furina dari Termux setelah konfirmasi, tetapi tidak menghapus shared Termux packages atau APK lama yang mungkin masih terpasang di Android.
