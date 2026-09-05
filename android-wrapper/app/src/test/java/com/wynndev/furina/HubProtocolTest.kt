package com.wynndev.furina

import android.app.Application
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35], application = Application::class)
class HubProtocolTest {
    @Test fun modelCatalogAcceptsBothSchemasAndDeduplicates() {
        assertEquals(listOf("alpha", "beta", "gamma"), ProviderProtocol.parseModelIds("""{"data":[{"id":"alpha"},{"name":"beta"},{"model":"gamma"}," alpha ",null,{}]}"""))
        assertEquals(listOf("delta"), ProviderProtocol.parseModelIds("""{"models":["delta"]}"""))
        assertTrue(ProviderProtocol.parseModelIds("invalid").isEmpty())
    }

    @Test fun contentPartsNeverExposeReasoning() {
        val parts = JSONArray("""[{"type":"reasoning","text":"private"},{"type":"text","text":"Halo"},{"type":"image_url","url":"https://invalid.test"},{"type":"text","text":" Wynn"}]""")
        assertEquals("Halo Wynn", ProviderProtocol.contentText(parts))
        assertEquals("", ProviderProtocol.contentText(JSONObject.NULL))
    }

    @Test fun errorsSupportStringAndNestedSchemasWithoutEchoingKeysOnAuthFailure() {
        assertEquals("kapasitas habis", ProviderProtocol.errorMessage("Core", 503, """{"error":"kapasitas habis"}"""))
        assertEquals("coba lagi", ProviderProtocol.errorMessage("Core", 500, """{"error":{"message":"coba lagi"}}"""))
        assertFalse(ProviderProtocol.errorMessage("Core", 401, """{"error":"key=private"}""").contains("private"))
    }

    @Test fun partialPersonaUpdatesPreserveAbsentPreferencesButAcceptFalseAndEmptyTraits() {
        val original = HubPersona(name = "Nara", nickname = "Wynn", traits = setOf(FurinaTraits.first().id), partner = true, roleplay = true)
        val parsed = HubPersona.parse(JSONObject("""{"partner_mode":false,"personality_traits":[]}"""), original)
        assertEquals("Nara", parsed.name)
        assertEquals("Wynn", parsed.nickname)
        assertFalse(parsed.partner)
        assertTrue(parsed.roleplay)
        assertTrue(parsed.traits.isEmpty())
        assertEquals(original, HubPersona.parse(original.json()))
    }

    @Test fun remoteMessagesHaveStableIdsAndOnlyConversationRoles() {
        val rows = JSONArray("""[{"id":2,"role":"user","content":"Halo"},{"id":3,"role":"assistant","text":"Hai"},{"id":3,"role":"assistant","text":"duplikat"},{"id":4,"role":"system","content":"private"}]""").toMessages()
        assertEquals(listOf("2", "3"), rows.map { it.id })
        assertEquals(listOf("Halo", "Hai"), rows.map { it.content })
    }
}
