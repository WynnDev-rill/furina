# Rencana Perubahan Besar

Aku bagi jadi beberapa area. Sebelum mulai aku perlu konfirmasi 1 hal penting (di bawah).

## 1. Hapus ElevenLabs sepenuhnya
- Buang server fn `speakFurina`, `cloneVoiceFromSamples`, `listElevenLabsVoices`, `deleteElevenLabsVoice`.
- Buang section "Clone suara" & pilihan provider ElevenLabs di UI.
- Hapus secret `ELEVENLABS_API_KEY` (kamu bisa hapus manual nanti).

## 2. Sistem multi-karakter (Furina + Hu Tao, mudah ditambah)
- Definisi karakter terpusat di `src/lib/characters.ts`:
  - `id`, `name`, `avatar`, `persona`, `personaRomantic` (mode pasangan), `recommendedVVSpeaker`, `originalVoiceUrl?` (kalau tersedia).
- **Furina**: persona seperti sekarang, voice rekomendasi VOICEVOX `九州そら あまあま` atau `冥鳴ひまり`.
- **Hu Tao**: persona ceria, jahil, suka topik kematian dengan ringan, owner Wangsheng Funeral Parlor, kontras antara konyol-bocah dan tiba-tiba bijak/puitis. Voice rekomendasi VOICEVOX speaker yang lebih playful (mis. `春日部つむぎ` atau `WhiteCUL`). Gambar yang kamu upload kupakai sebagai avatar Hu Tao.
- Menu pemilihan karakter di header (avatar + nama, klik untuk switch).

## 3. Voice: opsi per karakter
Tiap karakter punya 3 grup di selector:
1. **Rekomendasi** — VOICEVOX speaker yang paling cocok dengan karakter.
2. **Suara original (kalau tersedia)** — *lihat blok konfirmasi di bawah.*
3. **VOICEVOX lain** — daftar speaker lengkap.

### Perbaikan bug VOICEVOX
- **Teks panjang**: tts.quest sering timeout/fail kalau >~300 karakter. Aku akan auto-split teks jadi chunk per kalimat (~200 char), synth paralel terbatas, lalu gabung audio di browser via `MediaSource`/concat Blob.
- **Chat lama tidak bisa diputar**: ini karena audio base64 tidak disimpan, dan tombol play me-regenerate setiap kali. Aku akan cache hasil audio di IndexedDB per messageId, jadi sekali generate bisa diputar berkali-kali termasuk dari chat lama.
- Naikkan polling timeout & tampilkan error spesifik ("server tts.quest sibuk, coba lagi").

## 4. Mode Pasangan (toggle)
- Toggle global di Settings: "Mode Pasangan 💕".
- Saat aktif: persona di-swap ke `personaRomantic` karakter aktif → balasan jadi lebih mesra & intim tapi tetap natural (panggilan sayang, perhatian fisik ringan, candaan pacaran). Tetap aman (no NSFW eksplisit).
- Disimpan per karakter (Furina bisa pasangan, Hu Tao tidak, dst).

## 5. Memori terpisah per karakter (RAG)
- Tambah kolom `character_id` di tabel `memories`.
- Update fungsi `match_memories` agar filter `character_id`.
- Furina hanya mengingat percakapan dengan Furina, dst.

## 6. Login Google + sinkronisasi
- Aktifkan Lovable Cloud Auth + Google provider (managed, tanpa setup manual).
- Tabel baru: `conversations` (user_id, character_id, title, timestamps) dan `messages` (conversation_id, role, content, status, created_at).
- Migrasi data lokal → ditawarkan saat user pertama login.
- RLS: user hanya bisa baca/tulis miliknya.
- Memori RAG juga di-scope per `user_id` + `character_id`.

## 7. AI tahu waktu real
- Setiap request chat, inject `Waktu sekarang: <tanggal, jam, bagian hari (pagi/siang/sore/malam)>` ke system prompt. AI bisa menyapa "selamat malam" otomatis.

## 8. UI ala WhatsApp
- Bubble chat dengan timestamp kecil di pojok.
- Status pesan user: ✓ terkirim (abu) → ✓✓ biru saat AI mulai balas, dengan animasi fade-in.
- Pesan gagal: ikon ⚠ merah + tombol "Kirim ulang".
- Typing indicator (tiga titik bouncing) saat AI mengetik.

## 9. Hal yang TIDAK aku ubah
- Lovable AI Gateway (Gemini) tetap untuk chat & translate.
- VOICEVOX tts.quest tetap sebagai TTS utama (free).

---

## ⚠ Konfirmasi yang aku butuh sebelum mulai

**"Original voice Furina/Hu Tao dari Genshin Impact"** — suara asli dari game itu **aset berhak cipta milik HoYoverse**. Tidak ada API gratis legal yang menyediakan voice line on-demand untuk teks bebas. Pilihan realistis:

- **A) Skip "Suara Original"** → cukup pakai VOICEVOX rekomendasi yang paling mendekati (paling aman & legal, ini saranku).
- **B) Voice clone via model open source gratis** — aku siapkan integrasi dengan **Hugging Face Inference API** (gratis, butuh token HF) memakai model `OpenVoice` / `XTTS-v2`. Kamu upload 1 sample suara karakter (mis. clip dari YouTube yang kamu punya), hasil mirip tapi tidak 100% identik. Token HF gratis tinggal generate di huggingface.co.
- **C) Keduanya** — A untuk default + B sebagai opsi opsional.

**Jawab A / B / C** lalu aku langsung eksekusi semuanya di atas.
