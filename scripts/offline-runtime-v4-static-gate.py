#!/usr/bin/env python3
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"OFFLINE RUNTIME GATE FAILED: {message}")


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
        run("python3", str(ROOT / "scripts/fix-offline-runtime-v4-kotlin-regex.py"), str(impl))
        run("python3", str(ROOT / "scripts/apply-offline-checkpoint-chat-policy.py"), str(cpp))
        run("python3", str(ROOT / "scripts/apply-offline-backend-autotune-policy.py"), str(cpp), str(impl))
        run("python3", str(ROOT / "scripts/fix-offline-backend-cpp-includes.py"), str(cpp))
        run("python3", str(ROOT / "scripts/apply-hexagon-runtime-env-policy.py"), str(cpp))

        cpp_text = cpp.read_text(encoding="utf-8")
        impl_text = impl.read_text(encoding="utf-8")
        interface_text = interface.read_text(encoding="utf-8")
        bootstrap_text = (ROOT / "scripts/bootstrap-llama-android.sh").read_text(encoding="utf-8")
        hexagon_build_text = (ROOT / "scripts/build-hexagon-runtime.sh").read_text(encoding="utf-8")

        require("resetConversationKeepingSystemPromptNative" in cpp_text, "SYSTEM-prefix reset JNI missing")
        require("llama_state_seq_get_data" in cpp_text, "KV save API missing")
        require("llama_state_seq_set_data" in cpp_text, "KV restore API missing")
        require("FURINA_KV_VERSION = 5" in cpp_text, "checkpoint chat/KV format must be v5")
        require("chat_msgs = std::move(restored_chat)" in cpp_text, "exact chat framing must restore with KV")
        require("shift_context_for" in cpp_text, "system-preserving sliding context missing")
        require("LLAMA_FLASH_ATTN_TYPE_AUTO" in cpp_text, "Flash Attention AUTO missing")
        require("llama_set_n_threads" in cpp_text, "runtime thread retuning missing")
        require("runtimeProfileNative" in cpp_text, "runtime profile diagnostics missing")
        require("configureBackendPreferenceNative" in cpp_text, "backend selection JNI missing")
        require("availableBackendsNative" in cpp_text, "backend discovery JNI missing")
        require("find_device_for_backend" in cpp_text, "backend device matching missing")
        require("params.n_gpu_layers = -1" in cpp_text, "accelerator layer offload missing")
        require("cpu:fallback-load" in cpp_text, "accelerator CPU fallback missing")
        require('setenv("ADSP_LIBRARY_PATH", path_to_backend, 1)' in cpp_text,
                "Hexagon HTP runtime path must follow Android nativeLibDir")
        require("ggml_backend_load_all_from_path(path_to_backend)" in cpp_text,
                "dynamic accelerator registration missing")

        for symbol in (
            "saveCheckpoint", "restoreCheckpoint", "ensureRuntimeProfile", "runtimeProfile",
            "resetConversationKeepingSystemPrompt",
        ):
            require(symbol in interface_text, f"InferenceEngine API missing {symbol}")
            require(symbol in impl_text, f"InferenceEngineImpl missing {symbol}")
        require("currentThermalStatus" in impl_text, "thermal governor missing")
        require("furina_llama_runtime_v4" in impl_text, "persistent device profile missing")
        require("availableBackendCandidates" in impl_text, "backend candidate discovery missing")
        require("backendScores" in impl_text, "one-time backend benchmark sweep missing")
        require("$activeRuntimeKey:backend" in impl_text, "persistent backend winner missing")
        require("listOf(\"cpu\", \"vulkan\", \"opencl\", \"hexagon\")" in impl_text,
                "CPU/Vulkan/OpenCL/Hexagon candidate order missing")

        require("build-hexagon-runtime.sh" in bootstrap_text, "Hexagon builder not wired into AAR bootstrap")
        require("libggml-hexagon.so" in bootstrap_text, "AAR must verify Hexagon plugin packaging")
        for arch in ("v73", "v75", "v79", "v81"):
            require(f"libggml-htp-${{arch}}.so".replace("${arch}", arch) in bootstrap_text,
                    f"AAR must verify HTP {arch} skel packaging")
        require("ghcr.io/snapdragon-toolchain/arm64-android:v0.7" in hexagon_build_text,
                "Hexagon build must use pinned official Snapdragon toolchain image")
        require("arm64-android-snapdragon-release" in hexagon_build_text,
                "Hexagon build must use upstream Snapdragon preset")
        require("GGML_BACKEND_DL=ON" in hexagon_build_text,
                "Hexagon must be a dynamic backend, not replace Furina's CPU/GPU runtime")

    print("Offline runtime static gate passed: KV/session + CPU/Vulkan/OpenCL/Hexagon adaptive runtime invariants")


if __name__ == "__main__":
    main()
