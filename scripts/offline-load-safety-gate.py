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
        for patch in ("apply-companion-runtime-policy.py", "apply-offline-stability-policy.py"):
            subprocess.run(
                ["python3", str(ROOT / "scripts" / patch), str(cpp), str(kt)],
                check=True,
                capture_output=True,
                text=True,
            )
        native = cpp.read_text(encoding="utf-8")
        kotlin = kt.read_text(encoding="utf-8")

    require("jboolean jlow_memory_mode" in native, "native load must receive Android RAM profile")
    require("g_low_memory_mode = (jlow_memory_mode == JNI_TRUE)" in native,
            "Android low-memory decision must control the native profile")
    require("model_params.use_extra_bufts = false" in native,
            "multi-GB Android runtime must not allocate optional packed-weight buffers")
    require("g_active_batch_size = g_low_memory_mode ? 128 : 256" in native,
            "low-peak mode must reduce prompt scratch batch without changing model weights")
    require("ctx_params.n_ubatch = g_low_memory_mode ? 64 : 128" in native,
            "low-peak mode must reduce physical micro-batch scratch")
    require("if (g_large_model)" in native and "ctx_params.type_k = GGML_TYPE_Q8_0" in native,
            "KV quantization must remain restricted to the genuinely large-model profile")
    require("g_large_model ? DEFAULT_CONTEXT_SIZE / 2 : DEFAULT_CONTEXT_SIZE" in native,
            "4B low-peak mode must retain the 4096-token target context")
    require("LLAMA_LOAD_MODE_MMAP" in native and "llama_supports_mmap()" in native,
            "multi-GB Android load must remain mmap-backed")
    require("retrying without mmap" not in native and "model_params.load_mode = LLAMA_LOAD_MODE_NONE;" not in native,
            "multi-GB Android load must never retry with a full-buffer non-mmap path")
    require("user_tokens.erase(user_tokens.begin(), user_tokens.begin() + skipped_tokens)" in native,
            "overflow handling must preserve the newest user message")

    require("private external fun load(modelPath: String, lowMemoryMode: Boolean): Int" in kotlin,
            "Kotlin/JNI adaptive load signatures must match")
    require("ActivityManager.MemoryInfo" in kotlin and "multiGigabyteModel" in kotlin,
            "multi-GB model must deterministically select the low-peak Android profile")
    require('markProcessStage("native-weights-load")' in kotlin,
            "hard crash diagnostics must distinguish native weight mapping")
    require('markProcessStage("native-context-prepare")' in kotlin,
            "hard crash diagnostics must distinguish context/KV allocation")
    require('markProcessStage("native-model-ready")' in kotlin,
            "successful native load must clear the vulnerable load stage")

    manager = (ROOT / "android-wrapper/app/src/main/java/com/wynndev/furina/ModelDownloadManager.kt").read_text(encoding="utf-8")
    provider = (ROOT / "android-wrapper/app/src/main/java/com/wynndev/furina/LocalLlamaProvider.kt").read_text(encoding="utf-8")
    diagnostics = (ROOT / "android-wrapper/app/src/main/java/com/wynndev/furina/ProcessExitDiagnostics.kt").read_text(encoding="utf-8")
    bootstrap = (ROOT / "scripts/bootstrap-llama-android.sh").read_text(encoding="utf-8")

    require("context.noBackupFilesDir" in manager and "ensureRuntimeModel" in manager,
            "verified GGUF must migrate to app-private internal runtime storage before mmap")
    require("output.fd.sync()" in manager and "MessageDigest.getInstance(\"SHA-256\")" in manager,
            "internal migration must be fsynced and checksum-verified before promotion")
    require("modelDownloads.ensureRuntimeModel(spec)" in provider,
            "local provider must load the private runtime copy")
    require('ProcessExitDiagnostics.mark(appContext, "offline-engine-load")' in provider,
            "provider must mark the coarse engine-load stage")
    require("getHistoricalProcessExitReasons" in diagnostics and "setProcessStateSummary" in diagnostics,
            "Android process-exit diagnostics must survive hard native/LMKD process death")
    require("apply-offline-stability-policy.py" in bootstrap,
            "native build must apply the second-stage stability patch")

    print("Furina offline load safety gate passed: private mmap + deterministic low-peak 4K profile + exit-stage diagnostics")


if __name__ == "__main__":
    main()
