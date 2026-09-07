package com.wynndev.furina

import org.junit.Assert.*
import org.junit.Test

class MemoryRetrievalIndexTest {
    @Test fun unicodeAndNegationSurviveTokenization() {
        val terms = MemoryTerms.tokenize("Aku TIDAK suka kopi; café 日本語")
        assertTrue(terms.containsAll(listOf("tidak", "kopi", "café", "日本語")))
        assertFalse(terms.contains("aku"))
    }

    @Test fun retrievalFindsRelevantFactsBeyondOldThreeHundredRowLimit() {
        val rows = (1..500).map { IndexedMemory("$it", "catatan $it", 5, it.toLong(), false) } +
            IndexedMemory("old", "Alergi udang", 8, 0, false)
        assertEquals(listOf("Alergi udang"), MemoryRetrievalIndex(rows).search("Apakah ada alergi?", 6))
    }

    @Test fun exactTermsAvoidSubstringMatchesAndKeepCoreProfile() {
        val index = MemoryRetrievalIndex(listOf(
            IndexedMemory("a", "Nama Wynn", 9, 1, true),
            IndexedMemory("b", "Menyukai mikroskop", 8, 2, false),
            IndexedMemory("c", "Tidak suka kopi", 8, 3, false),
        ))
        assertEquals(listOf("Tidak suka kopi", "Nama Wynn"), index.search("kopi", 5))
        assertEquals(listOf("Nama Wynn"), index.search("cuaca", 5))
        assertTrue(index.search("kopi", 0).isEmpty())
    }

    @Test fun duplicateFactsDoNotConsumeTheWholeContext() {
        val index = MemoryRetrievalIndex(listOf(
            IndexedMemory("a", "Kopi hitam", 8, 1, false),
            IndexedMemory("b", "KOPI HITAM", 8, 2, false),
            IndexedMemory("c", "Kopi pahit", 8, 3, false),
        ))
        assertEquals(2, index.search("kopi", 10).size)
    }
}
