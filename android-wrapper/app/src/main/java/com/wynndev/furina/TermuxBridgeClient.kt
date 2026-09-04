package com.wynndev.furina

import android.app.Activity
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.util.Base64
import java.net.HttpURLConnection
import java.net.URL
import java.security.SecureRandom
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import org.json.JSONObject

/** Token-authenticated localhost bridge to the Furina Core installed in Termux. */
class TermuxBridgeClient(context: Context) {
    private val appContext = context.applicationContext
    private val prefs = appContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    var token: String
        get() = prefs.getString(KEY_TOKEN, "").orEmpty()
        private set(value) { prefs.edit().putString(KEY_TOKEN, value).apply() }

    fun isTermuxInstalled(): Boolean = try {
        appContext.packageManager.getPackageInfo(TERMUX_PACKAGE, 0)
        true
    } catch (_: PackageManager.NameNotFoundException) {
        false
    }

    fun hasRunCommandPermission(): Boolean =
        Build.VERSION.SDK_INT < Build.VERSION_CODES.M ||
            appContext.checkSelfPermission(RUN_COMMAND_PERMISSION) == PackageManager.PERMISSION_GRANTED

    /**
     * Starts Core with an app-owned token. Importing the module before calling main is deliberate:
     * Core 1.1.31 applies its latest compatibility overrides at the end of module import.
     */
    fun startCore(activity: Activity): String {
        check(isTermuxInstalled()) { "Termux belum terpasang" }
        check(hasRunCommandPermission()) { "Izin RUN_COMMAND Termux belum diberikan" }
        val nextToken = ByteArray(36).also(SecureRandom()::nextBytes)
            .let { Base64.encodeToString(it, Base64.NO_WRAP or Base64.URL_SAFE).trimEnd('=') }
        val intent = Intent(ACTION_RUN_COMMAND).apply {
            component = ComponentName(TERMUX_PACKAGE, TERMUX_RUN_SERVICE)
            putExtra(EXTRA_COMMAND_PATH, TERMUX_BASH)
            putExtra(
                EXTRA_ARGUMENTS,
                arrayOf(
                    "-lc",
                    "ROOT=\"\$HOME/.furina-agent\"; export FURINA_HOME=\"\$ROOT\"; export PYTHONPATH=\"\$ROOT/core\${PYTHONPATH:+:\$PYTHONPATH}\"; exec python -c 'import furina_agent.hub as hub; hub.main()' --replace --token \"\$1\"",
                    "furinahub-native",
                    nextToken,
                ),
            )
            putExtra(EXTRA_WORKDIR, TERMUX_HOME)
            putExtra(EXTRA_BACKGROUND, true)
            putExtra(EXTRA_COMMAND_LABEL, "FurinaHub Core")
            putExtra(EXTRA_COMMAND_DESCRIPTION, "Menjalankan Furina Core lokal untuk FurinaHub.")
        }
        activity.startService(intent)
        token = nextToken
        return nextToken
    }

    suspend fun waitUntilHealthy(candidate: String = token, timeoutMs: Long = 35_000L): JSONObject {
        val deadline = System.currentTimeMillis() + timeoutMs
        var lastError: Throwable? = null
        while (System.currentTimeMillis() < deadline) {
            try {
                val health = health(candidate)
                token = candidate
                return health
            } catch (error: Throwable) {
                lastError = error
                delay(650L)
            }
        }
        throw IllegalStateException(lastError?.message ?: "Furina Core belum merespons")
    }

    suspend fun health(candidate: String = token): JSONObject = withContext(Dispatchers.IO) {
        require(candidate.length >= 24) { "Token Core belum tersedia" }
        requestRaw("GET", "/health?access=${candidate}", null, candidate, api = false)
    }

    suspend fun get(path: String): JSONObject = withContext(Dispatchers.IO) {
        requestRaw("GET", path, null, token, api = true)
    }

    suspend fun post(path: String, body: JSONObject = JSONObject()): JSONObject = withContext(Dispatchers.IO) {
        requestRaw("POST", path, body.toString(), token, api = true)
    }

    fun forget() {
        token = ""
    }

    private fun requestRaw(method: String, path: String, body: String?, authToken: String, api: Boolean): JSONObject {
        if (api) require(path.startsWith("/api/")) { "Endpoint Core tidak valid" }
        val connection = URL(BASE_URL + path.removePrefix("/")).openConnection() as HttpURLConnection
        return try {
            connection.requestMethod = method
            connection.connectTimeout = if (api) 2_500 else 900
            connection.readTimeout = if (api) 300_000 else 900
            connection.useCaches = false
            connection.setRequestProperty("Accept", "application/json")
            if (api) connection.setRequestProperty("X-FurinaHub-Token", authToken)
            if (body != null) {
                val data = body.toByteArray(Charsets.UTF_8)
                require(data.size <= 2_000_000) { "Request terlalu besar" }
                connection.doOutput = true
                connection.setRequestProperty("Content-Type", "application/json; charset=utf-8")
                connection.setFixedLengthStreamingMode(data.size)
                connection.outputStream.use { it.write(data) }
            }
            val status = connection.responseCode
            val stream = if (status in 200..299) connection.inputStream else connection.errorStream
            val raw = stream?.bufferedReader(Charsets.UTF_8)?.use { it.readText() }.orEmpty()
            val payload = runCatching { JSONObject(raw.ifBlank { "{}" }) }.getOrElse {
                JSONObject().put("error", raw.take(500).ifBlank { "HTTP $status" })
            }
            if (status !in 200..299) {
                throw CoreBridgeException(status, payload.optString("error", "HTTP $status"))
            }
            payload
        } finally {
            connection.disconnect()
        }
    }

    companion object {
        const val RUN_COMMAND_PERMISSION = "com.termux.permission.RUN_COMMAND"
        private const val PREFS = "furinahub_termux"
        private const val KEY_TOKEN = "hub_token"
        private const val BASE_URL = "http://127.0.0.1:8787/"
        private const val TERMUX_PACKAGE = "com.termux"
        private const val TERMUX_RUN_SERVICE = "com.termux.app.RunCommandService"
        private const val TERMUX_BASH = "/data/data/com.termux/files/usr/bin/bash"
        private const val TERMUX_HOME = "/data/data/com.termux/files/home"
        private const val ACTION_RUN_COMMAND = "com.termux.RUN_COMMAND"
        private const val EXTRA_COMMAND_PATH = "com.termux.RUN_COMMAND_PATH"
        private const val EXTRA_ARGUMENTS = "com.termux.RUN_COMMAND_ARGUMENTS"
        private const val EXTRA_WORKDIR = "com.termux.RUN_COMMAND_WORKDIR"
        private const val EXTRA_BACKGROUND = "com.termux.RUN_COMMAND_BACKGROUND"
        private const val EXTRA_COMMAND_LABEL = "com.termux.RUN_COMMAND_COMMAND_LABEL"
        private const val EXTRA_COMMAND_DESCRIPTION = "com.termux.RUN_COMMAND_COMMAND_DESCRIPTION"
    }
}

class CoreBridgeException(val status: Int, message: String) : IllegalStateException(message)
