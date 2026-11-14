# Furina WebView Android

This is an intentionally separate Android wrapper for the **July 6, 2026 Lovable web app**. The Lovable website source on main is not changed by this wrapper.

- Opens `https://furina.lovable.app/` by default (based on the user's currently accessible preview).
- Does not load Vercel or use `/native`.
- Needs network access and a live Lovable preview/published site; AI/TTS/backend still require their hosted services.
- Uses separate application id `com.wynndev.furina.webview` so it cannot replace the existing native Furina app.
- Built as a locally installable **debug-signed** APK with GitHub Actions. Signature changes when runners change; for updatable production APKs provide a persistent signing key via GitHub Secrets, not source files.
- Handles image/file uploads, JavaScript, DOM storage, HTTPS, and Android back navigation.
- To change a broken hosted URL, long-press Android's Back key when supported, or use the URL dialog shown after page load failure.
- Google sign-in might be blocked in embedded WebViews, as Google OAuth may require an external browser.

Run: `gradle -p webview-android :app:assembleDebug` with JDK 17 and Android SDK 35.
