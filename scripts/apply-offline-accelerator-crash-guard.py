#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one match in {path}, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: apply-offline-accelerator-crash-guard.py <InferenceEngineImpl.kt>")
    path = Path(sys.argv[1])

    replace_once(
        path,
        '''    private fun availableBackendCandidates(): List<String> {
        val available = availableBackendsNative().split(',').map { it.trim().lowercase() }.filter { it.isNotBlank() }.toSet()
        return listOf("cpu", "vulkan", "opencl", "hexagon").filter { it in available }
    }
''',
        '''    private fun requiresCpuOnlyAcceleratorGuard(): Boolean {
        val soc = Build.SOC_MODEL.orEmpty().trim().lowercase()
        val device = Build.DEVICE.orEmpty().trim().lowercase()
        val product = Build.PRODUCT.orEmpty().trim().lowercase()
        // POCO F6 / Redmi Turbo 3 (peridot, Snapdragon 8s Gen 3 / SM8635) can expose
        // Vulkan/OpenCL devices while a full llama.cpp offload aborts inside the vendor driver.
        // Never probe a potentially fatal native backend in Furina's UI process on this target.
        return soc == "sm8635" || device == "peridot" || product.contains("peridot")
    }

    private fun availableBackendCandidates(): List<String> {
        val available = availableBackendsNative().split(',').map { it.trim().lowercase() }.filter { it.isNotBlank() }.toSet()
        if (requiresCpuOnlyAcceleratorGuard()) return listOf("cpu")
        return listOf("cpu", "vulkan", "opencl", "hexagon").filter { it in available }
    }
''',
        "Poco F6 accelerator candidate guard",
    )

    replace_once(
        path,
        '''        activeBackendPreference = runtimePrefs.getString("$activeRuntimeKey:backend", "cpu") ?: "cpu"
        configureBackendPreferenceNative(activeBackendPreference)
''',
        '''        val savedBackend = runtimePrefs.getString("$activeRuntimeKey:backend", "cpu") ?: "cpu"
        activeBackendPreference = if (requiresCpuOnlyAcceleratorGuard()) "cpu" else savedBackend
        if (activeBackendPreference == "cpu" && savedBackend != "cpu") {
            runtimePrefs.edit().putString("$activeRuntimeKey:backend", "cpu").apply()
            Log.w(TAG, "Quarantined persisted accelerator backend '$savedBackend' for crash-safe CPU recovery")
        }
        configureBackendPreferenceNative(activeBackendPreference)
''',
        "saved accelerator recovery guard",
    )

    print("Applied offline accelerator crash guard: SM8635/peridot uses CPU baseline; GPU modules remain packaged")


if __name__ == "__main__":
    main()
