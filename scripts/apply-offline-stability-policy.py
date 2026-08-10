#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def patch_cpp(path: Path) -> None:
    text = path.read_text(encoding="utf-8")

    # For a multi-GB mobile model, predictable peak RSS is more valuable than the
    # optional CPU weight-repacking speedup. None of these settings alter weights,
    # sampler, KV precision for 4B, or the 4096-token target context.
    text = replace_once(
        text,
        "g_active_batch_size = g_low_memory_mode ? 256 : BATCH_SIZE;",
        "g_active_batch_size = g_low_memory_mode ? 128 : 256;",
        "low-peak batch",
    )
    text = replace_once(
        text,
        "model_params.use_extra_bufts = !g_low_memory_mode;",
        "model_params.use_extra_bufts = false;",
        "disable extra packed-weight buffers",
    )
    text = replace_once(
        text,
        "ctx_params.n_ubatch = g_low_memory_mode ? 128 : UBATCH_SIZE;",
        "ctx_params.n_ubatch = g_low_memory_mode ? 64 : 128;",
        "low-peak micro-batch",
    )

    path.write_text(text, encoding="utf-8")


def patch_kotlin(path: Path) -> None:
    text = path.read_text(encoding="utf-8")

    text = replace_once(
        text,
        '''import android.app.ActivityManager
import android.content.Context
import android.util.Log''',
        '''import android.app.ActivityManager
import android.content.Context
import android.os.Build
import android.util.Log''',
        "Build import",
    )

    marker = '''    /**
     * Repacked CPU weights can materially improve throughput but also raise peak RSS.
     * Keep that optimization only when Android reports enough free memory for roughly
     * two model-sized resident representations plus a 2 GiB UI/context/system margin.
     * This changes memory layout and batch scratch only; model weights/context quality stay.
     */
    private fun shouldUseLowMemoryMode(modelBytes: Long): Boolean {'''
    replacement = '''    /** Persist the exact native-load stage so Android can report it after a hard process death. */
    private fun markProcessStage(stage: String) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.R) return
        runCatching {
            val manager = appContext.getSystemService(Context.ACTIVITY_SERVICE) as ActivityManager
            manager.setProcessStateSummary(stage.take(120).toByteArray(Charsets.UTF_8))
        }
    }

    /**
     * Repacked CPU weights can materially improve throughput but also raise peak RSS.
     * Furina's local GGUF is multi-gigabyte, so always use the deterministic low-peak
     * profile for it. This changes scratch/repack layout only, not model/context quality.
     */
    private fun shouldUseLowMemoryMode(modelBytes: Long): Boolean {'''
    text = replace_once(text, marker, replacement, "native stage marker helper")

    text = replace_once(
        text,
        '''        val performanceFloor = (modelBytes * 2L) + (2L * gib)
        val lowPeak = info.lowMemory || info.availMem < performanceFloor''',
        '''        val performanceFloor = (modelBytes * 2L) + (2L * gib)
        val multiGigabyteModel = modelBytes >= 2L * gib
        val lowPeak = multiGigabyteModel || info.lowMemory || info.availMem < performanceFloor''',
        "force multi-gigabyte low-peak profile",
    )

    text = replace_once(
        text,
        '''                val lowMemoryMode = shouldUseLowMemoryMode(modelFile.length())
                load(pathToModel, lowMemoryMode).let {
                    if (it != 0) {''',
        '''                val lowMemoryMode = shouldUseLowMemoryMode(modelFile.length())
                markProcessStage("native-weights-load")
                load(pathToModel, lowMemoryMode).let {
                    if (it != 0) {''',
        "weights-load stage marker",
    )

    text = replace_once(
        text,
        '''                }
                prepare().let {
                    if (it != 0) throw IOException("Failed to prepare resources")
                }
                Log.i(TAG, "Model loaded!")''',
        '''                }
                markProcessStage("native-context-prepare")
                prepare().let {
                    if (it != 0) throw IOException("Failed to prepare resources")
                }
                markProcessStage("native-model-ready")
                Log.i(TAG, "Model loaded!")''',
        "context stage marker",
    )

    path.write_text(text, encoding="utf-8")


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: apply-offline-stability-policy.py <ai_chat.cpp> <InferenceEngineImpl.kt>")
    cpp = Path(sys.argv[1])
    kotlin = Path(sys.argv[2])
    patch_cpp(cpp)
    patch_kotlin(kotlin)
    print("Applied Furina Android offline stability policy: private mmap + deterministic low-peak load")


if __name__ == "__main__":
    main()
