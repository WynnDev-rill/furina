#!/usr/bin/env python3
"""Enable llama.cpp mobile GPU backends in the pinned Android AAR build.

CPU remains compiled and is always the fallback. Vulkan is the generic Adreno path; OpenCL
uses llama.cpp's Qualcomm-oriented kernels when the target device exposes a compatible driver.
"""
from __future__ import annotations

import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: apply-mobile-gpu-build-policy.py <android-CMakeLists.txt>")
    path = Path(sys.argv[1])
    text = path.read_text(encoding="utf-8")
    old = '''    if(ANDROID_ABI STREQUAL "arm64-v8a")
        set(GGML_SYSTEM_ARCH "ARM")
        set(GGML_CPU_KLEIDIAI ON)
        set(GGML_OPENMP ON)'''
    new = '''    if(ANDROID_ABI STREQUAL "arm64-v8a")
        set(GGML_SYSTEM_ARCH "ARM")
        set(GGML_CPU_KLEIDIAI ON)
        set(GGML_OPENMP ON)
        # Keep CPU as the universal safe fallback, but compile both practical Adreno paths.
        # Runtime selection is benchmark-driven and may still choose CPU.
        set(GGML_VULKAN ON CACHE BOOL "" FORCE)
        set(GGML_OPENCL ON CACHE BOOL "" FORCE)
        set(GGML_OPENCL_USE_ADRENO_KERNELS ON CACHE BOOL "" FORCE)
        set(GGML_OPENCL_EMBED_KERNELS ON CACHE BOOL "" FORCE)'''
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"mobile GPU CMake anchor: expected exactly one match, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


if __name__ == "__main__":
    main()
