# Mirei Virtual Companion

An experimental Android and web virtual companion with an original 3D character, Japanese voice, contextual animation, touch reactions, local conversation history, and a realistic tsundere personality.

This branch is a complete reconstruction of the former Furina prototype. It intentionally avoids the lore, costume, identity, and protected visual design of existing game characters.

## Challenge structure

- **Stage 1 — Foundation:** online architecture, community inference, 3D runtime, Android networking, CI prototype.
- **Stage 2 — Character:** original VRM character, facial expressions, spring bones, animation state machine, mobile optimization.
- **Stage 3 — Interaction:** Japanese VOICEVOX speech, lip-sync, contextual gestures, touch regions, memory.
- **Stage 4 — Finalization:** UI polish, performance profiles, signed APK, production deployment, reliability testing.

Current work happens on `challenge/virtual-companion-3d`. The branch is kept separate from `main` until the web build and Android build both succeed.

## Current foundation

- React 19 and TanStack Start.
- Three.js through React Three Fiber and Drei.
- VRM runtime packages from pixiv.
- Anonymous AI Horde text generation for the initial experiment.
- Procedural 3D placeholder that already supports gaze, breathing, blinking, mouth motion, emotional poses, and touch regions.
- Android WebView with Internet and microphone support.

## Development

```sh
npm install
npm run dev
```

The anonymous community provider has the lowest queue priority and is deliberately isolated behind `src/lib/companion/ai-horde.ts`, so it can be replaced later without rebuilding the character system.
