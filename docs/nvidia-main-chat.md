> Catatan historis: NVIDIA untuk percakapan utama dihentikan pada 21 November 2026. NVIDIA pekerjaan latar tetap tersedia. Lihat `docs/ai-provider-audit-2026-11-21.md`.

# NVIDIA NIM untuk percakapan utama

Ditinjau 18 November 2026. Pilihan berada di **Pengaturan → AI dan API Key → AI opsional → Percakapan utama → NVIDIA NIM**. Masukkan key lalu Simpan; validasi yang berhasil mengaktifkan NVIDIA. Tambahkan beberapa key bila diperlukan, gunakan sakelar per-key atau sakelar penyedia, dan hapus key dengan tombol yang sudah ada. Key percakapan terpisah dari key pekerjaan latar.

Layout, komponen Radix, kelas kaca, dan pengaturan lama dipertahankan. Kelayakan usia mengikuti aturan API key percakapan Gemini yang sudah ada. Memilih Gemini mengembalikan kebijakan Gemini/Lovable lama. Memilih NVIDIA tidak mengaktifkan Lovable/Gemini sebagai fallback, termasuk ketika sakelar NVIDIA mati atau kuota habis. Pengaturan pekerjaan latar tetap independen; fitur ini tidak mengubah penyedia/biaya tugas latar yang sudah diaktifkan pengguna.

## Gratis, katalog dan validasi key

