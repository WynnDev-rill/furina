#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import os
import re
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
        core / "version.py", core / "cli.py", core / "tui.py", core / "hub.py",
        core / "chat.py", core / "persona.py", core / "relationship_v4.py",
        java / "MainActivity.java", java / "BridgeRuntime.java", html_path, bridge / "build.gradle",
    )
    for path in required:
        if not path.is_file():
            fail("FILE", f"missing {path.relative_to(stage)}")
    if blockers:
        print("\n".join(blockers)); return 1

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
    hub = read(core / "hub.py")
    chat = read(core / "chat.py")
    persona = read(core / "persona.py")
    relationship = read(core / "relationship_v4.py")
    build = read(bridge / "build.gradle")
    main_java = read(java / "MainActivity.java")
    runtime_java = read(java / "BridgeRuntime.java")
    page = read(html_path)
    page_low = page.lower()

    # Product: one companion surface, partner-first state, no exposed internal mode.
    for marker in ('data-view="relationship"', "Mode hubungan", "Mode DEKAT aktif", "setRelationshipMode", "Tambah Qwen dari Hugging Face", "Core aktif"):
        if marker in page:
            fail("PRODUCT_SURFACE", f"Android exposes `{marker}`")
    if 'id="relationship"' not in page or 'aria-hidden="true"' not in page:
        fail("RELATIONSHIP_STATE", "internal relationship state is not hidden")
    if "pasangan" not in (persona + relationship + tui).lower():
        fail("PARTNER_BASELINE", "partner-first identity is missing")
    if "mode pertemanan" in relationship.lower() or "fase pertemanan" in relationship.lower():
        fail("RELATIONSHIP_COPY", "obsolete friendship-mode wording remains")

    # Android boundary and native-feeling WebView behavior.
    for marker in ("setSupportZoom(false)", "setBuiltInZoomControls(false)", "setDisplayZoomControls(false)"):
        if marker not in main_java and marker not in runtime_java:
            warn("WEBVIEW_ZOOM", f"could not prove {marker}")
    for marker in ("setAllowFileAccess(false)", "setAllowContentAccess(false)"):
        if marker not in main_java and marker not in runtime_java:
            warn("WEBVIEW_BOUNDARY", f"could not prove {marker}")
    if "furina-apk-confirm" not in main_java:
        fail("APK_CONFIRM", "APK install confirmation hook is missing")

    # Full FurinaHub capabilities required by the final private surface.
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

    # CLI/TUI update must use local updater first; recovery is fallback only.
    if 'shutil.which("furina-update")' not in cli:
        fail("CLI_UPDATE", "TUI/CLI update still bypasses local single client")
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
    if "BODY_BLOB=" in active or "runtime-r38/install-body.sh" in active:
        fail("BOOTSTRAP", "legacy patch chain remains active")
    if not all(token in installer for token in ("render_header", "render_step", "Furina", "By Wynn")):
        fail("INSTALL_TUI", "installer does not use Furina terminal presentation")

    # Generate and audit the exact updater that will be published.
    with tempfile.TemporaryDirectory(prefix="furina-final-audit-") as td:
        output = Path(td) / "furina-update.py"
        subprocess.run([
            sys.executable, str(project / "overrides/runtime-final/build_client.py"),
            str(project / "overrides/runtime-r39/update_client.py"), str(output),
        ], check=True, stdout=subprocess.DEVNULL)
        updater = read(output)
    for marker in ("safe_extract", "commit_snapshot", "installed_is_current", "maybe_reexec", "pending_apk_bundle", "class TerminalUI", 'CLIENT_VERSION = "1.1.0"'):
        if marker not in updater:
            fail("UPDATER", f"missing {marker}")
    update_fn = updater[updater.index("def update("):updater.index("def status(")]
    if "ensure_termux_packages()" in update_fn:
        fail("NOOP_COST", "top-level updater still reconciles packages")
    for marker in ("core_current = installed_is_current", "if core_current and not force_core", "ensure_openconnector("):
        if marker not in update_fn:
            fail("NOOP_FASTPATH", f"missing {marker}")
    if update_fn.index("if core_current and not force_core") > update_fn.index("ensure_openconnector("):
        fail("NOOP_FASTPATH", "Plugin setup occurs before no-op return")
    if "FURINAHUB_MACHINE_PROGRESS" not in updater or "FURINA_FORCE_TUI" not in updater:
        fail("UPDATE_TUI", "interactive/machine progress split missing")

    # Docs are release truth, not historical RC notes.
    readme = read(project / "README.md")
    install_md = read(project / "INSTALL.md")
    for value in (manifest["version"], manifest["bridge_version"], manifest["dependency_revision"], manifest["bundle_id"]):
        if str(value) not in readme:
            fail("DOC_VERSION", f"README missing {value}")
    stable_cmd = "curl -fsSL https://github.com/WynnDev-rill/furina/releases/download/furina-update-stable/furina-install.sh | bash"
    if stable_cmd not in install_md or "furina update" not in install_md or "furina recover" not in install_md or "furina repair" not in install_md:
        fail("INSTALL_DOC", "installation/update/recovery guide incomplete")

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
