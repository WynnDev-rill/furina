# Furina Native Settings — Design QA

## 2026-08-09 — Native Android system bars

- Source target: user-provided MemoCard screenshot `/workspace/scratch/2bb5d7990f38/upload/02-1000081085.jpg`.
- Prior Furina issue: `/workspace/scratch/2bb5d7990f38/upload/01-1000081084.jpg` showed the status bar composited into the header and the three-button navigation composited into the message composer.
- Implemented: restored decor fitting, removed manual WebView system-inset padding, opted out of Android 15 edge-to-edge enforcement for this activity theme, and assigned opaque dedicated status/navigation bar surfaces matching the MemoCard structure.
- Remaining physical-device gate: install the produced APK and confirm the OEM's three-button navigation icons remain legible on `#D5D5D5`; OEM system UI may apply its own contrast treatment.

- Source visual truth: `/workspace/scratch/2bb5d7990f38/upload/03-1000081081.jpg` and `/workspace/scratch/2bb5d7990f38/upload/04-1000081080.jpg`
- Browser-rendered implementation: `/workspace/scratch/furina-settings-qa-dark-focused.jpg`
- Production URL: `https://furina-pi.vercel.app/native`
- Source pixels: 691 × 1536 each (Android screenshot including browser/system chrome)
- Implementation evidence: 300 × 700 focused crop from a 1363 × 936 CSS-pixel cloud-browser viewport at deviceScaleFactor 1
- State: dark theme, Settings open, no Android bridge (download controls correctly show APK-only state)

## Full-view comparison evidence

The production Settings sheet restores the source hierarchy: dark full-height surface, sticky title/description, bordered display card, character fields, TTS controls, language, background, memory, backup, and destructive conversation action. The local Qwen section is intentionally inserted after persona so it does not displace the restored voice/background/memory flow.

The source includes mobile browser chrome and a former account block. Browser chrome is not app-owned and is intentionally absent from the APK. Account login remains outside this local-first release scope; Google Drive transport is handled through Android's native folder picker instead.

## Focused region comparison evidence

Compared the source's top Settings region against the focused production capture in the same review pass:

- Typography hierarchy, dark navy palette, thin borders, rounded cards, form density, and vertical rhythm are consistent.
- The restored Display, name, and persona controls match the source order and interaction style.
- The Qwen card uses the same border/radius language rather than introducing a separate visual system.
- All primary touch targets are at least 44 CSS px where the component is interactive.

## Findings and iteration history

### Initial P1 — Mature settings were missing

- Evidence: the previous `/native` sheet contained only name, persona, Qwen, a single fixed TTS voice, summary-only memory, and backup.
- Fix: restored theme, provider/VOICEVOX selection, Japanese translation, audio pre-generation, autoplay, speed, reply language, background upload/reset, manual memory management, and clear-conversation controls.
- Post-fix evidence: production DOM snapshot exposes all restored controls and the focused screenshot shows the dark hierarchy matching the reference.

### Superseded P1 — Android system chrome was incorrectly merged into WebView

- Evidence: the follow-up APK screenshot showed the top system content over the Furina header and three-button navigation over the composer.
- Correction: system bars now occupy separate opaque surfaces, matching the MemoCard reference. Theme changes no longer make the Android bars transparent.
- Post-fix gate: Kotlin/Gradle compilation and signed APK verification, followed by a physical Poco F6 screenshot.

### Initial P2 — Memory controls were visual summaries only

- Fix: added SQLite-backed list/add/delete/clear operations and current-session clearing through `FurinaBridge`.
- Post-fix evidence: web production exposes the controls; Android compilation verifies the JavaScript interface signatures.

## Required fidelity surfaces

- Fonts and typography: hierarchy and readable sizing passed; production uses the repository's existing font stack.
- Spacing and layout rhythm: passed for the source-aligned top region and long-form settings flow.
- Colors and visual tokens: passed in dark mode; light mode toggle also verified.
- Image quality and asset fidelity: the original Furina background asset is preserved; custom background upload/reset is restored.
- Copy and content: restored controls use the earlier Indonesian labels, with local-Qwen and encrypted-backup copy retained.

## Primary interactions tested

- Open Settings.
- Toggle dark → light → dark.
- Verify all TTS, language, background, memory, backup, and clear-chat controls are present and accessible.
- Check browser console: no application-origin errors; only unrelated cloud-browser extension metadata warnings.

## Follow-up polish

- P3: confirm exact status/navigation icon contrast on a physical Poco F6 using three-button navigation.

final result: passed
