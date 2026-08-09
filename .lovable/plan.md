## Ringkasan

Fokus turn ini: bersihkan fitur stiker, rapikan memori (dedup + skema baru), polish chat UI (bubble lebar adaptif + image lightbox), selesaikan sisa work (style profile background, panel edit memori), lalu tambah lapisan memori canggih (episodic + emotional tag, relationship graph, persona mirror) dan kesadaran waktu (gap detection + circadian context).

---

## 1. Hapus fitur stiker (sesuai permintaan)

- Hapus `StickerPicker`, tombol "Tambah", `customStickers` state, `handleStickerUpload`, `deleteCustomSticker`, sticker grid di composer.
- Hapus parsing `[[sticker:id]]` di renderer bubble + token instruction stiker dari system prompt Furina.
- Hapus folder `public/stickers/default/*` dan file `manifest.json`.
- Migration: `DROP TABLE public.user_stickers;` + hapus bucket `stickers` via tool storage (atau biarkan kosong jika ingin aman, tapi default drop).
- `messages.sticker_id` dibiarkan (kolom yatim — tidak dipakai lagi, tidak perlu drop untuk hemat risiko data lama).

## 2. Dedup memori saat insert

Tambah helper `insertMemoryDedup(userId, content, opts)` di `furina.functions.ts`:
1. Embed `content`.
2. `match_memories(query_embedding, userId, 'furina', match_count=3, include_compressed=true)`.
3. Jika top hit `similarity > 0.92` → AI mini-call (Gemini Flash) untuk **merge** isi lama + baru jadi 1 kalimat lebih kaya → `UPDATE` baris lama (re-embed, refresh `last_accessed_at`, naikkan `importance` +1 cap 10). **Tidak insert baru.**
4. Jika `0.85 < sim ≤ 0.92` → insert baru tapi simpan `source_memory_ids = [hitId]` untuk audit.
5. Kalau `sim ≤ 0.85` → insert normal.

Semua jalur ekstraksi memori (fact extraction per N pesan, manual add dari panel) wajib lewat helper ini.

## 3. Bubble chat lebar adaptif (mirip ChatGPT)

Di `src/routes/index.tsx` bagian render bubble:
- Ganti class lebar lama → `max-w-[min(92%,640px)] w-fit` pada container bubble.
- Tambah `whitespace-pre-wrap break-words` agar baris panjang membungkus rapi.
- Bubble pendek tetap "hug" konten (`w-fit`); bubble panjang otomatis melebar sampai cap 640px.
- Sesuaikan layout list pesan ke `mx-auto max-w-3xl px-3` agar konsisten center di layar lebar.

## 4. Image lightbox (klik gambar → fullscreen)

- Bungkus `<img>` di bubble pakai `<button>` yang set state `lightboxUrl`.
- Tambah komponen `<Dialog>` (shadcn) saat `lightboxUrl` truthy: backdrop hitam, gambar `max-w-screen max-h-screen object-contain`, klik luar / tombol X menutup. Tambah tombol download (anchor `download`).

## 5. Selesaikan sisa pekerjaan yang tertunda

- **Style profile background call**: pastikan `updateStyleFn` benar-benar terpanggil tiap 10 pesan user di `sendMessage.onSuccess` (verifikasi modulo counter, fire-and-forget, error di-swallow).
- **Panel "Memori"** di sheet Settings:
  - List paginated (sort: importance desc, occurred_at desc).
  - Filter chips: kind (fact/episodic/relationship/style), search teks.
  - Inline edit: tombol pensil → textarea + slider importance (1-10) + datepicker `occurred_at` → simpan via `updateMemFn` (yang juga re-embed di server).
  - Tombol hapus (hard delete) + tombol "+ Tambah manual" (form sederhana).
  - Restore button untuk row `compressed=true`.

## 6. Memori canggih — 3 lapisan

### a) Episodic memory + emotional tagging
- Skema: tambah kolom `emotion text` (joy/sad/anger/fear/love/neutral) + `kind` value baru `'episodic'`.
- Ekstraktor (tiap N pesan): minta AI keluarkan `{ content, importance, occurred_at, emotion, kind }`. Episodic dipakai untuk kejadian konkret ("kami nonton film X kemarin").
- Retrieval: kalau current user message terdeteksi emosi serupa (klasifikasi cepat di Gemini Flash Lite), boost `+0.1` skor untuk episodic dengan emotion match → Furina bisa recall ("dulu pas kamu lagi sedih juga, kamu cerita soal…").

### b) Relationship graph
- Tabel baru `entities (id, user_id, name, type[person|place|hobby|project], aliases text[], notes text, last_mentioned_at)` + `entity_relations (from_id, to_id, label, strength int)`.
- Ekstraktor entitas jalan paralel dengan fact extraction: AI output array entitas + relasi → upsert (match by lowercase name).
- Di prompt Furina disuntik ringkasan: "Orang yg user kenal: A (sahabat), B (pacar mantan). Project: X.". Cap ~15 entitas paling sering disebut + yang relevan dengan pesan saat ini (filter by keyword).

