package com.wynndev.furina

import android.content.Intent
import android.graphics.Color
import android.net.Uri
import android.os.Bundle
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.OnBackPressedCallback
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.view.WindowCompat
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat

class MainActivity : ComponentActivity() {
    private lateinit var webView: WebView
    private lateinit var bridge: FurinaBridge

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

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        WindowCompat.setDecorFitsSystemWindows(window, false)
        window.statusBarColor = Color.TRANSPARENT
        window.navigationBarColor = Color.TRANSPARENT
        window.isStatusBarContrastEnforced = false
        window.isNavigationBarContrastEnforced = false

        webView = WebView(this).apply {
            setBackgroundColor(Color.rgb(5, 7, 18))
            settings.javaScriptEnabled = true
            settings.domStorageEnabled = true
            settings.cacheMode = WebSettings.LOAD_DEFAULT
            settings.allowFileAccess = false
            settings.allowContentAccess = false
            settings.mediaPlaybackRequiresUserGesture = false
            settings.mixedContentMode = WebSettings.MIXED_CONTENT_NEVER_ALLOW
            settings.safeBrowsingEnabled = true
            settings.userAgentString = settings.userAgentString + " FurinaAndroid/4.0"
        }
        applySystemTheme(true)
        WebView.setWebContentsDebuggingEnabled(false)
        ViewCompat.setOnApplyWindowInsetsListener(webView) { view, insets ->
            val bars = insets.getInsets(WindowInsetsCompat.Type.systemBars())
            view.setPadding(bars.left, bars.top, bars.right, bars.bottom)
            insets
        }

        val store = MemoryStore(this)
        val modelDownloads = ModelDownloadManager(this)
        val backupManager = BackupManager(this, store)
        bridge = FurinaBridge(this, webView, store, modelDownloads, backupManager)
        webView.addJavascriptInterface(bridge, "FurinaNative")

        webView.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(view: WebView?, request: WebResourceRequest?): Boolean {
                val uri = request?.url ?: return false
                if (uri.scheme == "https" && uri.host == APP_HOST) return false
                return try {
                    startActivity(Intent(Intent.ACTION_VIEW, uri))
                    true
                } catch (_: Throwable) { true }
            }

            override fun onPageFinished(view: WebView?, url: String?) {
                bridge.notifyNativeReady()
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

        setContentView(webView)
        if (savedInstanceState == null || webView.restoreState(savedInstanceState) == null) {
            webView.loadUrl(APP_URL)
        }

        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                if (webView.canGoBack()) webView.goBack() else finish()
            }
        })
    }

    fun launchBackupFolderPicker() = folderPicker.launch(null)
    fun launchRestorePicker() = restorePicker.launch(arrayOf("application/octet-stream", "application/zip", "*/*"))

    fun applySystemTheme(dark: Boolean) {
        val color = if (dark) Color.rgb(5, 7, 18) else Color.rgb(248, 250, 252)
        webView.setBackgroundColor(color)
        WindowCompat.getInsetsController(window, webView).apply {
            isAppearanceLightStatusBars = !dark
            isAppearanceLightNavigationBars = !dark
        }
    }

    private fun showLoadError(message: String) {
        Toast.makeText(this, message, Toast.LENGTH_LONG).show()
        val html = """
            <!doctype html><html lang="id"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
            <style>body{margin:0;min-height:100vh;display:grid;place-items:center;background:#050712;color:#fff;font-family:system-ui;padding:24px;box-sizing:border-box}.card{max-width:360px;text-align:center;background:#0c1022;border:1px solid #26304d;border-radius:20px;padding:24px}h1{font-size:22px;margin:0 0 10px}p{color:#b8c2d9;line-height:1.55}button{min-height:48px;border:0;border-radius:14px;padding:0 22px;background:#38bdf8;color:#03111b;font-weight:700}</style>
            <body><main class="card"><h1>Furina belum bisa dibuka</h1><p>${message.replace("<", "&lt;")}</p><button onclick="location.href='$APP_URL'">Coba lagi</button></main></body></html>
        """.trimIndent()
        webView.loadDataWithBaseURL(APP_URL, html, "text/html", "UTF-8", null)
    }

    override fun onSaveInstanceState(outState: Bundle) {
        webView.saveState(outState)
        super.onSaveInstanceState(outState)
    }

    override fun onDestroy() {
        bridge.destroy()
        webView.removeJavascriptInterface("FurinaNative")
        webView.destroy()
        super.onDestroy()
    }

    companion object {
        private const val APP_HOST = "furina-pi.vercel.app"
        private const val APP_URL = "https://furina-pi.vercel.app/native"
    }
}
