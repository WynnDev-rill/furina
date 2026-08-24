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

    required = [core / x for x in ("version.py", "config.py", "persona.py", "chat.py", "memory.py", "llm.py", "routing.py", "hub.py", "tui.py")]
    required += [bridge / "build.gradle", bridge / "src/main/java/com/wynndev/furinaagentbridge/MainActivity.java", bridge / "src/main/assets/furinahub/index.html"]
    for path in required:
        if not path.is_file():
            fail("FILE", f"missing {path.relative_to(stage)}")
    if blockers:
        print("\n".join(blockers)); return 1

    for path in core.glob("*.py"):
        try:
            ast.parse(read(path), filename=str(path))
        except SyntaxError as exc:
            fail("PY_PARSE", f"{path.name}: {exc}")

    manifest = json.loads(read(project / "manifest.json"))
    expected = {
        "version": "1.0.6",
        "dependency_revision": "2026.08.24-r46",
        "bundle_id": "furina-2026.08.24-private-1.0.6",
        "bridge_version": "1.0.6",
        "bridge_version_code": 10064,
        "runtime_contract": "furina-runtime/v12-session-isolation",
    }
    for key, value in expected.items():
        if manifest.get(key) != value:
            fail("MANIFEST", f"{key}={manifest.get(key)!r}, expected {value!r}")

    version = read(core / "version.py")
    config = read(core / "config.py")
    persona = read(core / "persona.py")
    chat = read(core / "chat.py")
    memory = read(core / "memory.py")
    llm = read(core / "llm.py")
    hub = read(core / "hub.py")
    tui = read(core / "tui.py")
    build = read(bridge / "build.gradle")
    main = read(bridge / "src/main/java/com/wynndev/furinaagentbridge/MainActivity.java")
    html = read(bridge / "src/main/assets/furinahub/index.html")

    if 'VERSION = "1.0.6"' not in version: fail("VERSION", "Core is not 1.0.6")
    if "config_revision: int = 9" not in config: fail("CONFIG", "config revision is not 9")
    if "versionCode 10064" not in build or "versionName '1.0.6'" not in build: fail("ANDROID", "FurinaHub is not 1.0.6/10064")
    if 'EXPECTED_CORE_VERSION = "1.0.6"' not in main or 'EXPECTED_DEPENDENCY_REVISION = "2026.08.24-r46"' not in main: fail("BOUNDARY", "Android/Core boundary mismatch")
    if 'EXPECTED_DEPENDENCY_REVISION = "2026.08.24-r46"' not in hub: fail("HUB", "Hub dependency revision mismatch")

    for token in ("_assistant_history_safe", "_recent_context", "_direct_temporal_answer", "_local_generation_budget", "assistant_history_quarantined"):
        if token not in chat: fail("CHAT_GUARD", f"missing {token}")
    for token in ("source=\"user_evidence\"", "source=\"user_evidence_pattern\"", "SHARED PERSONAL CONTEXT", "WAKTU LOKAL TERPERCAYA"):
        if token not in chat: fail("CONTEXT", f"missing {token}")
    if "behavior notes remain stored but are deliberately not injected" not in chat: fail("LEGACY_NOTES", "legacy behavior-note quarantine missing")
    if "Legacy model-authored sources are deliberately not trusted as facts" not in memory: fail("MEMORY_PROVENANCE", "legacy inferred-memory quarantine missing")
    if "trusted_sources" not in memory or "user_evidence_pattern" not in memory: fail("BELIEF_PROVENANCE", "belief provenance gate missing")
    if '"repeat_penalty": 1.10 if not json_mode else 1.0' not in llm or '"repeat_last_n": 192 if not json_mode else 64' not in llm: fail("SAMPLING", "local anti-loop sampling missing")
    if "Tsundere adalah warna kepribadian" not in persona or "Pesan sederhana mendapat jawaban sederhana" not in persona: fail("PERSONA", "natural local-persona guard missing")

    # 1.0.6: conversation history is session/thread scoped. Long-term memory is
    # still shared because the override changes only active conversation lookup.
    for token in ("def bind_conversation", "def create_session_conversation", "_conversation_override"):
        if token not in memory: fail("SESSION_SCOPE", f"memory missing {token}")
    for token in ("_TERMUX_CHAT_CONVERSATION_ID = None", "def _termux_chat_store", "def _ensure_termux_chat_conversation", "store = _termux_chat_store()", "_ensure_termux_chat_conversation(store)"):
        if token not in tui: fail("TERMUX_SESSION", f"TUI missing {token}")
    if "create_session_conversation" in hub: fail("HUB_SCOPE", "FurinaHub must not adopt Termux process-scoped conversation creation")
    if manifest.get("conversation_memory_model") != "short-term-thread-scoped-long-term-user-memory-cross-session": fail("MANIFEST_SESSION", "conversation memory model missing")
    if not str(manifest.get("termux_conversation_scope") or "").startswith("fresh-short-term-thread"): fail("MANIFEST_SESSION", "Termux process-session scope missing")
    if not str(manifest.get("hub_conversation_scope") or "").startswith("persistent-explicit-conversations"): fail("MANIFEST_SESSION", "FurinaHub persistent scope missing")

    try:
        start = html.index("async function sendMessage(forcedText)")
        end = html.index("\nfunction thinkingArchiveKey()", start)
        send = html[start:end]
        if "/api/chat/start" not in send or "state.partial" not in send: fail("HUB_STREAM", "async partial streaming missing")
        if "refreshConversation()" in send or "renderBoot()" in send: fail("HUB_RERENDER", "live send still rebuilds conversation")
    except ValueError:
        fail("HUB_STREAM", "sendMessage block missing")

    catalog = manifest.get("local_model_catalog") or []
    ids = [x.get("id") for x in catalog]
    if ids != ["wifugpt-1.7b-q4km", "qwen3-1.7b-heretic-q5km"]:
        fail("MODEL_CATALOG", f"unexpected local catalog: {ids}")

    installer = read(project / "install.sh")
    mirror = read(repo / "furina-agent-termux/experiments/furina-agent-final/install.sh")
    if installer != mirror: fail("INSTALLER", "installer mirrors differ")
    active = "\n".join(x for x in installer.splitlines() if not x.lstrip().startswith("#"))
    for token in ('FURINA_UPDATER_GENERATION="31"', 'VERSION="1.0.6"', 'DEPENDENCY_REVISION="2026.08.24-r46"', 'RUNTIME_CONTRACT="furina-runtime/v12-session-isolation"'):
        if token not in active: fail("INSTALLER", f"missing active {token}")
    for token in ('FURINA_UPDATER_GENERATION="30"', 'VERSION="1.0.5"', 'DEPENDENCY_REVISION="2026.08.24-r45"', 'RUNTIME_CONTRACT="furina-runtime/v11-conversation-quality"'):
        if token not in installer: fail("RECOVERY", f"missing historical {token}")
    if ".gguf" in active.casefold() or "wifugpt" in active.casefold(): fail("INSTALLER", "bootstrap references/downloads a model")
    if 'FURINA_RUNTIME_CONTRACT="furina-runtime/v2"' not in installer: fail("RECOVERY", "legacy v2 recovery marker missing")

    print(f"Python modules checked: {len(list(core.glob('*.py')))}")
    print(f"Blockers: {len(blockers)}")
    print(f"Warnings: {len(warnings)}")
    for item in blockers: print("BLOCKER", item)
    for item in warnings: print("WARNING", item)
    if blockers: return 1
    print("FURINA_PRIVATE_1_0_6_AUDIT_OK")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
