# Furina Companion

## Batas proyek

`main` berisi aplikasi web Lovable yang berasal dari `fdaf0a3` (6 Juli 2026). Lovable menyajikannya di `https://furina.lovable.app/`. `webview-android/` adalah launcher Android untuk situs tersebut. Proyek Termux dan aplikasi native generasi lain berada di riwayat yang terpisah. Pertahankan riwayat dan gunakan Lovable untuk publikasi produksi.

## Arsitektur

- `src/routes/index.tsx` menangani percakapan, panel pengaturan, identitas tamu, pilihan suara, dan cache browser. `src/styles.css` memuat tema dan tata letak responsif.
- `src/lib/furina.functions.ts` menjalankan chat, RAG, pengelolaan memori, sapaan, VOICEVOX, dan XTTS. `src/lib/furina-identity.server.ts` memverifikasi identitas sebelum operasi service-role terkait pengguna. Tamu lama memakai UUID acak privat sebagai kredensial dan UUID akun diverifikasi melalui Supabase Auth.
- `src/start.ts` memasang middleware untuk meneruskan sesi Supabase dari browser. Simpan kredensial server di Lovable/Supabase. Tabel akun bergantung pada RLS. Pertahankan data pengguna dan migrasi historis.
- Keep provider fallback policy, chat model ordering, and usage-share calculations in pure, independently tested helpers so status and reporting rules stay isolated from server handlers and UI.
- `src/lib/main-chat-provider.ts` menentukan akses Gemini personal dan Lovable untuk percakapan. Preferensi NVIDIA main-chat lama diabaikan sejak 21 November 2026; tabel ciphertext dan migrasi historis tetap disimpan. NVIDIA hanya tersedia untuk pekerjaan latar. Jangan menganggap daftar model NVIDIA publik sebagai bukti key valid: penyimpanan key latar wajib menguji inferensi teks dan embedding terautentikasi dengan deadline.
- Gemini memeriksa status moderasi sebelum menerima teks parsial. Rotasi key membuang respons yang tidak dipakai, mempertahankan respons kuota terakhir jika semua key terbatas. Fallback penyedia menghormati sakelar Lovable; moderasi dan kegagalan akses non-revokasi tidak memicu pergantian penyedia. Jika semua key ditolak sebagai tidak valid atau tidak bisa dibuka, kebijakan lama dapat memakai Lovable hanya bila sakelar Lovable aktif.
- Tes routing/handler: `node --test tests/*.test.mjs`. Tes migrasi terisolasi memerlukan `FURINA_PG_TEST_CONTAINER` untuk container PostgreSQL sementara. Tes browser komponen asli dengan API fixture: `FURINA_PLAYWRIGHT_MODULE=<module Playwright terpasang> node tests/ai-settings.browser.mjs`; gunakan Chromium lokal dan jangan memakai akun produksi.
- `src/lib/android-auth.ts` menghubungkan login Lovable di browser Android dengan sesi WebView. Kunci dan payload OAuth hanya berada di fragmen URL, dan payload yang kembali terenkripsi. `MainActivity.java` hanya membuka konten Furina di WebView dan memicu browser sistem untuk autentikasi.
- `webview-android/README.md` mencatat asal ikon, proses build Android, dan penandatanganan.

## Workflow

1. Verification-First. Catat kondisi awal, reproduksi dengan data uji terisolasi, lalu tentukan cara verifikasi. Periksa jalur normal dan kegagalan sebelum publikasi. Jangan melakukan pengujian tulis pada akun pengguna produksi.
2. Asset-First. Periksa aset, komponen Radix, dan riwayat Git lebih dulu. Untuk redesign besar, bandingkan 3–5 produk sejenis. Gunakan visual Furina yang sudah tersedia dan dokumentasikan commit asal aset historis.
3. Pakai Bun sesuai `bun.lock`. Jalankan `bun install --frozen-lockfile`, `bun run dev`, `bunx tsc --noEmit`, dan `bun run build`. Untuk Android, jalankan `gradle -p webview-android :app:assembleDebug` dengan JDK 17+ dan SDK 35.
4. Untuk perubahan UI, ukur lebar 320, 412, dan ≥1024 px. Uji terang/gelap, fokus keyboard, reduced motion, input IME, lampiran, dan scroll. Untuk autentikasi Android, cek browser sistem, pembatalan, kembali ke aplikasi, serta relog dan pemisahan akun/tamu. Laporkan batas pengujian secara eksplisit.
5. Pertahankan `main` selama verifikasi. Buat PR dengan catatan perubahan dan verifikasi. Setelah merge, cek commit yang dimuat Lovable, publikasikan lewat Lovable, lalu cek situs dan jalur APK.

## Skill coding

Skill proyek tersimpan di `.agents/skills/` dan dipasang dengan versi yang dicatat di `.agents/skills/SOURCES.md`. Pakai Ponytail dalam mode Full untuk implementasi. Pakai Ultra saat investigasi perlu menantang kompleksitas, dengan seluruh perilaku yang diminta tetap dipenuhi. Pakai UI UX Pro Max saat meneliti opsi desain dan Impeccable saat memoles serta mengaudit hasil. Keputusan visual yang sudah disetujui tercatat di `DESIGN.md`.

Graphify membantu menemukan relasi modul, dan kode sumber tetap menjadi sumber kebenaran. Baca `graphify-out/GRAPH_REPORT.md` atau jalankan `graphify query 'How does FurinaApp send a message?'`. Regenerasi peta struktural setelah perubahan arsitektur dengan `pip install graphifyy==0.9.108` lalu `graphify update .`. Gunakan script dan panduan skill seperlunya. Direktori skill tidak dibundel ke aplikasi.

## Identity Core

`src/lib/identity-core.ts` owns the fixed character anchor and evidence rules. `identity-core.server.ts` stores bounded state per verified account or legacy guest identity, using revision checks for competing writes. Preserve the separation between the app's persona, durable identity development, retrieved facts and memories, and contextual reactions. Follow `docs/identity-core.md` for the review policy and verification commands.
