#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path


INSTALLER = Path("experiments/furina-agent-final/install.sh")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text and old not in text:
        return text
    if text.count(old) != 1:
        raise SystemExit(f"installer hotfix marker mismatch {label}: {text.count(old)}")
    return text.replace(old, new, 1)


def main() -> None:
    text = INSTALLER.read_text(encoding="utf-8")

    pin = 'UI_RC12_TRANSFORM_BLOB="07d10d060f1e0e3e7b299e57661f2967ae7986d2"\n'
    pin_new = pin + (
        'UI_RC12_POSTFIX_URL="$BASE/overrides/apply-ui-rc12-postfix.py"\n'
        'UI_RC12_POSTFIX_BLOB="965ecc146715dc5daa2ec702cf37ca6749654df6"\n'
    )
    if "UI_RC12_POSTFIX_URL=" not in text:
        text = replace_once(text, pin, pin_new, "postfix pin")

    loop_old = '    "$UI_RC12_TRANSFORM_URL|$UI_RC12_TRANSFORM_BLOB|apply-ui-rc12.py"; do\n'
    loop_new = (
        '    "$UI_RC12_TRANSFORM_URL|$UI_RC12_TRANSFORM_BLOB|apply-ui-rc12.py" \\\n'
        '    "$UI_RC12_POSTFIX_URL|$UI_RC12_POSTFIX_BLOB|apply-ui-rc12-postfix.py"; do\n'
    )
    if 'apply-ui-rc12-postfix.py"; do' not in text:
        text = replace_once(text, loop_old, loop_new, "postfix transform sequence")

    deps_old = '''if [[ "$MODE" == "install" ]]; then
  run_quiet "Menyiapkan Termux" 8 env DEBIAN_FRONTEND=noninteractive pkg update -y
fi
run_quiet "Menyiapkan runtime Furina" 18 env DEBIAN_FRONTEND=noninteractive pkg install -y python python-pip git cmake ninja clang make curl ccache util-linux termux-tools patch gum
run_quiet "Menyiapkan tampilan" 22 python -m pip install --quiet 'rich>=13.9,<15' 'textual==8.2.8'
'''
    deps_new = '''# Install/update is intentionally self-contained. Every required Termux and
# Python dependency is reconciled automatically so a beginner does not need to
# diagnose missing packages manually.
run_quiet "Menyinkronkan Termux" 8 env DEBIAN_FRONTEND=noninteractive pkg update -y
run_quiet "Memasang dependency Furina" 18 env DEBIAN_FRONTEND=noninteractive pkg install -y python python-pip git cmake ninja clang make curl ccache coreutils tar gzip util-linux termux-tools patch gum
run_quiet "Menyiapkan dependency Python" 22 python -m pip install --quiet --upgrade 'rich>=13.9,<15' 'textual==8.2.8'

verify_dependencies() {
  local cmd
  for cmd in python git cmake ninja clang make curl sha256sum tar gzip patch gum; do
    command -v "$cmd" >/dev/null 2>&1 || { echo "Dependency wajib tidak ditemukan: $cmd" >&2; return 1; }
  done
  python -c 'import rich, textual; assert textual.__version__ == "8.2.8"'
}
run_quiet "Memeriksa dependency" 24 verify_dependencies
'''
    if "verify_dependencies() {" not in text:
        text = replace_once(text, deps_old, deps_new, "dependency bootstrap")

    swap_old = '''  rm -rf "$ROOT/core.new"
  mkdir -p "$ROOT/core.new"
  cp -R "$SRC/core/furina_agent" "$ROOT/core.new/"
'''
    swap_new = '''  # Validate the entire staged Core before replacing the active installation.
  # Syntax/import failures therefore leave the previous Core untouched.
  PYTHONPATH="$SRC/core" python -m compileall -q "$SRC/core/furina_agent"
  PYTHONPATH="$SRC/core" python -c 'import rich, textual, furina_agent.tui; from furina_agent.chat_surface import run_chat_surface; from furina_agent.tool_runtime import AgentToolRuntime'

  rm -rf "$ROOT/core.new"
  mkdir -p "$ROOT/core.new"
  cp -R "$SRC/core/furina_agent" "$ROOT/core.new/"
  PYTHONPATH="$ROOT/core.new" python -m compileall -q "$ROOT/core.new/furina_agent"
'''
    if 'PYTHONPATH="$SRC/core" python -m compileall' not in text:
        text = replace_once(text, swap_old, swap_new, "staged transactional verification")

    required = [
        "apply-ui-rc12-postfix.py",
        "verify_dependencies() {",
        "coreutils tar gzip",
        'PYTHONPATH="$SRC/core" python -m compileall',
        "furina_agent.tui",
    ]
    missing = [item for item in required if item not in text]
    if missing:
        raise SystemExit("installer hotfix incomplete: " + ", ".join(missing))

    INSTALLER.write_text(text, encoding="utf-8")
    print("Furina self-contained transactional installer patch: OK")


if __name__ == "__main__":
    main()
