# Instalasi Furina Lite + FurinaHub

Private build saat ini: Core `1.0.8`, FurinaHub `1.0.8` (`versionCode 10066`), dependency revision `2026.08.24-r48`.

## Instalasi baru

```bash
pkg update -y && pkg install -y curl
curl -fsSL https://github.com/WynnDev-rill/furina/releases/download/furina-update-stable/furina-install.sh | bash
furina
```

Bootstrap memverifikasi updater dan menyiapkan runtime yang diperlukan. `llama-cpp` ikut dipastikan tersedia, tetapi instalasi baru **tidak mengunduh GGUF/model LLM**. Model hanya diunduh dari **Provider & Model**.

Menu Furina Lite tetap: **Chat**, **Provider & Model**, **Pengaturan**, **Exit**.

## Perilaku sesi Chat Termux

Short-term history terpisah dari long-term memory.

- Proses `furina` baru membuat thread Chat Termux baru saat pesan pertama dikirim.
- Chat kosong tidak membawa percakapan Termux sebelumnya ke thread baru.
- `/back` lalu kembali ke Chat dalam proses yang sama tetap memakai thread saat ini.
- Memory personal terpercaya, relationship state, profile, provider/API, pilihan model, model lokal, dan shared moments tetap persisten.
- FurinaHub mempertahankan conversation selection miliknya sendiri.

## Model lokal

Katalog lokal hanya:

- **wifuGPT 1.7B Q4_K_M** — ~1.03 GiB.
- **Qwen3 1.7B Heretic Q5_K_M** — ~1.17 GiB.

Status model adalah **Unduh → Pilih → Aktif**. Unduhan mendukung resume dan diverifikasi dengan byte-size, header GGUF, dan SHA-256.

Saat Local dipilih atau Chat Local dibuka, Furina menyiapkan model di background dan mempertahankannya warm sekitar 10 menit idle.

### Grounded Dialogue State 1.0.8

1.0.8 menghapus conversational fast response, regex rewrite, held-prefix content guard, dan repair generation yang sebelumnya membuat chat terasa diprogram.

Setiap balasan percakapan sekarang benar-benar dihasilkan model yang sedang dipilih. Core hanya menyusun konteks menjadi tiga lapisan:

1. **Dialogue State** — keadaan thread saat ini: fresh/active, jenis respons user terbaru, topik yang benar-benar dibuat user, ucapan user sebagai evidence, dan ucapan Furina lama sebagai continuity yang belum tentu benar.
2. **Trusted Memory** — fakta personal dari shared Core Memory yang masuk hanya jika semantic retrieval menemukan kecocokan.
3. **Persona** — menentukan karakter Furina dan chemistry percakapan, bukan menciptakan fakta atau skenario.

Jika Furina menebak sesuatu dan user menjawab `tidak`, tebakan sebelumnya diberi status corrected/rejected. Jika user bertanya `maksud?`, ucapan Furina sebelumnya tetap tersedia untuk continuity tetapi tidak berubah menjadi fakta tentang user.

wifuGPT mendapat grounding lebih kuat karena ia memang waifu/roleplay fine-tune dari dataset multi-turn sintetis yang relatif kecil. Qwen3 Heretic tetap memakai non-thinking mode dan sampling yang dekat dengan rekomendasi Qwen3. Kedua model tetap sama; tidak ada pergantian quantization.

Jika runtime llama.cpp terhapus, installer/update atau runtime Local mencoba memulihkan paket `llama-cpp` tanpa menyentuh model yang sudah diunduh.

## Pengaturan

Kontrol yang jarang dipakai berada di **Pengaturan**:

- Identitas
- Kontrol perangkat
- Sistem
- Backup
- Update & Recovery

## Update dan recovery

```bash
furina update
furina recover
furina repair
```

Update Core/bridge memakai snapshot terverifikasi dan atomic swap. Data user di `~/.furina-agent/`—conversation, memory, provider secrets, local models, personalization, shared moments—tidak diganti oleh update normal.

## FurinaHub

FurinaHub memakai Core, katalog model, runtime, dan long-term personal memory yang sama dengan Furina Lite. Message history tetap mengikuti conversation/thread masing-masing surface. FurinaHub mempertahankan in-place streaming sehingga live chat tidak melakukan full rerender.

## Hapus seluruh Furina dari Termux

```bash
hapus furina
```

Perintah meminta konfirmasi `HAPUS`, lalu menghapus data/runtime/model/launcher Furina dari Termux. Ia tidak menghapus shared Termux packages dan tidak meng-uninstall APK FurinaHub Android.

Non-interaktif:

```bash
hapus furina --yes
```

## Plugin

```bash
furina-openconnector status
furina-openconnector repair
furina-openconnector logs
```
