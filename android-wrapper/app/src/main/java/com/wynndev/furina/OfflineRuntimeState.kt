package com.wynndev.furina

/** Exact durable message count used to validate local llama.cpp session checkpoints. */
internal fun MemoryStore.messageCountForSession(sessionId: String): Int = synchronized(this) {
    readableDatabase.rawQuery(
        "SELECT COUNT(*) FROM messages WHERE session_id=?",
        arrayOf(sessionId),
    ).use { cursor ->
        if (cursor.moveToFirst()) cursor.getInt(0) else 0
    }
}
