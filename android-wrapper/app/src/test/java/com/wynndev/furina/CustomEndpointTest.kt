package com.wynndev.furina

import org.junit.Assert.*
import org.junit.Test

class CustomEndpointTest {
    @Test fun normalizesTlsAndDeviceLocalEndpoints() {
        assertEquals("https://example.com/v1", CustomEndpoint.normalize(" https://example.com/v1/ "))
        assertEquals("http://127.0.0.1:8080/v1", CustomEndpoint.normalize("http://127.0.0.1:8080/v1"))
    }
    @Test fun rejectsRemoteCleartextCredentialsAndAmbiguousUrls() {
        listOf("http://example.com/v1", "http://127.0.0.1.example.com/v1", "https://secret@example.com/v1",
            "https://example.com/v1?key=secret", "file:///private/model", "https://example.com/v1#other",
            "http://127.0.0.1:99999/v1").forEach { raw ->
            assertTrue(raw, runCatching { CustomEndpoint.normalize(raw) }.isFailure)
        }
    }
}
