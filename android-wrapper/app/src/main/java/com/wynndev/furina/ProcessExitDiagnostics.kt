package com.wynndev.furina

import android.app.ActivityManager
import android.app.ApplicationExitInfo
import android.content.Context
import android.os.Build
import org.json.JSONObject

object ProcessExitDiagnostics {
    private const val PREFS = "furina_process_exit"
    private const val CONSUMED_TS = "consumed_timestamp"
    private const val RECENT_WINDOW_MS = 6L * 60L * 60L * 1000L
    private const val STAGE_PREFIX = "furina:"

    data class Snapshot(
        val reason: Int,
        val reasonName: String,
        val status: Int,
        val pssKb: Long,
        val rssKb: Long,
        val timestamp: Long,
        val stage: String,
        val description: String,
    ) {
        fun humanSummary(): String {
            val memory = buildString {
                if (rssKb > 0L) append("RSS ${rssKb / 1024} MB")
                if (pssKb > 0L) {
                    if (isNotEmpty()) append(" · ")
                    append("PSS ${pssKb / 1024} MB")
                }
            }
            return buildString {
                append("Crash sebelumnya terdeteksi: ").append(reasonName)
                if (status != 0) append(" (status/signal ").append(status).append(')')
                if (stage.isNotBlank()) append(" · tahap ").append(stage)
                if (memory.isNotBlank()) append(" · ").append(memory)
                if (description.isNotBlank()) append(" · ").append(description.take(220))
            }
        }
    }

    fun mark(context: Context, stage: String) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.R) return

        // On the first prepare attempt after a hard process death, surface Android's
        // historical exit reason instead of immediately entering the same crash loop.
        // The timestamp is consumed once, so reopening Furina proceeds on the next attempt.
        if (stage == "offline-verify") {
            consumeHumanSummary(context)?.let { summary ->
                throw IllegalStateException("$summary. Tutup lalu buka Furina sekali lagi untuk mencoba profil pemulihan.")
            }
        }

        runCatching {
            val manager = context.getSystemService(Context.ACTIVITY_SERVICE) as ActivityManager
            manager.setProcessStateSummary((STAGE_PREFIX + stage).take(120).toByteArray(Charsets.UTF_8))
        }
    }

    fun latestDangerous(context: Context): Snapshot? {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.R) return null
        val manager = context.getSystemService(Context.ACTIVITY_SERVICE) as ActivityManager
        val now = System.currentTimeMillis()
        val mainProcess = context.applicationInfo.processName
        val exits = runCatching { manager.getHistoricalProcessExitReasons(null, 0, 16) }.getOrDefault(emptyList())

        // WebView/Chromium renderer processes belong to the same package and may carry
        // binary process-state summaries. Only the APK's main process is relevant to
        // llama.cpp and only Furina-prefixed summaries are rendered as diagnostic stages.
        val exit = exits
            .filter { it.processName == mainProcess }
            .sortedByDescending { it.timestamp }
            .firstOrNull {
                now - it.timestamp in 0..RECENT_WINDOW_MS && isDangerousReason(it.reason)
            } ?: return null

        val rawSummary = runCatching {
            exit.processStateSummary?.toString(Charsets.UTF_8).orEmpty()
        }.getOrDefault("")
        val stage = rawSummary
            .takeIf { it.startsWith(STAGE_PREFIX) }
            ?.removePrefix(STAGE_PREFIX)
            ?.take(120)
            .orEmpty()

        return Snapshot(
            reason = exit.reason,
            reasonName = reasonName(exit.reason),
            status = exit.status,
            pssKb = exit.pss,
            rssKb = exit.rss,
            timestamp = exit.timestamp,
            stage = stage,
            description = exit.description.orEmpty(),
        )
    }

    fun shouldForceRecoveryProfile(context: Context): Boolean = latestDangerous(context) != null

    fun consumeHumanSummary(context: Context): String? {
        val snapshot = latestDangerous(context) ?: return null
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        if (prefs.getLong(CONSUMED_TS, 0L) >= snapshot.timestamp) return null
        prefs.edit().putLong(CONSUMED_TS, snapshot.timestamp).apply()
        return snapshot.humanSummary()
    }

    fun json(context: Context): JSONObject {
        val snapshot = latestDangerous(context) ?: return JSONObject().put("available", false)
        return JSONObject()
            .put("available", true)
            .put("reason", snapshot.reason)
            .put("reasonName", snapshot.reasonName)
            .put("status", snapshot.status)
            .put("pssKb", snapshot.pssKb)
            .put("rssKb", snapshot.rssKb)
            .put("timestamp", snapshot.timestamp)
            .put("stage", snapshot.stage)
            .put("description", snapshot.description)
    }

    private fun isDangerousReason(reason: Int): Boolean = reason == ApplicationExitInfo.REASON_CRASH ||
        reason == ApplicationExitInfo.REASON_CRASH_NATIVE ||
        reason == ApplicationExitInfo.REASON_LOW_MEMORY ||
        reason == ApplicationExitInfo.REASON_SIGNALED ||
        reason == ApplicationExitInfo.REASON_EXCESSIVE_RESOURCE_USAGE

    private fun reasonName(reason: Int): String = when (reason) {
        ApplicationExitInfo.REASON_CRASH -> "Java crash"
        ApplicationExitInfo.REASON_CRASH_NATIVE -> "native crash"
        ApplicationExitInfo.REASON_LOW_MEMORY -> "low-memory kill"
        ApplicationExitInfo.REASON_SIGNALED -> "OS signal"
        ApplicationExitInfo.REASON_EXCESSIVE_RESOURCE_USAGE -> "excessive resource usage"
        ApplicationExitInfo.REASON_ANR -> "ANR"
        else -> "reason-$reason"
    }
}
