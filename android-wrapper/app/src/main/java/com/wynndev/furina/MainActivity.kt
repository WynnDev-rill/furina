package com.wynndev.furina

import android.content.Intent
import android.content.pm.PackageManager
import android.content.res.ColorStateList
import android.graphics.Color
import android.graphics.Typeface
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.SystemClock
import android.util.TypedValue
import android.view.Gravity
import android.view.View
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.ProgressBar
import android.widget.TextView
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.OnBackPressedCallback
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.content.ContextCompat
import androidx.core.view.WindowCompat
import org.json.JSONObject

class MainActivity : ComponentActivity() {
    private lateinit var webView: WebView
    private lateinit var bridge: FurinaBridge
    private lateinit var cloudBridge: CloudBackupBridge
    private lateinit var evidenceBridge: DeviceEvidenceBridge
    private lateinit var loadingOverlay: View
    private var loadingStartedAt = 0L
    private var loadingDismissed = false
    private var pageReady = false
    private var pendingAuthCallback: String? = null

    private val folderPicker = registerForActivityResult(ActivityResultContracts.OpenDocumentTree()) { uri ->
        if (uri != null) {
            try {
                contentResolver.takePersistableUriPermission(
                    uri,
                    Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_GRANT_WRITE_URI_PERMISSION,
                )
            } catch (_: Throwable) {}
            bridge.onBackupFolderSelected(uri)
        }
    }

