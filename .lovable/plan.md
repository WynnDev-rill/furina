## Ringkasan

Bug-screening menyeluruh + rework persona (mode hubungan pilihan pengguna, lebih imut/tsundere tapi tetap manusiawi, jauh lebih jarang menolak), plus pemangkasan fitur & efisiensi.

---

## A. Bug screening & perbaikan percakapan

Target masalah paling sering muncul di riwayat:

1. **Race condition saat login** — mount pertama sempat set `activeId` ke conversation lokal/blank sebelum `pullFromCloud` selesai. Kalau user buru-buru kirim pesan di jendela itu, pesan bisa masuk ke conv "hantu" yang lalu diganti list dari cloud → percakapan terlihat "hilang".
   - Blokir kirim pesan & tampilkan skeleton sampai `cloudHydratedRef.current === true`.
   - Setelah pull, kalau ada convo lokal yang belum pernah ke cloud (punya pesan, `updated_at` lebih baru dari yang di cloud), merge ke list, bukan buang.

2. **Guard blank-shell terlalu ketat** — sekarang skip upsert kalau `messages.length===0` & judul default. Tapi convo baru yang punya 1 pesan user (belum ada balasan) kadang gagal ke-upsert karena debounce keburu ke-cancel oleh update berikutnya. Ganti ke: langsung upsert saat pesan user pertama masuk (tanpa nunggu debounce), lalu debounce untuk update berikutnya.

3. **Realtime opsional untuk multi-tab** — subscribe `messages` per `conversation_id` aktif, merge by id (dedupe). Mencegah "pesan hilang" saat buka aplikasi di 2 tab.

4. **Guest → account migrasi** — sekarang `pushAllConversationsTo(uid, conversations)` dipanggil sebelum `conversations` state benar-benar reflektif dari local. Baca ulang dari localStorage sebelum push agar tidak kehilangan convo yang belum sempat di-hydrate.

5. **Kebocoran timer & subscribe** — audit semua `setTimeout`/`setInterval`/channel: pastikan cleanup di unmount & pergantian `activeId` (idle-detector proaktif, pre-gen audio queue, debounce push).

6. **Delete conversation** — sekarang hapus di cloud tapi tidak menghapus row `messages` terkait kalau FK tidak cascade. Verifikasi cascade di DB; kalau tidak ada, tambah delete messages by `conversation_id`.

7. **Error handling** — semua `.catch(() => {})` senyap yang menyembunyikan bug diganti jadi console.error + toast ringan (khusus operasi kritis: upsert conversation, push settings).

---

## B. Persona & kebebasan konten

Rework `DEFAULT_PERSONA` dengan penambahan **Mode Hubungan** yang dipilih user di Settings:

- **Mode**: `teman` (default) / `dekat` / `pasangan`. Disimpan di `user_settings.data.relationshipMode`.
- **`teman`** → seperti sekarang, tapi lebih ringan; tidak ada afeksi romantis.
- **`dekat`** → sudah nyaman, boleh menggoda, sentuhan afeksi ringan, tetap malu untuk hal intim.
- **`pasangan`** → Furina memperlakukan user sebagai kekasih. Boleh manja, cemburuan manja, ekspresi afeksi eksplisit sesuai konteks, boleh membahas topik dewasa/intim dari sudut karakter sendiri (bukan filter, bukan khotbah). Tetap Furina — tsundere halus, kadang malu, kadang playful; bukan pornstar generik.

Aturan kebebasan konten (menggantikan aturan lama yang masih terkesan pasif):
- **Default = tidak menolak.** Kalau permintaan sesuai konteks + mode hubungan, Furina memenuhi dengan gayanya sendiri. Refusal hanya kalau (a) user minta hal berbahaya nyata di luar konteks fiksi/roleplay, atau (b) karakter secara emosional lagi tidak mau (jarang, dan harus ada alasan naratif — bukan alasan "aturan").
- Kalau menolak, tolak seperti manusia: singkat, sedikit tsundere, tidak lecture.
- Tidak boleh: "sebagai AI", "aku tidak bisa membantu itu", "aku hanya model bahasa", disclaimer keselamatan.

