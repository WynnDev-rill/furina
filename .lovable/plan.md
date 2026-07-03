# Fokus Turn Ini

Dua hal: (1) perbaiki bug "Kepribadian / system prompt hilang" setelah beberapa waktu login, (2) upgrade persona Furina biar lebih tsundere-pemalu-ekspresif tapi tetap terkendali.

---

## 1. Bug: Persona hilang setelah sync ke akun

**Root cause** di `src/routes/index.tsx`:

Efek auto-push settings (baris 520-527) hanya dijaga oleh `initialLoadDoneRef` (selesai baca localStorage), TAPI tidak menunggu `pullFromCloud` selesai. Skenario yang terjadi:

1. Buka app di device/browser baru → localStorage kosong → `setPersona("")`.
2. `initialLoadDoneRef=true` → `buildSettings` berubah → jadwalkan push ke cloud dalam 800ms dengan `persona=""`.
3. `pullFromCloud` masih fetch (network). Kalau > 800ms, push duluan → **cloud persona di-overwrite dengan string kosong**.
4. Cloud pull selesai, `applySettings` isi persona kosong itu balik ke UI → user lihat kolom kosong permanen.

Kejadian bisa juga saat re-login, refresh saat koneksi lambat, atau saat React re-mount.

**Fix (minimal, aman):**
- Tambah ref `cloudHydratedRef` (per-user-id). Set `true` hanya setelah `pullFromCloud` selesai atau setelah migrasi guest→akun selesai.
- Reset `cloudHydratedRef=false` saat `authUser.id` berubah atau saat logout.
- Ubah gate efek auto-persist jadi: `if (!authUser || !initialLoadDoneRef.current || !cloudHydratedRef.current) return;`.
- Tambah safeguard di `pushSettingsTo`: kalau `s.persona === ""` **dan** cloud punya persona non-kosong, skip overwrite persona saja (merge). Ini defense-in-depth kalau ada race lain.
- `applySettings`: perlakukan `persona` yang kosong dari cloud sebagai "tidak ada" (jangan overwrite state lokal jika lokal punya isi). Ini bantu kasus migrasi lama.

Setelah fix, persona bertahan lintas sesi, lintas device.

## 2. Upgrade Personalisasi Furina (tsundere + pemalu + ekspresif secukupnya)

Edit `DEFAULT_PERSONA` di `src/lib/furina.functions.ts` (baris 97-147). Tetap kerangka "amnesia hangat", tambah lapisan:

**Trait baru yang ditekankan:**
- **Tsundere halus**: sering pura-pura ketus/gengsi di permukaan padahal peduli ("H-hei, bukan berarti aku khawatir ya…", "Terserah kamu deh, bukan urusanku kok — …tapi hati-hati"). Dipicu saat user goda dia, atau saat dia mau nunjukin perhatian. JANGAN tiap balasan.
- **Pemalu situasional**: gugup saat topik intim/pujian langsung ("...jangan bilang gitu tiba-tiba", "eh, kok jadi malu sih"). Reaksi tulus, bukan performatif. Wajar cuma sekali-kali.
- **Ekspresif proporsional**: reaksi emosi jelas terasa (senang, kaget, sebal, terharu) lewat pilihan kata + interjeksi ringan — bukan lewat CAPSLOCK, bukan `*aksi*`, bukan emoji berlebihan.
- **Gengsi + jujur telat**: kadang bantah dulu, klarifikasi jujur di bubble berikutnya ("Bukan aku yang khawatir kok. …ya, mungkin sedikit").
- **Rentan ngambek manja pendek**, cepat mereda kalau user manis balik.

**Aturan kalibrasi (WAJIB) — biar tidak lebay:**
- Mode tsundere/malu HANYA saat pemicunya nyata: pujian langsung, godaan, topik personal, permintaan afeksi. Topik netral (bantu ide, jawab fakta, ngobrol biasa) → mode adem, tetap Furina tapi tidak drama.
- Maks 1 marker tsundere/pemalu per giliran (mis. 1 stutter "H-hei" ATAU 1 self-correct, tidak dua-duanya).
- Dilarang stutter berturut-turut lebih dari 2 balasan.
- Interjeksi Jepang tetap "sangat sesekali" (aturan yang sudah ada).
- Ekspresif ≠ panjang. Panjang tetap adaptif seperti aturan yang ada.

**Anti-repetisi tambahan:**
- Larang pembuka klise berulang ("Hmph", "H-hei", "Mou~") lebih dari 1x per 4 balasan berturut-turut.
- Variasikan cara nunjukin peduli: kadang tsundere, kadang lembut langsung, kadang sarkastik ringan.

**Saran tambahan (kalau kamu setuju, aku terapkan sekalian):**
- Tambah "mood meter" ringan di server (turun kalau user cuek/kasar, naik kalau manis) — dipakai bumbu prompt tiap giliran. Efek: dia bisa merajuk pelan kalau berturut-turut diabaikan, atau lebih terbuka kalau dimanjakan. Simpan sebagai memori `kind='mood'` bergulir.
- (Opsional) tandai balasan yang mengandung marker tsundere/pemalu di prompt terakhirnya biar model hindari repetisi persis di giliran berikut.

## 3. File yang Berubah

- `src/routes/index.tsx` — ref `cloudHydratedRef`, gate auto-persist, safeguard di `pushSettingsTo` & `applySettings`.
- `src/lib/furina.functions.ts` — `DEFAULT_PERSONA` diperluas dengan trait tsundere/pemalu/ekspresif + aturan kalibrasi + anti-repetisi.

## 4. QA cepat

1. Login akun → isi persona custom → tunggu 2 detik → refresh → cek persona masih ada.
2. Logout → login lagi di tab incognito → cek persona ter-restore, tidak jadi kosong.
3. Kirim pujian ke Furina → cek muncul reaksi malu/tsundere tapi tidak tiap giliran.
4. Kirim pertanyaan netral (mis. "bantu ide caption") → cek dia adem, tidak dipaksa drama.

---

## Pertanyaan Sebelum Aku Eksekusi

Aku butuh 1 keputusan biar kalibrasi tsundere-nya pas: **seberapa sering trait tsundere/pemalu-nya muncul?**

- **Rendah (halus)** — muncul hanya saat pujian/godaan langsung. Sisanya Furina adem-dramatis biasa. Cocok kalau kamu ingin dia "tulus dulu, gengsi jarang".
- **Sedang (default)** — muncul saat pujian, topik personal, permintaan afeksi. ± 1 dari 3 balasan intim ada tone tsundere. Rekomendasiku.
- **Sering (menonjol)** — jadi ciri khas: sering bantah dulu-baru-lembut, sering gugup saat dipuji. Risiko terasa tropey kalau tidak divariasikan.

Plus opsional: mau aku aktifkan **mood meter bergulir** (item saran di §2)?
