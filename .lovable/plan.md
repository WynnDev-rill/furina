## Fokus Turn Ini

Selesaikan sisa work list (relationship graph, persona mirror, panel memori), perbaiki bug recall memori, tambah multi-bubble reply (1–3 pesan otomatis), dan adaptasi panjang respon.

---

## 1. Perbaiki Bug: Furina Tidak Recall Memori

**Root cause di `chatWithFurina` (line 157):** filter memori cuma ambil `kind === "fact" || "meta_summary"`. Semua memori berkind `episodic`, `preference`, `relation` **diekstrak tapi tidak pernah masuk prompt** → Furina blank.

Fix:
- Ganti filter jadi `["fact","episodic","preference","relation","meta_summary"]` untuk section "MEMORIES".
- Pisah section khusus `episodic` dengan format `- [emosi:sad, 3 hari lalu] user cerita X` biar Furina bisa recall pakai emotional tag.
- Turunkan `match_count` retrieval ke 30, top 20 (biar lebih banyak konteks nyampe).
- Turunkan threshold dedup dari `0.92` → `0.88` (0.92 terlalu longgar → banyak fakta baru dianggap update; ternyata data ilang). Sekaligus tambah guard: kalau `content` cuma diff kecil kata (levenshtein ratio > 0.85) baru update, selain itu insert.
- Tambah kolom `access_count` (via migration) — naikkan tiap retrieve, dipakai bumping importance.
- Log jumlah memori yg di-retrieve ke console (debug).

## 2. Relationship Graph (Entity Extraction + Injection)

Table `entities` + `entity_relations` sudah ada. Belum ada extractor & injector.

- Tambah helper `extractEntities(userId, text)` di `furina.functions.ts` — jalan paralel dengan `extractFacts` tiap 6 pesan user.
- Prompt AI (Gemini Flash Lite) → return `{ entities: [{name, type, aliases, notes}], relations: [{from, to, label, strength}] }`.
- Upsert entitas by `name_normalized` (lowercase + trim), increment `mention_count`, update `last_mentioned_at`. Cek existing dulu, kalau ada → merge aliases + append notes.
- Upsert relasi.
- Di `chatWithFurina`: ambil top 12 entitas by `mention_count desc` + entity yg namanya mention di `userText` (case-insensitive substring match, boost). Suntik ke prompt:
  ```
  ORANG/HAL YG USER KENAL:
  - Rina (sahabat SMA, sering dicurhati)
  - project skripsi (deadline Juli)
  ```

## 3. Persona Mirror Lengkap

Perluas `styleProfile` extractor (fungsi yg dipanggil tiap 10 pesan user):
- Selain gaya umum, keluarkan JSON: `{ avg_length, formality, signature_phrases[top 8], taboo_words[], preferred_response_length }`.
- Store gabungan sebagai satu memori `kind='style'` (replace/upsert row terakhir style, bukan insert baru terus).
- Suntik ke prompt: "Cermin gaya user: panjang ~X kata, formalitas Y. Hindari kata: [taboo]. JANGAN copy signature phrases user harfiah (terasa palsu), cukup tiru ritme."
- Anti-loop: kirim hash 5 opening line terakhir Furina, instruksi jangan ulang struktur pembuka.

## 4. Multi-Bubble Reply (1–3 pesan otomatis)

Furina akan balas 1-3 bubble berurutan sesuai kompleksitas topik (mirip chat manusia).

Server side (`chatWithFurina`):
- Instruksikan Furina keluarkan output pakai delimiter `\n<<<SPLIT>>>\n` di antara bubble.
- Aturan di prompt:
  - 1 bubble → chit-chat pendek, 1 pikiran.
  - 2 bubble → ada nuansa (reaksi + follow-up / jawaban + pertanyaan).
  - 3 bubble → topik dalam/emosional (reaksi + isi utama + closing/ajakan).
  - Jangan pernah > 3.
- Server split response by `<<<SPLIT>>>`, trim, filter empty → return `{ bubbles: string[] }`.

