#!/usr/bin/env python3
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/furina-agent-rc54-validate/termux")
CORE = ROOT / "core/furina_agent"
MODELS = CORE / "local_models.py"
LLM = CORE / "llm.py"
RUNTIME = CORE / "local_runtime.py"


def replace_function(path: Path, name: str, source: str) -> None:
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(path))
    nodes = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name]
    if len(nodes) != 1:
        raise SystemExit(f"{path.name}:{name}: expected one function, got {len(nodes)}")
    node = nodes[0]
    lines = text.splitlines(keepends=True)
    start = sum(len(x) for x in lines[: node.lineno - 1])
    end = sum(len(x) for x in lines[: node.end_lineno])
    path.write_text(text[:start] + source.rstrip() + "\n" + text[end:], encoding="utf-8")


def replace_method(path: Path, class_name: str, name: str, source: str) -> None:
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(path))
    cls = next((n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == class_name), None)
    if cls is None:
        raise SystemExit(f"missing class {class_name}")
    nodes = [n for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name]
    if len(nodes) != 1:
        raise SystemExit(f"{path.name}:{class_name}.{name}: expected one method, got {len(nodes)}")
    node = nodes[0]
    lines = text.splitlines(keepends=True)
    start_line = min([node.lineno] + [d.lineno for d in node.decorator_list])
    start = sum(len(x) for x in lines[: start_line - 1])
    end = sum(len(x) for x in lines[: node.end_lineno])
    path.write_text(text[:start] + source.rstrip() + "\n" + text[end:], encoding="utf-8")


# ---------------------------------------------------------------------------
# Third local model. It remains on-demand; no install/update path downloads it.
# The source file is SHA-256 pinned. Hugging Face Xet does not expose a stable
# exact byte count in the public model card, so Furina learns Content-Length /
# Content-Range during download and persists a verified sidecar after hashing.
# ---------------------------------------------------------------------------
text = MODELS.read_text(encoding="utf-8")
if "qwen3-4b-2507-uncensored-q4km" not in text:
    marker = "\n)\n\n# Files previously owned by Furina's old local-chat catalog."
    if marker not in text:
        raise SystemExit("local model catalog boundary missing")
    entry = r'''
    {
        "id": "qwen3-4b-2507-uncensored-q4km",
        "name": "Qwen3 4B Instruct 2507 Uncensored Q4_K_M",
        "file": "Qwen3-4B-2507-Instruct-Uncensored-HauhauCS-Aggressive-Q4_K_M.gguf",
        "url": "https://huggingface.co/HauhauCS/Qwen3-4B-2507-Instruct-Uncensored-HauhauCS-Aggressive/resolve/main/Qwen3-4B-2507-Instruct-Uncensored-HauhauCS-Aggressive-Q4_K_M.gguf?download=true",
        "sha256": "6615b7b5184931e4df9c6d0ae9cd29ca9319b73908d4423283d4cc401a12a1cd",
        "size_bytes": 0,
        "size_hint_bytes": 2500000000,
        "size_label": "2,50 GB",
        "category": "chat-quality",
        "purpose": "Mode Quality: Qwen3 4B Instruct 2507 uncensored untuk percakapan companion yang lebih natural.",
    },
'''
    text = text.replace(marker, entry + marker, 1)
if "import json\n" not in text:
    text = text.replace("import hashlib\n", "import hashlib\nimport json\nimport re\n", 1)
MODELS.write_text(text, encoding="utf-8")

helpers = r'''

def _verified_marker(path: Path) -> Path:
    return path.with_name(path.name + ".furina-verified.json")


def _marker_valid(path: Path, item: dict) -> bool:
    marker = _verified_marker(path)
    try:
        raw = json.loads(marker.read_text(encoding="utf-8"))
        return (
            path.is_file()
            and path.stat().st_size == int(raw.get("size", -1))
            and str(raw.get("sha256", "")).lower() == str(item["sha256"]).lower()
            and _is_gguf(path)
        )
    except Exception:
        return False


def _write_verified_marker(path: Path, item: dict) -> None:
    payload = {"id": item["id"], "sha256": item["sha256"], "size": path.stat().st_size}
    marker = _verified_marker(path)
    marker.write_text(json.dumps(payload, separators=(",", ":")) + "\n", encoding="utf-8")
    os.chmod(marker, 0o600)
'''
model_text = MODELS.read_text(encoding="utf-8")
if "def _verified_marker" not in model_text:
    needle = "\ndef installed(item: dict) -> bool:\n"
    pos = model_text.find(needle)
    if pos < 0:
        raise SystemExit("installed function marker missing")
    model_text = model_text[:pos] + helpers + model_text[pos:]
    MODELS.write_text(model_text, encoding="utf-8")

replace_function(MODELS, "installed", r'''def installed(item: dict) -> bool:
    path = path_for(item)
    try:
        expected = int(item.get("size_bytes") or 0)
        if expected:
            return path.is_file() and path.stat().st_size == expected and _is_gguf(path)
        return _marker_valid(path, item)
    except OSError:
        return False''')

