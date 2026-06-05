
# Rencana Upgrade

## 1. Voice Clone — alur lengkap dengan status (HF Space gratis)

**File baru:** `src/components/VoiceCloneDialog.tsx`

Alur: Upload `.mp3/.wav/.m4a` → auto-convert ke wav mono 22kHz client-side via Web Audio API → validasi durasi (6–30 detik, ideal 15s) + cek RMS volume (tidak senyap) + cek SNR sederhana → tampilkan ✓ status kualitas (durasi, sample rate, volume) → upload ke bucket `voice-samples` di path `{userId}/clone-{timestamp}.wav` → simpan metadata di `user_settings.data.voiceClones[]` (array `{id, name, path, createdAt, durationSec, qualityScore}`) sehingga bisa punya banyak clone, bukan satu.

**Server fn `cloneVoiceSpeak`** (`src/lib/furina.functions.ts`):
- Input: `text`, `sampleSignedUrl`, `language` (id/ja/en).
- Chain: **Fish-Speech** Space (`fishaudio/fish-speech-1`) → fallback **XTTS** Space (`coqui/xtts`) → fallback **OpenVoice v2**.
- Pakai Gradio `/api/predict` queue endpoint (`/queue/join` + SSE `/queue/data`) supaya bisa stream progress.
- Return `{ audioUrl, engineUsed, durationMs, queuePosition? }`.

**UI:** dialog dengan 3 tab — Upload, Library (list semua clone, set default, hapus), Test (input teks → preview audio). Progress bar real-time saat generate (read `queuePosition` dari SSE). Timeout 90s, retry button.

**Pilih voice di settings:** dropdown TTS provider sekarang punya: `voicevox`, `cloneId-xxx` (list semua clone), `ariaTTS` (default fallback).

## 2. Stiker WhatsApp-style + AI Vision

**Hapus emoji-as-sticker. Stiker = gambar PNG/WebP transparan.**

- **Pack default**: bundle 30 stiker Furina/anime CC-licensed di `public/stickers/default/*.webp` + `manifest.json` ({id, url, label kosong dulu, defaultPack: true}).
- **Custom upload**: tombol "+" di sticker picker → user upload PNG/WebP → resize ke 512x512 client-side → upload ke bucket baru `stickers` (private, RLS by user_id) → simpan ke tabel baru `user_stickers (id, user_id, url, pack_name, label, created_at)`.
- **Sticker picker**: bottom sheet dengan tabs (Default | Pack-ku), grid 4 kolom, long-press untuk delete.

**AI baca stiker (Vision tiap kirim):**
- Saat user kirim stiker, frontend fetch URL stiker, kirim ke `chatWithFurina` sebagai multimodal content (sama seperti gambar) dengan instruksi sistem: *"User mengirim sebuah stiker bergambar. Tafsirkan emosi/maksudnya secara natural."*
- Untuk efisiensi: cache hasil interpretasi vision per `stickerId` (kolom `user_stickers.cached_label`) — pertama kali kirim → Vision; kirim ke-2 dst → pakai cached label di context.

**AI kirim stiker:** Furina output token `[[sticker:id]]` di balasannya. Frontend regex parse → render stiker dari pack. AI dikasih list 10 stiker paling relevan (random per balasan) di system prompt: *"Stiker tersedia: capek_gw (untuk lelah), wakatta (untuk paham), ya_ampun (untuk frustasi)... Pakai max 1 stiker tiap beberapa balasan, hanya jika sangat cocok."*

**Migration SQL:**
```sql
create table public.user_stickers (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null,
  url text not null,
  pack_name text default 'custom',
  label text,
  cached_label text,
  created_at timestamptz default now()
);
-- + GRANTS, RLS, bucket `stickers`
```

## 3. Memori tanpa batas + auto-compress + importance + waktu

**Skema:** tambah kolom ke `memories`:
- `importance int default 5` (1–10, AI scoring saat insert)
- `occurred_at timestamptz` (waktu kejadian yang direferensikan memori, bukan created_at)
- `last_accessed_at timestamptz` (untuk recency boost)
- `compressed boolean default false`
- `source_memory_ids uuid[]` (kalau hasil compress, refer ke memori asal)

**Retrieval baru** (`retrieveMemories`):
- Embedding similarity (cosine) ambil top 50.
- Re-rank: `score = 0.6*similarity + 0.25*(importance/10) + 0.15*recency_decay(last_accessed_at)`.
- Ambil top 15. Update `last_accessed_at` untuk yang dipakai.
- Tidak ada batas total di DB.

**Insert dedup:** sebelum insert memori baru, embed dulu → query `match_memories` similarity > 0.92 → kalau ada, AI dipanggil untuk **merge** (gabung jadi 1 memori lebih kaya, hapus yang lama) bukan duplikat. Mencegah pengulangan info saat ringkasan ke-2, ke-3, dst.

**Ringkasan progressive (no-repeat):**
- Tiap 20 pesan: ringkas 20 pesan terakhir → cek kalau ada `summary` sebelumnya untuk conversation yang sama → kirim ke AI: *"Ini ringkasan lama: X. Ini 20 pesan baru: Y. Buat ringkasan baru yang MENAMBAH info, jangan ulang yang sudah ada di ringkasan lama."* → upsert sebagai 1 summary aktif, summary lama di-archive (`compressed=true`).

