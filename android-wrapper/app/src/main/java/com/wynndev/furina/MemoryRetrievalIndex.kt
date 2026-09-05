/*
 * Adapted from LianYu MemoryIndex.kt / MemoryTokenizer.kt, Apache-2.0.
 * Copyright 2026 Sylvara-Lin and LianYu contributors.
 * Modified for FurinaHub: Indonesian/Unicode tokenization, deterministic ranking,
 * immutable snapshot rebuild, negation preservation, no popularity reinforcement.
 * See assets/licenses/LIANYU-LICENSE.txt and LIANYU-NOTICE.txt.
 */
package com.wynndev.furina

import java.util.Locale

internal object MemoryTerms {
    private val stopWords = setOf("aku", "saya", "kamu", "kau", "yang", "dan", "atau", "itu", "ini", "dengan", "untuk", "dari", "pada", "adalah", "the", "and", "your", "this", "that")

    fun tokenize(text: String): Set<String> = text.lowercase(Locale.ROOT)
        .split(Regex("[^\\p{L}\\p{N}]+"))
        .map(String::trim).filter { it.length >= 2 && it !in stopWords }.toSet()

    fun similarity(a: String, b: String): Float {
        val left = tokenize(a)
        val right = tokenize(b)
        if (left.isEmpty() || right.isEmpty()) return 0f
        return left.intersect(right).size.toFloat() / left.union(right).size
    }
}

internal data class IndexedMemory(val id: String, val content: String, val importance: Int, val updatedAt: Long, val core: Boolean)

/** Owned by MemoryStore; rebuilt from SQLite only when the database changes. */
internal class MemoryRetrievalIndex(items: List<IndexedMemory>) {
    private val rows = items.associateBy { it.id }
    private val keywordToIds = mutableMapOf<String, MutableSet<String>>()
    private val coreIds = items.filter { it.core }.map { it.id }.toSet()

    init {
        items.forEach { item -> MemoryTerms.tokenize(item.content).forEach { token ->
            keywordToIds.getOrPut(token) { mutableSetOf() }.add(item.id)
        } }
    }

    fun search(query: String, limit: Int): List<String> {
        if (limit <= 0) return emptyList()
        val scores = mutableMapOf<String, Int>()
        coreIds.forEach { scores[it] = 14 }
        MemoryTerms.tokenize(query).forEach { token ->
            keywordToIds[token]?.forEach { id -> scores[id] = (scores[id] ?: 0) + 20 }
        }
        return scores.keys.mapNotNull(rows::get)
            .sortedWith(compareByDescending<IndexedMemory> { (scores[it.id] ?: 0) + it.importance }
                .thenByDescending { it.updatedAt }.thenBy { it.id })
            .distinctBy { it.content.lowercase(Locale.ROOT) }.take(limit).map { it.content }
    }
}
