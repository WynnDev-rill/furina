# Instalasi Furina Lite + FurinaHub

Private build saat ini: Core `1.0.7`, FurinaHub `1.0.7` (`versionCode 10065`), dependency revision `2026.08.24-r47`.

## Instalasi baru

```bash
pkg update -y && pkg install -y curl
curl -fsSL https://github.com/WynnDev-rill/furina/releases/download/furina-update-stable/furina-install.sh | bash
furina
```

Bootstrap memverifikasi updater dan menyiapkan runtime yang diperlukan. `llama-cpp` adalah runtime untuk model lokal dan ikut dipastikan tersedia, tetapi instalasi baru **tidak mengunduh GGUF/model LLM**. Model tetap opsional dan hanya diunduh dari **Provider & Model**.

Menu Furina Lite tetap: **Chat**, **Provider & Model**, **Pengaturan**, **Exit**. Memory/Psyche aktif internal dan tidak menjadi menu pemeliharaan.

## Perilaku sesi Chat Termux

Short-term history terpisah dari long-term memory.

- Menjalankan `furina` dari proses baru memulai thread Chat Termux yang baru saat pesan pertama dikirim.
- Chat yang terlihat kosong tidak membawa percakapan Termux sebelumnya ke prompt.
- `/back` lalu masuk lagi ke Chat selama proses `furina` yang sama tetap melanjutkan thread saat ini.
- Menutup proses `furina` lalu menjalankannya lagi membuat short-term thread baru; thread lama tetap tersimpan.
- Memory personal terpercaya, relationship state, profile, provider/API, pilihan model, model lokal, dan shared moments tetap persisten.
- FurinaHub mempertahankan conversation selection miliknya sendiri; pembuatan sesi Termux tidak mengganti active conversation FurinaHub.

## Model lokal

Katalog lokal hanya:

- **wifuGPT 1.7B Q4_K_M** — ~1.03 GiB.
- **Qwen3 1.7B Heretic Q5_K_M** — ~1.17 GiB.

Status model adalah **Unduh → Pilih → Aktif**. Unduhan mendukung resume dan baru dapat dipilih setelah byte-size, header GGUF, dan SHA-256 sesuai metadata pin.

Saat Local dipilih atau Chat Local dibuka, Furina menyiapkan model di background. Model yang sehat dipertahankan warm hingga sekitar 10 menit idle.

### Conversation Quality Guard 1.0.7

Untuk Local, Core sekarang membedakan jenis konteks yang benar-benar dibutuhkan:

- Sapaan/filler pada thread baru seperti `hai` atau `hmm` dijawab langsung oleh Core agar model roleplay 1.7B tidak mengarang konteks.
- Obrolan generic tidak menerima memory personal yang tidak relevan. Memory bersama tetap dimasukkan saat user memang menanyakan fakta personal, preferensi, tujuan, profil, atau hubungan.
- Prompt Local mewajibkan format chat satu-lawan-satu dan melarang screenplay, dialog user imajiner, narasi pikiran user, atau pembukaan formal yang tidak natural.
- Beberapa kata pertama ditahan sangat singkat sebelum ditampilkan. Jika terdeteksi pola script-mode seperti `Saya mohon izin...`, fake `User:`/`Assistant:`, atau continuity palsu pada thread baru, jawaban tidak ditampilkan dan satu repair pass ringkas dijalankan.
- Short casual turn memakai temperature cap lebih konservatif, sedangkan pertanyaan mendalam tetap mempunyai budget lebih besar.

Perbaikan ini tidak mengganti wifuGPT/Qwen, quantization, memory database, atau conversation history yang sudah ada.

Jika runtime llama.cpp sengaja terhapus, installer/update atau runtime Local akan mencoba memulihkan paket `llama-cpp` tanpa menyentuh model yang sudah diunduh.

## Pengaturan

Kontrol yang jarang dipakai berada di **Pengaturan**:

- Identitas
- Kontrol perangkat
- Sistem
- Backup
- Update & Recovery

Kontrol Android tetap Normal/Shizuku/Root sesuai pilihan user.

## Update dan recovery

```bash
furina update
```

Jika updater lokal rusak/hilang:

```bash
furina recover
```

Untuk validasi ulang snapshot dan integrasi:

```bash
furina repair
```

Update Core/bridge menggunakan snapshot terverifikasi dan atomic swap. Data user di `~/.furina-agent/`—conversation, memory, provider secrets, local models, personalization, shared moments—tidak diganti oleh update normal.

## FurinaHub

FurinaHub memakai Core, katalog model, runtime, dan long-term personal memory yang sama dengan Furina Lite. Message history tetap mengikuti conversation/thread masing-masing surface. Pemilihan Local juga memicu background preparation. Status tetap **Unduh/Pilih/Aktif**, dan Memory/Psyche tetap internal-hidden.

Jika channel berisi APK baru, updater membuka Android Package Installer setelah verifikasi. Bundle baru baru dianggap terpasang setelah FurinaHub versi baru dijalankan dan mengonfirmasi dirinya ke Termux.

## Hapus seluruh Furina dari Termux

```bash
hapus furina
```

Perintah meminta konfirmasi `HAPUS`, lalu menghapus data/runtime/model/launcher Furina dari Termux. Ia tidak menghapus shared Termux packages dan tidak meng-uninstall APK FurinaHub Android.

Non-interaktif yang disengaja:

```bash
hapus furina --yes
```

## Plugin

OpenConnector tetap lokal dan opsional. No-op update tidak mengulang setup Plugin yang berat.

```bash
furina-openconnector status
furina-openconnector repair
furina-openconnector logs
```
