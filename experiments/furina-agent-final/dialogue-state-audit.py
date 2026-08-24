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
        "version.py", "config.py", "persona.py", "chat.py", "memory.py", "dialogue_state.py",
        "llm.py", "routing.py", "hub.py", "tui.py",
    )]
    required += [bridge / "build.gradle", bridge / "src/main/java/com/wynndev/furinaagentbridge/MainActivity.java", bridge / "src/main/assets/furinahub/index.html"]
    for path in required:
        if not path.is_file():
            fail("FILE", f"missing {path.relative_to(stage)}")
    if blockers:
        print("\n".join(blockers)); return 1

    for path in core.glob("*.py"):
        try: ast.parse(read(path), filename=str(path))
        except SyntaxError as exc: fail("PY_PARSE", f"{path.name}: {exc}")

    manifest = json.loads(read(project / "manifest.json"))
    expected = {
        "version": "1.0.8",
        "dependency_revision": "2026.08.24-r48",
        "bundle_id": "furina-2026.08.24-private-1.0.8",
        "bridge_version": "1.0.8",
        "bridge_version_code": 10066,
        "runtime_contract": "furina-runtime/v14-grounded-dialogue-state",
    }
    for key, value in expected.items():
        if manifest.get(key) != value: fail("MANIFEST", f"{key}={manifest.get(key)!r}, expected {value!r}")

    version = read(core / "version.py"); persona = read(core / "persona.py"); chat = read(core / "chat.py")
    memory = read(core / "memory.py"); ds = read(core / "dialogue_state.py"); llm = read(core / "llm.py")
    hub = read(core / "hub.py"); tui = read(core / "tui.py"); build = read(bridge / "build.gradle")
    main = read(bridge / "src/main/java/com/wynndev/furinaagentbridge/MainActivity.java")
    html = read(bridge / "src/main/assets/furinahub/index.html")

    if 'VERSION = "1.0.8"' not in version: fail("VERSION", "Core is not 1.0.8")
    if "versionCode 10066" not in build or "versionName '1.0.8'" not in build: fail("ANDROID", "FurinaHub is not 1.0.8/10066")
    if 'EXPECTED_CORE_VERSION = "1.0.8"' not in main or 'EXPECTED_DEPENDENCY_REVISION = "2026.08.24-r48"' not in main: fail("BOUNDARY", "Android/Core boundary mismatch")
    if 'EXPECTED_DEPENDENCY_REVISION = "2026.08.24-r48"' not in hub: fail("HUB", "Hub dependency boundary mismatch")

    for token in ("class DialogueStateBuilder", "topic_anchor", "user_evidence", "assistant_continuity", "rejected_or_corrected_by_user", "user_requests_clarification"):
        if token not in ds: fail("DIALOGUE_STATE", f"missing {token}")
    if "DialogueStateBuilder.build(history, user_text)" not in chat: fail("COMPOSER", "local chat does not use DialogueStateBuilder")
    if "len(msgs)==2" in chat: fail("COMPOSER", "test artifact leaked into runtime")

    # No conversational canned/repair pipeline may be active in 1.0.8.
    for token in (
        "def _fresh_social_answer", "def _local_answer_suspicious", "def _local_repair_messages",
        "def _direct_temporal_answer", "def _needs_personal_context", "def _needs_temporal_context",
        "held_prefix", "local_quality_repair",
    ):
        if token in chat: fail("RIGID_CHAT", f"legacy conversation patch remains: {token}")
    if "Every conversational answer comes from the selected model" not in chat: fail("MODEL_GENERATION", "model-generated chat contract missing")

    if "chemistry dua arah" not in persona or "Jika tebakanmu dikoreksi" not in persona: fail("PERSONA", "positive local persona grounding missing")
    if "DIALOGUE STATE" not in ds or "bukan fakta tentang user" not in ds: fail("PROVENANCE", "assistant/user truth boundary missing")
    if "Legacy model-authored sources are deliberately not trusted as facts" not in memory: fail("MEMORY", "legacy inferred-memory quarantine missing")
    if "trusted_sources" not in memory or "user_evidence_pattern" not in memory: fail("MEMORY", "trusted provenance gate missing")

    for token in ("qwen_heretic", "presence_penalty", "top_p = 0.80; top_k = 20", "top_p = 0.86; top_k = 30", '"enable_thinking": False'):
        if token not in llm: fail("SAMPLING", f"missing {token}")

    # Session isolation remains independent from dialogue state.
    for token in ("def bind_conversation", "def create_session_conversation", "_conversation_override"):
        if token not in memory: fail("SESSION_SCOPE", f"memory missing {token}")
    for token in ("_TERMUX_CHAT_CONVERSATION_ID = None", "def _termux_chat_store", "def _ensure_termux_chat_conversation"):
        if token not in tui: fail("SESSION_SCOPE", f"TUI missing {token}")

    if manifest.get("local_model_response_policy") != "selected-model-generates-every-conversational-turn-no-social-fast-response-no-regex-rewrite-no-repair-generation":
        fail("MANIFEST_CHAT", "no-canned-response policy mismatch")
    if not str(manifest.get("dialogue_grounding") or "").startswith("assistant-output-never-becomes"):
        fail("MANIFEST_CHAT", "dialogue grounding policy missing")
    if manifest.get("conversation_memory_model") != "short-term-thread-scoped-long-term-user-memory-cross-session":
        fail("MANIFEST_MEMORY", "thread/long-term memory split changed")

    try:
        start = html.index("async function sendMessage(forcedText)")
        end = html.index("\nfunction thinkingArchiveKey()", start)
        send = html[start:end]
        if "/api/chat/start" not in send or "state.partial" not in send: fail("HUB_STREAM", "async partial streaming missing")
        if "refreshConversation()" in send or "renderBoot()" in send: fail("HUB_RERENDER", "live send rebuilds conversation")
    except ValueError:
        fail("HUB_STREAM", "sendMessage block missing")

    catalog = manifest.get("local_model_catalog") or []
    if [x.get("id") for x in catalog] != ["wifugpt-1.7b-q4km", "qwen3-1.7b-heretic-q5km"]:
        fail("MODEL_CATALOG", "local catalog changed")

    installer = read(project / "install.sh"); mirror = read(repo / "furina-agent-termux/experiments/furina-agent-final/install.sh")
    if installer != mirror: fail("INSTALLER", "installer mirrors differ")
    active = "\n".join(x for x in installer.splitlines() if not x.lstrip().startswith("#"))
    for token in ('FURINA_UPDATER_GENERATION="33"','VERSION="1.0.8"','DEPENDENCY_REVISION="2026.08.24-r48"','RUNTIME_CONTRACT="furina-runtime/v14-grounded-dialogue-state"'):
        if token not in active: fail("INSTALLER", f"missing active {token}")
    for token in ('FURINA_UPDATER_GENERATION="32"','VERSION="1.0.7"','DEPENDENCY_REVISION="2026.08.24-r47"','RUNTIME_CONTRACT="furina-runtime/v13-conversation-quality-gate"'):
        if token not in installer: fail("RECOVERY", f"missing historical {token}")
    if ".gguf" in active.casefold() or "wifugpt" in active.casefold(): fail("INSTALLER", "bootstrap references model artifact")
    if 'FURINA_RUNTIME_CONTRACT="furina-runtime/v2"' not in installer: fail("RECOVERY", "RC67 compatibility marker missing")

    print(f"Python modules checked: {len(list(core.glob('*.py')))}")
    print(f"Blockers: {len(blockers)}")
    print(f"Warnings: {len(warnings)}")
    for item in blockers: print("BLOCKER", item)
    for item in warnings: print("WARNING", item)
    if blockers: return 1
    print("FURINA_PRIVATE_1_0_8_AUDIT_OK")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
