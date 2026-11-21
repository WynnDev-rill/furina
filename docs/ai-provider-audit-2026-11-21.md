# Audit AI dan API key Furina — 21 November 2026

## Perubahan

NVIDIA NIM dihentikan untuk percakapan utama, baik pilihan UI maupun endpoint server dan routing inferensinya. Preferensi NVIDIA percakapan yang tersimpan diabaikan. Gemini personal dan Lovable mengikuti sakelar masing-masing; Lovable tidak diaktifkan otomatis untuk akun yang sebelumnya menonaktifkannya. Persona, Identity Core, konteks usia, histori, kutipan, lampiran, dan memori percakapan tetap memakai jalur yang sama.

NVIDIA untuk pekerjaan latar tetap tersedia bersama OpenRouter. Tabel key terenkripsi, state historis, riwayat penggunaan dan migrasi tidak dihapus. Key NVIDIA percakapan lama tidak dipindahkan atau diaktifkan sebagai key latar.

## Temuan yang direproduksi dan diperbaiki

1. **Validasi key NVIDIA latar keliru memakai katalog publik.** Kontrol negatif langsung pada API mengembalikan HTTP 200 untuk `/models`, baik tanpa autentikasi maupun dengan key sintetis palsu; inferensi dengan key palsu ditolak HTTP 403. Penyimpanan kini memerlukan dua uji inferensi terautentikasi: teks Bolt singkat dengan thinking dimatikan serta embedding 2.048 nilai finite yang cocok dengan penyimpanan memori. Ada deadline total 16 detik. Kegagalan autentikasi, akses, kuota, model, respons rusak atau layanan mencegah penyimpanan; pesan tidak menampilkan key atau isi error upstream.
2. **Gemini menerima teks parsial sebelum memeriksa penanda moderasi.** Pengujian awal mengembalikan HTTP 200 walaupun kandidat bertanda `SAFETY`/`RECITATION` atau prompt diblokir. Pemeriksaan kini mendahului pembacaan teks, mengembalikan 422 dan menghentikan retry/fallback untuk respons tersebut.
3. **Respons yang tidak dipakai tertinggal saat rotasi/fallback.** Uji stream membuktikan body respons key yang ditolak, kuota yang dilewati, dan penyedia yang tidak dipakai tidak dibatalkan. Respons tersebut kini dilepas, sementara respons akhir tetap dapat dibaca. Error chat terminal juga melepas body sebelum ditampilkan.

## Logika yang diperiksa dan dipertahankan

- Gemini personal hanya untuk akun terverifikasi yang memenuhi batas usia dan mengaktifkan Gemini. Key diambil menurut waktu pembuatan lalu ID; key invalid dilewati, ciphertext dibuka di server dan terikat pemiliknya.
- Gemini mencoba model 3.8 Flash lalu 3.6 Flash untuk model tidak ditemukan, overload atau timeout, dalam deadline percakapan. Kuota 429 mencoba key berikutnya; penolakan kredensial eksplisit menandai key invalid. Kegagalan akses umum tidak menggilir key tanpa alasan.
- Lovable hanya dipanggil jika sakelarnya aktif. Kuota, gangguan Gemini, atau tidak adanya key yang dapat dipakai dapat memakai Lovable sesuai kebijakan lama. Penolakan moderasi dan akses non-revokasi tidak diteruskan ke penyedia lain. Model gateway mempertahankan urutan yang ada dan hanya beralih pada 429/503.
- Pekerjaan latar tetap OpenRouter → NVIDIA → Lovable, sesuai aktivasi. OpenRouter memakai `openrouter/free`; NVIDIA memakai model teks/embedding khusus yang sudah digunakan aplikasi. Kedua ID NVIDIA masih tercantum pada katalog API saat audit. Model embedding tidak diganti sembarangan karena ruang vektor memori harus konsisten.
- UI tetap memakai komponen dan tema glass Furina. Guard terhadap polling lama dipertahankan. Data key yang dikembalikan ke browser hanya metadata/suffix.

## Verifikasi

- `bun install --frozen-lockfile`: tidak mengubah dependensi.
- `tsc --noEmit` dan build produksi berhasil.
- 75 tes lulus, tanpa kegagalan atau skip, termasuk migrasi/RLS pada PostgreSQL sementara dengan data sintetis. Tidak ada uji tulis pada akun produksi.
- Browser Chromium: 320/412/1024 px, terang/gelap, tidak overflow, token glass tetap sama, simpan/hapus key, aktivasi Gemini, pilihan NVIDIA latar, keyboard, composition event, reduced motion, dan race polling.
- Peninjauan terpisah memeriksa penghapusan jalur NVIDIA utama, pemisahan latar, keamanan data, dan format probe. Temuan dimensi embedding serta thinking probe ditangani.
- Peta Graphify diperbarui; parser SQL opsional tidak tersedia, sehingga verifikasi SQL memakai tes PostgreSQL langsung.

## Bagian yang masih memerlukan referensi

Sistem “deteksi otomatis mirip Levyra” belum ditambahkan: repo atau tautan Levyra yang dimaksud belum diberikan. Pencarian pada akun GitHub dan workspace Lovable terhubung tidak menemukannya; hasil publik dengan nama sama tidak cukup untuk memastikan perilaku yang diminta. Implementasi deteksi akan mengikuti referensi yang dikonfirmasi, menggunakan tema Furina yang sama.

Uji keberhasilan inferensi memakai fixture, bukan key pribadi produksi. API NVIDIA langsung hanya dipakai untuk kontrol negatif dan ketersediaan katalog. Tidak ada perubahan aturan biaya, prioritas model, atau fitur deteksi baru berdasarkan dugaan.
