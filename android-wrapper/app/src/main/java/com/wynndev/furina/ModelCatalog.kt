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
    // Release catalog: lightweight 1.7B local companion models.
    // Retired migration marker for the current release gate: Qwen3.5 4B Deckard Heretic
    private const val WIFU_HF_REVISION = "8e9d8eb2c95e5f917af75f2e4c23c019ddb4798e"
    private const val HERETIC_HF_REVISION = "e2716dd20c87c9bf221059b942be6d33cbf4d647"

    val models = listOf(
        ModelSpec(
            id = "wifugpt-1.7b-q4km",
            displayName = "wifuGPT 1.7B",
            subtitle = "Uncensored · companion & roleplay · Q4_K_M",
            fileName = "wifuGPT-1.7B-Q4_K_M.gguf",
            downloadUrl = "https://huggingface.co/backpropSukuna/wifuGPT-1.7B-GGUF/resolve/$WIFU_HF_REVISION/wifuGPT-1.7B-Q4_K_M.gguf?download=true",
            expectedBytes = 1_107_408_480L,
            sha256 = "d256ccbab62bbd80064ecb73be0512b0b8d16bc930d5ae9ac8079216b88b2b54",
            recommended = true,
        ),
        ModelSpec(
            id = "qwen3-1.7b-heretic-q5km",
            displayName = "Qwen3 1.7B Heretic",
            subtitle = "Uncensored · natural companion · Q5_K_M",
            fileName = "Qwen3-1.7B-heretic.i1-Q5_K_M.gguf",
            downloadUrl = "https://huggingface.co/mradermacher/Qwen3-1.7B-heretic-i1-GGUF/resolve/$HERETIC_HF_REVISION/Qwen3-1.7B-heretic.i1-Q5_K_M.gguf?download=true",
            expectedBytes = 1_257_880_480L,
            sha256 = "f2b0b5f7fead5fdcfb79f783b96465fe97f56361b11e8de972afd71b9ba994a2",
            recommended = false,
        ),
    )

    fun byId(id: String?): ModelSpec? = models.firstOrNull { it.id == id }
}
