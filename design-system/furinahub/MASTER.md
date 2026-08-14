# FurinaHub Design System

Source: repository-scoped UI UX Pro Max v2.15.0 guidance plus the FurinaHub product requirements.

## Product direction

- Product: Android AI companion + device agent.
- Primary task: conversation. Opening the APK lands directly in Chat.
- Technical configuration is progressive disclosure, never the home screen.
- Visual inspiration: clean native Android / Material 3 hierarchy similar in spirit to RikkaHub, without copying its exact screens or branding.
- FurinaHub must remain usable as a shell while Termux Core is offline.

## Visual system

- Light-first neutral lavender surface system with a restrained violet accent.
- Dark mode uses near-black neutral surfaces; no saturated neon/glow dashboard aesthetic.
- System sans typography for offline reliability and consistent Android rendering.
- Radius: 14px controls, 18–22px conversational/card surfaces.
- Borders are subtle 1px semantic dividers; shadows are sparse and shallow.
- Icons are SVG/line icons, not emoji.

## Interaction

- Every primary interactive target is at least 44x44 CSS px.
- Connection, update, agent, and permission operations always show an explicit state.
- Termux integration is user-initiated from Settings. The APK UI never blocks startup waiting for Core.
- Errors are shown near the action that caused them with a clear next action.
- Back/navigation behavior is predictable; main navigation remains under six destinations.

## Motion

- Standard motion intensity: 4–6/10.
- Page/view entry: 180–240ms opacity + small translate only.
- Drawer: ~260ms spatial transition.
- Message entry: ~220ms.
- Button press: short scale feedback.
- Loading indicators use opacity/transform rather than layout-changing width/height animation.
- `prefers-reduced-motion` disables non-essential motion.

## Accessibility

- Body text targets at least 4.5:1 contrast.
- Visible labels for form fields; placeholders are not labels.
- State is never communicated by color alone; text/badges accompany status dots.
- Responsive text must wrap rather than clip.
- Focus styles remain visible for form controls.

## FurinaHub-specific invariants

1. Chat is the default view.
2. No relationship score/"Ringkasan Hubungan" UI.
3. UI works without localhost/Core.
4. `RUN_COMMAND` is requested only after the user taps **Hubungkan ke Termux**.
5. Skill Agent settings can only narrow capability; policy/firewall remains authoritative.
6. APK update works without Core; Core/dependency update requires a connected Termux Core.
