#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import os
import sys
from pathlib import Path


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def main() -> int:
    repo = Path(os.environ.get("GITHUB_WORKSPACE") or Path.cwd()).resolve()
    stage = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/furina-agent-rc54-validate/termux").resolve()
    project = repo / "experiments/furina-agent-final"
    core = stage / "core/furina_agent"
    bridge = stage / "bridge/app"
    blockers: list[str] = []
    warnings: list[str] = []

    def fail(code: str, detail: str) -> None:
        blockers.append(f"{code}: {detail}")

    required = [core / x for x in (
        "version.py", "config.py", "persona.py", "chat.py", "dialogue_state.py",
        "memory.py", "llm.py", "local_models.py", "local_runtime.py", "tui.py", "hub.py",
    )]
    required += [
        bridge / "build.gradle",
        bridge / "src/main/java/com/wynndev/furinaagentbridge/MainActivity.java",
    ]
    for path in required:
        if not path.is_file():
            fail("FILE", f"missing {path.relative_to(stage)}")
    if blockers:
        for x in blockers: print("BLOCKER", x)
        return 1

    for path in core.glob("*.py"):
        try:
            ast.parse(read(path), filename=str(path))
        except SyntaxError as exc:
            fail("PY_PARSE", f"{path.name}: {exc}")

    manifest = json.loads(read(project / "manifest.json"))
    version = read(core / "version.py")
    models = read(core / "local_models.py")
    llm = read(core / "llm.py")
    runtime = read(core / "local_runtime.py")
    chat = read(core / "chat.py")
    dialogue = read(core / "dialogue_state.py")
    hub = read(core / "hub.py")
    build = read(bridge / "build.gradle")
    main_java = read(bridge / "src/main/java/com/wynndev/furinaagentbridge/MainActivity.java")

    expected = {
        "version": "1.0.9",
        "dependency_revision": "2026.08.24-r49",
        "bundle_id": "furina-2026.08.24-private-1.0.9",
        "bridge_version": "1.0.9",
        "bridge_version_code": 10067,
        "runtime_contract": "furina-runtime/v15-qwen3-4b-quality",
    }
    for key, value in expected.items():
        if manifest.get(key) != value:
            fail("MANIFEST", f"{key}={manifest.get(key)!r}, expected {value!r}")

    ids = [x.get("id") for x in manifest.get("local_model_catalog", [])]
    expected_ids = ["wifugpt-1.7b-q4km", "qwen3-1.7b-heretic-q5km", "qwen3-4b-2507-uncensored-q4km"]
    if ids != expected_ids:
        fail("MODEL_CATALOG", f"ids={ids!r}")
    q = next((x for x in manifest.get("local_model_catalog", []) if x.get("id") == "qwen3-4b-2507-uncensored-q4km"), {})
    if q.get("sha256") != "6615b7b5184931e4df9c6d0ae9cd29ca9319b73908d4423283d4cc401a12a1cd":
        fail("MODEL_SHA", "quality model SHA mismatch")

    if 'VERSION = "1.0.9"' not in version: fail("VERSION", "Core is not 1.0.9")
    if "versionCode 10067" not in build or "versionName '1.0.9'" not in build: fail("ANDROID", "FurinaHub is not 1.0.9/10067")
    if 'EXPECTED_CORE_VERSION = "1.0.9"' not in main_java: fail("BOUNDARY", "Android/Core boundary mismatch")
    if 'EXPECTED_DEPENDENCY_REVISION = "2026.08.24-r49"' not in main_java: fail("BOUNDARY", "Android dependency mismatch")
    if 'EXPECTED_DEPENDENCY_REVISION = "2026.08.24-r49"' not in hub: fail("HUB", "Hub dependency mismatch")

    for token in (
        "qwen3-4b-2507-uncensored-q4km",
        "Qwen3 4B Instruct 2507 Uncensored Q4_K_M",
        "6615b7b5184931e4df9c6d0ae9cd29ca9319b73908d4423283d4cc401a12a1cd",
        "Content-Range", "_write_verified_marker", "verify_download(part, item)",
    ):
        if token not in models: fail("MODEL_RUNTIME", f"missing {token}")
    if 'qwen_quality = "qwen3-4b-2507-instruct-uncensored" in model_hint' not in llm:
        fail("SAMPLING", "quality model detection missing")
    if "elif qwen_heretic or qwen_quality:" not in llm:
        fail("SAMPLING", "quality model Qwen3 branch missing")
    if 'cmd.append("--jinja")' not in runtime:
        fail("TEMPLATE", "capability-gated Jinja missing")

    # The 1.0.9 model addition must preserve the 1.0.8 conversational architecture.
    for token in (
        "DialogueStateBuilder.build(history, user_text)",
        "Every conversational answer comes from the selected model",
    ):
        if token not in chat: fail("DIALOGUE", f"missing {token}")
    for removed in (
        "def _fresh_social_answer", "def _local_answer_suspicious", "def _local_repair_messages",
    ):
        if removed in chat: fail("DIALOGUE", f"canned/repair path returned: {removed}")
    for token in ("DIALOGUE STATE", "unverified_character_utterance", "rejected_or_corrected_by_user"):
        if token not in dialogue: fail("DIALOGUE", f"missing {token}")

    installers = [
        project / "install.sh",
        repo / "furina-agent-termux/experiments/furina-agent-final/install.sh",
    ]
    if read(installers[0]) != read(installers[1]):
        fail("INSTALLER", "installer mirrors differ")
    installer = read(installers[0])
    active = "\n".join(x for x in installer.splitlines() if not x.lstrip().startswith("#"))
    for token in (
        'FURINA_UPDATER_GENERATION="34"', 'VERSION="1.0.9"',
        'DEPENDENCY_REVISION="2026.08.24-r49"',
        'RUNTIME_CONTRACT="furina-runtime/v15-qwen3-4b-quality"',
    ):
        if token not in active: fail("INSTALLER", f"missing active {token}")
    if ".gguf" in active.lower() or "huggingface.co" in active.lower():
        fail("INSTALLER", "bootstrap must not download/reference a GGUF")
    if 'FURINA_RUNTIME_CONTRACT="furina-runtime/v2"' not in installer:
        fail("RECOVERY", "RC67 compatibility marker missing")

    print(f"Python modules checked: {len(list(core.glob('*.py')))}")
    print(f"Blockers: {len(blockers)}")
    print(f"Warnings: {len(warnings)}")
    for x in blockers: print("BLOCKER", x)
    for x in warnings: print("WARNING", x)
    if blockers:
        return 1
    print("FURINA_PRIVATE_1_0_9_AUDIT_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
