from __future__ import annotations

import hashlib
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable

ROOT = Path(os.environ.get("FURINA_HOME") or (Path.home() / ".furina-agent")).expanduser().resolve()
MODELS_DIR = ROOT / "models"

CATALOG = (
    {
        "id": "wifugpt-1.7b-q4km",
        "name": "wifuGPT 1.7B Q4_K_M",
        "file": "wifuGPT-1.7B-Q4_K_M.gguf",
        "url": "https://huggingface.co/backpropSukuna/wifuGPT-1.7B-GGUF/resolve/8e9d8eb2c95e5f917af75f2e4c23c019ddb4798e/wifuGPT-1.7B-Q4_K_M.gguf?download=true",
        "sha256": "d256ccbab62bbd80064ecb73be0512b0b8d16bc930d5ae9ac8079216b88b2b54",
        "size_bytes": 1107408480,
        "size_label": "1,03 GB",
        "category": "chat",
        "purpose": "Percakapan lokal ringan dan ekspresif.",
    },
    {
        "id": "qwen3-1.7b-heretic-q5km",
        "name": "Qwen3 1.7B Heretic Q5_K_M",
        "file": "Qwen3-1.7B-heretic.i1-Q5_K_M.gguf",
        "url": "https://huggingface.co/mradermacher/Qwen3-1.7B-heretic-i1-GGUF/resolve/e2716dd20c87c9bf221059b942be6d33cbf4d647/Qwen3-1.7B-heretic.i1-Q5_K_M.gguf?download=true",
        "sha256": "f2b0b5f7fead5fdcfb79f783b96465fe97f56361b11e8de972afd71b9ba994a2",
        "size_bytes": 1257880480,
        "size_label": "1,17 GB",
        "category": "chat",
        "purpose": "Percakapan lokal multibahasa dengan quantization Q5_K_M.",
    },
)

# Files previously owned by Furina's old local-chat catalog. Arbitrary user GGUF
# files are intentionally never deleted by migration.
LEGACY_CATALOG_FILES = (
    "Qwen3.5-4B-Deckard-HERETIC-UNCENSORED-Thinking.i1-Q4_K_M.gguf",
    "Qwen3.5-4B-Deckard-HERETIC-UNCENSORED-Thinking-Q4_K_M.gguf",
    "Qwen_Qwen3.5-4B-Q4_K_M.gguf",
    "Qwen_Qwen3-4B-Q4_K_M.gguf",
    "Qwen2.5-0.5B-Instruct-Q4_K_M.gguf",
)


def catalog_item(catalog_id: str) -> dict:
    item = next((entry for entry in CATALOG if entry["id"] == catalog_id), None)
    if not item:
        raise ValueError("model lokal tidak dikenal")
    return dict(item)


def path_for(item: dict) -> Path:
    return MODELS_DIR / str(item["file"])


def _is_gguf(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            return handle.read(4) == b"GGUF"
    except OSError:
        return False


def installed(item: dict) -> bool:
    path = path_for(item)
    try:
        return path.is_file() and path.stat().st_size == int(item["size_bytes"]) and _is_gguf(path)
    except OSError:
        return False


def catalog_state(active_path: str = "") -> list[dict]:
    active = None
    try:
        active = Path(active_path).expanduser().resolve() if active_path else None
    except Exception:
        active = None
    rows = []
    for source in CATALOG:
        item = dict(source)
        target = path_for(item)
        item["path"] = str(target)
        item["installed"] = installed(item)
        item["active"] = bool(active and item["installed"] and active == target.resolve())
        rows.append(item)
    return rows


def retire_legacy_catalog(cfg=None) -> bool:
    """Remove only Furina-owned legacy catalog files and repair stale selection."""
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    removed: set[Path] = set()
    for name in LEGACY_CATALOG_FILES:
        target = MODELS_DIR / name
        part = MODELS_DIR / (name + ".part")
        if target.exists():
            target.unlink(missing_ok=True)
            removed.add(target.resolve())
        part.unlink(missing_ok=True)
    if cfg is None:
        return bool(removed)
    changed = False
    selected = None
    try:
        selected = Path(str(getattr(cfg, "model_path", ""))).expanduser().resolve() if getattr(cfg, "model_path", "") else None
    except Exception:
        selected = None
    if selected in removed or (selected and selected.name in LEGACY_CATALOG_FILES):
        cfg.model_path = ""
        cfg.routing_mode = "online"
        changed = True
    if getattr(cfg, "routing_mode", "online") == "auto":
        cfg.routing_mode = "online"
        changed = True
    if getattr(cfg, "auto_start", False):
        cfg.auto_start = False
        changed = True
    return changed


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_download(path: Path, item: dict) -> None:
    size = path.stat().st_size if path.exists() else 0
    if size != int(item["size_bytes"]):
        raise RuntimeError(f"ukuran model tidak cocok: {size} != {item['size_bytes']}")
    if not _is_gguf(path):
        raise RuntimeError("file unduhan bukan GGUF yang valid")
    actual = _sha256(path)
    if actual.lower() != str(item["sha256"]).lower():
        raise RuntimeError("SHA-256 model tidak cocok; file tidak diaktifkan")


def download_model(catalog_id: str, progress: Callable[[int, int, int, bool], None] | None = None) -> Path:
    """Download a pinned catalog model with resume, exact-size and SHA-256 verification."""
    item = catalog_item(catalog_id)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    target = path_for(item)
    if installed(item):
        if progress:
            progress(int(item["size_bytes"]), int(item["size_bytes"]), 100, False)
        return target
    part = target.with_name(target.name + ".part")
    expected = int(item["size_bytes"])
    if part.exists() and part.stat().st_size > expected:
        part.unlink(missing_ok=True)

    last: Exception | None = None
    for attempt in range(1, 5):
        offset = part.stat().st_size if part.is_file() else 0
        headers = {"User-Agent": "Furina/1.0.1", "Cache-Control": "no-cache"}
        if offset:
            headers["Range"] = f"bytes={offset}-"
        try:
            req = urllib.request.Request(str(item["url"]), headers=headers)
            response = urllib.request.urlopen(req, timeout=60)
            code = int(getattr(response, "status", response.getcode()) or 200)
            if offset and code != 206:
                response.close()
                part.unlink(missing_ok=True)
                offset = 0
                req = urllib.request.Request(str(item["url"]), headers={"User-Agent": "Furina/1.0.1", "Cache-Control": "no-cache"})
                response = urllib.request.urlopen(req, timeout=60)
            received = offset
            resumed = bool(offset)
            with response, part.open("ab" if offset else "wb") as out:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    out.write(chunk)
                    received += len(chunk)
                    if received > expected:
                        raise RuntimeError("ukuran model melebihi metadata katalog")
                    if progress:
                        progress(received, expected, min(99, int(received * 100 / expected)), resumed)
            if received != expected:
                raise RuntimeError(f"unduhan belum lengkap: {received}/{expected} byte")
            verify_download(part, item)
            os.replace(part, target)
            os.chmod(target, 0o600)
            if progress:
                progress(expected, expected, 100, resumed)
            return target
        except (urllib.error.URLError, TimeoutError, OSError, RuntimeError) as exc:
            last = exc
            if attempt == 4:
                break
            time.sleep(float(attempt) * 1.5)
    raise RuntimeError(f"unduhan model gagal setelah retry: {last}")
