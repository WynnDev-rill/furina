# Instalasi Furina Lite + FurinaHub

Private build saat ini: Core `1.0.3`, FurinaHub `1.0.3` (`versionCode 10061`), dependency revision `2026.08.24-r43`.

## Instalasi baru

```bash
pkg update -y && pkg install -y curl
curl -fsSL https://github.com/WynnDev-rill/furina/releases/download/furina-update-stable/furina-install.sh | bash
furina
```

Bootstrap memverifikasi updater dan menyiapkan runtime yang diperlukan. `llama-cpp` adalah runtime untuk model lokal dan ikut dipastikan tersedia, tetapi instalasi baru **tidak mengunduh GGUF/model LLM**. Model tetap opsional dan hanya diunduh dari **Provider & Model**.

Menu Furina Lite tetap: **Chat**, **Provider & Model**, **Pengaturan**, **Exit**. Memory/Psyche aktif internal dan tidak menjadi menu pemeliharaan.

## Model lokal

Katalog lokal hanya:

- **wifuGPT 1.7B Q4_K_M** — ~1.03 GiB.
- **Qwen3 1.7B Heretic Q5_K_M** — ~1.17 GiB.

Status model adalah **Unduh → Pilih → Aktif**. Unduhan mendukung resume dan baru dapat dipilih setelah byte-size, header GGUF, dan SHA-256 sesuai metadata pin.

Saat Local dipilih atau Chat Local dibuka, Furina menyiapkan model di background. Model yang sehat dipertahankan warm hingga sekitar 10 menit idle.

### Perbaikan Local Fast Path 1.0.3

1.0.3 memperbaiki perangkat 1.0.2 yang masih menyimpan context `6144` menjadi `4096`, menghapus inferensi classifier tersembunyi dari percakapan biasa, memperkecil prompt Local secara adaptif tanpa menghapus memory, dan menunda pekerjaan memory LLM sampai Local idle sekitar dua menit. Jika user kembali saat background work berjalan, foreground chat diprioritaskan dan pekerjaan memory ditunda kembali.

Persona Local tetap membawa identitas Furina, karakter, hubungan pasangan, memory/context relevan, sampling, dan budget jawaban yang sama. Boilerplate Android-agent dan contoh dialog tidak lagi dikirim pada setiap chat kasual Local. Online tetap memakai prompt penuh.

`llama-server` normal menggunakan optimasi yang didukung binary. Jika optimized launch gagal, Furina mencoba ulang CPU baseline yang minimal dan aman. Positive process priority tidak dipaksakan di Termux. Streaming Local maupun Online tetap aktif.

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

FurinaHub memakai Core, katalog model, runtime, dan state model yang sama dengan Furina Lite. Pemilihan Local juga memicu background preparation. Status tetap **Unduh/Pilih/Aktif**, dan Memory/Psyche tetap internal-hidden.

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
