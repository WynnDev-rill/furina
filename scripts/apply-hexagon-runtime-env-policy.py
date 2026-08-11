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
        raise SystemExit("usage: apply-hexagon-runtime-env-policy.py <ai_chat.cpp>")
    path = Path(sys.argv[1])

    replace_once(
        path,
        "#include <cctype>\n#include <cstdint>\n",
        "#include <cctype>\n#include <cstdlib>\n#include <cstdint>\n",
        "Hexagon setenv include",
    )

    replace_once(
        path,
        '''    const auto *path_to_backend = env->GetStringUTFChars(jnative_lib_dir, 0);
    ggml_backend_load_all_from_path(path_to_backend);
    env->ReleaseStringUTFChars(jnative_lib_dir, path_to_backend);''',
        '''    const auto *path_to_backend = env->GetStringUTFChars(jnative_lib_dir, 0);
    // Qualcomm HTP skel libraries are packaged beside Furina's other native libraries.
    // Hexagon's rpcmem/session loader resolves them through ADSP_LIBRARY_PATH.
    if (path_to_backend && path_to_backend[0] != '\\0') {
        setenv("ADSP_LIBRARY_PATH", path_to_backend, 1);
    }
    ggml_backend_load_all_from_path(path_to_backend);
    env->ReleaseStringUTFChars(jnative_lib_dir, path_to_backend);''',
        "Hexagon ADSP runtime path",
    )

    print("Applied Hexagon runtime environment policy: ADSP_LIBRARY_PATH=nativeLibDir")


if __name__ == "__main__":
    main()
