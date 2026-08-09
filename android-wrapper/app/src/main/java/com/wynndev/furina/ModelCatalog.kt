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
    val models = listOf(
        ModelSpec(
            id = "qwen35-4b-uncensored-q4km",
            displayName = "Qwen3.5 4B Uncensored",
            subtitle = "Q4_K_M · cepat · rekomendasi harian",
            fileName = "Qwen3.5-4B-Uncensored-HauhauCS-Aggressive-Q4_K_M.gguf",
            downloadUrl = "https://huggingface.co/HauhauCS/Qwen3.5-4B-Uncensored-HauhauCS-Aggressive/resolve/55e05aba5a4e1e2d6c4919753a68941c4ad4cb11/Qwen3.5-4B-Uncensored-HauhauCS-Aggressive-Q4_K_M.gguf?download=true",
            expectedBytes = 2_707_513_696L,
            sha256 = "79e28ecacf84e75b6056cf4059636d435aa9eb67795780f7b7dbc7d32a962741",
            recommended = true,
        ),
        ModelSpec(
            id = "qwen35-9b-uncensored-q4km",
            displayName = "Qwen3.5 9B Uncensored",
            subtitle = "Q4_K_M · kualitas lebih tinggi · lebih berat",
            fileName = "Qwen3.5-9B-Uncensored-HauhauCS-Aggressive-Q4_K_M.gguf",
            downloadUrl = "https://huggingface.co/HauhauCS/Qwen3.5-9B-Uncensored-HauhauCS-Aggressive/resolve/a5ebf434dfbf9646d1bb97a469c1d8f69e4feb2e/Qwen3.5-9B-Uncensored-HauhauCS-Aggressive-Q4_K_M.gguf?download=true",
            expectedBytes = 5_627_044_224L,
            sha256 = "2ca636d9e81d3d23ca9b60c234fe185d30ec082eeba69ce770fdb0c76559a4f5",
            recommended = false,
        ),
    )

    fun byId(id: String?): ModelSpec? = models.firstOrNull { it.id == id }
}
