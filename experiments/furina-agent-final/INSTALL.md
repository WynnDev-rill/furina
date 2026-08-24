# Instalasi Furina Lite + FurinaHub

Private build saat ini: Core `1.0.9`, FurinaHub `1.0.9` (`versionCode 10067`), dependency revision `2026.08.24-r49`.

## Instalasi baru

```bash
pkg update -y && pkg install -y curl
curl -fsSL https://github.com/WynnDev-rill/furina/releases/download/furina-update-stable/furina-install.sh | bash
furina
```

Bootstrap memverifikasi updater dan memastikan `llama-cpp` tersedia, tetapi **tidak mengunduh model LLM**. Semua GGUF hanya diunduh dari **Provider & Model**.

## Sesi dan memory

Short-term history terpisah dari long-term Core Memory. Proses `furina` baru mendapat thread Termux baru; `/back` dalam proses yang sama tetap memakai thread sekarang. Memory personal terpercaya, relationship/profile, provider/API, pilihan model, local model files, dan shared moments tetap persisten. FurinaHub mempertahankan conversation selection miliknya sendiri.

## Model lokal

Tiga pilihan tersedia:

- **wifuGPT 1.7B Q4_K_M** — ~1.03 GiB, ringan/roleplay.
- **Qwen3 1.7B Heretic Q5_K_M** — ~1.17 GiB, ringan/multibahasa.
- **Qwen3 4B Instruct 2507 Uncensored Q4_K_M** — ~2.50 GB, **Quality**.

Status model: **Unduh → Pilih → Aktif**. Model 4B tidak diunduh otomatis oleh `furina update`. Buka **Provider & Model**, pilih model 4B, lalu **Unduh**.

Download mendukung resume. Dua model lama tetap memakai exact byte-size + GGUF + SHA-256 validation. Artifact 4B dari Hugging Face/Xet menggunakan remote Content-Length/Content-Range discovery lalu wajib lolos GGUF + pinned SHA-256 sebelum diaktifkan. SHA model 4B:

```text
6615b7b5184931e4df9c6d0ae9cd29ca9319b73908d4423283d4cc401a12a1cd
```

Setelah unduhan selesai pilih **Pilih**, status berubah menjadi **Aktif**. Local tetap tidak mempunyai fallback diam-diam ke Online.

## Grounded Dialogue State

1.0.9 mempertahankan Grounded Dialogue State 1.0.8. Semua balasan percakapan tetap dibuat oleh model yang dipilih—tidak ada fast-response sosial, regex content rewrite, atau repair generation kedua.

User statements menjadi evidence utama thread. Ucapan Furina sebelumnya hanya continuity sampai user mengonfirmasi. Trusted long-term memory tetap dibaca dari Core yang sama oleh Online dan semua model Local.

Qwen3 4B Quality memakai non-thinking Qwen3 sampling (`top_p 0.8`, `top_k 20`) dan Jinja chat template jika llama.cpp di perangkat mendukung flag tersebut.

## Runtime Local

- Context phone-first: `4096`.
- Prewarm saat Local/chat dibuka.
- Keep-warm sekitar 10 menit idle.
- Prompt/cache reuse dan native streaming tetap aktif.
- Safe CPU retry tetap tersedia jika optimized llama-server gagal.
- 4B memerlukan lebih banyak RAM dan compute; dua model 1.7B tetap tersedia sebagai pilihan cepat.

Jika `llama-cpp` terhapus, installer/update/runtime mencoba memulihkannya tanpa menghapus atau mengunduh ulang model.

## Update dan recovery

```bash
furina update
furina recover
furina repair
```

Update Core/bridge memakai snapshot terverifikasi dan atomic swap. Conversation, memory, provider secrets, local models, personalization dan shared moments di `~/.furina-agent/` tidak diganti oleh update normal.

## FurinaHub

FurinaHub memakai Core, katalog model, runtime, dan long-term personal memory yang sama dengan Furina Lite. Model 4B muncul di **Provider & Model** yang sama. FurinaHub tetap memakai in-place streaming untuk live response.

## Hapus seluruh Furina dari Termux

```bash
hapus furina
```

Perintah ini menghapus data/runtime/model/launcher Furina dari Termux setelah konfirmasi, tetapi tidak menghapus shared Termux packages atau APK FurinaHub.

Non-interaktif:

```bash
hapus furina --yes
```
