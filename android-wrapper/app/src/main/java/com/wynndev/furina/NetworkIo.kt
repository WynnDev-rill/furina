package com.wynndev.furina

import java.net.HttpURLConnection
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.launch

/** Disconnect the socket when the owning coroutine stops, including a blocked stream read. */
internal suspend fun <T> HttpURLConnection.cancellableRead(block: suspend () -> T): T = coroutineScope {
    val watcher = launch(start = CoroutineStart.UNDISPATCHED) {
        try { awaitCancellation() } finally { disconnect() }
    }
    try { block() } finally { watcher.cancel(); disconnect() }
}
