# Furina WebView

Android launcher for `https://furina.lovable.app/`. Version 1.1.0 (code 2), package `com.wynndev.furina.webview`, minimum Android 8 and target SDK 34. The usual Android system insets apply to the hosted UI, including the software keyboard.

Build with Gradle 8.7, JDK 17+, and Android SDK 35. Run `gradle -p webview-android :app:assembleDebug`. For an upgrade, sign with the same certificate used by the installed APK. Earlier snapshot builds used temporary debug signing. The GitHub workflow uploads a CI APK as an artifact.

The launcher artwork is the historical Furina source from commit `2db6631`, `android-wrapper/app/src/main/res/drawable-nodpi/furina_icon_source.png`. `drawable-nodpi/furina_launcher.png` is a resized copy of that artwork.

Android OAuth opens Google in the system browser using hosted Lovable OAuth. After authenticating, use the return button in the browser to transfer the encrypted session to the originating WebView. The transfer expires after ten minutes. Local guest data and Supabase account data follow the web app's existing storage model.
