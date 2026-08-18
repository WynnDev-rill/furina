#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import shutil
import sys


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text and old not in text:
        return text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"Android RC40 marker mismatch: {label} ({count})")
    return text.replace(old, new, 1)


def install_uploaded_launcher_icon(app: Path, source: Path) -> None:
    if not source.is_file() or source.stat().st_size < 4096:
        raise SystemExit(f"Uploaded FurinaHub icon missing: {source}")
    raw = source.read_bytes()
    # The uploaded file is named .png but currently contains JPEG bytes. Keep
    # the exact artwork while using an Android resource extension that matches
    # the encoded data so aapt does not mis-parse it.
    if not raw.startswith(b"\xff\xd8\xff"):
        raise SystemExit("furinahub.png no longer contains the expected JPEG artwork")

    res = app / "src/main/res"
    drawable = res / "drawable-nodpi"
    xxx = res / "mipmap-xxxhdpi"
    anydpi = res / "mipmap-anydpi-v26"
    for directory in (drawable, xxx, anydpi):
        directory.mkdir(parents=True, exist_ok=True)

    for stale in (
        drawable / "furinahub_launcher_foreground.webp",
        drawable / "furinahub_launcher_foreground.png",
        xxx / "ic_launcher.webp",
        xxx / "ic_launcher.png",
        xxx / "ic_launcher_round.webp",
        xxx / "ic_launcher_round.png",
    ):
        stale.unlink(missing_ok=True)

    shutil.copyfile(source, drawable / "furinahub_launcher_foreground.jpg")
    shutil.copyfile(source, xxx / "ic_launcher.jpg")
    shutil.copyfile(source, xxx / "ic_launcher_round.jpg")

    adaptive = '''<?xml version="1.0" encoding="utf-8"?>
<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">
    <background android:drawable="@color/furinahub_icon_background" />
    <foreground android:drawable="@drawable/furinahub_launcher_foreground" />
</adaptive-icon>
'''
    (anydpi / "ic_launcher.xml").write_text(adaptive, encoding="utf-8")
    (anydpi / "ic_launcher_round.xml").write_text(adaptive, encoding="utf-8")


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("usage: apply.py <termux-root>")
    root = Path(sys.argv[1]).resolve()
    app = root / "bridge/app"
    html_path = app / "src/main/assets/furinahub/index.html"
    gradle_path = app / "build.gradle"
    hub_path = root / "core/furina_agent/hub.py"
    updater_path = app / "src/main/java/com/wynndev/furinaagentbridge/BridgeUpdater.java"
    source_icon = Path(__file__).resolve().parents[4] / "furinahub.png"
    for path in (html_path, gradle_path, hub_path, updater_path):
        if not path.is_file():
            raise SystemExit(f"Android RC40 source missing: {path}")

    gradle = gradle_path.read_text(encoding="utf-8")
    gradle = replace_once(gradle, "versionCode 10039", "versionCode 10040", "versionCode")
    gradle = replace_once(gradle, "versionName '1.0.0-rc39'", "versionName '1.0.0-rc40'", "versionName")
    gradle_path.write_text(gradle, encoding="utf-8")

    hub = hub_path.read_text(encoding="utf-8")
    if '"bridge_target": "1.0.0-rc39"' in hub:
        hub = hub.replace('"bridge_target": "1.0.0-rc39"', '"bridge_target": "1.0.0-rc40"')
    if '"bridge_target": "1.0.0-rc40"' not in hub:
        raise SystemExit("Android RC40 bridge target missing")
    hub_path.write_text(hub, encoding="utf-8")

    updater = updater_path.read_text(encoding="utf-8")
    updater = replace_once(updater, "FurinaHub-Updater/5", "FurinaHub-Updater/6", "updater agent")
    updater_path.write_text(updater, encoding="utf-8")

    install_uploaded_launcher_icon(app, source_icon)

    html = html_path.read_text(encoding="utf-8")
    css = r'''
/* RC40: crop overlay must never darken the pixels inside the selected crop. */
.cropOverlay{
  background-color:transparent!important;
  background-blend-mode:normal!important;
  touch-action:none!important;
  box-sizing:border-box!important;
}
.cropOverlay .cropHandle{touch-action:none!important}
.editorStage #editorCanvas{
  opacity:1!important;
  filter:none!important;
  background:transparent!important;
}
'''
    html = replace_once(html, "</style>", css + "\n</style>", "transparent crop CSS")

    old_wire_start = html.find("function wireCropOverlay(){")
    old_wire_end = html.find("function wireEditorCanvas(", old_wire_start)
    if old_wire_start < 0 or old_wire_end < 0:
        raise SystemExit("Android RC40 crop handler boundary missing")
    crop_handler = r'''function wireCropOverlay(){const o=document.getElementById('cropOverlay'),c=document.getElementById('editorCanvas');if(!o||!c)return;let drag=null;const finish=e=>{if(!drag)return;try{o.releasePointerCapture(e.pointerId)}catch(_){}drag=null};o.onpointerdown=e=>{if(editorTool!=='crop'||!editorCrop)return;const handle=e.target?.dataset?.handle||'move';drag={mode:handle,start:canvasPoint(c,e),rect:{...editorCrop},pointerId:e.pointerId};try{o.setPointerCapture(e.pointerId)}catch(_){}e.preventDefault();e.stopPropagation()};o.onpointermove=e=>{if(!drag||editorTool!=='crop'||e.pointerId!==drag.pointerId)return;const p=canvasPoint(c,e),dx=p.x-drag.start.x,dy=p.y-drag.start.y,r={...drag.rect},min=Math.max(28,Math.min(c.width,c.height)*.08);if(drag.mode==='move'){r.x=Math.max(0,Math.min(c.width-r.w,r.x+dx));r.y=Math.max(0,Math.min(c.height-r.h,r.y+dy))}else{let x1=r.x,y1=r.y,x2=r.x+r.w,y2=r.y+r.h;if(drag.mode.includes('w'))x1=Math.max(0,Math.min(x2-min,x1+dx));if(drag.mode.includes('e'))x2=Math.min(c.width,Math.max(x1+min,x2+dx));if(drag.mode.includes('n'))y1=Math.max(0,Math.min(y2-min,y1+dy));if(drag.mode.includes('s'))y2=Math.min(c.height,Math.max(y1+min,y2+dy));r={x:x1,y:y1,w:x2-x1,h:y2-y1}}editorCrop=r;syncEditorLayers();e.preventDefault();e.stopPropagation()};o.onpointerup=finish;o.onpointercancel=finish}
'''
    html = html[:old_wire_start] + crop_handler + html[old_wire_end:]

    apply_start = html.find("function applyImageEdit(){")
    auto_grow = html.find("function autoGrow(", apply_start)
    if apply_start < 0 or auto_grow < 0:
        raise SystemExit("Android RC40 editor apply boundary missing")
    apply_editor = r'''function applyImageEdit(){const src=document.getElementById('editorCanvas'),draw=document.getElementById('drawCanvas');if(!src||!draw||!src.width||!src.height)return;const merged=document.createElement('canvas');merged.width=src.width;merged.height=src.height;const m=merged.getContext('2d');m.clearRect(0,0,merged.width,merged.height);m.drawImage(src,0,0);redrawDrawCanvas();m.drawImage(draw,0,0);const r=editorCrop||{x:0,y:0,w:src.width,h:src.height},sx=Math.max(0,Math.min(src.width-1,Math.round(r.x))),sy=Math.max(0,Math.min(src.height-1,Math.round(r.y))),sw=Math.max(1,Math.min(src.width-sx,Math.round(r.w))),sh=Math.max(1,Math.min(src.height-sy,Math.round(r.h))),out=document.createElement('canvas');out.width=sw;out.height=sh;out.getContext('2d').drawImage(merged,sx,sy,sw,sh,0,0,sw,sh);const sourceMime=(editorSource?.mime||'image/jpeg').toLowerCase(),preserveAlpha=sourceMime==='image/png'||sourceMime==='image/webp';let mime=preserveAlpha?'image/png':'image/jpeg',quality=.94,data=out.toDataURL(mime,quality),base64=data.split(',')[1];if(Math.floor(base64.length*.75)>5800000){const flat=document.createElement('canvas');flat.width=out.width;flat.height=out.height;const f=flat.getContext('2d');f.fillStyle='#fff';f.fillRect(0,0,flat.width,flat.height);f.drawImage(out,0,0);mime='image/jpeg';data=flat.toDataURL(mime,.9);base64=data.split(',')[1]}const ext=mime==='image/png'?'.png':'.jpg';selectedAttachment={kind:'image',name:(editorSource?.name||'gambar').replace(/\.[^.]+$/,'')+'-edit'+ext,mime,base64,size:Math.floor(base64.length*.75)};showAttachment();closeImageEditor()}'''
    html = html[:apply_start] + apply_editor + "\n" + html[auto_grow:]
    html_path.write_text(html, encoding="utf-8")

    combined = gradle + "\n" + hub + "\n" + updater + "\n" + html
    checks = (
        "versionCode 10040",
        "versionName '1.0.0-rc40'",
        '"bridge_target": "1.0.0-rc40"',
        "FurinaHub-Updater/6",
        "RC40: crop overlay must never darken",
        "preserveAlpha=sourceMime==='image/png'||sourceMime==='image/webp'",
        "f.fillStyle='#fff'",
        "function wireCropOverlay(){",
    )
    missing = [item for item in checks if item not in combined]
    if missing:
        raise SystemExit(f"Android RC40 marker hilang: {missing}")
    print("FURINAHUB_ANDROID_RC40_MEDIA_ICON_OK")


if __name__ == "__main__":
    main()
