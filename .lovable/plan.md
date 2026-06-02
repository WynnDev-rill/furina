Permintaanmu besar — aku pecah jadi 6 blok kerja. Semua dikerjakan dalam satu pass.

## 1. Fix bug VOICEVOX & TTS chat lama
**Penyebab voice gagal:** mp3 dari `tts.quest` di-fetch oleh server, di-base64-kan, dikirim balik ke browser. Untuk balasan panjang base64 bisa >1MB → server-fn timeout/tertolak. Audio chat lama gak bisa diputar karena base64 tidak disimpan, cuma di state sementara.

**Fix:**
- Streaming audio langsung dari URL `mp3DownloadUrl` ke `<audio>` (skip base64 round-trip) → no size limit, instant playback.
- Cache `audioUrl` per-message di tabel `messages` (kolom baru `audio_url`, `audio_emotion`) → chat lama tetap bisa diputar.
- Tombol play tetap men-trigger generate kalau belum ada cache.
- Loading badge hanya saat user klik play (sudah benar di versi terakhir, dipertahankan).

## 2. Hapus ElevenLabs, ganti voice engine baru
- Hapus semua kode ElevenLabs (server-fn `speakFurina`, `cloneVoiceFromSamples`, `listElevenLabsVoices`, `deleteElevenLabsVoice`, UI clone di settings).
- Engine baru tersedia per karakter:
  - **VOICEVOX** (default, gratis stabil) — dengan emotion profile yang sudah ada.
  - **Recommended preset per karakter** — Furina dipetakan ke VOICEVOX speaker yang paling mendekati (style manja-anggun, mis. *Nijisanji Lize Helesta-style*).
  - **Voice Clone (HuggingFace XTTS-v2)** — server-fn baru `speakClone` memanggil HF Inference API (`coqui/XTTS-v2`) dengan sampel suara yang user upload. Gratis tapi user perlu set HF token sekali (free dari huggingface.co).
  - **"Original voice" mode** — jika user upload sampel asli (mis. dump JP Furina dari Genshin), pakai XTTS clone dengan sampel itu. UI menyebut "Suara asli karakter (jika sampel diupload)". Aku tidak akan menyertakan voice line Genshin (hak cipta HoYoverse) — user yang upload sendiri.

## 3. Google Login (opsional, di Settings)
- Aktifkan Google OAuth via `supabase--configure_social_auth`.
- Tombol "Masuk dengan Google" di panel Settings (tidak wajib, app tetap jalan sebagai guest).
- Saat login pertama:
  - Semua data guest dari `localStorage` (conversations, messages, memories, settings) di-upload ke akun (tabel `conversations`, `messages`, `memories`, `user_settings` yang sudah ada — tinggal isi `user_id`).
  - Flag `guest_migrated` disimpan agar tidak dobel-migrasi.
- Saat ganti akun: load dari DB akun itu, guest data lokal di-clear.
- Saat logout: kembali ke mode guest (localStorage kosong → fresh).

## 4. Memori lintas-percakapan
Sudah ada tabel `memories` dengan RAG. Tinggal:
- Untuk guest: tetap pakai RAG via `supabaseAdmin` dengan `user_id` placeholder konstan per-browser (UUID disimpan di localStorage).
- Untuk user login: pakai `user_id` asli.
- RAG retrieval di `chatWithFurina` sudah otomatis ambil memori tanpa peduli conversation_id → memori lintas-chat sudah jalan. Aku verify & perbaiki kalau ada bug.

## 5. Real-time awareness
- Inject ke system prompt setiap request: tanggal, hari, jam (WIB), apakah pagi/siang/sore/malam.
- Furina otomatis bisa nyebut waktu kalau relevan ("udah malam loh, belum tidur?").

## 6. UI WhatsApp-style
- Timestamp kecil di bawah setiap bubble (format `HH:mm`).
- Status pesan user:
  - ✓ abu-abu = terkirim (saat user submit).
  - ✓✓ abu-abu = sampai server (saat request dikirim).
  - ✓✓ biru + animasi fade-pop = AI sudah balas.
- Pesan gagal: ikon ⚠️ + tombol "Kirim ulang" di samping bubble.
- Status disimpan di state pesan (`status: sending | sent | delivered | read | failed`).

---

## Detail teknis singkat

**Migrasi DB:**
- Tambah kolom `audio_url TEXT`, `audio_emotion TEXT` ke `messages`.
- Tambah kolom `voice_engine TEXT`, `voice_speaker INT`, `clone_sample_url TEXT` ke `user_settings.data` (JSONB, no migrate).
- Storage bucket `voice-samples` (private) untuk sampel clone.

**Server fns baru:**
- `speakVoicevoxUrl` — return `{ mp3Url, emotion, japaneseText }` (no base64, langsung URL).
- `speakClone` — pakai HF Inference, return base64 (clone hasil kecil-medium).
- `migrateGuestData` — upload bulk guest data ke akun login.
- `getRealtimeContext` — helper inline (bukan server-fn), inject di prompt.

**Secret baru:**
- `HUGGINGFACE_TOKEN` (user request via add_secret saat pertama pakai clone).

**Files yang berubah:**
- `src/lib/furina.functions.ts` — refactor besar
- `src/routes/index.tsx` — UI WhatsApp, Settings baru, login, migrasi
- `src/routes/_authenticated/` — tidak perlu (login opsional, bukan gate)
- Migrasi SQL untuk kolom audio_url, voice_samples bucket

Estimasi cukup besar. Aku eksekusi sekarang.