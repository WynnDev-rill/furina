#!/usr/bin/env python3
from __future__ import annotations

import ast
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent.parent
BASE_BUILDER = PROJECT / "runtime-final/build_client.py"
DEFAULT_BASE = PROJECT / "runtime-r39/update_client.py"


def replace_function(text: str, name: str, replacement: str) -> str:
    tree = ast.parse(text)
    nodes = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name]
    if len(nodes) != 1:
        raise SystemExit(f"{name}: expected one function, got {len(nodes)}")
    node = nodes[0]
    lines = text.splitlines(keepends=True)
    start = sum(len(x) for x in lines[: node.lineno - 1])
    end = sum(len(x) for x in lines[: node.end_lineno])
    return text[:start] + replacement.rstrip() + "\n" + text[end:]


def build(base: Path, output: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="furina-update-private-101-") as td:
        staged = Path(td) / "client.py"
        subprocess.run([sys.executable, str(BASE_BUILDER), str(base), str(staged)], check=True)
        text = staged.read_text(encoding="utf-8")

    text = text.replace('CLIENT_VERSION = "1.1.0"', 'CLIENT_VERSION = "1.2.0"', 1)
    text = replace_function(
        text,
        "launcher_texts",
'''def launcher_texts(root: Path) -> dict[str, str]:
    update_py = root / "updater/update_client.py"
    shell = "#!/data/data/com.termux/files/usr/bin/bash\\nset -euo pipefail\\n"
    return {
        "furina": shell + 'PREFIX="${PREFIX:-/data/data/com.termux/files/usr}"\\nif [[ "${1:-}" == update ]]; then shift; exec "$PREFIX/bin/furina-update" "$@"; fi\\nexec "$PREFIX/bin/furina-real" "$@"\\n',
        "furina-real": shell + 'ROOT="$HOME/.furina-agent"\\nexport FURINA_HOME="$ROOT"\\nexport PYTHONPATH="$ROOT/core${PYTHONPATH:+:$PYTHONPATH}"\\nexec python -m furina_agent "$@"\\n',
        "furina-hub": shell + 'ROOT="$HOME/.furina-agent"\\nexport FURINA_HOME="$ROOT"\\nexport PYTHONPATH="$ROOT/core${PYTHONPATH:+:$PYTHONPATH}"\\nexec python -m furina_agent.hub "$@"\\n',
        "furina-update": shell + f'CLIENT="{update_py}"\\nif [[ ! -s "$CLIENT" ]]; then\\n  RECOVERY="$HOME/.furina-agent/run/furina-install.sh"\\n  mkdir -p "$(dirname "$RECOVERY")"\\n  curl -fsSL --retry 4 --retry-all-errors "{DEFAULT_CHANNEL.rsplit("/",1)[0]}/furina-install.sh" -o "$RECOVERY"\\n  exec bash "$RECOVERY" --update "$@"\\nfi\\nexec python "$CLIENT" update "$@"\\n',
        "furina-update-apk": shell + f'exec python "{update_py}" apk-only "$@"\\n',
        "furina-apk-confirm": shell + f'exec python "{update_py}" confirm-apk "$@"\\n',
        "hapus": shell + f'if [[ "${{1:-}}" != "furina" ]]; then echo "Gunakan: hapus furina" >&2; exit 2; fi\\nshift\\nexec python "{update_py}" uninstall "$@"\\n',
    }''',
    )

    insert = '''\n\ndef uninstall_termux(args: argparse.Namespace) -> int:\n    root = root_dir()\n    if not args.yes:\n        if not sys.stdin.isatty():\n            print("Gunakan `hapus furina --yes` untuk penghapusan non-interaktif.", file=sys.stderr)\n            return 2\n        answer = input("Hapus seluruh Furina di Termux termasuk memori, model, provider, dan backup? Ketik HAPUS: ").strip()\n        if answer != "HAPUS":\n            print("Dibatalkan.")\n            return 0\n    # Stop only Furina-owned processes whose pid files live under FURINA_HOME.\n    import signal\n    run_dir = root / "run"\n    if run_dir.is_dir():\n        for pid_file in run_dir.glob("*.pid"):\n            try:\n                pid = int(pid_file.read_text(encoding="utf-8").strip())\n                if pid > 1:\n                    os.kill(pid, signal.SIGTERM)\n            except Exception:\n                pass\n    # Remove Furina-owned data and downloaded APK copies, but never shared\n    # Termux packages or global Termux settings.\n    shutil.rmtree(root, ignore_errors=True)\n    for pattern in ("FurinaHub.apk", "FurinaHub-v*.apk"):\n        for apk in Path.home().glob(pattern):\n            try: apk.unlink()\n            except OSError: pass\n    bindir = prefix_dir() / "bin"\n    for name in ("furina", "furina-real", "furina-hub", "furina-update", "furina-update-apk", "furina-apk-confirm", "furina-openconnector", "hapus"):\n        try: (bindir / name).unlink()\n        except OSError: pass\n    print("Furina sudah dihapus dari Termux. APK FurinaHub di Android tidak dihapus.")\n    return 0\n'''
    marker = "\ndef status(args: argparse.Namespace) -> int:"
    if marker not in text:
        raise SystemExit("status marker missing")
    text = text.replace(marker, insert + marker, 1)

    text = replace_function(
        text,
        "build_parser",
'''def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="furina-update")
    sub = parser.add_subparsers(dest="command")
    for name in ("update", "repair", "apk-only"):
        p = sub.add_parser(name)
        p.add_argument("--channel-file")
        p.add_argument("--force", action="store_true")
    confirm = sub.add_parser("confirm-apk")
    confirm.add_argument("bundle_id")
    uninstall = sub.add_parser("uninstall")
    uninstall.add_argument("--yes", action="store_true")
    sub.add_parser("status")
    return parser''',
    )
    text = replace_function(
        text,
        "main",
'''def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if not args.command:
        args = parser.parse_args(["update"])
    if args.command == "confirm-apk":
        return confirm_apk(root_dir(), args.bundle_id)
    if args.command == "status":
        return status(args)
    if args.command == "uninstall":
        return uninstall_termux(args)
    return update(args)''',
    )

    ast.parse(text, filename=str(output))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding="utf-8")
    output.chmod(0o755)


def main() -> int:
    if len(sys.argv) not in {2, 3}:
        print(f"usage: {sys.argv[0]} [base-update-client.py] OUTPUT", file=sys.stderr)
        return 2
    if len(sys.argv) == 2:
        base, output = DEFAULT_BASE, Path(sys.argv[1]).resolve()
    else:
        base, output = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
    build(base, output)
    print("FURINA_PRIVATE_1_0_1_UPDATER_BUILD_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
