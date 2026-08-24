# Instalasi Furina Lite + FurinaHub

Private build saat ini: Core `1.1.0`, FurinaHub `1.1.0` (`versionCode 10068`), dependency revision `2026.08.24-r50`.

## Instalasi baru

```bash
pkg update -y && pkg install -y curl
curl -fsSL https://github.com/WynnDev-rill/furina/releases/download/furina-update-stable/furina-install.sh | bash
furina
```

Bootstrap memverifikasi updater dan memastikan `llama-cpp` tersedia, tetapi tidak mengunduh model LLM. Semua GGUF hanya diunduh dari **Provider & Model**.

## Personalisasi

Buka **Pengaturan → Personalisasi** di Termux atau **Personalisasi** di FurinaHub. Keduanya membaca dan menulis state Core yang sama.

Ada 20 toggle independen: Tsundere, Yandere, Kuudere, Dandere, Deredere, Himedere, Kamidere, Sadodere, Mayadere, Bakadere, Hajidere, Darudere, Shundere, Utsudere, Bodere, Hiyakasudere, Nyandere, Oujodere, Genki girl, dan Onee-san type. Klik untuk aktif, klik lagi untuk nonaktif. Tidak ada batas jumlah kombinasi.

Core mengompilasi kombinasi ke facet perilaku yang ringkas; nama trope tidak dilempar sebagai daftar panjang ke model. Kombinasi besar tetap dipakai secara kontekstual.

## Model lokal

Tiga pilihan tetap tersedia:

- **wifuGPT 1.7B Q4_K_M** — ~1.03 GiB.
- **Qwen3 1.7B Heretic Q5_K_M** — ~1.17 GiB.
- **Qwen3 4B Instruct 2507 Uncensored Q4_K_M** — ~2.50 GB, Quality.

Status model: **Unduh → Pilih → Aktif**. FurinaHub dan Termux sekarang memakai pemilihan model Core yang sama. Memilih Local di salah satu permukaan mengubah state yang sama; Local tidak memiliki fallback diam-diam ke Online.

Download mendukung resume dan wajib lolos verifikasi GGUF + SHA-256. Model 4B tidak pernah diunduh otomatis oleh install/update.

## Percakapan 1.1.0

Grounded Dialogue State memisahkan ucapan user yang faktual dari wording Furina sendiri. Balasan Furina sebelumnya hanya dibawa ke turn baru jika user memang merujuknya untuk koreksi, klarifikasi, atau acknowledgement. Pergantian topik tidak membawa motif/kalimat balasan lama ke prompt Local.

Semua balasan conversational tetap dibuat oleh model yang dipilih. Adaptive pacing hanya memberi target kedalaman/panjang secara abstrak; tidak ada canned social response atau rewrite isi jawaban.

## FurinaHub task lifecycle

- Live response tetap streaming in-place.
- Conversation title tidak lagi membutuhkan worker/model inference terpisah.
- Poller update APK/Core di FurinaHub dihapus.
- Pemilihan model adalah aksi Core tunggal berdasarkan catalog id.
- Status/progress chat dibatasi pada chat aktif, bukan loop background permanen.

## Update: Termux sebagai satu-satunya owner

FurinaHub tidak lagi memiliki tombol/cek update sendiri. Jalankan:

```bash
furina update
```

Perintah ini memeriksa stable channel, memperbarui Core/dependency, memverifikasi FurinaHub APK bila ada versi baru, lalu membuka installer Android. Setelah APK baru dibuka, konfirmasi versi menyelesaikan transaksi update.

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

Menghapus data/runtime/model/launcher Furina dari Termux setelah konfirmasi, tetapi tidak menghapus shared Termux packages atau APK FurinaHub.
