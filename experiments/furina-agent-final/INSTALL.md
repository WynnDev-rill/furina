# Instalasi Furina Termux

Private build saat ini: Core `1.1.26`, dependency revision `2026.08.27-r76`. FurinaHub tidak didistribusikan oleh installer/updater untuk sementara; source dan rilis lamanya tidak dihapus.

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

Semua sifat yang dipilih dilebur menjadi satu profil gabungan yang stabil dan tidak bergantung pada urutan klik. Core tidak bergantian menjadi sifat A lalu B. Konteks hanya mengubah tindakan dari watak gabungan yang sama. Kartu tindakan v2 mencakup situasi santai, dekat, bercanda, konflik, dan romantis; konflik atau batas user selalu mengalahkan teasing.

## Lanjutan

Buka **Pengaturan → Lanjutan**:

- **Training Room** — sembilan materi memakai prompt-only corpus percakapan Indonesia yang telah difilter. Panah kiri/kanan menggeser kartu `A`, `B`, `Lewati`, `R`, atau `Selesai`; Enter mengonfirmasi. Prompt yang dijawab atau dilewati dipensiunkan permanen di seluruh materi, sedangkan `R` mempertahankan prompt yang sama.
- **Saran latihan di chat** — nonaktif secara default. Saat aktif, sistem sesekali menawarkan carousel `A`, `B`, atau `Lewati` pada momen percakapan yang bernilai. Batas dan jedanya otomatis, maksimal dua tawaran per sesi; tidak ada pengaturan frekuensi. `Lewati` membuat satu jawaban normal baru dan chat langsung berlanjut.
- **Mode pasangan** — nonaktif secara default. Saat aktif, status dan tindakan romantis menjadi bagian dari respons; saat nonaktif, Furina tetap companion personal dan trait tidak dapat mengaktifkan hubungan romantis sendiri.
- **Memori penuh lokal** — nonaktif secara default. Saat aktif, seluruh teks percakapan baru diarsipkan lokal. FTS5 dan embedding multilingual opsional memilih maksimal enam potongan relevan; isi arsip tidak dikirim seluruhnya ke model.

Training Room adalah sandbox terpisah. Prompt korpus tidak menerima nama, sifat, mode pasangan, memori, atau preferensi user. Personalisasi baru diterapkan ketika model membuat kandidat A/B. Isi prompt tidak masuk ke chat, fakta, episode, relationship ledger, atau graph; hanya pola pilihan abstrak, ID prompt yang dipensiunkan, dan alasan reroll yang disimpan lokal. Dalam saran chat, data latihan hanya menyimpan hash pesan dan kutub preferensi—bukan salinan kedua isi percakapan.

Menonaktifkan Memori penuh lokal menghentikan arsip dan pencarian baru tetapi tidak menghapus data lama secara diam-diam.

## Model lokal

Tiga pilihan tetap tersedia:

- **wifuGPT 1.7B Q4_K_M** — ~1.03 GiB.
- **Qwen3 1.7B Heretic Q5_K_M** — ~1.17 GiB.
- **Qwen3 4B Instruct 2507 Uncensored Q4_K_M** — ~2.50 GB, Quality.

Status model: **Unduh → Kelola → Aktif**. Model yang sudah diunduh dapat dipilih atau dihapus dari menu yang sama. Jika model aktif adalah satu-satunya mesin chat yang siap, Furina memberi peringatan tegas sebelum penghapusan. Local tidak memiliki fallback diam-diam ke Online saat inferensi.

Download mendukung resume dan wajib lolos verifikasi GGUF + SHA-256. Model 4B tidak pernah diunduh otomatis oleh install/update.

## Percakapan dan memori 1.1.21

Grounded Dialogue State memisahkan ucapan user yang faktual dari wording Furina sendiri. Balasan Furina sebelumnya hanya dibawa ke turn baru jika user memang merujuknya untuk koreksi, klarifikasi, atau acknowledgement. Pergantian topik tidak membawa motif/kalimat balasan lama ke prompt Local.

Semua balasan conversational tetap dibuat oleh model yang dipilih. Response Rhythm Controller memberi target 1–6 gagasan: opini kasual biasanya dua, sedangkan audit nyata lima atau enam. Preferensi seperti “jawab ringkas” atau “jelaskan rinci” mengalahkan keputusan otomatis. Tidak ada canned social response atau rewrite isi jawaban.

Setiap proses Termux memulai thread jangka pendek baru. Memori terstruktur dasar tetap bekerja, tetapi pencarian teks lintas sesi hanya aktif saat **Memori penuh lokal** dinyalakan. Sumber pesan, tanggal, dan confidence ikut dibawa secara internal. Fakta yang dikoreksi membuat klaim lama berstatus superseded; episode lama tetap tersimpan sebagai sejarah tetapi tidak mengalahkan fakta aktif. Episode terkait digabung, sedangkan graph lokal mengaitkan user dengan orang, proyek, dan perangkat hanya dari pola eksplisit. Jika bukti recall lemah, Furina diperintah mengatakan tidak yakin daripada menebak.

Dialogue Decision Engine menggabungkan state emosi bertahap, tempo percakapan, kontrol bahasa, anti-klise, opini yang konsisten, silence-aware follow-up, dan inisiatif playful yang tunduk pada batas user. Semua kontrol ini masuk ke jalur generasi Local dan Online yang sama.

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