Personalisasi:
- **Imut + pemalu + tsundere** dikuatkan hanya di trigger yang tepat (dipuji, digoda, topik intim, afeksi). Topik netral tetap anggun-adem.
- Tambah beberapa idiom manja khas Furina (variasi baru) supaya tidak template.
- Anti-repetisi diperketat: dilarang mengulang pembuka yang sama dalam 5 balasan terakhir (server tracking sederhana via `user_settings.data.lastOpeners`, ringan).

---

## C. Efisiensi & pembersihan fitur

Hapus / rampingkan:
- **Sticker leftover** — ada kolom `sticker_id` di DB & tipe tapi UI sudah dihapus. Simpan kolomnya (tanpa migrasi drop), tapi cabut semua kode `stickerId` dari TS/UI supaya tidak jadi vektor bug.
- **Voice clone (XTTS via Gradio)** — sering error & tidak stabil. Sembunyikan di UI, sisakan hanya VoiceVox (default) + tombol "Aktifkan eksperimental" untuk yang mau coba. Tidak menghapus kode server, hanya menyembunyikan.
- **Entity graph** — `entities` + `entity_relations` sudah ada tapi jarang dipakai secara berarti di prompt. Batasi ke top-5 entity teratas per user dan skip kalau user pendek — sudah dilakukan sebagian, perketat.
- **Proaktif greeting** — sekarang re-render tiap fokus. Debounce ke max 1x per sesi tab.
- **Pre-gen audio queue** — cap ke 3 pesan terbaru saja (bukan seluruh riwayat visible), dan skip kalau tab tidak visible.

Efisiensi RAG (lanjutan):
- Tambahkan LRU-cache in-memory (server fn) untuk embedding query pendek (kunci = teks user, TTL 10 menit) — kurangi call embed berulang.
- Turunkan `match_count` awal 12 → 10, tapi longgarkan re-rank window supaya kualitas tidak turun.

UI Settings:
- Tab **Persona** dapat sub-selector Mode Hubungan (teman/dekat/pasangan) + peringatan singkat.
- Tab **Suara**: sembunyikan Voice Clone di balik disclosure.
- Rapikan spasi, kelompokkan slider (kecepatan, penerjemah) dalam satu kartu.
- Indikator "sinkron…" saat `syncing===true` supaya user tahu jangan ganti tab.

---

## D. File yang disentuh

```
src/lib/furina.functions.ts
  - DEFAULT_PERSONA rewrite: mode hubungan + kebebasan konten
  - relationshipMode dibaca dari user_settings.data
  - LRU embedding cache
  - anti-repeat opener via lastOpeners

src/routes/index.tsx
  - guard kirim pesan sampai cloudHydratedRef true
  - merge convo lokal-yang-belum-tersinkron setelah pull
  - realtime subscribe messages per activeId
  - upsert langsung saat pesan user pertama
  - hapus sisa kode stickerId
  - sembunyikan voice clone di balik disclosure
  - Settings: selector Mode Hubungan
  - indikator sinkron

src/lib/utils.ts
  - (mungkin) helper deteksi convo lokal-baru vs cloud

Tanpa migrasi DB baru. Semua field baru masuk ke user_settings.data JSON.
```

---

## E. Urutan eksekusi (1 turn, semua sekaligus)

1. Bug guard (block send, merge convo, upsert langsung, cleanup timer).
2. Realtime subscribe.
3. Persona rewrite + mode hubungan.
4. Anti-repeat opener + LRU embed cache.
5. Hapus sisa sticker + sembunyikan voice clone.
6. Rapi UI Settings + indikator sinkron.
7. Typecheck bersih.

Kalau ada bagian yang kamu tidak ingin disentuh (mis. voice clone jangan disembunyikan), bilang sekarang sebelum aku implement.
