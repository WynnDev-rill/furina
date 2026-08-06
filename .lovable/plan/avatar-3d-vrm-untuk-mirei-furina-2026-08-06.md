# Avatar 3D VRM untuk Mirei/Furina

Menambahkan panel avatar 3D di layar chat: model VRM gratis berlisensi terbuka, animasi VRMA gratis, ekspresi dan gaze yang mengikuti emosi balasan AI, plus lip-sync mengikuti pemutaran suara VOICEVOX. Semua AI tetap lewat Lovable AI Gateway — tidak ada API key tambahan.

## 0. Perbaikan build lebih dulu

Build saat ini gagal dan harus diberesi sebelum fitur baru:

- Paket klien backend `@supabase/supabase-js` belum terpasang (sudah saya pasang saat pengecekan, tinggal dipastikan ikut terbawa).
- Type error di `src/routes/index.tsx` baris 329: field `role` pada pesan sentuhan perlu di-cast ke tipe peran chat.

## 1. Sumber model dan lisensi

Model diambil dari koleksi avatar VRM berlisensi terbuka (Open Source Avatars / VTubeMe — CC0 atau CC BY 4.0, mengizinkan pemakaian di aplikasi, modifikasi, distribusi dalam APK, dan penggunaan pribadi). Saya pilih satu model VRM 1.0 perempuan bergaya anime yang paling mendekati arah karakter, unduh, verifikasi metadata lisensinya, lalu simpan:

```text
public/avatar/mirei.vrm
public/avatar/LICENSE.txt      # nama model, pembuat, URL sumber, jenis lisensi
public/avatar/anim/idle.vrma
public/avatar/anim/wave.vrma   # dst. sesuai yang tersedia gratis
```

Kalau ukurannya besar, file diunggah ke penyimpanan CDN Lovable dan dirujuk lewat pointer, agar repo tetap ringan. Kalau nanti kamu punya model sendiri, tinggal ganti file `.vrm`-nya — kode tidak perlu diubah.

## 2. Panel avatar di layar chat

- Komponen baru `src/components/avatar/VrmStage.tsx`: kanvas React Three Fiber, dimuat hanya di browser (bukan saat render server), dengan indikator loading dan fallback aman bila model gagal dimuat.
- Ditempatkan sebagai panel di layar chat yang sudah ada — tata letak chat, komposer, dan setting tidak diubah. Di layar sempit (mobile) panel tampil sebagai area avatar di atas transkrip, dengan tombol untuk menyembunyikan.
- Kamera close-up wajah/torso, pencahayaan lembut, latar transparan supaya menyatu dengan tema terang dan gelap.

## 3. Gerakan dan ekspresi

- Animasi klip `.vrma` gratis untuk idle, talk, wave, thinking, dan reaksi sentuhan, di-blend dengan crossfade halus.
- Lapisan prosedural tetap aktif di atas klip: napas, kedip acak, gaze mengikuti kursor/sentuhan, dan micro-sway — jadi avatar tidak pernah terlihat beku meski klip terbatas.
- Peta emosi (`happy`, `embarrassed`, `annoyed`, `sad`, `surprised`, `playful`, `neutral`) ke ekspresi VRM dan pose, memakai emosi yang sudah dikeluarkan sistem balasan sekarang.
- Spring bone (rambut/pakaian) aktif dengan intensitas yang bisa diturunkan pada profil performa rendah.

## 4. Lip-sync dengan VOICEVOX

Saat audio VOICEVOX diputar, amplitudo audio dibaca lewat analyser dan dipetakan ke bentuk mulut VRM, sehingga mulut bergerak sesuai suara, bukan sekadar buka-tutup acak. Saat suara dimatikan, mulut mengikuti ritme teks yang muncul.

## 5. Performa dan Android

- Batas frame rate adaptif dan penurunan resolusi render otomatis di perangkat lemah, agar WebView Android tetap lancar.
- Kanvas dijeda saat tab/aplikasi tidak aktif supaya baterai tidak terkuras.
- Setelan baru di tab Setting yang sudah ada: tampilkan/sembunyikan avatar, dan kualitas render (rendah/sedang/tinggi).

## Catatan teknis

- Paket `@pixiv/three-vrm`, `@pixiv/three-vrm-animation`, `@react-three/fiber`, dan `@react-three/drei` sudah terpasang; tidak ada dependensi berat baru.
- Modul three.js hanya diimpor secara dinamis di sisi klien agar SSR tidak pecah.
- Emosi/gaze memakai kontrak data balasan yang sudah ada, jadi logika chat, memori, dan persona tidak disentuh.