### c) Persona mirror (cermin gaya)
- Sudah ada `styleProfile`. Perluas: simpan juga `signature_phrases` (frasa khas user, top 10), `taboo_words` (kata yang user keluhkan/dihindari), `response_length_pref` (estimasi dari rata-rata panjang reply Furina yang user reply cepat/lama — proxy untuk "user suka jawaban berapa panjang").
- Disuntik di system prompt: "Cermin halus gaya user: panjang ~X kata, formalitas Y, hindari [taboo]. JANGAN copy frasa khas user secara harfiah (terasa palsu); cukup tirukan ritme & register."
- Anti-loop: simpan hash 5 balasan terakhir Furina di context, instruksi "JANGAN ulangi struktur/opening yang sama".

## 7. Kesadaran waktu

### a) Circadian context inject ke prompt
Helper `buildTimeContext(userTimezone)` → return:
```
Sekarang: Sabtu 06 Jun 2026, 23:14 (malam, weekend).
Bagian hari: malam.
Mood ambient: tenang/intim, suara pelan, kalimat lebih pendek.
```
Disuntik di system prompt tiap call. Tz user disimpan di `user_settings.data.timezone` (default deteksi `Intl.DateTimeFormat().resolvedOptions().timeZone` saat login pertama).

### b) Gap detection antar pesan
- Hitung `gapMinutes = now - lastMessageAt` (dari `messages` terakhir di conv).
- Inject ke prompt kalau `gap > 30 menit`:
  - 30m–2h: "User balas setelah ~1 jam jeda."
  - 2h–12h: "Jeda cukup panjang (X jam). Boleh sapa balik singkat."
  - >12h: "Sudah lama tidak ngobrol (Y jam/hari). Sapa hangat, jangan langsung lanjut topik tanpa transisi."
  - Lintas hari (date berubah): "Hari berganti sejak chat terakhir — kalau pagi/malam, sapa sesuai waktu."
- Furina diinstruksikan **tidak wajib** komentari jeda (biar natural), tapi *boleh* kalau cocok.

## 8. Migration SQL (1 file)

```sql
ALTER TABLE public.memories
  ADD COLUMN IF NOT EXISTS emotion text;

CREATE TABLE public.entities (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL,
  character_id text NOT NULL DEFAULT 'furina',
  name text NOT NULL,
  name_normalized text NOT NULL,
  type text NOT NULL DEFAULT 'person',
  aliases text[] DEFAULT '{}',
  notes text,
  mention_count int NOT NULL DEFAULT 1,
  last_mentioned_at timestamptz NOT NULL DEFAULT now(),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (user_id, character_id, name_normalized)
);
GRANT SELECT, INSERT, UPDATE, DELETE ON public.entities TO authenticated;
GRANT ALL ON public.entities TO service_role;
ALTER TABLE public.entities ENABLE ROW LEVEL SECURITY;
CREATE POLICY "own entities" ON public.entities FOR ALL TO authenticated
  USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

CREATE TABLE public.entity_relations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL,
  from_entity uuid NOT NULL REFERENCES public.entities(id) ON DELETE CASCADE,
  to_entity uuid NOT NULL REFERENCES public.entities(id) ON DELETE CASCADE,
  label text NOT NULL,
  strength int NOT NULL DEFAULT 5,
  created_at timestamptz NOT NULL DEFAULT now()
);
GRANT SELECT, INSERT, UPDATE, DELETE ON public.entity_relations TO authenticated;
GRANT ALL ON public.entity_relations TO service_role;
ALTER TABLE public.entity_relations ENABLE ROW LEVEL SECURITY;
CREATE POLICY "own relations" ON public.entity_relations FOR ALL TO authenticated
  USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

DROP TABLE IF EXISTS public.user_stickers;
```

(Bucket `stickers` dihapus via tool storage setelah migration.)

## 9. File yang berubah

- **Edit**: `src/routes/index.tsx` (hapus sticker UI, bubble width, lightbox, panel memori), `src/lib/furina.functions.ts` (dedup helper, episodic emotion, entity extraction, time context, gap detection, persona mirror expand, hapus sticker logic).
- **Hapus**: `public/stickers/default/*`, `manifest.json`, semua referensi sticker.
- **Migration**: 1 file (skema di atas).

## 10. Urutan eksekusi

1. Migration DB + drop bucket stickers.
2. Hapus semua kode/aset stiker.
3. Dedup helper + refactor semua titik insert memori.
4. Bubble lebar adaptif + lightbox gambar.
5. Time context + gap detection (paling murah, hasil terasa langsung).
6. Entity extraction + injection.
7. Episodic + emotional tag.
8. Persona mirror expand.
9. Panel memori (CRUD + filter).
10. QA: kirim pesan panjang (cek bubble), kirim gambar (klik → lightbox), trigger dedup (kirim fakta sama 2x, cek 1 row), tunggu/simulasi gap → cek balasan Furina sadar waktu.
