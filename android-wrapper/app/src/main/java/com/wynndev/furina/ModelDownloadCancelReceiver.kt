package com.wynndev.furina

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

class ModelDownloadCancelReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != ACTION_CANCEL) return
        val model = ModelCatalog.byId(intent.getStringExtra(EXTRA_MODEL_ID)) ?: return
        ModelDownloadManager(context.applicationContext).cancel(model)
    }

    companion object {
        const val ACTION_CANCEL = "com.wynndev.furina.CANCEL_MODEL_DOWNLOAD"
        const val EXTRA_MODEL_ID = "model_id"
    }
}
