package com.wynndev.furina

import android.webkit.WebView

/**
 * WebView exposes destroy() but no public isDestroyed API. Keep the bridge's
 * lifecycle guard compile-safe by treating a detached, parentless WebView as
 * no longer usable for queued JavaScript callbacks.
 */
val WebView.isDestroyed: Boolean
    get() = !isAttachedToWindow && parent == null
