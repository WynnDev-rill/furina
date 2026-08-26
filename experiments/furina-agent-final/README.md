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

Every conversational response still comes from the selected model. There are no canned social replies, regex content rewrites, or second-pass repair generations. The response-rhythm controller assigns 1–6 semantic beats: a casual opinion normally gets two beats, while a real audit can receive five or six. A stored request for concise or detailed answers overrides the automatic length choice.

Local and Online engines use the same trusted Core memory, relationship state, and personalization. Fresh installs are personal companions, not romantic partners; romance is opt-in.

## Personalization 1.1.0

The old preset/slider/custom-instruction personality surface is replaced by one Core-owned system. It is available through **Personalisasi** in the Termux main menu.

Twenty independent traits can be toggled in any combination, including all 20: Tsundere, Yandere, Kuudere, Dandere, Deredere, Himedere, Kamidere, Sadodere, Mayadere, Bakadere, Hajidere, Darudere, Shundere, Utsudere, Bodere, Hiyakasudere, Nyandere, Oujodere, Genki girl, and Onee-san type. Fresh installs start with no optional trait selected; Furina's stable Identity Kernel remains active.

The labels are UI shorthand backed by 20 behavioral action cards. Two selected traits both remain active. Larger selections use one stable anchor plus situational and coverage-debt slots, so underused traits surface over time without dumping all traits into one prompt. A small emotional state changes gradually and the final contract tells the model what to do, not merely what traits it knows.

## Advanced settings

**Pengaturan → Lanjutan** contains two switches:

- **Mode pasangan**: disabled by default; enables explicit romantic-partner behavior and a bounded evidence ledger.
- **Memori penuh lokal**: disabled by default; archives exact new user and assistant text locally and retrieves at most six relevant excerpts through FTS5 plus optional multilingual embedding rerank.

Traits cannot silently enable romance. Disabling full memory stops new archival/retrieval without deleting old data.

## Provider & Model

There is no AUTO mode. Chat uses Online or exactly one selected Local model:

| Model | Role | Quantization | Approx. download |
| --- | --- | --- | ---: |
| wifuGPT 1.7B | lightweight roleplay | Q4_K_M | ~1.03 GiB |
| Qwen3 1.7B Heretic | lightweight multilingual | Q5_K_M | ~1.17 GiB |
| Qwen3 4B Instruct 2507 Uncensored | Quality | Q4_K_M | ~2.50 GB |

States are **Unduh → Kelola → Aktif**. Model terpasang dapat dipilih atau dihapus dari menu yang sama. If the active model is the only usable engine, deletion now requires an explicit warning; routing never silently pretends Online is ready without a configured provider. Downloads remain resumable and verified by GGUF structure plus pinned SHA-256.

## Update ownership

Satu-satunya jalur update yang didukung adalah:

```bash
furina update
```

Updater hanya mengganti Core Termux secara atomik. Tidak ada sinkronisasi, unduhan, atau installer APK.

## Sessions and memory

- A new `furina` process gets a fresh Termux short-term chat thread.
- `/back` keeps the current thread while that process is running.
- Cross-session raw-text recall runs only when **Memori penuh lokal** is enabled. FTS5 candidates can be reranked by a local multilingual embedding; weak matches return zero excerpts.
- Fakta eksplisit masuk langsung bersama `source_message_id`. Inferensi konsolidator yang lemah menjadi kandidat sampai didukung ucapan user lain; inferensi yang sangat dekat dengan bukti dapat masuk langsung.
- Koreksi disimpan sebagai versi baru dan versi lama ditandai usang. Link ringan `evidence`, `related`, dan `replaces` menjaga asal serta konflik tanpa framework memory eksternal.
- Backfill embedding berjalan dalam batch kecil ketika worker memory idle, bukan di jalur balasan.
- Trusted long-term memory, profile, relationship state, personality selection, provider secrets, model selection dan model unduhan tetap persisten saat update.

## Update / recovery

```bash
furina update
furina recover
```

Updater memvalidasi channel dan snapshot Core, lalu mengganti Core secara atomik sementara data pengguna tetap di luar batas penggantian.

## Current versions

- Core: `1.1.20`
- FurinaHub: tidak didistribusikan (rilis lama dipertahankan)
- Dependency revision: `2026.08.26-r70`
- Bundle: `furina-2026.08.26-termux-1.1.20`
- Update client: `1.4.3`
- Runtime contract: `furina-runtime/v21-synthesized-personality-evidence-memory-termux`

See [`INSTALL.md`](./INSTALL.md) for the operational flow.
