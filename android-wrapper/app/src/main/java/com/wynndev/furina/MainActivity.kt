package com.wynndev.furina

import android.content.Intent
import android.graphics.Color
import android.net.Uri
import android.os.Bundle
import android.webkit.WebResourceRequest
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.activity.ComponentActivity
import androidx.activity.OnBackPressedCallback
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.view.WindowCompat

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
        WindowCompat.setDecorFitsSystemWindows(window, true)
        window.statusBarColor = Color.rgb(5, 7, 18)
        window.navigationBarColor = Color.rgb(5, 7, 18)

        webView = WebView(this).apply {
            setBackgroundColor(Color.rgb(5, 7, 18))
            settings.javaScriptEnabled = true
            settings.domStorageEnabled = true
            settings.databaseEnabled = true
            settings.cacheMode = WebSettings.LOAD_DEFAULT
            settings.allowFileAccess = false
            settings.allowContentAccess = false
            settings.mediaPlaybackRequiresUserGesture = false
            settings.mixedContentMode = WebSettings.MIXED_CONTENT_NEVER_ALLOW
            settings.userAgentString = settings.userAgentString + " FurinaAndroid/4.0"
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
