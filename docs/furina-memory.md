# Memori Furina

## Cara kerja

- **Memori tersimpan** berisi catatan yang ditambahkan, dikoreksi, atau dipilih pengguna. Catatan ini dapat dipakai saat referensi riwayat dijeda.
- **Referensi riwayat** memakai ekstraksi fakta dan kejadian, ringkasan, pencarian semantik untuk catatan, dan pencarian teks pada chat lama yang tersinkron. Saat dijeda, chat berhenti mengambil dan membuat konteks otomatis lintas percakapan. Pesan dalam percakapan aktif tetap tersedia untuk menjawab giliran saat ini.
- **Ringkasan** menampilkan cuplikan catatan aktif yang dikelompokkan menurut topik. Tampilan ini dirakit dari data yang dapat ditinjau dan tidak menjalankan permintaan model tambahan.
- **Lupakan** menghapus catatan terpilih dan menggeser batas konteks sehingga turunan riwayat lama dan giliran di balik batas itu tidak dipakai kembali. Koreksi hanya memperbarui catatan terpilih dan membatalkan ringkasan otomatis yang tercatat sebagai turunannya. Batas riwayat tidak berubah. Riwayat pesan asli tetap dapat dibuka.
- Data yang sudah berada di balik batas privasi tetap di luar daftar dan konteks AI. Tampilan pemulihan sementara telah dihapus.
- Database sebelumnya tidak mencatat apakah sebuah catatan ditambahkan secara manual. Catatan lama tetap dapat ditinjau di bawah referensi riwayat, lalu dipindahkan ke daftar tersimpan.
- Akun dan tamu memiliki ruang memori terpisah. Memori aktif tamu dapat dipindahkan saat masuk untuk pertama kalinya.
- Hapus semua memori mempertahankan Identity Core dan profil seperti tanggal lahir. Identity Core memiliki pengaturan dan reset tersendiri. Detail yang kembali dibagikan secara eksplisit dalam pesan baru dapat dipelajari lagi apabila referensi riwayat aktif.
- Sebagian fitur lama, seperti graf entitas dan profil gaya lama yang tidak menyimpan seluruh asal teks, dihentikan setelah batas privasi pertama dibuat. Pencarian vektor dan ekstraksi serta ringkasan percakapan baru serta penggabungan catatan yang mirip tetap berjalan.

## Pengambilan konteks

Furina menggabungkan kecocokan kata dan vektor pada catatan, lalu mencari cuplikan percakapan berdasarkan topik atau tanggal. Pencarian menerapkan pemilik akun, kontrol memori, dan batas privasi sebelum hasil disusun. Pesan yang sudah berada di konteks percakapan aktif dilewati. Koreksi pengguna diprioritaskan, sedangkan balasan lama Furina berfungsi sebagai konteks percakapan.

Gemini langsung dan Lovable menerima konteks yang sudah disusun Furina. Pencarian teks dan penyimpanan koreksi tetap tersedia saat penyedia embedding gagal. Indeks vektor yang kosong diisi bertahap. Riwayat pengguna tamu yang hanya tersimpan di perangkat tersedia melalui konteks percakapan aktif.

## Kelanjutan lintas chat

Permintaan seperti “lanjut yang tadi” memakai percakapan aktif jika topiknya sudah jelas. Jika belum jelas, Furina mencari percakapan yang berisi pesan pengguna dalam 72 jam terakhir. Untuk topik yang disebutkan, kecocokan kata dan judul mempersempit kandidat. Maksimal dua percakapan dan empat cuplikan per percakapan masuk ke prompt. Jika beberapa topik yang sama-sama baru membuat maksud belum jelas, model diarahkan meminta klarifikasi singkat. Memori dan riwayat lama tetap bisa dicari berdasarkan topik.

Sapaan proaktif memakai topik terbaru jika ada tindak lanjut yang jelas. Sintesis pada ringkasan percakapan mendahulukan keputusan yang dikonfirmasi dan status terbaru. Referensi [Dreaming](https://openai.com/index/chatgpt-memory-dreaming/) membahas kesinambungan dan kesegaran informasi. Furina memakai database untuk menemukan percakapan terbaru tanpa panggilan model tambahan.

## Penggabungan otomatis

Catatan otomatis dengan isi identik tidak dibuat ulang. Untuk catatan yang sangat mirip, pencarian vektor menghasilkan kandidat dan model memeriksa apakah semua catatan merujuk pada fakta yang sama atau saling melengkapi. Perbedaan tanggal kejadian, konflik, dan keputusan yang meragukan menahan penggabungan. Isi unik dipertahankan, dan catatan eksplisit pengguna tetap dikelola pengguna. Pemindaian bertahap juga memeriksa catatan otomatis yang sudah aktif. Sumber yang tergabung tetap tersimpan di belakang satu catatan kanonik dan tidak diambil ulang saat merespons.

## Referensi produk dan tampilan

- [Pencarian percakapan Claude](https://support.anthropic.com/en/articles/10185728-understanding-claude-s-personalization-features) sebagai acuan pengambilan detail lama saat topik dirujuk lagi.
- [Hybrid search Supabase](https://supabase.com/docs/guides/ai/hybrid-search) untuk pencarian teks PostgreSQL dan pencarian vektor yang saling melengkapi.

- [Memory in ChatGPT](https://help.openai.com/en/articles/8590148-memory-in-chatgpt) mendokumentasikan perbedaan ingatan eksplisit, konteks riwayat, koreksi, sumber, dan penghapusan.
- [Dreaming](https://openai.com/index/chatgpt-memory-dreaming/) mendeskripsikan sintesis latar belakang serta evaluasi untuk kontinuitas, kepatuhan terhadap preferensi, dan kesegaran. Furina menggunakan ringkasan dari catatan yang bisa dikoreksi langsung untuk menjaga biaya dan keterlacakan.
- [Temporary Chat](https://help.openai.com/en/articles/8914046) menunjukkan bagaimana kontrol per percakapan berbeda dari kontrol akun.
- [Glassmorphism Settings](https://dribbble.com/shots/24472630-Mobile-App-Settings-Glassmorphism-Daily-UI-007) untuk dua kontrol ringkas dan material glass yang sama dengan pengaturan Furina.
- [AI Notes](https://dribbble.com/shots/27303132-AI-Notes-Your-Second-Brain-Powered-by-AI) untuk pencarian dan akses catatan yang mudah dipindai.
- [Mirello](https://www.behance.net/gallery/220307723/Mirello-Notes-Journaling-Mobile-App-Design) untuk hierarki bagian dan keterbacaan teks.