    private val restorePicker = registerForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri != null) bridge.onRestoreFileSelected(uri)
    }

    private val notificationPermission = registerForActivityResult(ActivityResultContracts.RequestPermission()) { }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        WindowCompat.setDecorFitsSystemWindows(window, true)
        window.statusBarColor = STATUS_BAR_COLOR
        window.navigationBarColor = NAVIGATION_BAR_COLOR
        window.isStatusBarContrastEnforced = false
        window.isNavigationBarContrastEnforced = false

        webView = WebView(this).apply {
            alpha = 0f
            setBackgroundColor(Color.rgb(5, 7, 18))
            settings.javaScriptEnabled = true
            settings.javaScriptCanOpenWindowsAutomatically = false
            settings.setSupportMultipleWindows(true)
            settings.domStorageEnabled = true
            settings.cacheMode = WebSettings.LOAD_DEFAULT
            settings.allowFileAccess = false
            settings.allowContentAccess = false
            settings.setGeolocationEnabled(false)
            settings.mediaPlaybackRequiresUserGesture = false
            settings.mixedContentMode = WebSettings.MIXED_CONTENT_NEVER_ALLOW
            settings.safeBrowsingEnabled = true
            settings.userAgentString = settings.userAgentString + " FurinaAndroid/4.3"
        }
        applySystemTheme(true)
        WebView.setWebContentsDebuggingEnabled(false)

        val store = MemoryStore(this)
        val modelDownloads = ModelDownloadManager(this)
        val backupManager = BackupManager(this, store)
        bridge = FurinaBridge(this, webView, store, modelDownloads, backupManager)
        cloudBridge = CloudBackupBridge(this, webView, backupManager, bridge::withAiPaused)
        evidenceBridge = DeviceEvidenceBridge(this, webView, store, modelDownloads, bridge::withAiPaused)
        webView.addJavascriptInterface(bridge, "FurinaNative")
        webView.addJavascriptInterface(cloudBridge, "FurinaCloud")
        webView.addJavascriptInterface(evidenceBridge, "FurinaEvidence")

        webView.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(view: WebView?, request: WebResourceRequest?): Boolean {
                val uri = request?.url ?: return true
                if (isTrustedAppUri(uri)) return false
                val scheme = uri.scheme?.lowercase()
                if (scheme !in SAFE_EXTERNAL_SCHEMES) return true
                return try {
                    startActivity(Intent(Intent.ACTION_VIEW, uri))
                    true
                } catch (_: Throwable) { true }
            }

            override fun onPageFinished(view: WebView?, url: String?) {
                val uri = runCatching { Uri.parse(url) }.getOrNull()
                if (uri != null && isTrustedAppUri(uri)) {
                    pageReady = true
                    installNativeVisualPolish(view)
                    bridge.notifyNativeReady()
                    deliverPendingAuthCallback()
                    dismissLoadingOverlay()
                }
            }

            override fun onReceivedHttpError(view: WebView?, request: WebResourceRequest?, errorResponse: WebResourceResponse?) {
                if (request?.isForMainFrame == true && (errorResponse?.statusCode ?: 0) >= 400) {
                    showLoadError("Server Furina mengembalikan ${errorResponse?.statusCode ?: "error"}.")
                }
            }

            override fun onReceivedError(view: WebView?, request: WebResourceRequest?, error: android.webkit.WebResourceError?) {
                if (request?.isForMainFrame == true) showLoadError("Antarmuka Furina belum dapat dimuat. Periksa koneksi lalu coba lagi.")
            }
        }

        val root = FrameLayout(this)
        root.addView(webView, FrameLayout.LayoutParams(
            FrameLayout.LayoutParams.MATCH_PARENT,
            FrameLayout.LayoutParams.MATCH_PARENT,
        ))
        loadingOverlay = buildLoadingOverlay()
        root.addView(loadingOverlay, FrameLayout.LayoutParams(
            FrameLayout.LayoutParams.MATCH_PARENT,
            FrameLayout.LayoutParams.MATCH_PARENT,
        ))
        loadingStartedAt = SystemClock.elapsedRealtime()
        setContentView(root)

        handleAuthIntent(intent)
        if (savedInstanceState == null || webView.restoreState(savedInstanceState) == null) {
            webView.loadUrl(APP_URL)
        }

        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                if (webView.canGoBack()) webView.goBack() else finish()
            }
        })
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        handleAuthIntent(intent)
    }

    private fun handleAuthIntent(intent: Intent?) {
        val uri = intent?.data ?: return
        if (!uri.scheme.equals(AUTH_SCHEME, ignoreCase = true) ||
            !uri.host.equals("auth", ignoreCase = true) ||
            uri.path?.startsWith("/callback") != true
        ) return
        pendingAuthCallback = uri.toString()
        deliverPendingAuthCallback()
    }

    private fun deliverPendingAuthCallback() {
        if (!pageReady) return
        val raw = pendingAuthCallback ?: return
        pendingAuthCallback = null
        val quoted = JSONObject.quote(raw)
        longArrayOf(120L, 650L, 1500L).forEach { delay ->
            webView.postDelayed({
                if (!webView.isDestroyed) {
                    webView.evaluateJavascript(
                        "window.__furinaCloudAuthCallback && window.__furinaCloudAuthCallback($quoted)",
                        null,
                    )
                }
            }, delay)
        }
    }

    private fun buildLoadingOverlay(): View {
        val overlay = FrameLayout(this).apply {
            setBackgroundColor(Color.rgb(5, 7, 18))
            isClickable = true
            importantForAccessibility = View.IMPORTANT_FOR_ACCESSIBILITY_NO_HIDE_DESCENDANTS
        }
        val content = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER_HORIZONTAL
            setPadding(dp(28), 0, dp(28), 0)
        }
        val title = TextView(this).apply {
            text = "Furina"
            setTextColor(Color.WHITE)
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 27f)
            typeface = Typeface.create("sans-serif-medium", Typeface.NORMAL)
            letterSpacing = 0.045f
            gravity = Gravity.CENTER
        }
        val subtitle = TextView(this).apply {
            text = "Menyiapkan percakapan…"
            setTextColor(Color.rgb(166, 177, 201))
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 12.5f)
            gravity = Gravity.CENTER
        }
        val progress = ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal).apply {
            isIndeterminate = true
            indeterminateTintList = ColorStateList.valueOf(Color.rgb(56, 189, 248))
        }
        content.addView(title, LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.WRAP_CONTENT,
            LinearLayout.LayoutParams.WRAP_CONTENT,
        ))
        content.addView(subtitle, LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.WRAP_CONTENT,
            LinearLayout.LayoutParams.WRAP_CONTENT,
        ).apply { topMargin = dp(10) })
        content.addView(progress, LinearLayout.LayoutParams(dp(172), dp(3)).apply { topMargin = dp(24) })
        overlay.addView(content, FrameLayout.LayoutParams(
            FrameLayout.LayoutParams.WRAP_CONTENT,
            FrameLayout.LayoutParams.WRAP_CONTENT,
            Gravity.CENTER,
        ))
        content.alpha = 0f
        content.translationY = dp(8).toFloat()
        content.animate().alpha(1f).translationY(0f).setDuration(420L).start()
        return overlay
    }

    private fun dismissLoadingOverlay() {
        if (loadingDismissed) return
        loadingDismissed = true
        val elapsed = SystemClock.elapsedRealtime() - loadingStartedAt
        val delay = (MIN_LOADING_MS - elapsed).coerceAtLeast(0L)
        loadingOverlay.postDelayed({
            if (isFinishing || isDestroyed) return@postDelayed
            webView.animate().alpha(1f).setDuration(280L).start()
            loadingOverlay.animate()
                .alpha(0f)
                .setDuration(340L)
                .withEndAction { loadingOverlay.visibility = View.GONE }
                .start()
        }, delay)
    }

    private fun installNativeVisualPolish(view: WebView?) {
        val css = """
            html.dark header.absolute.inset-x-0.top-0 {
              background: rgba(7,11,24,.44) !important;
              border-bottom-color: rgba(255,255,255,.055) !important;
              box-shadow: 0 8px 26px rgba(0,0,0,.08) !important;
              -webkit-backdrop-filter: blur(22px) saturate(118%);
              backdrop-filter: blur(22px) saturate(118%);
            }
            html.dark main .rounded-bl-md {
              background: rgba(9,15,32,.58) !important;
              border-color: rgba(255,255,255,.075) !important;
              box-shadow: 0 8px 24px rgba(0,0,0,.12) !important;
              -webkit-backdrop-filter: blur(18px) saturate(112%);
              backdrop-filter: blur(18px) saturate(112%);
            }
            html.dark div.absolute.inset-x-0.bottom-0.z-30 {
              background: rgba(7,11,24,.28) !important;
              border-top-color: rgba(255,255,255,.035) !important;
              box-shadow: none !important;
              -webkit-backdrop-filter: blur(24px) saturate(120%);
              backdrop-filter: blur(24px) saturate(120%);
            }
            html.dark div.absolute.inset-x-0.bottom-0.z-30 > div {
              background: rgba(10,16,33,.42) !important;
              border-color: rgba(255,255,255,.10) !important;
              box-shadow: 0 8px 28px rgba(0,0,0,.10) !important;
            }
        """.trimIndent().replace("`", "\\`")
        val script = """
            (() => {
              const old = document.getElementById('furina-native-polish');
              if (old) old.remove();
              const style = document.createElement('style');
              style.id = 'furina-native-polish';
              style.textContent = `$css`;
              document.head.appendChild(style);
            })();
        """.trimIndent()
        view?.evaluateJavascript(script, null)
    }

    fun launchBackupFolderPicker() = folderPicker.launch(null)
    fun launchRestorePicker() = restorePicker.launch(arrayOf("application/octet-stream", "application/zip", "*/*"))

    fun requestDownloadNotificationPermission() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
            ContextCompat.checkSelfPermission(this, android.Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
        ) {
            notificationPermission.launch(android.Manifest.permission.POST_NOTIFICATIONS)
        }
    }

    fun applySystemTheme(dark: Boolean) {
        val color = if (dark) Color.rgb(5, 7, 18) else Color.rgb(248, 250, 252)
        webView.setBackgroundColor(color)
        window.statusBarColor = STATUS_BAR_COLOR
        window.navigationBarColor = NAVIGATION_BAR_COLOR
        WindowCompat.getInsetsController(window, webView).apply {
            isAppearanceLightStatusBars = false
            isAppearanceLightNavigationBars = false
        }
    }

    private fun isTrustedAppUri(uri: Uri): Boolean =
        uri.scheme.equals("https", ignoreCase = true) && uri.host.equals(APP_HOST, ignoreCase = true)

    private fun showLoadError(message: String) {
        Toast.makeText(this, message, Toast.LENGTH_LONG).show()
        val html = """
            <!doctype html><html lang="id"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
            <style>body{margin:0;min-height:100vh;display:grid;place-items:center;background:#050712;color:#fff;font-family:system-ui;padding:24px;box-sizing:border-box}.card{max-width:360px;text-align:center;background:#0c1022;border:1px solid #26304d;border-radius:20px;padding:24px}h1{font-size:22px;margin:0 0 10px}p{color:#b8c2d9;line-height:1.55}button{min-height:48px;border:0;border-radius:14px;padding:0 22px;background:#38bdf8;color:#03111b;font-weight:700}</style>
            <body><main class="card"><h1>Furina belum bisa dibuka</h1><p>${message.replace("<", "&lt;")}</p><button onclick="location.href='$APP_URL'">Coba lagi</button></main></body></html>
        """.trimIndent()
        webView.loadDataWithBaseURL(APP_URL, html, "text/html", "UTF-8", null)
    }

    private fun dp(value: Int): Int = (value * resources.displayMetrics.density).toInt()

    override fun onSaveInstanceState(outState: Bundle) {
        webView.saveState(outState)
        super.onSaveInstanceState(outState)
    }

    override fun onDestroy() {
        // Stop cloud/evidence jobs first because FurinaBridge owns the shared MemoryStore lifecycle.
        cloudBridge.destroy()
        evidenceBridge.destroy()
        bridge.destroy()
        webView.removeJavascriptInterface("FurinaNative")
        webView.removeJavascriptInterface("FurinaCloud")
        webView.removeJavascriptInterface("FurinaEvidence")
        webView.destroy()
        super.onDestroy()
    }

    companion object {
        private const val APP_HOST = "furina-pi.vercel.app"
        private const val APP_URL = "https://furina-pi.vercel.app/native"
        private const val AUTH_SCHEME = "com.wynndev.furina"
        private const val MIN_LOADING_MS = 720L
        private val SAFE_EXTERNAL_SCHEMES = setOf("https", "http", "mailto", "tel")
        private val STATUS_BAR_COLOR = Color.rgb(45, 45, 45)
        private val NAVIGATION_BAR_COLOR = Color.rgb(213, 213, 213)
    }
}
