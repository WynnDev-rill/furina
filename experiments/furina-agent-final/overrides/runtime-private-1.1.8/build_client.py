#!/usr/bin/env python3
"""Build updater 1.4.0 with only supported Termux launchers."""
from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / "runtime-private-1.1.7" / "build_client.py"
spec = importlib.util.spec_from_file_location("furina_117_builder", BASE)
if spec is None or spec.loader is None:
    raise SystemExit("base builder unavailable")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def replace_function(text: str, name: str, replacement: str) -> str:
    tree = ast.parse(text)
    nodes = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name]
    if len(nodes) != 1:
        raise SystemExit(f"{name}: expected one top-level function, got {len(nodes)}")
    node = nodes[0]; lines = text.splitlines(keepends=True)
    start = sum(len(line) for line in lines[:node.lineno - 1]); end = sum(len(line) for line in lines[:node.end_lineno])
    return text[:start] + replacement.rstrip() + "\n" + text[end:]


def build(base: Path, output: Path) -> None:
    module.build(base, output)
    text = output.read_text(encoding="utf-8")
    text = text.replace('CLIENT_VERSION = "1.3.0"', 'CLIENT_VERSION = "1.4.0"', 1)
    text = replace_function(text, "launcher_texts", r'''def launcher_texts(root: Path) -> dict[str,str]:
    update_py=root/"updater/update_client.py"; shell="#!/data/data/com.termux/files/usr/bin/bash\nset -euo pipefail\n"
    return {
      "furina":shell+'PREFIX="${PREFIX:-/data/data/com.termux/files/usr}"\nif [[ "${1:-}" == update ]]; then shift; exec "$PREFIX/bin/furina-update" "$@"; fi\nexec "$PREFIX/bin/furina-real" "$@"\n',
      "furina-real":shell+'ROOT="$HOME/.furina-agent"\nexport FURINA_HOME="$ROOT"\nexport PYTHONPATH="$ROOT/core${PYTHONPATH:+:$PYTHONPATH}"\nexec python -m furina_agent "$@"\n',
      "furina-update":shell+f'CLIENT="{update_py}"\nif [[ ! -s "$CLIENT" ]]; then RECOVERY="$HOME/.furina-agent/run/furina-install.sh"; mkdir -p "$(dirname "$RECOVERY")"; curl -fsSL --retry 4 --retry-all-errors "{DEFAULT_CHANNEL.rsplit("/",1)[0]}/furina-install.sh" -o "$RECOVERY"; exec bash "$RECOVERY" --update "$@"; fi\nexec python "$CLIENT" update "$@"\n',
      "hapus":shell+f'if [[ "${{1:-}}" != "furina" ]]; then echo "Gunakan: hapus furina" >&2; exit 2; fi\nshift\nexec python "{update_py}" uninstall "$@"\n',
    }''')
    text = replace_function(text, "install_launchers", r'''def install_launchers(root: Path) -> None:
    bindir=prefix_dir()/"bin"; bindir.mkdir(parents=True,exist_ok=True)
    for name,value in launcher_texts(root).items(): atomic_text(bindir/name,value,0o755)
    # Historical Hub/APK commands are deliberately removed during migration.
    for retired in ("furina-hub","furina-apk-confirm","furina-update-apk"):
        try: (bindir/retired).unlink()
        except OSError: pass''')
    text = replace_function(text, "build_parser", r'''def build_parser() -> argparse.ArgumentParser:
    parser=argparse.ArgumentParser(prog="furina-update"); sub=parser.add_subparsers(dest="command")
    for name in ("update","repair"):
        item=sub.add_parser(name); item.add_argument("--channel-file"); item.add_argument("--force",action="store_true")
    uninstall=sub.add_parser("uninstall"); uninstall.add_argument("--yes",action="store_true")
    sub.add_parser("status"); return parser''')
    compile(text, str(output), "exec")
    output.write_text(text, encoding="utf-8"); output.chmod(0o755)


def main() -> int:
    if len(sys.argv) not in {2, 3}:
        print(f"usage: {sys.argv[0]} [base-update-client.py] OUTPUT", file=sys.stderr); return 2
    base, output = (Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()) if len(sys.argv) == 3 else (module.module.module.module.module.module.DEFAULT_BASE, Path(sys.argv[1]).resolve())
    build(base, output); print("FURINA_TERMUX_117_UPDATER_BUILD_OK"); return 0


if __name__ == "__main__":
    raise SystemExit(main())
