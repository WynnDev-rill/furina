# Furina — Termux private build

Furina untuk sementara berfokus pada satu surface: **Termux**. Source dan rilis lama FurinaHub tetap disimpan untuk kemungkinan pengembangan kembali, tetapi instalasi baru dan `furina update` tidak mengunduh atau membuka APK.

## Install

```bash
pkg update -y && pkg install -y curl
curl -fsSL https://github.com/WynnDev-rill/furina/releases/download/furina-update-stable/furina-install.sh | bash
furina
```

Fresh install does not download a GGUF. Local models are downloaded only from **Provider & Model**.

## Conversation architecture

1.1.0 keeps Grounded Dialogue State but removes the remaining cause of local pattern anchoring. User statements are authoritative. Furina's previous wording is only carried forward when the next user turn genuinely refers to it (for example a correction or clarification); an unrelated new topic does not inherit old assistant prose or motifs.

Every conversational response still comes from the selected model. There are no canned social replies, regex content rewrites, or second-pass repair generations. Adaptive pacing only tells the model roughly how much depth a turn needs; it never supplies response text.

Local and Online engines use the same trusted Core memory, relationship state, and personalization.

## Personalization 1.1.0

The old preset/slider/custom-instruction personality surface is replaced by one shared Core-owned system. It is available in **Pengaturan → Personalisasi** in Termux and in **Personalisasi** in FurinaHub.

Twenty independent traits can be toggled in any combination, including all 20: Tsundere, Yandere, Kuudere, Dandere, Deredere, Himedere, Kamidere, Sadodere, Mayadere, Bakadere, Hajidere, Darudere, Shundere, Utsudere, Bodere, Hiyakasudere, Nyandere, Oujodere, Genki girl, and Onee-san type.

The labels are UI shorthand. Core compiles selected traits into a bounded set of behavioral facets such as warmth, reserve, pride, teasing, composure, energy, shyness, elegance, caretaking and maturity. Opposing traits become situational tension instead of one trait deleting another, so large 10–20 trait combinations remain usable without dumping a long trope list into every prompt.

## Provider & Model

There is no AUTO mode. Chat uses Online or exactly one selected Local model:

| Model | Role | Quantization | Approx. download |
| --- | --- | --- | ---: |
| wifuGPT 1.7B | lightweight roleplay | Q4_K_M | ~1.03 GiB |
| Qwen3 1.7B Heretic | lightweight multilingual | Q5_K_M | ~1.17 GiB |
| Qwen3 4B Instruct 2507 Uncensored | Quality | Q4_K_M | ~2.50 GB |

States are **Unduh → Kelola → Aktif**. Model terpasang dapat dipilih atau dihapus dari menu yang sama; menghapus model aktif lebih dulu memindahkan routing ke Online. Downloads remain resumable and verified by GGUF structure plus pinned SHA-256.

## Update ownership

Satu-satunya jalur update yang didukung adalah:

```bash
furina update
```

Updater hanya mengganti Core Termux secara atomik. Tidak ada sinkronisasi, unduhan, atau installer APK.

## Sessions and memory

- A new `furina` process gets a fresh Termux short-term chat thread.
- `/back` keeps the current thread while that process is running.
- Ucapan user dari percakapan lama diindeks dengan SQLite FTS5 dan hanya potongan relevan yang diambil untuk pesan saat ini.
- Konsolidasi AI tetap memilih fakta/preferensi/tujuan yang layak menjadi memori jangka panjang; tidak terbatas pada frasa “ingat ini”.
- Trusted long-term memory, profile, relationship state, personality selection, provider secrets, model selection dan model unduhan tetap persisten saat update.

## Update / recovery

```bash
furina update
furina recover
furina repair
```

Updater memvalidasi channel dan snapshot Core, lalu mengganti Core secara atomik sementara data pengguna tetap di luar batas penggantian.

## Current versions

- Core: `1.1.16`
- FurinaHub: tidak didistribusikan (rilis lama dipertahankan)
- Dependency revision: `2026.08.25-r66`
- Bundle: `furina-2026.08.25-termux-1.1.16`
- Update client: `1.3.0`
- Runtime contract: `furina-runtime/v17-termux-adaptive-memory`

See [`INSTALL.md`](./INSTALL.md) for the operational flow.
