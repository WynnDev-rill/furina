#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import re
import shutil
import sys


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text and old not in text:
        return text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"RC39 marker mismatch: {label} ({count})")
    return text.replace(old, new, 1)


def replace_js_function(text: str, name: str, next_name: str, replacement: str) -> str:
    marker = f"function {name}("
    start = text.find(marker)
    if start >= 6 and text[start - 6:start] == "async ":
        start -= 6
    end = text.find(f"function {next_name}(", max(start, 0) + 1)
    if end >= 6 and text[end - 6:end] == "async ":
        end -= 6
    if start < 0 or end < 0 or end <= start:
        raise SystemExit(f"RC39 JS boundary mismatch: {name} -> {next_name}")
    return text[:start] + replacement.rstrip() + "\n" + text[end:]


def install_launcher_icon(app: Path, source: Path) -> None:
    if not source.is_file() or source.stat().st_size < 4096:
        raise SystemExit(f"RC39 launcher source missing: {source}")
    res = app / "src/main/res"
    drawable = res / "drawable-nodpi"
    values = res / "values"
    anydpi = res / "mipmap-anydpi-v26"
    xxx = res / "mipmap-xxxhdpi"
    for d in (drawable, values, anydpi, xxx):
        d.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, drawable / "furinahub_launcher_foreground.webp")
    shutil.copyfile(source, xxx / "ic_launcher.webp")
    shutil.copyfile(source, xxx / "ic_launcher_round.webp")
    (values / "furinahub_icon.xml").write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n<resources>\n'
        '    <color name="furinahub_icon_background">#0755B7</color>\n'
        '</resources>\n', encoding="utf-8")
    adaptive = '''<?xml version="1.0" encoding="utf-8"?>
<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">
    <background android:drawable="@color/furinahub_icon_background" />
    <foreground android:drawable="@drawable/furinahub_launcher_foreground" />
</adaptive-icon>
'''
    (anydpi / "ic_launcher.xml").write_text(adaptive, encoding="utf-8")
    (anydpi / "ic_launcher_round.xml").write_text(adaptive, encoding="utf-8")

    manifest_path = app / "src/main/AndroidManifest.xml"
    manifest = manifest_path.read_text(encoding="utf-8")
    if 'android:icon=' in manifest:
        manifest = re.sub(r'android:icon="[^"]+"', 'android:icon="@mipmap/ic_launcher"', manifest, count=1)
    else:
        manifest = manifest.replace('<application', '<application android:icon="@mipmap/ic_launcher"', 1)
    if 'android:roundIcon=' in manifest:
        manifest = re.sub(r'android:roundIcon="[^"]+"', 'android:roundIcon="@mipmap/ic_launcher_round"', manifest, count=1)
    else:
        manifest = manifest.replace('<application', '<application android:roundIcon="@mipmap/ic_launcher_round"', 1)
    manifest_path.write_text(manifest, encoding="utf-8")


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("usage: apply.py <termux-root>")
    root = Path(sys.argv[1]).resolve()
    app = root / "bridge/app"
    html_path = app / "src/main/assets/furinahub/index.html"
    updater_path = app / "src/main/java/com/wynndev/furinaagentbridge/BridgeUpdater.java"
    gradle_path = app / "build.gradle"
    hub_path = root / "core/furina_agent/hub.py"
    source_icon = Path(__file__).resolve().parents[2] / "assets/furinahub-launcher.webp"
    for path in (html_path, updater_path, gradle_path, hub_path):
        if not path.is_file():
            raise SystemExit(f"RC39 source missing: {path}")

    # Update metadata: the explicit Furina machine release is authoritative.
    updater = updater_path.read_text(encoding="utf-8")
    old_urls = '''    private static final String[] MANIFEST_URLS = new String[]{
            "https://github.com/WynnDev-rill/furina/releases/latest/download/manifest.json",
            "https://github.com/WynnDev-rill/furina/releases/download/furina-update-stable/manifest.json",
            "https://cdn.jsdelivr.net/gh/WynnDev-rill/furina@furina-bootstrap-v1.0.0/experiments/furina-agent-final/manifest.json",
            "https://api.github.com/repos/WynnDev-rill/furina/contents/experiments/furina-agent-final/manifest.json?ref=experiment/furina-agent-termux",
            "https://raw.githubusercontent.com/WynnDev-rill/furina/experiment/furina-agent-termux/experiments/furina-agent-final/manifest.json",
            "https://github.com/WynnDev-rill/furina/raw/refs/heads/experiment/furina-agent-termux/experiments/furina-agent-final/manifest.json"
    };'''
    new_urls = '''    private static final String[] MANIFEST_URLS = new String[]{
            "https://github.com/WynnDev-rill/furina/releases/download/furina-update-stable/manifest.json",
            "https://cdn.jsdelivr.net/gh/WynnDev-rill/furina@furina-bootstrap-v1.0.0/experiments/furina-agent-final/manifest.json",
            "https://api.github.com/repos/WynnDev-rill/furina/contents/experiments/furina-agent-final/manifest.json?ref=experiment/furina-agent-termux",
            "https://raw.githubusercontent.com/WynnDev-rill/furina/experiment/furina-agent-termux/experiments/furina-agent-final/manifest.json",
            "https://github.com/WynnDev-rill/furina/raw/refs/heads/experiment/furina-agent-termux/experiments/furina-agent-final/manifest.json"
    };'''
    updater = replace_once(updater, old_urls, new_urls, "dedicated manifest channel")
    updater = replace_once(updater, 'FurinaHub-Updater/4', 'FurinaHub-Updater/5', "updater agent")
    updater_path.write_text(updater, encoding="utf-8")

    gradle = gradle_path.read_text(encoding="utf-8")
    gradle = replace_once(gradle, "versionCode 10038", "versionCode 10039", "versionCode")
    gradle = replace_once(gradle, "versionName '1.0.0-rc38'", "versionName '1.0.0-rc39'", "versionName")
    gradle_path.write_text(gradle, encoding="utf-8")

    hub = hub_path.read_text(encoding="utf-8")
    hub = replace_once(hub, '"bridge_target": "1.0.0-rc38"', '"bridge_target": "1.0.0-rc39"', "bridge target")
    hub_path.write_text(hub, encoding="utf-8")

    install_launcher_icon(app, source_icon)

    html = html_path.read_text(encoding="utf-8")
    css = r'''
/* RC39: WhatsApp-inspired crop/draw editor. Only crop and draw are primary tools. */
.editorLayer{background:#000!important;color:#fff!important;overflow:hidden}.editorWhatsTop{height:78px;padding:12px 18px!important;background:#000!important;gap:14px!important}.editorIcon{width:50px!important;height:50px!important;background:#0c1216!important;color:#fff!important;border-radius:50%!important}.editorIcon.on{background:#252c32!important}.editorDone{height:50px!important;border-radius:25px!important;padding:0 20px!important;background:var(--accent)!important;color:#15131c!important;font-weight:800!important}.editorStage{position:relative!important;flex:1!important;min-height:0!important;padding:8px 16px 112px!important;background:#000!important;display:flex!important;align-items:center!important;justify-content:center!important;overflow:hidden!important}.editorStage #editorCanvas{display:block!important;max-width:100%!important;max-height:100%!important;border-radius:0!important;box-shadow:none!important;background:#000!important}.drawCanvas{position:absolute;z-index:3;touch-action:none;pointer-events:none}.editorLayer.drawMode .drawCanvas{pointer-events:auto}.editorLayer.drawMode .cropOverlay{display:none!important}.cropOverlay{z-index:4!important;border:2px solid #fff!important;box-shadow:0 0 0 9999px rgba(0,0,0,.42)!important;background-image:linear-gradient(to right,transparent 33.1%,rgba(255,255,255,.48) 33.3%,rgba(255,255,255,.48) 33.55%,transparent 33.75%,transparent 66.1%,rgba(255,255,255,.48) 66.3%,rgba(255,255,255,.48) 66.55%,transparent 66.75%),linear-gradient(to bottom,transparent 33.1%,rgba(255,255,255,.48) 33.3%,rgba(255,255,255,.48) 33.55%,transparent 33.75%,transparent 66.1%,rgba(255,255,255,.48) 66.3%,rgba(255,255,255,.48) 66.55%,transparent 66.75%)!important}.cropHandle{width:34px!important;height:34px!important}.cropHandle.edge{position:absolute}.cropHandle.n{left:50%;top:-14px;transform:translateX(-50%)}.cropHandle.s{left:50%;bottom:-14px;transform:translateX(-50%)}.cropHandle.w{left:-14px;top:50%;transform:translateY(-50%)}.cropHandle.e{right:-14px;top:50%;transform:translateY(-50%)}.cropHandle.edge:after{content:'';position:absolute;background:#fff;border-radius:2px}.cropHandle.n:after,.cropHandle.s:after{width:34px;height:4px;left:0;top:15px}.cropHandle.w:after,.cropHandle.e:after{width:4px;height:34px;left:15px;top:0}
.waDrawTop{display:none;height:78px;align-items:center;padding:12px 18px;gap:12px;background:#000;z-index:8}.editorLayer.drawMode .editorWhatsTop{display:none!important}.editorLayer.drawMode .waDrawTop{display:flex}.waDrawDone{border:0;background:#10171b;color:#fff;border-radius:24px;padding:0 18px;height:48px;font-weight:700}.waDrawSpacer{flex:1}.waDrawRound{width:50px;height:50px;border:0;border-radius:50%;background:#10171b;color:#fff;display:grid;place-items:center}.waDrawRound.active{background:var(--accent);color:#17141b}.waDrawRound svg{width:24px;height:24px;fill:none;stroke:currentColor;stroke-width:2.2;stroke-linecap:round;stroke-linejoin:round}.colorRail{display:none;position:absolute;right:20px;top:105px;bottom:175px;width:22px;border-radius:14px;background:linear-gradient(to bottom,#fff,#f00,#ff0,#0f0,#0ff,#00f,#f0f,#ff4773);z-index:7;touch-action:none;box-shadow:0 1px 6px #0008}.editorLayer.drawMode .colorRail{display:block}.colorRailKnob{position:absolute;left:50%;width:30px;height:30px;border:3px solid #fff;border-radius:50%;transform:translate(-50%,-50%);box-shadow:0 1px 5px #0009;background:#8d7cff}.waBrushBar{display:none;position:absolute;left:0;right:0;bottom:24px;height:86px;align-items:center;justify-content:center;gap:44px;z-index:8;background:linear-gradient(transparent,#000 38%)}.editorLayer.drawMode .waBrushBar{display:flex}.waBrush{width:58px;height:58px;border:0;border-radius:50%;background:transparent;color:#fff;display:grid;place-items:center}.waBrush.on{background:#555}.waBrush svg{width:37px;height:37px;fill:none;stroke:currentColor;stroke-linecap:round}.waBrush.thin svg{stroke-width:2}.waBrush.medium svg{stroke-width:4}.waBrush.thick svg{stroke-width:7}
'''
    html = replace_once(html, "</style>", css + "\n</style>", "RC39 editor CSS")

    old_editor = '''<div id="imageEditor" class="editorLayer" role="dialog" aria-modal="true"><div class="editorWhatsTop"><button class="editorIcon" aria-label="Batal" onclick="closeImageEditor()"><svg viewBox="0 0 24 24"><path d="M6 6l12 12M18 6 6 18"/></svg></button><div class="editorWhatsSpacer"></div><button id="toolCrop" class="editorIcon on" aria-label="Pangkas" onclick="setEditorTool('crop')"><svg viewBox="0 0 24 24"><path d="M7 3v14a2 2 0 0 0 2 2h12M3 7h14a2 2 0 0 1 2 2v12M7 7h10v10"/></svg></button><button id="toolDraw" class="editorIcon" aria-label="Coret" onclick="setEditorTool('draw')"><svg viewBox="0 0 24 24"><path d="m4 20 4.5-1 10-10a2.1 2.1 0 0 0-3-3l-10 10L4 20Z"/><path d="m14 7 3 3"/></svg></button><button class="editorDone" onclick="applyImageEdit()">Selesai</button></div><div id="editorStage" class="editorStage"><canvas id="editorCanvas"></canvas><div id="cropOverlay" class="cropOverlay"><i class="cropHandle nw" data-handle="nw"></i><i class="cropHandle ne" data-handle="ne"></i><i class="cropHandle sw" data-handle="sw"></i><i class="cropHandle se" data-handle="se"></i></div></div></div>'''
    new_editor = '''<div id="imageEditor" class="editorLayer" role="dialog" aria-modal="true"><div class="editorWhatsTop"><button class="editorIcon" aria-label="Batal" onclick="closeImageEditor()"><svg viewBox="0 0 24 24"><path d="M6 6l12 12M18 6 6 18"/></svg></button><div class="editorWhatsSpacer"></div><button id="toolCrop" class="editorIcon on" aria-label="Pangkas" onclick="setEditorTool('crop')"><svg viewBox="0 0 24 24"><path d="M7 3v14a2 2 0 0 0 2 2h12M3 7h14a2 2 0 0 1 2 2v12M7 7h10v10"/></svg></button><button id="toolDraw" class="editorIcon" aria-label="Coret" onclick="setEditorTool('draw')"><svg viewBox="0 0 24 24"><path d="m4 20 4.5-1 10-10a2.1 2.1 0 0 0-3-3l-10 10L4 20Z"/><path d="m14 7 3 3"/></svg></button><button class="editorDone" onclick="applyImageEdit()">Selesai</button></div><div class="waDrawTop"><button class="waDrawDone" onclick="setEditorTool('crop')">Selesai</button><div class="waDrawSpacer"></div><button class="waDrawRound" aria-label="Urungkan" onclick="undoDraw()"><svg viewBox="0 0 24 24"><path d="M9 7 4 12l5 5"/><path d="M5 12h8a6 6 0 0 1 6 6"/></svg></button><button class="waDrawRound active" aria-label="Pensil"><svg viewBox="0 0 24 24"><path d="m4 20 4.5-1 10-10a2.1 2.1 0 0 0-3-3l-10 10L4 20Z"/><path d="m14 7 3 3"/></svg></button></div><div id="editorStage" class="editorStage"><canvas id="editorCanvas"></canvas><canvas id="drawCanvas" class="drawCanvas"></canvas><div id="cropOverlay" class="cropOverlay"><i class="cropHandle nw" data-handle="nw"></i><i class="cropHandle ne" data-handle="ne"></i><i class="cropHandle sw" data-handle="sw"></i><i class="cropHandle se" data-handle="se"></i><i class="cropHandle edge n" data-handle="n"></i><i class="cropHandle edge s" data-handle="s"></i><i class="cropHandle edge w" data-handle="w"></i><i class="cropHandle edge e" data-handle="e"></i></div><div id="colorRail" class="colorRail"><i id="colorRailKnob" class="colorRailKnob"></i></div></div><div class="waBrushBar"><button class="waBrush thin" data-width="0.006" onclick="setBrushWidth(.006,this)" aria-label="Tipis"><svg viewBox="0 0 40 40"><path d="M5 25c6-13 11 12 17-5s7 12 13-5"/></svg></button><button class="waBrush medium on" data-width="0.012" onclick="setBrushWidth(.012,this)" aria-label="Sedang"><svg viewBox="0 0 40 40"><path d="M5 25c6-13 11 12 17-5s7 12 13-5"/></svg></button><button class="waBrush thick" data-width="0.022" onclick="setBrushWidth(.022,this)" aria-label="Tebal"><svg viewBox="0 0 40 40"><path d="M5 25c6-13 11 12 17-5s7 12 13-5"/></svg></button></div></div>'''
    html = replace_once(html, old_editor, new_editor, "WhatsApp image editor shell")

    editor_funcs = r'''let editorCrop=null,drawStrokes=[],drawStroke=null,drawColor='#8d7cff',drawWidth=.012;
function openImageEditor(){if(selectedAttachment?.kind!=='image')return;editorSource={...selectedAttachment};editorTool='crop';drawStrokes=[];drawStroke=null;const img=new Image();img.onload=()=>{const c=document.getElementById('editorCanvas'),scale=Math.min(1,1800/Math.max(img.naturalWidth,img.naturalHeight));c.width=Math.max(1,Math.round(img.naturalWidth*scale));c.height=Math.max(1,Math.round(img.naturalHeight*scale));c.getContext('2d').drawImage(img,0,0,c.width,c.height);editorCrop={x:0,y:0,w:c.width,h:c.height};const d=document.getElementById('drawCanvas');d.width=c.width;d.height=c.height;wireEditorCanvas();wireCropOverlay();wireColorRail();setEditorTool('crop');document.getElementById('imageEditor').classList.add('show');requestAnimationFrame(syncEditorLayers)};img.src='data:'+editorSource.mime+';base64,'+editorSource.base64}
function closeImageEditor(){const layer=document.getElementById('imageEditor');layer.classList.remove('show','drawMode');editorTool='crop';editorCrop=null;drawStrokes=[];drawStroke=null}
function setEditorTool(tool){editorTool=tool;const layer=document.getElementById('imageEditor');layer.classList.toggle('drawMode',tool==='draw');document.getElementById('toolCrop')?.classList.toggle('on',tool==='crop');document.getElementById('toolDraw')?.classList.toggle('on',tool==='draw');document.getElementById('cropOverlay')?.classList.toggle('show',tool==='crop');requestAnimationFrame(syncEditorLayers)}
function syncEditorLayers(){const c=document.getElementById('editorCanvas'),d=document.getElementById('drawCanvas'),o=document.getElementById('cropOverlay'),stage=document.getElementById('editorStage');if(!c||!d||!stage)return;const cr=c.getBoundingClientRect(),sr=stage.getBoundingClientRect();d.style.left=(cr.left-sr.left)+'px';d.style.top=(cr.top-sr.top)+'px';d.style.width=cr.width+'px';d.style.height=cr.height+'px';if(editorCrop&&o){const sx=cr.width/c.width,sy=cr.height/c.height;o.style.left=(cr.left-sr.left+editorCrop.x*sx)+'px';o.style.top=(cr.top-sr.top+editorCrop.y*sy)+'px';o.style.width=(editorCrop.w*sx)+'px';o.style.height=(editorCrop.h*sy)+'px'}redrawDrawCanvas()}
function syncCropOverlay(){syncEditorLayers()}
function wireCropOverlay(){const o=document.getElementById('cropOverlay'),c=document.getElementById('editorCanvas');if(!o||!c)return;let drag=null;o.onpointerdown=e=>{if(editorTool!=='crop')return;const h=e.target?.dataset?.handle||'move';drag={mode:h,start:canvasPoint(c,e),rect:{...editorCrop}};o.setPointerCapture(e.pointerId);e.preventDefault()};o.onpointermove=e=>{if(!drag||editorTool!=='crop')return;const p=canvasPoint(c,e),dx=p.x-drag.start.x,dy=p.y-drag.start.y,r={...drag.rect},min=Math.max(28,Math.min(c.width,c.height)*.08);if(drag.mode==='move'){r.x=Math.max(0,Math.min(c.width-r.w,r.x+dx));r.y=Math.max(0,Math.min(c.height-r.h,r.y+dy))}else{let x1=r.x,y1=r.y,x2=r.x+r.w,y2=r.y+r.h;if(drag.mode.includes('w'))x1=Math.max(0,Math.min(x2-min,x1+dx));if(drag.mode.includes('e'))x2=Math.min(c.width,Math.max(x1+min,x2+dx));if(drag.mode.includes('n'))y1=Math.max(0,Math.min(y2-min,y1+dy));if(drag.mode.includes('s'))y2=Math.min(c.height,Math.max(y1+min,y2+dy));r={x:x1,y:y1,w:x2-x1,h:y2-y1}}editorCrop=r;syncEditorLayers();e.preventDefault()};o.onpointerup=o.onpointercancel=()=>{drag=null}}
function wireEditorCanvas(){const d=document.getElementById('drawCanvas'),c=document.getElementById('editorCanvas');if(!d||!c)return;d.onpointerdown=e=>{if(editorTool!=='draw')return;d.setPointerCapture(e.pointerId);const p=canvasPoint(d,e);drawStroke={color:drawColor,width:drawWidth,points:[p]};e.preventDefault()};d.onpointermove=e=>{if(!drawStroke||editorTool!=='draw')return;drawStroke.points.push(canvasPoint(d,e));redrawDrawCanvas(true);e.preventDefault()};d.onpointerup=d.onpointercancel=e=>{if(!drawStroke)return;if(drawStroke.points.length>1)drawStrokes.push(drawStroke);drawStroke=null;redrawDrawCanvas();try{d.releasePointerCapture(e.pointerId)}catch(_){};e.preventDefault()}}
function redrawDrawCanvas(includeActive=false){const d=document.getElementById('drawCanvas');if(!d)return;const ctx=d.getContext('2d');ctx.clearRect(0,0,d.width,d.height);const list=includeActive&&drawStroke?[...drawStrokes,drawStroke]:drawStrokes;for(const s of list){if(!s.points?.length)continue;ctx.beginPath();ctx.strokeStyle=s.color;ctx.lineWidth=Math.max(2,d.width*s.width);ctx.lineCap='round';ctx.lineJoin='round';ctx.moveTo(s.points[0].x,s.points[0].y);for(let i=1;i<s.points.length;i++)ctx.lineTo(s.points[i].x,s.points[i].y);ctx.stroke()}}
function undoDraw(){if(drawStrokes.length)drawStrokes.pop();drawStroke=null;redrawDrawCanvas()}
function setBrushWidth(v,el){drawWidth=Number(v)||.012;document.querySelectorAll('.waBrush').forEach(b=>b.classList.toggle('on',b===el))}
function railColorAt(frac){const t=Math.max(0,Math.min(1,frac));if(t<.08)return'#ffffff';return`hsl(${Math.round((t-.08)/.92*340)},100%,62%)`}
function setRailColorFromEvent(e){const rail=document.getElementById('colorRail'),knob=document.getElementById('colorRailKnob');if(!rail||!knob)return;const r=rail.getBoundingClientRect(),f=Math.max(0,Math.min(1,(e.clientY-r.top)/r.height));drawColor=railColorAt(f);knob.style.top=(f*100)+'%';knob.style.background=drawColor}
function wireColorRail(){const rail=document.getElementById('colorRail');if(!rail)return;rail.onpointerdown=e=>{rail.setPointerCapture(e.pointerId);setRailColorFromEvent(e);e.preventDefault()};rail.onpointermove=e=>{if(rail.hasPointerCapture(e.pointerId)){setRailColorFromEvent(e);e.preventDefault()}}}
'''
    html = replace_js_function(html, "openImageEditor", "canvasPoint", editor_funcs)

    apply_start = html.find("function applyImageEdit(){")
    auto_grow = html.find("function autoGrow(", apply_start)
    if apply_start < 0 or auto_grow < 0:
        raise SystemExit("RC39 editor apply boundary missing")
    apply_editor = r'''function applyImageEdit(){const src=document.getElementById('editorCanvas'),draw=document.getElementById('drawCanvas'),merged=document.createElement('canvas');merged.width=src.width;merged.height=src.height;const m=merged.getContext('2d');m.drawImage(src,0,0);redrawDrawCanvas();m.drawImage(draw,0,0);const out=document.createElement('canvas'),r=editorCrop||{x:0,y:0,w:src.width,h:src.height},sx=Math.max(0,Math.round(r.x)),sy=Math.max(0,Math.round(r.y)),sw=Math.max(1,Math.min(src.width-sx,Math.round(r.w))),sh=Math.max(1,Math.min(src.height-sy,Math.round(r.h)));out.width=sw;out.height=sh;out.getContext('2d').drawImage(merged,sx,sy,sw,sh,0,0,sw,sh);const data=out.toDataURL('image/jpeg',.92),base64=data.split(',')[1];selectedAttachment={kind:'image',name:(editorSource?.name||'gambar').replace(/\.[^.]+$/,'')+'-edit.jpg',mime:'image/jpeg',base64,size:Math.floor(base64.length*.75)};showAttachment();closeImageEditor()}'''
    html = html[:apply_start] + apply_editor + "\n" + html[auto_grow:]
    html_path.write_text(html, encoding="utf-8")

    combined = updater + "\n" + gradle + "\n" + hub + "\n" + html
    checks = (
        "releases/download/furina-update-stable/manifest.json",
        "FurinaHub-Updater/5",
        "versionCode 10039",
        "versionName '1.0.0-rc39'",
        '"bridge_target": "1.0.0-rc39"',
        'id="drawCanvas"',
        'id="colorRail"',
        'function undoDraw(',
        'function setBrushWidth(',
    )
    missing = [item for item in checks if item not in combined]
    if missing:
        raise SystemExit(f"RC39 marker hilang: {missing}")
    if "releases/latest/download/manifest.json" in updater:
        raise SystemExit("RC39 Android updater masih memakai repository-wide latest")
    print("FURINAHUB_ANDROID_RC39_MEDIA_UPDATER_ICON_OK")


if __name__ == "__main__":
    main()
