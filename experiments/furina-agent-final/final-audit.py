#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import os
import re
import sys
from pathlib import Path


def fail(items: list[str], code: str, detail: str) -> None:
    items.append(f"{code}: {detail}")


def warn(items: list[str], code: str, detail: str) -> None:
    items.append(f"{code}: {detail}")


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
    blockers: list[str] = []
    warnings: list[str] = []

    manifest_path = project / "manifest.json"
    manifest = json.loads(read(manifest_path))
    core = stage / "core/furina_agent"
    bridge = stage / "bridge/app"
    java = bridge / "src/main/java/com/wynndev/furinaagentbridge"
    html = bridge / "src/main/assets/furinahub/index.html"
    required_paths = (
        core / "version.py", core / "cli.py", core / "tui.py", core / "hub.py",
        core / "chat.py", core / "persona.py", core / "relationship_v4.py",
        java / "MainActivity.java", java / "BridgeRuntime.java", html, bridge / "build.gradle",
    )
    for path in required_paths:
        if not path.is_file():
            fail(blockers, "FILE", f"missing {path.relative_to(stage)}")
    if blockers:
        print("FINAL_AUDIT_BLOCKERS")
        print("\n".join(blockers))
        return 1

    # Architecture / maintainability: every shipped Python module must parse.
    py_files = sorted(core.glob("*.py"))
    for path in py_files:
        try:
            ast.parse(read(path), filename=str(path))
        except SyntaxError as exc:
            fail(blockers, "PY_PARSE", f"{path.name}: {exc}")
    for path, cls in ((core / "hub.py", "Runtime"), (core / "chat.py", "FurinaChat")):
        dup = duplicate_methods(path, cls)
        if dup:
            fail(blockers, "DUP_METHOD", f"{path.name}:{cls} -> {dup}")

    version = read(core / "version.py")
    build = read(bridge / "build.gradle")
    main_java = read(java / "MainActivity.java")
    runtime_java = read(java / "BridgeRuntime.java")
    page = read(html)
    tui = read(core / "tui.py")
    cli = read(core / "cli.py")
    hub = read(core / "hub.py")
    chat = read(core / "chat.py")
    persona = read(core / "persona.py")
    relationship = read(core / "relationship_v4.py")

    # Product truth: one companion, one state, no friendship-mode fork.
    forbidden_product = (
        'data-view="relationship"', "Mode hubungan", "Mode DEKAT aktif",
        "setRelationshipMode", "Tambah Qwen dari Hugging Face", "Core aktif",
    )
    for marker in forbidden_product:
        if marker in page:
            fail(blockers, "PRODUCT_SURFACE", f"Android still exposes `{marker}`")
    if 'id="relationship"' not in page or 'aria-hidden="true"' not in page:
        fail(blockers, "RELATIONSHIP_STATE", "internal relationship state is not hidden from primary navigation")
    if "pasangan" not in (persona + relationship + tui).lower():
        fail(blockers, "PARTNER_BASELINE", "partner-first identity not present")
    if "friend" in relationship.lower() or "pertemanan" in relationship.lower():
        warn(warnings, "RELATIONSHIP_COPY", "friendship wording still exists in relationship engine")

    # Android WebView/native boundaries and no accidental zoom/browser feel.
    zoom_false = (
        "setSupportZoom(false)", "setBuiltInZoomControls(false)", "setDisplayZoomControls(false)"
    )
    for marker in zoom_false:
        if marker not in main_java and marker not in runtime_java:
            warn(warnings, "WEBVIEW_ZOOM", f"could not prove {marker}")
    for marker in ("setAllowFileAccess(false)", "setAllowContentAccess(false)"):
        if marker not in main_java and marker not in runtime_java:
            warn(warnings, "WEBVIEW_BOUNDARY", f"could not prove {marker}")
    if "furina-apk-confirm" not in main_java:
        fail(blockers, "APK_CONFIRM", "native app launch does not confirm installed APK bundle")

    # Chat/media UX expected from the current product direction.
    page_low = page.lower()
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
            warn(warnings, "UX_CAPABILITY", f"could not prove {group} from final HTML")

    # Runtime / performance: foreground chat must not spawn one worker per turn.
    if "threading.Thread" in chat and "_background_queue" not in chat:
        fail(blockers, "CHAT_WORKER", "background chat work is not queue-backed")
    queue_calls = re.findall(r"queue\.Queue\(([^)]*)\)", chat)
    if queue_calls and any(not item.strip() for item in queue_calls):
        warn(warnings, "QUEUE_BOUND", "chat background queue is unbounded; verify microbatch drain under long sessions")

    # Update architecture: one client, atomic snapshot, recovery compatibility.
    installer = read(project / "install.sh")
    updater = read(project / "overrides/runtime-r39/update_client.py")
    installer_active = "\n".join(line for line in installer.splitlines() if not line.lstrip().startswith("#"))
    required_update = (
        'UPDATE_PROTOCOL="furina-update/1"', 'CHANNEL_URL="$STABLE_RELEASE/channel.json"',
        'FURINA_INSTALLER_ID="furinahub-core-bootstrap-v2"',
        'FURINA_RUNTIME_CONTRACT="furina-runtime/v2"',
    )
    for marker in required_update:
        if marker not in installer:
            fail(blockers, "BOOTSTRAP", f"missing compatibility/update marker {marker}")
    if "BODY_BLOB=" in installer_active or "runtime-r38/install-body.sh" in installer_active:
        fail(blockers, "BOOTSTRAP", "legacy patch-chain code remains active")
    for marker in ("safe_extract", "commit_snapshot", "installed_is_current", "maybe_reexec", "pending_apk_bundle"):
        if marker not in updater:
            fail(blockers, "UPDATER", f"missing {marker}")
    if '"furina-update"' not in updater or '"furina-hub"' not in updater or '"furina-real"' not in updater:
        fail(blockers, "LAUNCHERS", "launcher set is incomplete")

    # Efficiency: no-op should not reinstall optional heavy dependencies.
    update_fn = updater[updater.find("def update("):]
    idx_openconnector = update_fn.find("ensure_openconnector(")
    idx_core = update_fn.find("install_core(")
    if 0 <= idx_openconnector < idx_core:
        warn(warnings, "NOOP_COST", "optional OpenConnector check/install runs before Core no-op decision")
    idx_packages = update_fn.find("ensure_termux_packages(")
    if 0 <= idx_packages < idx_core:
        warn(warnings, "NOOP_COST", "package reconciliation runs before Core no-op decision")

    # Installation/update presentation should match Furina's existing TUI language.
    tui_tokens = ("FURINA", "COMPANION", "By Wynn")
    if not all(token in tui for token in tui_tokens):
        fail(blockers, "TUI_BASE", "current Furina TUI identity could not be verified")
    if "PROGRESS " in updater and not any(token in updater for token in ("╭", "progress bar", "render_tui", "TerminalUI")):
        warn(warnings, "UPDATE_TUI", "interactive updater still exposes machine-style progress instead of Furina TUI")
    if not any(token in installer for token in ("╭", "FURINA  COMPANION", "draw_", "render_")):
        warn(warnings, "INSTALL_TUI", "bootstrap has no Furina-styled interactive loading surface")

    # Docs must describe what is actually shipped, not old RC state.
    readme = read(project / "README.md")
    install_md = read(project / "INSTALL.md")
    current_core = manifest.get("version", "")
    current_hub = manifest.get("bridge_version", "")
    current_rev = manifest.get("dependency_revision", "")
    if current_core not in readme or current_hub not in readme or current_rev not in readme:
        fail(blockers, "DOC_VERSION", "README current-version block is stale relative to manifest")
    if "curl -fsSL https://github.com/WynnDev-rill/furina/releases/download/furina-update-stable/furina-install.sh | bash" not in install_md:
        fail(blockers, "INSTALL_DOC", "stable one-line install command missing")
    if "furina update" not in install_md or "furina recover" not in install_md:
        fail(blockers, "INSTALL_DOC", "update/recovery commands are incomplete")

    # Cross-surface version/bundle truth.
    for expected, where, code in (
        (str(manifest["version"]), version, "CORE_VERSION"),
        (str(manifest["bridge_version"]), build, "APK_VERSION"),
        (str(manifest["bundle_id"]), main_java + runtime_java, "BUNDLE_ID"),
        (str(manifest["bridge_version"]), hub, "BRIDGE_TARGET"),
    ):
        if expected not in where:
            fail(blockers, code, f"manifest value {expected} is not reflected in staged runtime")

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
    print("FURINA_FINAL_AUDIT_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
