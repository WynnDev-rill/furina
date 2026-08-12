package com.wynndev.furina

import android.app.Activity
import android.content.Intent
import android.net.Uri
import android.os.Bundle

/**
 * Verified HTTPS OAuth callback entry point. The public callback never exposes a custom URI
 * scheme; after Android verifies the owned domain, this activity forwards the payload to
 * MainActivity through an explicit in-app intent only.
 */
class AuthCallbackActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        forward(intent?.data)
    }

    override fun onNewIntent(intent: Intent?) {
        super.onNewIntent(intent)
        forward(intent?.data)
    }

    private fun forward(uri: Uri?) {
        if (uri == null ||
            uri.scheme != "https" ||
            !uri.host.equals(TRUSTED_HOST, ignoreCase = true) ||
            uri.path != TRUSTED_PATH ||
            uri.getQueryParameter("native") != "1"
        ) {
            finish()
            return
        }

        val internal = Uri.Builder()
            .scheme("com.wynndev.furina")
            .authority("auth")
            .path("callback")
        uri.queryParameterNames.forEach { key ->
            if (key != "native") uri.getQueryParameters(key).forEach { value -> internal.appendQueryParameter(key, value) }
        }

        startActivity(Intent(this, MainActivity::class.java).apply {
            action = Intent.ACTION_VIEW
            data = internal.build()
            addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP)
        })
        finish()
    }

    companion object {
        private const val TRUSTED_HOST = "furina-pi.vercel.app"
        private const val TRUSTED_PATH = "/backup-auth"
    }
}