replace_function(MODELS, "verify_download", r'''def verify_download(path: Path, item: dict) -> int:
    size = path.stat().st_size if path.exists() else 0
    expected = int(item.get("size_bytes") or 0)
    if expected and size != expected:
        raise RuntimeError(f"ukuran model tidak cocok: {size} != {expected}")
    if not _is_gguf(path):
        raise RuntimeError("file unduhan bukan GGUF yang valid")
    actual = _sha256(path)
    if actual.lower() != str(item["sha256"]).lower():
        raise RuntimeError("SHA-256 model tidak cocok; file tidak diaktifkan")
    return size''')

replace_function(MODELS, "download_model", r'''def download_model(catalog_id: str, progress: Callable[[int, int, int, bool], None] | None = None) -> Path:
    """Resumable download with GGUF + SHA verification; remote size may be learned dynamically."""
    item = catalog_item(catalog_id)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    target = path_for(item)
    expected = int(item.get("size_bytes") or 0)
    hint = int(item.get("size_hint_bytes") or expected or 0)
    if installed(item):
        total = target.stat().st_size
        if progress:
            progress(total, total, 100, False)
        return target
    part = target.with_name(target.name + ".part")
    if expected and part.exists() and part.stat().st_size > expected:
        part.unlink(missing_ok=True)

    last: Exception | None = None
    for attempt in range(1, 5):
        offset = part.stat().st_size if part.is_file() else 0
        headers = {"User-Agent": "Furina/1.0.9", "Cache-Control": "no-cache"}
        if offset:
            headers["Range"] = f"bytes={offset}-"
        try:
            req = urllib.request.Request(str(item["url"]), headers=headers)
            response = urllib.request.urlopen(req, timeout=60)
            code = int(getattr(response, "status", response.getcode()) or 200)
            if offset and code != 206:
                response.close(); part.unlink(missing_ok=True); offset = 0
                req = urllib.request.Request(str(item["url"]), headers={"User-Agent": "Furina/1.0.9", "Cache-Control": "no-cache"})
                response = urllib.request.urlopen(req, timeout=60)
                code = int(getattr(response, "status", response.getcode()) or 200)

            remote_total = expected
            content_range = str(response.headers.get("Content-Range") or "")
            match = re.search(r"/(\d+)\s*$", content_range)
            if match:
                remote_total = int(match.group(1))
            else:
                try:
                    length = int(response.headers.get("Content-Length") or 0)
                except Exception:
                    length = 0
                if length:
                    remote_total = (offset + length) if offset and code == 206 else length
            total_for_progress = remote_total or hint

            received = offset; resumed = bool(offset)
            with response, part.open("ab" if offset else "wb") as out:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    out.write(chunk); received += len(chunk)
                    if remote_total and received > remote_total:
                        raise RuntimeError("ukuran model melebihi metadata remote")
                    if progress:
                        percent = min(99, int(received * 100 / total_for_progress)) if total_for_progress else 0
                        progress(received, total_for_progress, percent, resumed)
            if remote_total and received != remote_total:
                raise RuntimeError(f"unduhan belum lengkap: {received}/{remote_total} byte")

            actual_size = verify_download(part, item)
            os.replace(part, target); os.chmod(target, 0o600)
            _write_verified_marker(target, item)
            if progress:
                progress(actual_size, actual_size, 100, resumed)
            return target
        except (urllib.error.URLError, TimeoutError, OSError, RuntimeError) as exc:
            last = exc
            if attempt == 4:
                break
            time.sleep(float(attempt) * 1.5)
    raise RuntimeError(f"unduhan model gagal setelah retry: {last}")''')

# Qwen3 4B Instruct should use Qwen3 non-thinking sampling rather than the
# broader wifuGPT roleplay profile inherited by the previous fallback branch.
llm_text = LLM.read_text(encoding="utf-8")
needle = 'qwen_heretic = "qwen3-1.7b-heretic" in model_hint\n'
if needle not in llm_text:
    raise SystemExit("Qwen Heretic sampling marker missing")
llm_text = llm_text.replace(needle, needle + '        qwen_quality = "qwen3-4b-2507-instruct-uncensored" in model_hint\n', 1)
llm_text = llm_text.replace('elif qwen_heretic:\n            top_p = 0.80; top_k = 20; min_p = 0.0', 'elif qwen_heretic or qwen_quality:\n            top_p = 0.80; top_k = 20; min_p = 0.0', 1)
LLM.write_text(llm_text, encoding="utf-8")

# The source model explicitly recommends Jinja chat-template handling. Gate the
# flag by llama.cpp capability so older Termux builds still start safely.
runtime_text = RUNTIME.read_text(encoding="utf-8")
if '"--jinja"' not in runtime_text:
    marker = '        if _flag_supported(help_text, "--flash-attn"):\n'
    if marker not in runtime_text:
        raise SystemExit("runtime optional flag marker missing")
    runtime_text = runtime_text.replace(marker, '        if _flag_supported(help_text, "--jinja"):\n            cmd.append("--jinja")\n' + marker, 1)
    RUNTIME.write_text(runtime_text, encoding="utf-8")

for path in (MODELS, LLM, RUNTIME):
    compile(path.read_text(encoding="utf-8"), str(path), "exec")
print("FURINA_PRIVATE_1_0_9_QWEN4B_QUALITY_OK")
