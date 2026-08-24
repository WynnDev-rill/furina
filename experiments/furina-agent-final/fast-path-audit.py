#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import os
import sys
from pathlib import Path


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def method(text: str, class_name: str, name: str) -> str:
    tree=ast.parse(text)
    cls=next((n for n in tree.body if isinstance(n,ast.ClassDef) and n.name==class_name),None)
    if cls is None: return ""
    node=next((n for n in cls.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name==name),None)
    if node is None: return ""
    lines=text.splitlines(); start=min([node.lineno]+[d.lineno for d in node.decorator_list])
    return "\n".join(lines[start-1:node.end_lineno])


def main() -> int:
    repo=Path(os.environ.get("GITHUB_WORKSPACE") or Path.cwd()).resolve()
    stage=Path(sys.argv[1] if len(sys.argv)>1 else "/tmp/furina-agent-rc54-validate/termux").resolve()
    project=repo/"experiments/furina-agent-final"; core=stage/"core/furina_agent"; bridge=stage/"bridge/app"
    blockers=[]; warnings=[]
    def fail(code,detail): blockers.append(f"{code}: {detail}")

    required=[core/x for x in ("version.py","config.py","persona.py","companion.py","chat.py","routing.py","llm.py","providers.py","local_runtime.py","local_models.py","tui.py","hub.py")]
    required += [bridge/"build.gradle",bridge/"src/main/java/com/wynndev/furinaagentbridge/MainActivity.java",bridge/"src/main/assets/furinahub/index.html"]
    for p in required:
        if not p.is_file(): fail("FILE",f"missing {p.relative_to(stage)}")
    if blockers:
        print("\n".join(blockers)); return 1
    for p in core.glob("*.py"):
        try: ast.parse(read(p),filename=str(p))
        except SyntaxError as e: fail("PY_PARSE",f"{p.name}: {e}")

    manifest=json.loads(read(project/"manifest.json")); version=read(core/"version.py"); config=read(core/"config.py"); persona=read(core/"persona.py"); companion=read(core/"companion.py"); chat=read(core/"chat.py"); routing=read(core/"routing.py"); llm=read(core/"llm.py"); providers=read(core/"providers.py"); runtime=read(core/"local_runtime.py"); models=read(core/"local_models.py"); tui=read(core/"tui.py"); hub=read(core/"hub.py"); build=read(bridge/"build.gradle"); main=read(bridge/"src/main/java/com/wynndev/furinaagentbridge/MainActivity.java"); page=read(bridge/"src/main/assets/furinahub/index.html")

    expected={"version":"1.0.3","dependency_revision":"2026.08.24-r43","bundle_id":"furina-2026.08.24-private-1.0.3","bridge_version":"1.0.3","bridge_version_code":10061,"runtime_contract":"furina-runtime/v9-local-fast-path"}
    for k,v in expected.items():
        if manifest.get(k)!=v: fail("MANIFEST",f"{k}={manifest.get(k)!r} expected {v!r}")
    if 'VERSION = "1.0.3"' not in version: fail("VERSION","Core is not 1.0.3")
    if "versionCode 10061" not in build or "versionName '1.0.3'" not in build: fail("ANDROID_VERSION","FurinaHub is not 1.0.3/10061")
    if 'EXPECTED_CORE_VERSION = "1.0.3"' not in main or expected["bundle_id"] not in main: fail("ANDROID_BOUNDARY","Core/bundle target mismatch")
    if 'EXPECTED_DEPENDENCY_REVISION = "2026.08.24-r43"' not in hub: fail("HUB_REVISION","Hub dependency boundary is stale")

    if '["Chat", "Provider & Model", "Pengaturan", "Exit"]' not in tui: fail("TUI_MENU","top-level menu changed")
    if 'data-view="memory"' in page: fail("MEMORY_SURFACE","Memory became user-facing again")
    if "Qwen3.5-4B" in page or "Tambah Qwen dari Hugging Face" in page: fail("LEGACY_MODEL","legacy model UI returned")
    for token in ("wifugpt-1.7b-q4km","qwen3-1.7b-heretic-q5km","Range","verify_download","sha256"):
        if token not in models: fail("MODEL_CATALOG",f"missing {token}")

    local_prompt=method(persona,"","") if False else ""
    if "def build_local_system_prompt" not in persona: fail("LOCAL_PROMPT","compact local persona missing")
    if "LOCAL_FAST_PATH_V3" not in chat: fail("LOCAL_PROMPT","local prompt path missing")
    if "recent_limit = 6 if profile.name" not in chat or "else 4" not in chat: fail("LOCAL_HISTORY","adaptive short history missing")
    if "budget = 1100" not in chat or "char_budget=700" not in chat: fail("LOCAL_MEMORY","retrieval budget missing")
    if "LOCAL_FAST_CHAT_ROUTER" not in companion: fail("CLASSIFIER","ordinary-chat fast router missing")
    if "max_tokens=80" not in companion: fail("CLASSIFIER","ambiguous device classifier is not compact")
    if "idle >= 120.0" not in chat or "_background_active" not in chat: fail("BACKGROUND","local memory work is not foreground-preemptible and idle-deferred")
    if "queue.Queue(maxsize=64)" not in chat: fail("QUEUE","bounded queue was lost")

    for token in ('config_revision: int = 7','context_size: int = 4096','server_priority: int = 0','LOCAL_FAST_PATH_V3_MIGRATION'):
        if token not in config: fail("CONFIG",f"missing {token}")
    for token in ('safe: bool = False','retrying safe CPU baseline','if ctx == 6144','ctx = 4096','"llama-cpp"'):
        if token not in runtime: fail("RUNTIME",f"missing {token}")
    if '["--prio"' in runtime and '> 0' not in runtime: fail("RUNTIME","unprivileged priority is unconditional")
    if "SmoothStream" not in llm or '"stream": bool(on_token) and not json_mode' not in llm: fail("LOCAL_STREAM","local streaming missing")
    if "SmoothStream" not in providers or '"stream": bool(on_token) and not json_mode' not in providers: fail("ONLINE_STREAM","online streaming missing")
    if "LOCAL_FAST_PATH_CHAT_PREWARM" not in tui: fail("PREWARM","opening local chat does not prewarm")

    installers=[project/"install.sh",repo/"furina-agent-termux/experiments/furina-agent-final/install.sh"]
    if read(installers[0])!=read(installers[1]): fail("INSTALLER","installer mirrors differ")
    active="\n".join(x for x in read(installers[0]).splitlines() if not x.lstrip().startswith("#"))
    for token in ('FURINA_UPDATER_GENERATION="28"','VERSION="1.0.3"','DEPENDENCY_REVISION="2026.08.24-r43"','RUNTIME_CONTRACT="furina-runtime/v9-local-fast-path"','pkg install -y llama-cpp'):
        if token not in active: fail("INSTALLER",f"missing active {token}")
    if ".gguf" in active.lower() or "wifugpt" in active.lower(): fail("INSTALLER","first install downloads/references a model artifact")
    if 'FURINA_RUNTIME_CONTRACT="furina-runtime/v2"' not in read(installers[0]): fail("RECOVERY","RC67 compatibility marker missing")

    print(f"Python modules checked: {len(list(core.glob('*.py')))}")
    print(f"Blockers: {len(blockers)}")
    print(f"Warnings: {len(warnings)}")
    for x in blockers: print("BLOCKER",x)
    for x in warnings: print("WARNING",x)
    if blockers: return 1
    print("FURINA_PRIVATE_1_0_3_AUDIT_OK")
    return 0

if __name__=="__main__": raise SystemExit(main())
