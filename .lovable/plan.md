
# Rencana Upgrade

## 1. Login Google = sinkronisasi penuh per akun (PRIORITAS UTAMA)

**Tujuan:** Saat login Google, *seluruh* data ikut ke akun (chat, persona, setting, voice sample, tema, bahasa, dll). Saat logout → kembali ke mode guest dengan data guest-nya sendiri (terpisah). User baru pertama kali login = bersih. Tidak ada kebocoran antar user.

### Skema data baru di Cloud
- Tabel `conversations` & `messages` sudah ada → tetap dipakai (sudah RLS by `user_id`).
- Tambah kolom `messages.image_url` (cache gambar opsional).
- Tabel `user_settings` sudah ada (`data jsonb`) → dipakai untuk *semua* setting (persona, name, bg, lang, speed, provider, vvSpeaker, vvTranslate, theme, preGen, cloneSampleName).
- Voice sample file → upload ke bucket `voice-samples` privat (sudah ada), path `{user_id}/sample.{ext}`. Kolom `user_settings.data.cloneSamplePath` simpan referensi.

### Logika sinkronisasi
- **Mode guest** (belum login): semua tetap di `localStorage` dengan namespace `furina:guest:*`. Tidak menulis ke DB.
- **Saat login Google:**
  1. Cek `user_settings` & `conversations` user di DB.
  2. Jika DB **kosong** dan localStorage punya data guest → tawarkan *one-time migration* (toast: "Pindahkan data guest ke akun?"). Jika ya → upload semua (settings + conversations + messages + voice sample), tandai `furina:migratedTo:{userId}=true`, lalu **hapus localStorage guest**.
  3. Jika DB **sudah ada** → abaikan localStorage guest, load dari DB.
  4. Realtime: setiap perubahan setting / kirim pesan / buat conversation → langsung `upsert` ke DB (debounced).
- **Saat logout:** clear semua state in-memory & semua key `furina:*` di localStorage kecuali namespace guest (yang memang milik browser ini sebelum pernah login). User baru di device sama = state guest kosong.
- **User baru pertama kali login:** DB kosong, localStorage juga tidak punya guest data milik dia → app mulai bersih. Tidak pernah baca data user lain (RLS + filter `user_id` di setiap query).

### Keamanan
- Semua query pakai client Supabase ber-session (RLS aktif `auth.uid() = user_id`).
- Server fn yang pakai `supabaseAdmin` (RAG memori) **wajib filter** `user_id` dari context auth — tidak terima `userId` dari body lagi → ubah `chatWithFurina`, `listMemories`, dll. pakai `requireSupabaseAuth` middleware untuk user login. Untuk guest, pakai guestId tapi memori guest disimpan ke `user_id` placeholder yang **unik per browser** (UUID generated, tidak pernah collision dengan user real).
- Guest memori & data **tidak pernah** ter-query oleh user login (filter ketat by `user_id`).

## 2. Memori percakapan menyeluruh + improvisasi (PRIORITAS 2)

- **Recall lebih luas**: RAG saat ini ambil 6 memori. Naikkan ke 10 + tambahkan **ringkasan percakapan lama** sebagai memori turunan.
- **Auto-summarize**: setiap conversation yang sudah > 20 pesan → trigger background job (server fn dipanggil setelah balasan ke-20, 40, 60) yang minta Gemini bikin ringkasan padat lalu disimpan sebagai memori bertipe `summary` di tabel `memories` (tambah kolom opsional `kind text default 'fact'`).
- **Cross-conversation context**: saat mulai pesan baru, ambil juga 2 ringkasan paling relevan dari conversation **lain** (via embedding) → diselipkan ke system prompt.
- **Belajar gaya user**: tiap N pesan, extract preferensi gaya bicara user (panjang reply, formalitas, topik favorit) → disimpan sebagai memori `style`. Furina pakai itu untuk menyesuaikan.
- **Improvisasi**: tambahkan instruksi di persona: "Variasikan reaksi berdasarkan memori. Jangan ulangi frasa yang sama dari balasan sebelumnya. Boleh refer balik ke topik lama secara natural."