**Auto-compress lama:**
- Server fn `compressOldMemories` (jalan via pg_cron tiap minggu, atau lazy saat user open app & belum jalan 7 hari):
- Cari memori `kind='fact'` & `created_at < now() - 90 days` & `last_accessed_at < now() - 30 days`.
- Group by topic via clustering embedding (k-means sederhana di JS, k=10).
- Tiap cluster → AI ringkas jadi 1 meta-memory `kind='meta_summary'`, simpan `source_memory_ids`. Memori asal di-set `compressed=true` (tidak di-retrieve default tapi bisa restore di panel).

**Waktu di memori:** saat ekstrak fakta, AI diminta output juga `occurred_at` kalau bisa di-infer ("kemarin" → now-1day, "minggu lalu" → now-7day, "tadi pagi" → today 09:00). Disimpan di kolom. Saat retrieval, format ke natural: "Kamu bilang ini sekitar 2 minggu lalu: ..."

## 4. Style Profile per-user (improvisasi gaya bicara)

**Skema:** kolom `user_settings.data.styleProfile`:
```ts
{
  avgMsgLength: number,
  formality: 'casual'|'mixed'|'formal',
  emojiRate: number,
  frequentWords: string[],  // top 20
  avoidedTopics: string[],
  slangUsed: string[],
  lastUpdated: timestamp,
  sampleCount: number
}
```

**Update tiap 10 pesan user:** server fn `updateStyleProfile` baca 30 pesan user terakhir → kirim ke Gemini 3 Flash → parse JSON profile → merge dengan existing (weighted avg).

**Pemakaian:** system prompt Furina ditambah:
> "Gaya user: panjang rata-rata X kata, formalitas Y, sering pakai kata: [...]. Tirukan ritme & vocab user (tanpa mengubah karakterku). Jangan pakai kata yang TIDAK PERNAH user pakai. Variasikan respons — jangan ulangi struktur balasan sebelumnya."

Anti-repetisi sederhana via instruction (tidak perlu state tambahan, AI patuh dengan recall 5 balasan terakhir yang sudah masuk history).

## 5. Panel Memori (edit/hapus/tambah manual)

**Halaman baru:** `src/routes/_authenticated/memori.tsx` (atau modal di settings).

Fitur:
- List paginated semua memori user (sort: importance, recency, occurred_at).
- Filter: kind (fact/summary/style/meta_summary), kategori auto-tag (relasi/preferensi/kejadian/emosi), search teks.
- Inline edit teks → re-embed otomatis on save.
- Edit `importance` (slider 1-10) & `occurred_at`.
- Hapus (soft via `compressed=true` atau hard delete).
- Tombol "+ Tambah memori manual" → form: content + importance + occurred_at.
- Restore meta-summary → kembalikan source memories.

## 6. Fix waktu formatting (final touch)

Sudah ada `humanizeDelta` dari turn sebelumnya, tinggal pastikan dipakai konsisten + tambah untuk `occurred_at` di memori ("sekitar 3 hari lalu", "Senin minggu lalu", "tadi pagi").

## 7. Fix security warning: Extension in Public

Migration:
```sql
create schema if not exists extensions;
alter extension vector set schema extensions;
-- update pg_net juga kalau ada
grant usage on schema extensions to authenticated, service_role;
```
Update `match_memories` & semua referensi `vector` type → pakai `extensions.vector(...)`.

## File yang berubah

- **Baru**: `src/components/VoiceCloneDialog.tsx`, `src/components/StickerPicker.tsx`, `src/components/MemoriPanel.tsx`, `src/routes/_authenticated/memori.tsx`, `public/stickers/default/*` (30 file webp).
- **Edit**: `src/lib/furina.functions.ts` (cloneVoice, retrieveMemories dgn rerank, dedup, style profile, vision sticker, compress jobs, occurred_at extraction), `src/routes/index.tsx` (sticker picker baru, voice clone dialog wiring, hapus emoji sticker), `src/styles.css` (sticker bubble style).
- **Migrations**: kolom baru di `memories`, tabel `user_stickers`, bucket `stickers`, move extension `vector` ke schema `extensions`.

## Urutan eksekusi
1. Migration DB (kolom memori + user_stickers + extension schema).
2. Bucket `stickers` + RLS.
3. Bundle 30 stiker default (akan aku generate via Lovable Assets / imagegen).
4. Sticker picker UI + vision integration + AI sticker output parser.
5. Voice clone dialog + Gradio queue client + library management.
6. Memori upgrade: rerank, dedup, progressive summary, occurred_at, importance.
7. Style profile + injection ke prompt.
8. Panel memori CRUD.
9. QA: test stiker (kirim+terima), voice clone end-to-end, memori dedup di summary ke-3.

## Pertanyaan saat eksekusi (akan ditanya saat build):
- Stiker default 30 mau aku generate AI (anime Furina-style) atau cari pack CC dari TwemojiAnime? → akan kutawarkan saat sampai langkah 3.
- Apakah panel memori jadi route terpisah `/memori` atau modal di tombol settings? Saat ini aku rencanakan **modal/sheet di settings** biar konsisten dengan UI sekarang.
