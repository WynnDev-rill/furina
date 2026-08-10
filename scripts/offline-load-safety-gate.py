#!/usr/bin/env python3
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"OFFLINE LOAD GATE FAILED: {message}")


def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        cpp = td_path / "ai_chat.cpp"
        kt = td_path / "InferenceEngineImpl.kt"
        shutil.copy2(ROOT / "scripts/overlays/ai_chat.cpp", cpp)
        shutil.copy2(ROOT / "scripts/overlays/InferenceEngineImpl.kt", kt)
        subprocess.run(
            ["python3", str(ROOT / "scripts/apply-companion-runtime-policy.py"), str(cpp), str(kt)],
            check=True,
            capture_output=True,
            text=True,
        )
        native = cpp.read_text(encoding="utf-8")
        kotlin = kt.read_text(encoding="utf-8")

    require("jboolean jlow_memory_mode" in native, "native load must receive Android RAM profile")
    require("g_low_memory_mode = (jlow_memory_mode == JNI_TRUE)" in native,
            "Android low-memory decision must control the native profile")
    require("model_params.use_extra_bufts = !g_low_memory_mode" in native,
            "weight repacking must be disabled under RAM pressure")
    require("ctx_params.n_ubatch = g_low_memory_mode ? 128 : UBATCH_SIZE" in native,
            "low-memory mode must reduce scratch micro-batch, not model quality")
    require("if (g_large_model)" in native and "ctx_params.type_k = GGML_TYPE_Q8_0" in native,
            "KV quantization must remain restricted to the large-model profile")
    require("g_large_model ? DEFAULT_CONTEXT_SIZE / 2 : DEFAULT_CONTEXT_SIZE" in native,
            "4B low-memory mode must retain the 4096-token context target")
    require("LLAMA_LOAD_MODE_MMAP" in native and "llama_supports_mmap()" in native,
            "multi-GB Android load must remain mmap-backed")
    require("retrying without mmap" not in native and "LLAMA_LOAD_MODE_NONE" not in native,
            "multi-GB Android load must never retry with a full-buffer non-mmap path")
    require("user_tokens.erase(user_tokens.begin(), user_tokens.begin() + skipped_tokens)" in native,
            "overflow handling must preserve the newest user message")
    require("private external fun load(modelPath: String, lowMemoryMode: Boolean): Int" in kotlin,
            "Kotlin/JNI adaptive load signatures must match")
    require("shouldUseLowMemoryMode" in kotlin and "ActivityManager.MemoryInfo" in kotlin,
            "Android available RAM must be measured before model load")
    require("(modelBytes * 2L) + (2L * gib)" in kotlin,
            "performance repacking requires explicit headroom for model/UI/context memory")
    require("load(pathToModel, lowMemoryMode)" in kotlin,
            "computed RAM profile must be passed into native model load")

    print("Furina offline load safety gate passed: adaptive mmap profile + 4K-quality-preserving low-peak mode")


if __name__ == "__main__":
    main()