NVIDIA menyatakan akses gratis hosted NIM untuk **prototyping, penelitian, pengembangan dan evaluasi**, bukan jaminan produksi gratis tanpa batas. Lihat [General FAQ](https://docs.api.nvidia.com/nim/docs/product), [Run NIM Anywhere](https://docs.api.nvidia.com/nim/docs/run-anywhere), dan [API Catalog](https://build.nvidia.com/models). Antarmuka menampilkan batas ini. Tidak ada provisioning, endpoint partner, langganan, atau peningkatan berbayar otomatis.

Pemilihan kandidat mengambil irisan dua sumber langsung:

1. ID model hosted dari `https://integrate.api.nvidia.com/v1/models`.
2. Metadata katalog NVIDIA `https://api.ngc.nvidia.com/v2/search/catalog/resources/ENDPOINT`, memakai label `nim_type_preview`, atribut `PREVIEW=true`, dan kemampuan chat. Ini metadata yang dipakai NVIDIA untuk badge **Free Endpoint**. Status download `AVAILABLE` adalah hal berbeda: MiniMax M3.1 mempunyai `AVAILABLE=false` tetapi endpoint gratisnya berhasil diuji. Jangan menganggapnya sebagai status inferensi hosted.

Daftar `/models` bersifat publik: key palsu dapat memperoleh respons 200. Karena itu penambahan key **wajib** lulus inferensi kecil terautentikasi pada kandidat gratis terverifikasi, dengan prompt sintetis netral dan maksimum 32 token. HTTP 401, kuota, katalog tak terverifikasi atau tidak adanya inferensi sukses tidak menyimpan/mengaktifkan key. Uji validasi tidak mengirim riwayat percakapan pengguna.

Metadata gratis disimpan sementara maksimum lima menit, daftar ID maksimum dua menit. Setiap pemakaian mengiris ulang daftar ID dengan metadata gratis terbaru. Jika verifikasi yang sudah kedaluwarsa gagal, sistem berhenti; tidak memakai daftar lama atau endpoint berbayar. Respons model yang hilang tetap memicu rotasi. URL tujuan tetap NVIDIA dan redirect inferensi tidak diikuti. API publik tersebut tidak memberikan tarif token; fitur ini menggunakan status Free Endpoint resmi dan tidak mengklaim mengetahui sisa kuota akun secara pasti.

## Evaluasi dan urutan model

API dan katalog pada tanggal pemeriksaan memberikan enam kandidat percakapan: MiniMax M3.1 Flash, Nemotron 3 Ultra, Nemotron 3.5 Bolt, Super VL, Lightning, dan Nano Omni. Kandidat model berasal dari API, bukan daftar ID yang diasumsikan terus tersedia. Peringkat keluarga adalah heuristik kualitas yang sengaja dapat ditinjau; keluarga yang belum diuji tidak dimasukkan otomatis.

| Kandidat yang diuji    | Pengamatan pada percakapan sintetis dengan persona Furina dan memori SmartClip                                                                        |
| ---------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| MiniMax M3.1 Flash     | Prioritas utama: bahasa paling konsisten dan tidak menambahkan kutipan fiktif pada sampel. Sekitar 10–16 detik pada uji awal.                         |
| Nemotron 3 Ultra       | Cadangan berkualitas dan lebih cepat, sekitar 4 detik. Beberapa keluaran tetap memerlukan kehati-hatian terhadap detail yang diada-adakan.            |
| Nemotron 3.5 Bolt      | Ringkas dan cepat, sekitar 1 detik; urutan setelah Ultra untuk teks.                                                                                  |
| Nemotron 3.5 Super VL  | Mendukung gambar. Tanpa menonaktifkan thinking, uji awal menghabiskan batas token tanpa jawaban. Dengan thinking dimatikan, respons sekitar 1 detik.  |
| Nemotron 3.5 Lightning | Lebih rendah karena sampel melanggar arahan untuk tidak menarasikan aksi.                                                                             |
| Nemotron 3 Nano Omni   | Kandidat terakhir yang tersedia, termasuk gambar melalui metadata `usecase=Image-to-Text`/VLM. Tidak dinilai secara komprehensif pada uji dialog ini. |

Ini evaluasi terbatas, bukan bukti satu model selalu terbaik dalam semua roleplay. Semua model menerima persona Furina, Identity Core, instruksi usia, memori, riwayat, kutipan dan gambar yang **sama persis** dari builder chat yang sudah ada. Tidak ada persona alternatif per model. `enable_thinking=false` digunakan dan reasoning tidak dikembalikan sebagai pesan pengguna. Kandidat yang tidak mendukung gambar dilewati untuk giliran bergambar; gambar tidak dibuang diam-diam.

## Rotasi dan transparansi

Model/key sukses disimpan per akun dan dipertahankan untuk pesan berikutnya selama masih layak. Pengaturan menampilkan model terakhir dan pemberitahuan perubahan; perpindahan model juga dapat muncul sebagai pemberitahuan chat. Backup key/model baru diperiksa bila diperlukan, bukan seluruh key sebelum setiap pesan.

- Maksimum empat discovery key dan empat percobaan inferensi per giliran, dengan anggaran total sekitar 45 detik dan maksimum 20 detik per inferensi. Discovery HTTP dan pembacaan body dibatasi waktu. Tidak ada retry tanpa batas.
- HTTP 429 memberi cooldown pada key dan mencoba key lain. HTTP 408, timeout, dan error server memberi cooldown model. Model hilang (404/410) diberi jeda sepuluh menit. `Retry-After` yang valid tidak dipersingkat; cooldown default dipakai ketika header tidak tersedia.
- HTTP 401 menandai key tidak bisa digunakan; key yang tak lagi dapat didekripsi perlu ditambahkan ulang. Key rusak tidak terus menutupi key baru di belakangnya.
- HTTP 402 menghentikan giliran dan menyimpan jeda kuota percobaan untuk akun, tanpa berpindah ke layanan berbayar.
- Input tidak valid, penolakan moderasi (`content_filter`/`refusal`), dan pembatalan konfigurasi tidak dicoba ke model lain. Respons kosong/thinking-only dapat dicoba ke kandidat berikutnya.
- Tidak melakukan streaming dari percobaan yang gagal. Hanya satu completion sukses dikembalikan, sehingga rotasi tidak menambahkan bubble duplikat. Ini bukan jaminan exactly-once upstream: provider dapat menyelesaikan request yang responsnya timeout, tetapi hasil percobaan tersebut tidak diterbitkan ke UI.
- Aktivasi penyedia, kepemilikan, ciphertext dan status key diperiksa lagi sebelum discovery dan setiap inferensi. Pergantian penyedia menghentikan percobaan lanjutan; key yang dinonaktifkan/dihapus dilewati. Request yang sudah dikirim ke NVIDIA tidak bisa ditarik kembali secara atomik.

State/cooldown disimpan di Supabase, bukan hanya memori worker. RPC menggabungkan waktu cooldown yang lebih konservatif dan mempertahankan model sukses ketika request lain gagal. Respons polling lama di UI dibuang setelah mutasi, agar key yang dihapus atau pilihan penyedia baru tidak tampak dibatalkan.

## Penyimpanan dan migrasi

Migrasi tambahan: `supabase/migrations/20261118021140_furina_nvidia_main_chat.sql`.

- Tambah `chat_provider` (default `gemini`) dan `use_nvidia_chat` (default false); pilihan lama tidak diubah.
- `furina_nvidia_chat_keys`: AES-GCM, fingerprint terikat pemilik, suffix, aktivasi/invalid. Secret enkripsi memakai pola server yang sudah ada. Tidak ada key penuh dalam payload pengaturan, frontend bundle, repository, atau log.
- `furina_nvidia_chat_state`: model/key sukses, cooldown, notice. RLS aktif, akses tabel/RPC hanya service role. Foreign key key aktif dibersihkan ketika key dihapus; RPC menolak pengaitan key akun lain.
- Pelaporan penggunaan menerima provider `nvidia`. Memori, key pekerjaan latar, dan migrasi historis tetap dipertahankan.

Untuk rilis, terapkan migrasi tambahan melalui proses Supabase proyek, merge PR, pastikan Lovable memuat commit yang benar, lalu publikasikan melalui Lovable. Jangan mempublikasikan kode baru sebelum skema tersedia. API key uji dari percakapan tidak disimpan dalam database akun nyata; pengguna memasukkan key sendiri melalui pengaturan.

## Verifikasi

Hasil akhir: **111/111 tes Node lolos**, pemeriksaan TypeScript dan production build lolos. File baru dan kedua komponen pengaturan lolos ESLint; detector UI mengembalikan daftar temuan kosong.

- Tes unit/integrasi menjalankan katalog, routing dan handler asli dengan boundary eksternal terisolasi. Cakupan meliputi paid-only/unknown catalog, expiry, auth key, cooldown lintas pesan, retry limit/Retry-After, 408/402/503, key rusak, moderasi, respons kosong, model ditarik, gambar, provider/key berubah, enkripsi dan pemisahan akun.
- Migrasi diuji pada PostgreSQL 17 sementara: default lama, usage NVIDIA, larangan akses anon/authenticated, penggabungan cooldown, kepemilikan dan penghapusan key.
- Chromium menjalankan komponen pengaturan asli dengan API fixture pada 320/412/1024 px, terang/gelap: dropdown, tambah/hapus/nonaktif key, input keyboard, tidak ada overflow, token kaca dan polling terlambat. Fixture tidak menyambung akun produksi.
- Probe nyata dengan key uji: inferensi validasi kecil berhasil; key palsu ditolak; fallback setelah 503 buatan berhasil ke Nemotron Ultra dan model tetap dipakai pada giliran berikutnya; inferensi gambar berhasil melalui Super VL. Hanya konten sintetis dan ikon publik dipakai.
- Jalankan `FURINA_PG_TEST_CONTAINER=furina-nvidia-schema-test node --test tests/*.test.mjs`, `bunx tsc --noEmit`, `bun run build`, serta browser test yang dicatat di AGENTS.md.
- APK/perangkat Android fisik dan login Google produksi tidak diuji. UI browser diverifikasi pada fixture, bukan sesi Supabase pengguna nyata. Lint repo masih mempunyai utang format/rule lama; pemeriksaan file baru dan komponen yang diubah dijalankan terpisah.

## Catatan rilis

Perubahan disiapkan di [PR #238](https://github.com/WynnDev-rill/furina/pull/238). Migrasi `20261118021140` sudah diterapkan secara atomik pada database Furina yang terhubung ke Lovable dan tercatat di riwayat migrasi. Verifikasi sesudah migrasi memastikan RLS aktif, role anon/authenticated tidak memiliki akses tabel maupun RPC, service role memiliki akses, dan tabel key percakapan masih kosong. Tidak ada akun pengguna atau key uji yang dipakai sebagai fixture produksi.
