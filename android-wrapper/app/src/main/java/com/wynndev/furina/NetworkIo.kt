package com.wynndev.furina

import java.net.HttpURLConnection
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.launch

/** Disconnect the socket when the owning coroutine stops, including a blocked stream read. */
internal suspend fun <T> HttpURLConnection.cancellableRead(block: suspend () -> T): T = coroutineScope {
    val watcher = launch(start = CoroutineStart.UNDISPATCHED) {
        try { awaitCancellation() } finally { disconnect() }
    }
    try { block() }
    catch (error: Exception) {
        // Closing a blocked socket during Stop can surface as IOException. Preserve the
        // owning coroutine's cancellation instead of displaying a transport failure.
        currentCoroutineContext().ensureActive()
        throw error
    } finally { watcher.cancel(); disconnect() }
}
