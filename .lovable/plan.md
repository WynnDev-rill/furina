# Rencana Update Besar Furina

Berdasarkan pilihanmu: **Mood meter**, **Semantic recall + Auto-summarize**, **Rombak panel Setting**, **Sistem proaktif + Follow-up cerdas**.

---

## 1. Mood Meter Bergulir

Skor mood -100..+100 (default 0). Naik saat user manis/afeksi, turun saat cuek/kasar/lama hilang. Memengaruhi tone Furina tiap giliran, tapi dibatasi supaya tidak drama.

- Simpan di `user_settings.data.mood` = `{ score, updatedAt, streak }` (tanpa tabel baru — hemat).
- Update di server tiap giliran: klasifikasi ringan pesan user (regex + heuristik kata kunci ID/EN: pujian, sayang, kasar, cuek, permintaan bantuan) → delta ±1..±5. Decay perlahan ke 0 (mean-reversion) tiap hari.
- Inject ke system prompt: label `mood: cerah / adem / merajuk / ngambek / tersentuh`. Aturan: mood cuma memodulasi warna, TIDAK memaksa drama. Netral kalau skor -20..+20.
- Indikator halus di UI: dot warna kecil di header avatar (hover = label mood). Tidak intrusif.

## 2. Memori: Semantic Recall + Auto-Summarize

Skema `memories` sudah punya `embedding`, `importance`, `kind`, `compressed`, dan RPC `match_memories`. Yang perlu ditambah:

- **Semantic recall aktif**: saat kirim pesan, embed pesan user → panggil `match_memories(top_k=6)` → sisipkan ke prompt sebagai "Memori relevan" (bukan semua memori dijejalkan). Sudah ada infrastruktur, tinggal dipakai konsisten dan diberi batas token.
- **Auto-summarize memori lama**: server fn `compactMemories` — dipicu saat total memori aktif (`compressed=false`) > threshold (mis. 60). Ambil batch memori terlama+low importance, minta model ringkas jadi 1 memori padat `kind='summary'`, tandai sumber sebagai `compressed=true` (via `source_memory_ids`). Panggil di background setelah kirim pesan (fire-and-forget), rate-limited 1x per 10 menit per user.
- **Kualitas embedding**: pakai `google/gemini-embedding-001` (default AI Gateway). Kolom sudah `vector` — cek dimensi cocok; kalau perlu migrasi ukuran, dilakukan.

## 3. Rombak Panel Setting

Setting sekarang scroll panjang. Rombak jadi **Tabs** rapi:

- **Persona** — nama, system prompt, slider "intensitas tsundere" (opsional, kecil), preview mood.
- **Memori** — daftar memori dengan search, filter kategori (`fact / preference / event / mood / summary`), pin, edit inline, hapus batch, tombol "Ringkas sekarang" manual.
- **Model & Suara** — pilih model, ElevenLabs voice, toggle audio.
- **Proaktif** — toggle sistem proaktif + slider frekuensi + jam aktif.
- **Data & Akun** — export, import, reset, sign out.

Visual: pakai `Tabs` dari shadcn, layout mobile-first (tab jadi vertikal list di layar kecil), sticky header saat scroll.

## 4. Sistem Proaktif Ringan + Follow-up Cerdas

**Proaktif**: kalau user diam > X jam (default 6, atur di Setting) dan tab aktif → Furina bisa "nyapa duluan" 1 bubble pendek. Sumber: ambil 1-2 memori random ber-importance tinggi + mood → generate pesan singkat. Batasi maks 1x per sesi buka app. Bisa dimatikan.

**Follow-up cerdas**: di server, setelah balasan utama, opsional tambah 1 pertanyaan/observasi pendek yang nyambung topik (bukan template "ada lagi?"). Diaktifkan per giliran secara probabilistik (mis. 35%), dan **tidak** muncul kalau balasan sudah berupa pertanyaan atau topik sensitif.

## 5. Perubahan File

- `src/lib/furina.functions.ts` — mood classifier + injeksi mood ke prompt, semantic recall aktif, follow-up rule, `compactMemories` server fn, `proactiveGreeting` server fn.
- `src/routes/index.tsx` — indikator mood di header, panggil `proactiveGreeting` saat idle-return, jadwalkan `compactMemories` background.
- **Setting baru**: pisah jadi komponen `src/components/settings/*` (PersonaTab, MemoryTab, ModelTab, ProactiveTab, DataTab) + `SettingsSheet.tsx` sebagai container Tabs. Menggantikan blok setting lama di `index.tsx`.
- Migrasi ringan (kalau perlu): index HNSW untuk `embedding` (kalau belum), kolom tak perlu ditambah — semua field mood disimpan di `user_settings.data`.

## 6. Prioritas & Urutan Eksekusi

1. Rombak Setting (fondasi UI, biar fitur baru punya tempat).
2. Mood meter (kecil, high impact).
3. Semantic recall aktif + follow-up cerdas (perbaiki kualitas balasan).
4. Auto-summarize (background, tidak blocking).
5. Sistem proaktif (paling akhir, butuh idle detection).

## 7. Pertanyaan Sebelum Eksekusi

Cukup satu: mau aku kerjakan **semua sekaligus dalam 1 turn besar**, atau **bertahap per nomor** (lebih aman, bisa review tiap langkah)? Rekomendasiku: bertahap, mulai dari #1 (Setting) + #2 (Mood) dulu.
