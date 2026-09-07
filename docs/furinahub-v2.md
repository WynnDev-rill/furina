# FurinaHub V2

FurinaHub V2 combines a relationship-first companion surface with a native, provider-agnostic AI
workspace while keeping Furina Lite in Termux as the preferred Core. The integration is selective:
it does not embed either reference application or inherit their unrelated services.

## Product sources

- **LianYu direction:** companion identity, composable traits, memory as a first-class surface,
  private chat wallpaper storage, and motion that can be reduced.
- **EchoFlow direction:** a focused native chat surface, concise connection/model context, resilient
  provider boundaries, and grouped appearance settings.
- **Furina direction:** one adaptive persona, shared Termux memory, Android fallback engines, and a
  localhost bridge authenticated by a per-session token.

## V2 chat appearance contract

- Four built-in dark-first gradient presets.
- A user can import one photo or one silent looping MP4/WebM wallpaper.
- Imported files are validated, copied into app-private storage, and never included in Core or AI
  payloads.
- Photos are limited to 12 MB and 12,000 px per side.
- Videos are limited to 20 MB, 30 seconds, and 1080p.
- Video audio is always muted. Playback pauses with the Activity and can be disabled by the user.
- A 0–72% dim layer maintains message and composer contrast.
- Only one imported wallpaper is retained; replacing or resetting it removes the old private copy.

## Connection presentation

The healthy state is a compact `Core` indicator. Version and bridge details live in Settings. A
disconnected state becomes actionable (`Sambungkan`) without occupying permanent chat space.

## Reference licenses

The design study used the public editions of LianYu (Apache License 2.0) and EchoFlow (MIT). V2's
implementation is written for FurinaHub and does not copy either application's package structure,
model/provider code, assets, identity, or private integrations.
