#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import sys


def once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        if new in text:
            return text
        raise SystemExit(f"RC47 marker missing: {label}")
    return text.replace(old, new, 1)


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("usage: apply.py <termux-root>")
    root = Path(sys.argv[1]).resolve()
    app = root / "bridge/app"
    htmlp = app / "src/main/assets/furinahub/index.html"
    gradlep = app / "build.gradle"
    hubp = root / "core/furina_agent/hub.py"
    updaterp = app / "src/main/java/com/wynndev/furinaagentbridge/BridgeUpdater.java"
    for p in (htmlp, gradlep, hubp, updaterp):
        if not p.is_file():
            raise SystemExit(f"RC47 source missing: {p}")

    gradle = gradlep.read_text(encoding="utf-8")
    gradle = once(gradle, "versionCode 10046", "versionCode 10047", "versionCode")
    gradle = once(gradle, "versionName '1.0.0-rc46'", "versionName '1.0.0-rc47'", "versionName")

    hub = hubp.read_text(encoding="utf-8")
    hub = once(hub, '"bridge_target": "1.0.0-rc46"', '"bridge_target": "1.0.0-rc47"', "bridge target")

    updater = updaterp.read_text(encoding="utf-8")
    updater = once(updater, "FurinaHub-Updater/12", "FurinaHub-Updater/13", "updater agent")

    html = htmlp.read_text(encoding="utf-8")
    helper = "function editorSetStatus(text,kind){const stage=document.getElementById('editorStage');if(!stage)return;let el=document.getElementById('editorDecodeStatus');if(!text){el?.remove();return}if(!el){el=document.createElement('div');el.id='editorDecodeStatus';stage.appendChild(el)}el.className='editorDecodeStatus'+(kind==='error'?' error':'');el.textContent=text}\n"
    if "function editorSetStatus(" not in html:
        marker = "function editorDataUrl(source)"
        pos = html.find(marker)
        if pos < 0:
            raise SystemExit("RC47 editorDataUrl boundary missing")
        html = html[:pos] + helper + html[pos:]

    checks = (
        "versionCode 10047",
        "versionName '1.0.0-rc47'",
        '"bridge_target": "1.0.0-rc47"',
        "FurinaHub-Updater/13",
        "function editorSetStatus(text,kind)",
        "editorSetStatus('Menyiapkan gambar…')",
        "img.src=editorDataUrl(editorSource)",
        "async function openImageEditor()",
    )
    combined = "\n".join((gradle, hub, updater, html))
    missing = [x for x in checks if x not in combined]
    if missing:
        raise SystemExit("RC47 markers missing: " + ", ".join(missing))

    # There must be exactly one helper definition so click runtime cannot fail
    # from either a missing helper or accidental duplicate declaration.
    if html.count("function editorSetStatus(") != 1:
        raise SystemExit("RC47 editorSetStatus definition count invalid")

    gradlep.write_text(gradle, encoding="utf-8")
    hubp.write_text(hub, encoding="utf-8")
    updaterp.write_text(updater, encoding="utf-8")
    htmlp.write_text(html, encoding="utf-8")
    print("FURINAHUB_ANDROID_RC47_EDITOR_CLICK_OK")


if __name__ == "__main__":
    main()
