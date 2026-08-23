#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def duplicate_methods(path: Path, class_name: str) -> list[str]:
    tree = ast.parse(read(path), filename=str(path))
    cls = next((node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == class_name), None)
    if cls is None:
        return [f"class {class_name} missing"]
    counts: dict[str, int] = {}
    for node in cls.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            counts[node.name] = counts.get(node.name, 0) + 1
    return [name for name, count in counts.items() if count > 1]


def top_level_function(path: Path, name: str) -> str:
    text = read(path)
    tree = ast.parse(text, filename=str(path))
    nodes = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name]
    if len(nodes) != 1:
        return ""
    node = nodes[0]
    return "\n".join(text.splitlines()[node.lineno - 1 : node.end_lineno])


def literal_assignment(path: Path, name: str):
    tree = ast.parse(read(path), filename=str(path))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return ast.literal_eval(node.value)
    raise ValueError(f"{name} assignment missing")


def main() -> int:
    repo = Path(os.environ.get("GITHUB_WORKSPACE") or Path.cwd()).resolve()
    stage = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/furina-agent-rc54-validate/termux").resolve()
    project = repo / "experiments/furina-agent-final"
    manifest = json.loads(read(project / "manifest.json"))
    blockers: list[str] = []
    warnings: list[str] = []

    def fail(code: str, detail: str) -> None:
        blockers.append(f"{code}: {detail}")

    def warn(code: str, detail: str) -> None:
        warnings.append(f"{code}: {detail}")

    core = stage / "core/furina_agent"
    bridge = stage / "bridge/app"
    java = bridge / "src/main/java/com/wynndev/furinaagentbridge"
    html_path = bridge / "src/main/assets/furinahub/index.html"
    required = (
        core / "version.py", core / "cli.py", core / "tui.py", core / "hub.py", core / "routing.py",
        core / "local_models.py", core / "chat.py", core / "persona.py", core / "relationship_v4.py",
        core / "config.py", core / "llm.py", core / "providers.py", core / "local_runtime.py",
        core / "streaming.py", core / "performance.py",
        java / "MainActivity.java", java / "BridgeRuntime.java", html_path, bridge / "build.gradle",
    )
    for path in required:
        if not path.is_file():
            fail("FILE", f"missing {path.relative_to(stage)}")
    if blockers:
        print("\n".join(blockers))
        return 1

    py_files = sorted(core.glob("*.py"))
    for path in py_files:
        try:
            ast.parse(read(path), filename=str(path))
        except SyntaxError as exc:
            fail("PY_PARSE", f"{path.name}: {exc}")
    for path, cls in ((core / "hub.py", "Runtime"), (core / "chat.py", "FurinaChat")):
        dup = duplicate_methods(path, cls)
        if dup:
            fail("DUP_METHOD", f"{path.name}:{cls} -> {dup}")

    version = read(core / "version.py")
    cli = read(core / "cli.py")
    tui = read(core / "tui.py")
    routing = read(core / "routing.py")
    hub = read(core / "hub.py")
    chat = read(core / "chat.py")
    persona = read(core / "persona.py")
    relationship = read(core / "relationship_v4.py")
    local_models = read(core / "local_models.py")
    config = read(core / "config.py")
    llm = read(core / "llm.py")
    providers_src = read(core / "providers.py")
    local_runtime = read(core / "local_runtime.py")
    performance = read(core / "performance.py")
    streaming = read(core / "streaming.py")
    build = read(bridge / "build.gradle")
    main_java = read(java / "MainActivity.java")
    runtime_java = read(java / "BridgeRuntime.java")
    page = read(html_path)
    page_low = page.lower()

    # Product surface: one companion, four Termux entries, no maintenance-only memory screen.
    for marker in ('data-view="relationship"', "Mode hubungan", "Mode DEKAT aktif", "setRelationshipMode", "Tambah Qwen dari Hugging Face", "Core aktif"):
        if marker in page:
            fail("PRODUCT_SURFACE", f"Android exposes `{marker}`")
    if 'id="relationship"' not in page or 'aria-hidden="true"' not in page:
        fail("RELATIONSHIP_STATE", "internal relationship state is not hidden")
    if 'data-view="memory"' in page or '<section id="memory" class="view hidden" aria-hidden="true">' not in page:
        fail("MEMORY_SURFACE", "Memory/Psyche is not internal-only on FurinaHub")
    if "pasangan" not in (persona + relationship + tui).lower():
        fail("PARTNER_BASELINE", "partner-first identity is missing")
    if "mode pertemanan" in relationship.lower() or "fase pertemanan" in relationship.lower():
        fail("RELATIONSHIP_COPY", "obsolete friendship-mode wording remains")

    run_tui = top_level_function(core / "tui.py", "run_tui")
    main_menu = top_level_function(core / "tui.py", "_main_menu")
    provider_menu = top_level_function(core / "tui.py", "_providers")
    settings = top_level_function(core / "tui.py", "_settings")
    if tui.count("def run_tui():") != 1 or not run_tui:
        fail("TUI_ENTRY", "TUI has shadowed or missing run_tui entrypoints")
    if '["Chat", "Provider & Model", "Pengaturan", "Exit"]' not in main_menu:
        fail("TUI_MENU", "top-level Termux menu is not the four-item final surface")
    if "_auto_start_local" in run_tui:
        fail("MODEL_PREWARM", "opening `furina` still prepares a local model")
    for item in ("Identitas", "Kontrol perangkat", "Sistem", "Backup", "Update & Recovery"):
        if item not in settings:
            fail("SETTINGS_GROUP", f"missing nested Settings item {item}")
    if "Unduh" not in provider_menu or "Pilih" not in provider_menu or "Aktif" not in provider_menu:
        fail("MODEL_STATE", "Termux local models do not expose Unduh/Pilih/Aktif states")
    if "AUTO" in provider_menu or 'routing_mode = "auto"' in provider_menu:
        fail("AUTO_ROUTE", "AUTO is still user-selectable in Termux")
    if "sedang disiapkan di background" not in provider_menu:
        fail("PREWARM_UX", "local selection does not expose background preparation")

    # Model catalog is intentionally tiny, pinned and on-demand.
    try:
        catalog = literal_assignment(core / "local_models.py", "CATALOG")
    except Exception as exc:
        catalog = ()
        fail("MODEL_CATALOG", str(exc))
    expected_models = {
        "wifugpt-1.7b-q4km": ("wifuGPT-1.7B-Q4_K_M.gguf", 1107408480, "d256ccbab62bbd80064ecb73be0512b0b8d16bc930d5ae9ac8079216b88b2b54"),
        "qwen3-1.7b-heretic-q5km": ("Qwen3-1.7B-heretic.i1-Q5_K_M.gguf", 1257880480, "f2b0b5f7fead5fdcfb79f783b96465fe97f56361b11e8de972afd71b9ba994a2"),
    }
    if len(catalog) != 2:
        fail("MODEL_CATALOG", f"expected exactly two local chat models, got {len(catalog)}")
    for item in catalog:
        wanted = expected_models.get(item.get("id"))
        if not wanted:
            fail("MODEL_CATALOG", f"unsupported catalog id {item.get('id')}")
            continue
        filename, size, sha = wanted
        if item.get("file") != filename or item.get("size_bytes") != size or item.get("sha256") != sha:
            fail("MODEL_PIN", f"metadata changed for {item.get('id')}")
        if not str(item.get("url", "")).startswith("https://huggingface.co/") or "/resolve/" not in str(item.get("url", "")):
            fail("MODEL_PIN", f"model URL is not pinned for {item.get('id')}")
    for marker in ("Range", "verify_download", "sha256", "size_bytes", "GGUF"):
        if marker not in local_models:
            fail("MODEL_VERIFY", f"download verifier missing {marker}")
    if "MODEL_CATALOG = tuple(dict(item) for item in LOCAL_MODEL_CATALOG)" not in hub:
        fail("MODEL_PARITY", "FurinaHub does not consume the shared catalog")
    if not all(token in page for token in ("localModelRows", "downloadLocalModel", "selectLocalModel", "selectOnlineModel", "Unduh", "Pilih", "Aktif")):
        fail("MODEL_PARITY", "FurinaHub model surface is incomplete")
    if "['local','auto','online']" in page or "AUTO · online" in page:
        fail("AUTO_ROUTE", "AUTO remains exposed in FurinaHub")
    if "Qwen_Qwen3.5-4B-Q4_K_M.gguf" in hub or "Qwen3.5-4B" in page:
        fail("LEGACY_MODEL", "Deckard/old 4B catalog remains active")

    routing_tree = ast.parse(routing, filename=str(core / "routing.py"))
    routing_chat_nodes = [node for node in ast.walk(routing_tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "chat"]
    chat_fn = ""
    if len(routing_chat_nodes) == 1:
        node = routing_chat_nodes[0]
        chat_fn = "\n".join(routing.splitlines()[node.lineno - 1 : node.end_lineno])
    else:
        fail("ROUTING", f"expected one routing chat method, got {len(routing_chat_nodes)}")
    if 'routing_mode in {"auto", "online"}' in chat_fn or "falling back to local" in chat_fn.lower():
        fail("ROUTING", "online route can still silently fall back to local")
    if 'self.cfg.routing_mode == "local"' not in chat_fn or "self._ensure_local(" not in chat_fn:
        fail("ROUTING", "single selected local route is not prepared on demand")

    # Local Performance V2: latency optimizations may not change model identity
    # or reduce the established response-quality budget.
    for marker in (
        "context_size: int = 4096", "threads: int = 5", "max_tokens: int = 2048",
        "response_continuations: int = 4", "cache_reuse: int = 256",
        "keep_warm_seconds: int = 600", 'flash_attention: str = "auto"',
    ):
        if marker not in config:
            fail("LOCAL_PERF_CONFIG", f"missing {marker}")
    for marker in ("get_local_runtime", "ensure_ready(timeout=45.0", "prewarm_local", "stop_local", "def cancel(self)"):
        if marker not in routing:
            fail("LOCAL_RUNTIME", f"routing missing {marker}")
    if "timeout=135" in routing:
        fail("LOCAL_RUNTIME", "legacy multi-minute local wait remains")
    for marker in ("min(timeout, 45.0)", "_idle_watchdog", "--cache-reuse", "--flash-attn", "_flag_supported"):
        if marker not in local_runtime:
            fail("LOCAL_RUNTIME", f"runtime missing {marker}")
    if "for threads in (4, 5, 6)" not in performance:
        fail("LOCAL_TUNER", "4/5/6 thread tuner is missing")
    for marker in ("FURINA_LLAMA_SERVER_OPENCL", "FURINA_LLAMA_SERVER_VULKAN", 'return shutil.which("llama-server") if backend == "cpu" else None'):
        if marker not in performance:
            fail("LOCAL_ACCEL", f"accelerator gate missing {marker}")
    if "SmoothStream" not in llm or '"stream": bool(on_token) and not json_mode' not in llm:
        fail("LOCAL_STREAM", "local native stream path is incomplete")
    if "SmoothStream" not in providers_src or '"stream": bool(on_token) and not json_mode' not in providers_src:
        fail("ONLINE_STREAM", "online native stream path is incomplete")
    if "Never fail over after visible text has streamed" not in routing:
        fail("ONLINE_STREAM", "visible-stream provider failover boundary is missing")
    for marker in ("Never delay the first token/chunk", "frame_ms", "max_buffer_chars"):
        if marker not in streaming:
            fail("STREAM_RENDER", f"stream coalescer missing {marker}")
    if "action:'prewarm'" not in page or "Menyiapkan model lokal" not in page:
        fail("HUB_PREWARM", "FurinaHub does not trigger/show local background preparation")
    if 'action == "stop-generation"' not in hub:
        fail("STOP_GENERATION", "Core stop-generation endpoint missing")

    # Android boundary and native-feeling WebView behavior.
    for marker in ("setSupportZoom(false)", "setBuiltInZoomControls(false)", "setDisplayZoomControls(false)"):
        if marker not in main_java and marker not in runtime_java:
            warn("WEBVIEW_ZOOM", f"could not prove {marker}")
    for marker in ("setAllowFileAccess(false)", "setAllowContentAccess(false)"):
        if marker not in main_java and marker not in runtime_java:
            warn("WEBVIEW_BOUNDARY", f"could not prove {marker}")
    if "furina-apk-confirm" not in main_java:
        fail("APK_CONFIRM", "APK install confirmation hook is missing")

    for group, alternatives in {
        "image attachment": ("image", "gambar"),
        "image crop/editor": ("crop", "pangkas"),
        "image draw/markup": ("draw", "coret"),
        "message long press": ("longpress", "long-press", "pointerdown", "contextmenu"),
        "provider test": ("test", "uji"),
        "model download": ("download", "unduh"),
        "plugin": ("plugin", "openconnector"),
    }.items():
        if not any(token in page_low for token in alternatives):
            warn("UX_CAPABILITY", f"could not prove {group}")

    # Performance: one ordered worker with bounded backlog.
    if "threading.Thread" in chat and "_background_queue" not in chat:
        fail("CHAT_WORKER", "background work is not queue-backed")
    if "queue.Queue(maxsize=64)" not in chat:
        fail("QUEUE_BOUND", "background memory queue is not bounded at 64")
    if "self._background_queue.put((user_text, answer, turn))" not in chat:
        fail("QUEUE_LOSSLESS", "ordered background enqueue contract changed")

    # CLI/TUI update uses the local updater first; recovery is fallback only.
    if 'shutil.which("furina-update")' not in cli:
        fail("CLI_UPDATE", "TUI/CLI update bypasses the local single client")
    if not all(token in tui for token in ("_display_name()", "By Wynn", "─")):
        fail("TUI_BASE", "Furina Lite header language is incomplete")

    installer = read(project / "install.sh")
    mirror = read(repo / "furina-agent-termux/experiments/furina-agent-final/install.sh")
    if installer != mirror:
        fail("INSTALL_MIRROR", "installer mirrors differ")
    active = "\n".join(line for line in installer.splitlines() if not line.lstrip().startswith("#"))
    for marker in ('FURINA_INSTALLER_ID="furinahub-core-bootstrap-v2"', 'UPDATE_PROTOCOL="furina-update/1"', 'FURINA_RUNTIME_CONTRACT="furina-runtime/v2"'):
        if marker not in installer:
            fail("BOOTSTRAP", f"missing {marker}")
    for marker in ('FURINA_UPDATER_GENERATION="27"', 'VERSION="1.0.2"', 'DEPENDENCY_REVISION="2026.08.24-r42"', 'RUNTIME_CONTRACT="furina-runtime/v8-local-performance-v2"'):
        if marker not in active:
            fail("BOOTSTRAP", f"active bootstrap missing {marker}")
    if "BODY_BLOB=" in active or "runtime-r38/install-body.sh" in active:
        fail("BOOTSTRAP", "legacy patch chain remains active")
    if not all(token in installer for token in ("render_header", "render_step", "Furina", "By Wynn")):
        fail("INSTALL_TUI", "installer does not use Furina terminal presentation")
    if ".gguf" in active.lower() or "wifugpt" in active.lower():
        fail("FIRST_INSTALL_MODEL", "bootstrap still contains a local model download")

    # Audit exact update client to be published, including destructive uninstall.
    with tempfile.TemporaryDirectory(prefix="furina-final-audit-") as td:
        output = Path(td) / "furina-update.py"
        subprocess.run([
            sys.executable, str(project / "overrides/runtime-private-1.0.1/build_client.py"),
            str(project / "overrides/runtime-r39/update_client.py"), str(output),
        ], check=True, stdout=subprocess.DEVNULL)
        updater = read(output)
    for marker in ("safe_extract", "commit_snapshot", "installed_is_current", "maybe_reexec", "pending_apk_bundle", "class TerminalUI", 'CLIENT_VERSION = "1.2.0"', '"hapus"', "def uninstall_termux"):
        if marker not in updater:
            fail("UPDATER", f"missing {marker}")
    if "wifuGPT-1.7B-Q4_K_M.gguf" in updater or "Qwen3-1.7B-heretic" in updater:
        fail("FIRST_INSTALL_MODEL", "updater embeds chat-model download policy")
    update_fn = updater[updater.index("def update("):updater.index("def uninstall_termux(")]
    if "ensure_termux_packages()" in update_fn:
        fail("NOOP_COST", "top-level updater still reconciles packages")
    for marker in ("core_current = installed_is_current", "if core_current and not force_core", "ensure_openconnector("):
        if marker not in update_fn:
            fail("NOOP_FASTPATH", f"missing {marker}")
    if update_fn.index("if core_current and not force_core") > update_fn.index("ensure_openconnector("):
        fail("NOOP_FASTPATH", "Plugin setup occurs before no-op return")
    if "FURINAHUB_MACHINE_PROGRESS" not in updater or "FURINA_FORCE_TUI" not in updater:
        fail("UPDATE_TUI", "interactive/machine progress split missing")
    uninstall_fn = updater[updater.index("def uninstall_termux("):updater.index("def status(")]
    for marker in ('shutil.rmtree(root, ignore_errors=True)', '"furina-openconnector"', '"hapus"', "APK FurinaHub di Android tidak dihapus"):
        if marker not in uninstall_fn:
            fail("UNINSTALL", f"uninstall contract missing {marker}")
    if "pkg uninstall" in uninstall_fn or "apt remove" in uninstall_fn:
        fail("UNINSTALL", "uninstall attempts to remove shared Termux packages")

    # Documentation is release truth.
    readme = read(project / "README.md")
    install_md = read(project / "INSTALL.md")
    for value in (manifest["version"], manifest["bridge_version"], manifest["dependency_revision"], manifest["bundle_id"], manifest["update_client_version"], manifest["runtime_contract"]):
        if str(value) not in readme:
            fail("DOC_VERSION", f"README missing {value}")
    stable_cmd = "curl -fsSL https://github.com/WynnDev-rill/furina/releases/download/furina-update-stable/furina-install.sh | bash"
    for marker in (stable_cmd, "furina update", "furina recover", "furina repair", "hapus furina", "wifuGPT 1.7B Q4_K_M", "Qwen3 1.7B Heretic Q5_K_M", "tidak mengunduh model"):
        if marker not in install_md:
            fail("INSTALL_DOC", f"installation guide missing {marker}")

    # Cross-surface version and bundle identity.
    for expected, where, code in (
        (manifest["version"], version, "CORE_VERSION"),
        (manifest["bridge_version"], build, "APK_VERSION"),
        (str(manifest["bridge_version_code"]), build, "APK_CODE"),
        (manifest["bundle_id"], main_java + runtime_java, "BUNDLE_ID"),
        (manifest["bridge_version"], hub, "BRIDGE_TARGET"),
    ):
        if str(expected) not in where:
            fail(code, f"manifest value {expected} not reflected in staged runtime")

    print("FURINA FINAL AUDIT")
    print(f"Python modules checked: {len(py_files)}")
    print(f"Blockers: {len(blockers)}")
    for item in blockers:
        print(f"BLOCKER {item}")
    print(f"Warnings: {len(warnings)}")
    for item in warnings:
        print(f"WARN {item}")
    if blockers:
        return 1
    print("FURINA_PRIVATE_FINAL_AUDIT_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
