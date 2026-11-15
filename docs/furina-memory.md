# Memori Furina

## Cara kerja

- **Memori tersimpan** berisi catatan yang ditambahkan, dikoreksi, atau dipilih pengguna. Catatan ini dapat dipakai saat referensi riwayat dijeda.
- **Referensi riwayat** memakai ekstraksi fakta dan kejadian, ringkasan, serta pencarian semantik yang sudah dimiliki Furina. Saat dijeda, chat berhenti mengambil dan membuat konteks otomatis lintas percakapan. Pesan dalam percakapan aktif tetap tersedia untuk menjawab giliran saat ini.
- **Ringkasan** menampilkan cuplikan catatan aktif yang dikelompokkan menurut topik. Tampilan ini dirakit dari data yang dapat ditinjau dan tidak menjalankan permintaan model tambahan.
- **Lupakan** menghapus catatan terpilih dan menggeser batas konteks sehingga turunan riwayat lama dan giliran di balik batas itu tidak dipakai kembali. Koreksi hanya memperbarui catatan terpilih dan membatalkan ringkasan otomatis yang tercatat sebagai turunannya. Batas riwayat tidak berubah. Riwayat pesan asli tetap dapat dibuka.
- Catatan lama di balik batas masih bisa ditinjau dan dipulihkan satu per satu lewat Kelola memori. Catatan yang dipilih pulih sebagai memori tersimpan.
- Database sebelumnya tidak mencatat apakah sebuah catatan ditambahkan secara manual. Catatan lama tetap dapat ditinjau di bawah referensi riwayat, lalu dipindahkan ke daftar tersimpan.
- Akun dan tamu memiliki ruang memori terpisah. Memori aktif tamu dapat dipindahkan saat masuk untuk pertama kalinya.
- Hapus semua memori mempertahankan Identity Core dan profil seperti tanggal lahir. Identity Core memiliki pengaturan dan reset tersendiri. Detail yang kembali dibagikan secara eksplisit dalam pesan baru dapat dipelajari lagi apabila referensi riwayat aktif.
- Sebagian fitur lama, seperti graf entitas dan profil gaya lama yang tidak menyimpan seluruh asal teks, dihentikan setelah batas privasi pertama dibuat. Pencarian vektor dan ekstraksi serta ringkasan percakapan baru serta kompaksi catatan baru tetap berjalan.

## Referensi produk dan tampilan

- [Memory in ChatGPT](https://help.openai.com/en/articles/8590148-memory-in-chatgpt) mendokumentasikan perbedaan ingatan eksplisit, konteks riwayat, koreksi, sumber, dan penghapusan.
- [Dreaming](https://openai.com/index/chatgpt-memory-dreaming/) mendeskripsikan sintesis latar belakang serta evaluasi untuk kontinuitas, kepatuhan terhadap preferensi, dan kesegaran. Furina menggunakan ringkasan dari catatan yang bisa dikoreksi langsung untuk menjaga biaya dan keterlacakan.
- [Temporary Chat](https://help.openai.com/en/articles/8914046) menunjukkan bagaimana kontrol per percakapan berbeda dari kontrol akun.
- [Glassmorphism Settings](https://dribbble.com/shots/24472630-Mobile-App-Settings-Glassmorphism-Daily-UI-007) untuk dua kontrol ringkas dan material glass yang sama dengan pengaturan Furina.
- [AI Notes](https://dribbble.com/shots/27303132-AI-Notes-Your-Second-Brain-Powered-by-AI) untuk pencarian dan akses catatan yang mudah dipindai.
- [Mirello](https://www.behance.net/gallery/220307723/Mirello-Notes-Journaling-Mobile-App-Design) untuk hierarki bagian dan keterbacaan teks.
