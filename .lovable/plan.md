# Ganti aset VRM jadi karakter anime asli + perbaiki APK

Penilaian kamu benar. Yang ada sekarang: loader VRM + animasi prosedural + fallback, dengan model sample teknis pixiv yang disajikan lewat pointer CDN Lovable (`/__l5e/assets-v1/...`) — path itu memang tidak ada di Vercel, jadi di APK model gagal dimuat dan jatuh ke avatar prosedural.

## 1. Model VRM nyata di repo

- Cari dan verifikasi model VRM 1.0 karakter anime perempuan berlisensi terbuka (CC0 / CC-BY 4.0) dari koleksi avatar open-source, syarat: humanoid rig lengkap, expression preset (aa/ih/ou/ee/oh, blink, happy, angry, sad, relaxed, surprised), lookAt, dan spring bone rambut/rok.
- Verifikasi metadata lisensi di dalam file (`VRMC_vrm.meta`): `avatarPermission`, `allowRedistribution`, `commercialUsage`, `modification` — harus mengizinkan pemakaian aplikasi, modifikasi, dan redistribusi di dalam APK.
- Simpan sebagai file biner sungguhan di `public/avatar/mirei.vrm` (masuk repo dan build Vercel), bukan pointer CDN.
- Perbarui `public/avatar/LICENSE.txt`: nama model, pembuat, URL sumber, lisensi, isi metadata verbatim.
- Hapus `src/assets/mirei.vrm.asset.json` dan pointer CDN-nya; `VrmAvatar.tsx` memuat dari `/avatar/mirei.vrm`.
- Tambahkan cache header panjang untuk `/avatar/*` di `vercel.json` supaya model besar tidak diunduh ulang tiap buka.

Kalau nanti kamu punya model berbayar/kustom, cukup timpa file `.vrm` itu — tidak ada perubahan kode.

## 2. Kualitas gerakan

- Implementasikan pemuatan VRMA yang selama ini cuma rencana: `@pixiv/three-vrm-animation` + `VRMAnimationLoaderPlugin`, `AnimationMixer`, crossfade antar klip.
- Direktori `public/avatar/anim/` untuk `idle`, `talk`, `happy`, `embarrassed`, `annoyed`, `sad`, `thinking`, `wave`, `touch`. Klip yang tidak ada diabaikan tanpa error, jadi kamu bisa menambah sendiri kapan saja.
- Sertakan klip VRMA berlisensi terbuka bila tersedia; jika tidak, layer prosedural dihaluskan: easing per-bone, sway pinggul-bahu berlawanan fase, kedip berpasangan acak non-periodik, saccade mata, dan micro-head-drift saat diam.
- Layer prosedural tetap aktif di atas klip (napas, gaze, lip-sync), jadi bukan animasi kaku loop.

## 3. Perbaikan wrapper APK

Penyebab "APK membuka Chrome": `shouldOverrideUrlLoading` melempar semua host non-Vercel ke browser eksternal — dan login Google memang mengarah ke `accounts.google.com`. Google juga memblokir OAuth di dalam WebView biasa (`disallowed_useragent`), jadi menambah host ke whitelist bukan solusi.

- Ganti intent mentah dengan Chrome Custom Tabs (`androidx.browser`) supaya login tampil sebagai lembar dalam aplikasi, bukan pindah ke Chrome.
- Daftarkan intent-filter deep link untuk URL callback, sehingga setelah login pengguna otomatis kembali ke WebView aplikasi dengan sesi aktif.
- Perbaiki juga: `setDomStorageEnabled` sudah ada tetapi tambah dukungan unduhan/`onShowFileChooser` untuk fitur kirim foto (sekarang tombol upload gambar tidak berfungsi di APK), dan pertahankan izin mikrofon yang sudah jalan.
- Model besar di dalam WebView: pastikan WebGL/hardware acceleration aktif dan tambah timeout + pesan jelas kalau `.vrm` gagal dimuat.

## 4. Verifikasi

- Build web, cek `/avatar/mirei.vrm` benar-benar terlayani dari domain aplikasi (bukan 404).
- Uji render VRM di preview lewat browser otomatis: model tampil, ekspresi berganti, lip-sync ikut audio.
- Sesuaikan `.github/workflows/build-furina-apk.yml`: hapus pengecekan yang sudah tidak relevan, tambah cek keberadaan `public/avatar/mirei.vrm` dan Custom Tabs di MainActivity.

## Catatan teknis

- `@pixiv/three-vrm` 3.5.5 dan `@pixiv/three-vrm-animation` 3.5.5 sudah terpasang; tidak ada dependensi berat baru selain `androidx.browser` di sisi Android.
- File `.vrm` 15-40 MB akan ikut repo GitHub sesuai persetujuanmu; build Vercel tetap di bawah batas.
- Logika chat, memori, persona, dan VOICEVOX tidak disentuh.