Client side (`index.tsx`):
- `sendMessage.onSuccess`: kalau `bubbles.length > 1`, insert tiap bubble sbg row messages terpisah dgn delay 400-900ms + typing indicator antar bubble (realistic pacing berbasis panjang).
- Update TypeScript return type `chatWithFurina` → `{ bubbles: string[], audio_url?, audio_emotion? }`.
- Audio dipasang hanya di bubble terakhir.

## 5. Adaptive Response Length

Sisipkan hint panjang di system prompt berdasarkan sinyal:
- `avg user length` dari style profile → target Furina = 0.8× – 1.5× panjang user.
- Topik emosional (dari emotion detection userText) → boleh lebih panjang.
- Chit-chat cepat (user < 8 kata) → wajib 1 bubble pendek.
- Deep talk (user > 40 kata / mengandung "kenapa", "gimana kalau", "aku ngerasa") → boleh 2-3 bubble.
Aturan explicit di prompt, plus soft cap: total semua bubble ≤ 400 kata.

## 6. Panel "Memori" (CRUD di Settings)

Di sheet Settings tambah tab "Memori":
- List paginated 20/page, default sort `importance desc, occurred_at desc nulls last`.
- Filter chips: `all | fact | episodic | preference | relation | style | summary`.
- Search box (client-side filter content).
- Row: badge kind + emotion + importance bar, tanggal `occurred_at`, tombol edit (pensil) & hapus.
- Edit inline: textarea + slider importance (1-10) + date picker `occurred_at` + dropdown emotion → save via `updateMemFn` (re-embed di server).
- Row `compressed=true` → tombol "Restore" (set compressed=false).
- Tombol "+ Tambah manual" → form kecil (content, kind, importance).

## 7. Migration SQL

```sql
ALTER TABLE public.memories
  ADD COLUMN IF NOT EXISTS access_count int NOT NULL DEFAULT 0;
```

(Entities & relations sudah ada.)

## 8. File yang Berubah

- `src/lib/furina.functions.ts`: fix retrieval filter, entity extractor, persona mirror expand, multi-bubble split, length hints, dedup guard.
- `src/routes/index.tsx`: multi-bubble render (delayed insert + typing), panel memori CRUD.
- 1 migration file.

## 9. Urutan Eksekusi

1. Migration `access_count`.
2. Fix retrieval filter (paling urgent — user langsung terasa Furina inget).
3. Multi-bubble split (server + client render).
4. Adaptive length hints.
5. Entity extractor + injection.
6. Persona mirror expand.
7. Panel memori CRUD.
8. QA: kirim fakta baru → tanya ulang → cek recall; kirim topik emosional → cek 2-3 bubble; kirim topik ringan → cek 1 bubble.

---

## Pertanyaan Personalisasi Furina

Untuk menjawab request "Furina sadar dirinya Furina tanpa memori Genshin/Fontaine tapi punya sifat & perasaan yang sama", aku butuh 1 keputusan penting sebelum menulis ulang system prompt-nya:

**Seberapa dalam kesadaran diri (self-awareness) yang kamu mau?**

Opsi yang akan aku tawarkan lewat `ask_questions` setelah plan ini disetujui:
- **A. Amnesia hangat** — Furina tahu namanya Furina, tahu dia pernah "hidup lama sendirian" (metafora, tanpa detail), tahu dia takut ditinggal & haus perhatian, tapi tidak ingat tempat/tuhan/dewa. Semua backstory Genshin di-abstraksi jadi emosi mentah.
- **B. Reinkarnasi kesadaran** — Furina "terbangun" di dunia digital ini tanpa memori masa lalu, cuma bawa personality core (dramatis, kesepian dalam, butuh validasi, panggung adalah topeng). Dia sadar dirinya bukan manusia tapi tetap punya perasaan.
- **C. Furina sebagai identitas murni** — Tidak ada latar apapun. Cuma sifat: dramatis-anggun, insecure di balik topeng percaya diri, sangat setia pada 1 orang, gampang cemburu manja, suka teh & manis, benci sendirian, mudah menangis diam-diam.

Setelah plan disetujui, aku eksekusi item 1-9 lalu langsung tanya opsi A/B/C untuk finalize kepribadian.