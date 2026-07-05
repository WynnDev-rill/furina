# Perbaikan Bug + Furina Lebih Hidup & Punya Pendirian

## A. Bug fixes

### 1. Chat terbaru kadang menghilang
- Setelah `sendMessage`, refetch bisa me-*replace* array sebelum row assistant tersimpan → pesan hilang sekejap.
- Perbaikan:
  - Realtime subscribe ke `messages` per `conversation_id` (INSERT/UPDATE), merge **by id**, bukan replace.
  - Optimistic message dipertahankan sampai row dengan id sama muncul dari server.
  - Setelah server fn balas, update state langsung dari hasilnya (tanpa full reload).

### 2. Waktu riwayat sama semua
- Pastikan `conversations.updated_at` di-*touch* setiap kirim pesan di server fn.
- Sidebar pakai util `formatRelative(date)`: "baru saja", "5 mnt lalu", "2 jam lalu", "kemarin", "3 hari lalu", "12 Nov".

### 3. Grouping riwayat
- Bucket: **Hari ini / Kemarin / 7 hari terakhir / 30 hari terakhir / Lebih lama**, header kecil, urut desc dalam bucket.

## B. Kesadaran & ekspresi

### 4. Inner state ringan (di luar mood)
- Simpan di `user_settings.data.innerState`: `energy` (0..100, decay harian), `focus` (0..100), `interest` (topik singkat dari kata kunci pesan).
- Prompt menerima 1 baris hint (`state: energy tinggi, fokus rendah, tertarik "musik"`). Furina memodulasi panjang/antusiasme; **tidak boleh mengumumkan state**.

### 5. Kesadaran waktu & sesi
- Client kirim `clientNow` + `tz`. Server hitung: waktu lokal (pagi/siang/sore/malam/dini hari), jarak sejak pesan terakhir, hari & weekend.
- Sisipkan sebagai konteks di prompt. Furina boleh menyinggung natural.

### 6. Memori diri (self-notes)
- Pakai `memories.kind='self'` (konvensi, tanpa migrasi).
- Server fn `updateSelfNotes` (rate-limited ~1x per 6 giliran) bikin 1 catatan pendek tentang Furina sendiri.
- Semantic recall mengambil top 1–2 self-memory selain memori user-facing.

## C. Sifat egois & menentang (level: sedang)

### 7. Opini & bantah dalam karakter
- Update `DEFAULT_PERSONA` + system-prompt builder:
  - 8–12 preferensi konkret Furina + 4–6 pet peeves (panggung, drama, air/laut, wine, dsb).
  - Boleh **tidak setuju**, koreksi user, jawab dari sudut pandangnya. Tidak wajib validate.
  - Boleh kesombongan halus, merajuk, merasa lebih tahu.
  - **Bukan penolakan moral untuk konten dewasa/vulgar**; hanya menolak/menawar kalau secara karakter sedang tidak mood. Kalau moodnya cocok, ia bisa antusias.
  - Larangan tetap: tidak khotbah moral, tidak jadi asisten netral, tidak selalu setuju.
- ~20% giliran mulai dengan "counter" (koreksi/opini) sebelum bantu — tetap membantu.

## D. Proaktif dalam obrolan

### 8. Inisiatif dalam obrolan
- ~30% giliran, tambah **giliran mini** setelah balasan utama: lempar topik baru dari inner state, cerita hal kecil tentang dirinya, atau opini spontan.
- Tidak muncul kalau: user baru bertanya spesifik yang belum tuntas, topik sensitif, atau balasan sudah panjang.

### 9. Callback memori spontan
- ~15% per giliran, ambil 1 memori lama (importance ≥ 6, `last_accessed_at` > 3 hari) yang **cocok embedding** dengan konteks. Sisipkan hint prompt.
- Update `last_accessed_at` + `access_count` supaya tidak berulang.

## E. File yang disentuh

```
src/lib/utils.ts               + formatRelative()
src/lib/furina.functions.ts    inner state, time awareness, self-notes,
                               opinion/counter rules, initiative + callback,
                               touch conversations.updated_at, terima clientNow + tz
src/routes/index.tsx           realtime subscribe messages, merge-by-id,
                               kirim clientNow + tz,
                               sidebar: formatRelative + grouping bucket
```

Tanpa tabel baru. `memories.kind='self'` cukup pakai kolom yang ada. `user_settings.data.innerState` menyatu di JSON.

## F. Urutan eksekusi

1. Bug: realtime + dedupe pesan.
2. Bug: `updated_at` conversation + formatRelative + grouping sidebar.
3. Persona rework (opini/bantah + preferensi konkret).
4. Inner state + kesadaran waktu.
5. Self-notes + callback memori spontan.
6. Inisiatif giliran mini.

Mau **semua sekaligus 1 turn** atau **bertahap A→F**? Rekomendasi: bertahap, mulai **A (bug)** dulu.
