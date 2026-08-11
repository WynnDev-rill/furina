#!/usr/bin/env python3
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"OFFLINE RUNTIME V4 GATE FAILED: {message}")


def run(*args: str) -> None:
    subprocess.run(args, check=True, capture_output=True, text=True)


def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        work = Path(td)
        cpp = work / "ai_chat.cpp"
        impl = work / "InferenceEngineImpl.kt"
        interface = work / "InferenceEngine.kt"
        shutil.copy2(ROOT / "scripts/overlays/ai_chat.cpp", cpp)
        shutil.copy2(ROOT / "scripts/overlays/InferenceEngineImpl.kt", impl)
        shutil.copy2(ROOT / "scripts/fixtures/llama-7ba604f1-InferenceEngine.kt", interface)

        run("python3", str(ROOT / "scripts/apply-companion-runtime-policy.py"), str(cpp), str(impl))
        run("python3", str(ROOT / "scripts/apply-offline-stability-policy.py"), str(cpp), str(impl))
        run("python3", str(ROOT / "scripts/apply-warm-session-reset-policy.py"), str(cpp), str(interface), str(impl))
        run("python3", str(ROOT / "scripts/normalize-offline-runtime-v4-input.py"), str(cpp))
        run("python3", str(ROOT / "scripts/apply-offline-runtime-v4-policy.py"), str(cpp), str(interface), str(impl))
        run("python3", str(ROOT / "scripts/apply-offline-checkpoint-chat-policy.py"), str(cpp))

        cpp_text = cpp.read_text(encoding="utf-8")
        impl_text = impl.read_text(encoding="utf-8")
        interface_text = interface.read_text(encoding="utf-8")

        require("resetConversationKeepingSystemPromptNative" in cpp_text, "SYSTEM-prefix reset JNI missing")
        require("llama_state_seq_get_data" in cpp_text, "KV save API missing")
        require("llama_state_seq_set_data" in cpp_text, "KV restore API missing")
        require("FURINA_KV_VERSION = 5" in cpp_text, "checkpoint chat/KV format must be v5")
        require("chat_msgs = std::move(restored_chat)" in cpp_text, "exact chat framing must restore with KV")
        require("shift_context_for" in cpp_text, "system-preserving sliding context missing")
        require("LLAMA_FLASH_ATTN_TYPE_AUTO" in cpp_text, "Flash Attention AUTO missing")
        require("llama_set_n_threads" in cpp_text, "runtime thread retuning missing")
        require("runtimeProfileNative" in cpp_text, "runtime profile diagnostics missing")

        for symbol in (
            "saveCheckpoint", "restoreCheckpoint", "ensureRuntimeProfile", "runtimeProfile",
            "resetConversationKeepingSystemPrompt",
        ):
            require(symbol in interface_text, f"InferenceEngine API missing {symbol}")
            require(symbol in impl_text, f"InferenceEngineImpl missing {symbol}")
        require("currentThermalStatus" in impl_text, "thermal governor missing")
        require("furina_llama_runtime_v4" in impl_text, "persistent device profile missing")

    print("Offline runtime v4 static gate passed: full pinned patch chain + KV/chat/profile invariants")


if __name__ == "__main__":
    main()
