#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import sys


def once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        if new in text:
            return text
        raise SystemExit(f"RC48 marker missing: {label}")
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
            raise SystemExit(f"RC48 source missing: {p}")

    gradle = gradlep.read_text(encoding="utf-8")
    gradle = once(gradle, "versionCode 10047", "versionCode 10048", "versionCode")
    gradle = once(gradle, "versionName '1.0.0-rc47'", "versionName '1.0.0-rc48'", "versionName")

    hub = hubp.read_text(encoding="utf-8")
    hub = once(hub, '"bridge_target": "1.0.0-rc47"', '"bridge_target": "1.0.0-rc48"', "bridge target")

    updater = updaterp.read_text(encoding="utf-8")
    updater = once(updater, "FurinaHub-Updater/13", "FurinaHub-Updater/14", "updater agent")

    html = htmlp.read_text(encoding="utf-8")
    old_stage = ".editorStage{flex:1;min-height:0;display:grid;place-items:center;overflow:hidden;padding:10px}"
    new_stage = ".editorStage{position:relative;flex:1;min-height:0;display:grid;place-items:center;overflow:hidden;padding:10px}"
    html = once(html, old_stage, new_stage, "editor stage containing block")

    # Make the preview's local coordinate system explicit. syncEditorLayers() already
    # computes left/top relative to editorStage, so the preview must be positioned
    # relative to editorStage as well.
    marker = "/* RC46: direct decoded IMG preview. Canvas is geometry/output only. */"
    if marker not in html:
        raise SystemExit("RC48 direct-preview CSS marker missing")

    checks = (
        "versionCode 10048",
        "versionName '1.0.0-rc48'",
        '"bridge_target": "1.0.0-rc48"',
        "FurinaHub-Updater/14",
        ".editorStage{position:relative;",
        ".editorPreviewImage{position:absolute!important;",
        "img.src=editorDataUrl(editorSource)",
        "stage.insertBefore(img,c.nextSibling)",
        "const cr=c.getBoundingClientRect(),sr=stage.getBoundingClientRect()",
    )
    combined = "\n".join((gradle, hub, updater, html))
    missing = [x for x in checks if x not in combined]
    if missing:
        raise SystemExit("RC48 markers missing: " + ", ".join(missing))

    forbidden = (
        "createImageBitmap(packed.blob)",
        "URL.createObjectURL(blob)",
    )
    present = [x for x in forbidden if x in html]
    if present:
        raise SystemExit("RC48 obsolete decode path returned: " + ", ".join(present))

    gradlep.write_text(gradle, encoding="utf-8")
    hubp.write_text(hub, encoding="utf-8")
    updaterp.write_text(updater, encoding="utf-8")
    htmlp.write_text(html, encoding="utf-8")
    print("FURINAHUB_ANDROID_RC48_EDITOR_POSITION_OK")


if __name__ == "__main__":
    main()
