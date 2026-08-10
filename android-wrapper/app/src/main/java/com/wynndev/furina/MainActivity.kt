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
    private lateinit var loadingOverlay: View
    private var loadingStartedAt = 0L
    private var loadingDismissed = false
    private var pageReady = false
    private var pendingAuthCallback: String? = null

    private val folderPicker = registerForActivityResult(ActivityResultContracts.OpenDocumentTree()) { uri ->
        if (uri != null) {
            try { contentResolver.takePersistableUriPermission(uri, Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_GRANT_WRITE_URI_PERMISSION) } catch (_: Throwable) {}
            bridge.onBackupFolderSelected(uri)
        }
    }
    private val restorePicker = registerForActivityResult(ActivityResultContracts.OpenDocument()) { uri -> if (uri != null) bridge.onRestoreFileSelected(uri) }
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
            settings.userAgentString = settings.userAgentString + " FurinaAndroid/4.2"
        }
        applySystemTheme(true)
        WebView.setWebContentsDebuggingEnabled(false)

        val store = MemoryStore(this)
        val modelDownloads = ModelDownloadManager(this)
        val backupManager = BackupManager(this, store)
        bridge = FurinaBridge(this, webView, store, modelDownloads, backupManager)
        cloudBridge = CloudBackupBridge(this, webView, store, backupManager)
        webView.addJavascriptInterface(bridge, "FurinaNative")
        webView.addJavascriptInterface(cloudBridge, "FurinaCloud")

        webView.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(view: WebView?, request: WebResourceRequest?): Boolean {
                val uri = request?.url ?: return true
                if (isTrustedAppUri(uri)) return false
                if (uri.scheme?.lowercase() !in SAFE_EXTERNAL_SCHEMES) return true
                return try { startActivity(Intent(Intent.ACTION_VIEW, uri)); true } catch (_: Throwable) { true }
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
            override fun onReceivedHttpError(view: WebView?, request: WebResourceRequest?, response: WebResourceResponse?) {
                if (request?.isForMainFrame == true && (response?.statusCode ?: 0) >= 400) showLoadError("Server Furina mengembalikan ${response?.statusCode ?: "error"}.")
            }
            override fun onReceivedError(view: WebView?, request: WebResourceRequest?, error: android.webkit.WebResourceError?) {
                if (request?.isForMainFrame == true) showLoadError("Antarmuka Furina belum dapat dimuat. Periksa koneksi lalu coba lagi.")
            }
        }

        val root = FrameLayout(this)
        root.addView(webView, FrameLayout.LayoutParams(-1, -1))
        loadingOverlay = buildLoadingOverlay()
        root.addView(loadingOverlay, FrameLayout.LayoutParams(-1, -1))
        loadingStartedAt = SystemClock.elapsedRealtime()
        setContentView(root)

        handleAuthIntent(intent)
        if (savedInstanceState == null || webView.restoreState(savedInstanceState) == null) webView.loadUrl(APP_URL)
        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() { if (webView.canGoBack()) webView.goBack() else finish() }
        })
    }

    override fun onNewIntent(intent: Intent) { super.onNewIntent(intent); setIntent(intent); handleAuthIntent(intent) }

    private fun handleAuthIntent(intent: Intent?) {
        val uri = intent?.data ?: return
        if (!uri.scheme.equals(AUTH_SCHEME, true) || !uri.host.equals("auth", true) || uri.path?.startsWith("/callback") != true) return
        pendingAuthCallback = uri.toString()
        deliverPendingAuthCallback()
    }

    private fun deliverPendingAuthCallback() {
        if (!pageReady) return
        val raw = pendingAuthCallback ?: return
        pendingAuthCallback = null
        val quoted = JSONObject.quote(raw)
        longArrayOf(120L, 650L, 1500L).forEach { delay ->
            webView.postDelayed({ if (!webView.isDestroyed) webView.evaluateJavascript("window.__furinaCloudAuthCallback&&window.__furinaCloudAuthCallback($quoted)", null) }, delay)
        }
    }

    private fun buildLoadingOverlay(): View {
        val overlay = FrameLayout(this).apply { setBackgroundColor(Color.rgb(5, 7, 18)); isClickable = true }
        val box = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; gravity = Gravity.CENTER_HORIZONTAL; setPadding(dp(28), 0, dp(28), 0) }
        val title = TextView(this).apply { text = "Furina"; setTextColor(Color.WHITE); setTextSize(TypedValue.COMPLEX_UNIT_SP, 27f); typeface = Typeface.create("sans-serif-medium", Typeface.NORMAL); letterSpacing = .045f }
        val subtitle = TextView(this).apply { text = "Menyiapkan percakapanâ€¦"; setTextColor(Color.rgb(166,177,201)); setTextSize(TypedValue.COMPLEX_UNIT_SP, 12.5f) }
        val progress = ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal).apply { isIndeterminate = true; indeterminateTintList = ColorStateList.valueOf(Color.rgb(56,189,248)) }
        box.addView(title); box.addView(subtitle, LinearLayout.LayoutParams(-2,-2).apply { topMargin = dp(10) }); box.addView(progress, LinearLayout.LayoutParams(dp(172),dp(3)).apply { topMargin = dp(24) })
        overlay.addView(box, FrameLayout.LayoutParams(-2,-2,Gravity.CENTER))
        return overlay
    }

    private fun dismissLoadingOverlay() {
        if (loadingDismissed) return
        loadingDismissed = true
        val delay = (MIN_LOADING_MS - (SystemClock.elapsedRealtime() - loadingStartedAt)).coerceAtLeast(0L)
        loadingOverlay.postDelayed({
            if (isFinishing || isDestroyed) return@postDelayed
            webView.animate().alpha(1f).setDuration(280L).start()
            loadingOverlay.animate().alpha(0f).setDuration(340L).withEndAction { loadingOverlay.visibility = View.GONE }.start()
        }, delay)
    }

    private fun installNativeVisualPolish(view: WebView?) {
        val css = "html.dark header.absolute.inset-x-0.top-0{background:rgba(7,11,24,.44)!important;backdrop-filter:blur(22px)}html.dark main .rounded-bl-md{background:rgba(9,15,32,.58)!important}html.dašÈ]‹˜XœÛÛ]Kš[œÙ]^L˜›İÛKL‹LÌØ˜XÚÙÜ›İ[™œ™Ø˜JËLKŒ
HZ[\Ü[Ø˜XÚÙ›ÜYš[\˜›\Š
_H‚ˆšY]ÏË™]˜[X]R˜]˜\ØÜš\
Š

OOÛ]ÏYØİ[Y[™Ù][[Y[RY
	Ù\š[˜K[˜]]™K\Û\Ú	ÊNÚYŠÊ\Ëœ™[[İ™J
NÜÏYØİ[Y[˜Ü™X]Q[[Y[
	Üİ[IÊNÜËšYIÙ\š[˜K[˜]]™K\Û\Ú	ÎÜË^ÛÛ[IÒ”ÓÓ“Øš™Xİœ][İJÜÜÊ_NÙØİ[Y[šXY˜\[™Ú[
Ê_JJ
H‹[
BˆB‚ˆ[ˆ][˜Ú˜XÚİ\›Û\”XÚÙ\Š
HH›Û\”XÚÙ\‹›][˜Ú
[
Bˆ[ˆ][˜Ú™\İÜ™TXÚÙ\Š
HH™\İÜ™TXÚÙ\‹›][˜Ú
\œ˜^SÙŠ˜\XØ][Û‹ÛØİ]\İ™X[H‹˜\XØ][Û‹Şš\‹Š‹ÊˆŠJBˆ[ˆ™\]Y\İİÛ›ØY›İYšXØ][Û”\›Z\ÜÚ[ÛŠ
HÂˆYˆ
Z[•‘T”ÒSÓ‹”Ñ×ÒS•HZ[•‘T”ÒSÓ—ĞÓÑTË•TSRTÕH	‰ˆÛÛ^ÛÛ\]˜ÚXÚÔÙ[”\›Z\ÜÚ[ÛŠ\Ë[™›ÚY“X[šY™\İœ\›Z\ÜÚ[Û‹”ÔÕÓ“ÕQ’PĞUSÓ”ÊHOHXÚØYÙSX[˜YÙ\‹”T“RTÔÒSÓ—ÑÔS•Q
H›İYšXØ][Û”\›Z\ÜÚ[Û‹›][˜Ú
[™›ÚY“X[šY™\İœ\›Z\ÜÚ[Û‹”ÔÕÓ“ÕQ’PĞUSÓ”ÊBˆBˆ[ˆ\TŞ\İ[U[YJ\šÎˆ›ÛÛX[ŠHÂˆÙX•šY]ËœÙ]˜XÚÙÜ›İ[™ÛÛÜŠYˆ
\šÊHÛÛÜ‹œ™ØŠKËN
H[ÙHÛÛÜ‹œ™ØŠLLŠJBˆÚ[™İËœİ]\Ğ˜\ÛÛÜˆHÕUT×ĞT—ĞÓÓÔÈÚ[™İË›˜]šYØ][Û˜\ÛÛÜˆHU’QĞUSÓ—ĞT—ĞÓÓÔ‚ˆÚ[™İĞÛÛ\]™Ù][œÙ]ĞÛÛ›Û\ŠÚ[™İËÙX•šY]ÊK˜\HÈ\Ğ\X\˜[˜ÙSYÚİ]\Ğ˜\œÈH˜[ÙNÈ\Ğ\X\˜[˜ÙSYÚ˜]šYØ][Û˜\œÈH˜[ÙHBˆBˆš]˜]H[ˆ\Õ\İY\\šJ\šNˆ\šJNˆ›ÛÛX[ˆH\šKœØÚ[YK™\]X[ÊšÈ‹YJH	‰ˆ\šKšÜİ™\]X[ÊTÒÔÕYJBˆš]˜]H[ˆÚİÓØY\œ›ÜŠY\ÜØYÙNˆİš[™ÊHÈØ\İ›XZÙU^
\ËY\ÜØYÙKØ\İ“S‘ÕÓÓ‘ÊKœÚİÊ
HBˆš]˜]H[ˆ
˜[YNˆ[
HH
˜[YH
ˆ™\Ûİ\˜Ù\Ë™\Ü^SY]šXÜË™[œÚ]JKÒ[

Bˆİ™\œšYH[ˆÛ”Ø]™R[œİ[˜ÙTİ]Jİ]İ]Nˆ[™JHÈÙX•šY]ËœØ]™Tİ]Jİ]İ]JNÈİ\\‹›Û”Ø]™R[œİ[˜ÙTİ]Jİ]İ]JHBˆİ™\œšYH[ˆÛ‘\İ›ŞJ
HÂˆœšYÙK™\İ›ŞJ
NÈÛİYœšYÙK™\İ›ŞJ
NÈÙX•šY]Ëœ™[[İ™R˜]˜\ØÜš\[\™˜XÙJ‘\š[˜S˜]]™HŠNÈÙX•šY]Ëœ™[[İ™R˜]˜\ØÜš\[\™˜XÙJ‘\š[˜PÛİYŠNÈÙX•šY]Ë™\İ›ŞJ
NÈİ\\‹›Û‘\İ›ŞJ
BˆB‚ˆÛÛ\[š[ÛˆØš™XİÂˆš]˜]HÛÛœİ˜[TÒÔÕH™\š[˜K\K™\˜Ù[˜\‚ˆš]˜]HÛÛœİ˜[TÕT“HšÎ‹ËÙ\š[˜K\K™\˜Ù[˜\Û˜]]™H‚ˆš]˜]HÛÛœİ˜[UUÔĞÒSQHH˜ÛÛKŞ[›™]‹™\š[˜H‚ˆš]˜]HÛÛœİ˜[RS—ÓĞQS‘×ÓTÈHÌŒˆš]˜]H˜[ĞQ‘WÑVT“SÔĞÒSQTÈHÙ]ÙŠšÈ‹š‹›XZ[È‹[ŠBˆš]˜]H˜[ÕUT×ĞT—ĞÓÓÔˆHÛÛÜ‹œ™ØŠKKJBˆš]˜]H˜[U’QĞUSÓ—ĞT—ĞÓÓÔˆHÛÛÜ‹œ™ØŠŒLËŒLËŒLÊBˆBŸB