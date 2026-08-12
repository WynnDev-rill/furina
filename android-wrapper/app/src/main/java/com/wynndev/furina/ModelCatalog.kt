package com.wynndev.furina

data class ModelSpec(
    val id: String,
    val displayName: String,
    val subtitle: String,
    val fileName: String,
    val downloadUrl: String,
    val expectedBytes: Long,
    val sha256: String,
    val recommended: Boolean,
)

object ModelCatalog {
    private const val DECKARD_HF_REVISION = "e9cf779"

    val models = listOf(
        ModelSpec(
            id = "qwen35-4b-deckard-heretic-q4km",
            displayName = "Qwen3.5 4B Deckard Heretic",
            subtitle = "Uncensored · natural companion · Q4_K_M",
            fileName = "Qwen3.5-4B-Deckard-HERETIC-UNCENSORED-Thinking.i1-Q4_K_M.gguf",
            downloadUrl = "https://huggingface.co/mradermacher/Qwen3.5-4B-Deckard-HERETIC-UNCENSORED-Thinking-i1-GGUF/resolve/$DECKARD_HF_REVISION/Qwen3.5-4B-Deckard-HERETIC-UNCENSORED-Thinking.i1-Q4_K_M.gguf?download=true",
            expectedBytes = 2_708_805_792L,
            sha256 = "dda8f686b793f189a84c854832bb8b4db59c381a60275a567513d5ebb4d92906",
            recommended = true,
        ),
    )

    fun byId(id: String?): ModelSpec? = models.firstOrNull { it.id == id }
}
