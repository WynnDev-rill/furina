# Furina

Repository utama proyek Furina Android.

## Furina Agent — Eksperimen Termux

Furina Agent adalah eksperimen terpisah yang berjalan di Termux dan dapat memakai Furina Bridge untuk kontrol Android. Agent **tidak menjadi bagian dari build APK Furina utama** dan dikembangkan di branch `experiment/furina-agent-termux`.

### Instalasi cepat

Buka Termux dan jalankan:

```bash
pkg update -y && pkg install -y curl
curl -fsSL https://raw.githubusercontent.com/WynnDev-rill/furina/experiment/furina-agent-termux/experiments/furina-agent-final/install.sh | bash
furina
```

Panduan lengkap: [Memasang Furina Agent di Termux](https://github.com/WynnDev-rill/furina/blob/experiment/furina-agent-termux/experiments/furina-agent-final/INSTALL.md)

> Furina Agent masih eksperimental. Dokumentasi di halaman ini hanya menjadi pintu masuk; source, installer, dan pengembangan Agent tetap dipisahkan dari Furina utama.
