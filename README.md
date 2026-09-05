# Furina

Repository utama proyek Furina Android.

## Furina Lite + FurinaHub

Furina adalah companion AI *relationship-first* untuk percakapan kasual dan romantis. **Furina Lite** berjalan mandiri di Termux; **FurinaHub** menambahkan pengalaman Android lengkap, multimedia, dan pengaturan visual. Keduanya memakai Core, memori, serta hubungan lokal yang sama.

FurinaHub V2 memakai integrasi selektif dari dua fondasi Android terbuka: arah companion, memori, dan wallpaper privat dari LianYu; serta struktur chat native, pengaturan terkelompok, dan batas provider dari EchoFlow. Wallpaper chat dapat berupa preset, foto, atau video lokal berulang tanpa suara. Detail teknis dan batas media ada di [docs/furinahub-v2.md](docs/furinahub-v2.md).

Pada instalasi baru, setup hanya meminta nama pengguna. Furina langsung mengenali pengguna sebagai pasangannya; memori awal lain tetap kosong sampai berkembang dari percakapan atau disimpan secara eksplisit.

### Instalasi cepat

Buka Termux dan jalankan:

```bash
pkg update -y && pkg install -y curl
curl -fsSL https://github.com/WynnDev-rill/furina/releases/download/furina-update-stable/furina-install.sh | bash
furina
```

Panduan lengkap: [Memasang Furina Agent di Termux](https://github.com/WynnDev-rill/furina/blob/experiment/furina-agent-termux/experiments/furina-agent-final/INSTALL.md)

Installer stabil memverifikasi snapshot Core + bridge sebelum aktivasi dan dapat dipakai untuk instalasi baru maupun pemulihan instalasi lama. Data pengguna dan model tidak dihapus saat pembaruan.
