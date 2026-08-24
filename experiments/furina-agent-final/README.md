# Furina — private final build

Furina is one local-first companion with two surfaces sharing the same Core and user data:

- **Furina Lite** in Termux: Chat, Provider & Model, Pengaturan, Exit.
- **FurinaHub** on Android: full multimedia, provider/model, Plugin, personalization, and Android-control surface.

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

States are **Unduh → Pilih → Aktif**. FurinaHub and Termux now write the same Core model/routing state, so choosing a Local model in either surface changes the same active model. Downloads remain resumable and verified by GGUF structure plus pinned SHA-256.

## FurinaHub runtime ownership

FurinaHub no longer owns update checks or update polling. The only supported update entry point is:

```bash
furina update
```

That single updater coordinates the Core snapshot and FurinaHub APK. FurinaHub only reports a version mismatch and directs the user to Termux.

The old LLM-based conversation-title worker and periodic Hub update pollers are removed. Conversation titles are deterministic, active chat streaming remains in-place, and Hub status/progress work stays bounded in the existing Core runtime. This avoids repeated background task/process churn while preserving live streaming.

## Sessions and memory

- A new `furina` process gets a fresh Termux short-term chat thread.
- `/back` keeps the current thread while that process is running.
- FurinaHub keeps explicit persistent conversations.
- Trusted long-term memory, profile, relationship state, personality selection, provider secrets, model selection and downloaded models persist across sessions and normal updates.

## Update / recovery

```bash
furina update
furina recover
furina repair
```

The updater validates the channel and assets, stages a complete Core+bridge snapshot, and swaps Core/bridge atomically while user data remains outside the replacement boundary.

## Current versions

- Core: `1.1.0`
- FurinaHub: `1.1.0` (`versionCode 10068`)
- Dependency revision: `2026.08.24-r50`
- Bundle: `furina-2026.08.24-private-1.1.0`
- Update client: `1.2.0`
- Runtime contract: `furina-runtime/v16-personality-matrix-hub-runtime`

See [`INSTALL.md`](./INSTALL.md) for the operational flow.