## 3. Voice clone yang benar-benar berfungsi

Masalah sekarang: HF Inference `coqui/XTTS-v2` sering 404 / butuh GPU berbayar. Ganti strategi:

- **Engine baru: `fishaudio/fish-speech` Space gratis di HF** (atau alternatif `tts-arena` Space) → akses via Gradio Client API (gratis, tanpa token, hanya rate-limited).
- Implementasi pakai endpoint Gradio publik (`https://<space>.hf.space/api/predict`) → kirim text + sample wav (base64), terima audio.
- Fallback chain: **Fish-Speech** → kalau gagal **XTTS demo space** → kalau gagal kasih pesan "server clone sedang ramai, coba lagi 1 menit".
- Sample audio diupload ke bucket `voice-samples` (signed URL 1 jam) sehingga server fn bisa fetch ulang tanpa simpan base64 di localStorage (lebih cepat).
- Tambahkan progress indicator dan timeout 60 detik di UI.

## 4. Sticker pack gratis tanpa API

- Pakai **dataset emoji/sticker statis** yang di-bundle (TwemojiAnimated atau Telegram-style PNG pack gratis lisensi CC).
- Tombol stiker di composer → buka popover berisi grid ±60 stiker, kategori (emosi, reaksi, anime).
- Kirim stiker = pesan dengan tipe `sticker` (URL ke file static di `/public/stickers/`).
- Untuk Furina bisa "baca" stiker yang user kirim: tiap stiker punya metadata `label` (ex: "menangis", "tertawa"). Saat dikirim, content message = `[stiker: menangis]` → AI paham konteksnya tanpa perlu vision.
- Furina juga bisa balas stiker: di response, kalau dia output token spesial `:sticker:nama:`, frontend render sebagai stiker.

## 5. Formatting waktu yang natural

Ubah `humanizeDelta` jadi natural Indonesia:
- `< 10 detik` → "baru saja"
- `< 60 detik` → "beberapa detik lalu"
- `< 2 menit` → "barusan"
- `< 10 menit` → "beberapa menit lalu"
- `< 30 menit` → "sekitar X menit lalu" (round ke 5)
- `< 45 menit` → "setengah jam lalu"
- `< 90 menit` → "sekitar sejam lalu"
- `< 6 jam` → "sekitar X jam lalu"
- hari yg sama → "tadi pagi/siang/sore/malam"
- kemarin → "kemarin"
- > 1 hari → "X hari lalu"

Persona instruction diperketat: **jangan pernah sebut menit/jam pasti** kecuali user nanya. Selalu pakai bahasa kira-kira.

## Detail teknis

**File yang diubah:**
- `src/lib/furina.functions.ts` — `humanizeDelta` baru, `chatWithFurina` pakai `requireSupabaseAuth` (versi authed) + tetap ada versi guest, RAG diperluas, summary helper, sticker label handling, hapus XTTS code, tambah Fish-Speech caller.
- `src/routes/index.tsx` — sync layer baru (load/save semua state ke DB saat login), logout clears, sticker picker, voice clone via upload bucket.
- Migration SQL:
  - `ALTER TABLE messages ADD COLUMN IF NOT EXISTS image_url text, ADD COLUMN IF NOT EXISTS sticker_id text;`
  - `ALTER TABLE memories ADD COLUMN IF NOT EXISTS kind text NOT NULL DEFAULT 'fact';`
- Asset baru: `public/stickers/*.png` (± 60 file, kategori folder).

**Secret:** tidak perlu tambahan (Fish-Speech space gratis tanpa token; kalau perlu fallback HF, pakai `HUGGINGFACE_TOKEN` yang sudah ada di plan sebelumnya — opsional).

## Urutan eksekusi
1. Migration DB + bucket policy.
2. Refactor auth sync (login/logout/migration) — prioritas 1.
3. Refactor memori (summary, cross-convo recall) — prioritas 2.
4. Voice clone Fish-Speech.
5. Sticker pack + UI.
6. Natural time formatting + persona tweak.
7. QA: test guest→login→logout flow, dua akun berbeda di device sama (pastikan tidak bocor).
