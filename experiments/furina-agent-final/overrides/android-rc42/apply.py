#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text and old not in text:
        return text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"Android RC42 marker mismatch: {label} ({count})")
    return text.replace(old, new, 1)


def replace_js_function(text: str, name: str, next_name: str, replacement: str) -> str:
    start = text.find(f"function {name}(")
    end = text.find(f"function {next_name}(", max(start, 0) + 1)
    if start < 0 or end < 0 or end <= start:
        raise SystemExit(f"Android RC42 JS boundary mismatch: {name} -> {next_name}")
    return text[:start] + replacement.rstrip() + "\n" + text[end:]


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("usage: apply.py <termux-root>")
    root = Path(sys.argv[1]).resolve()
    app = root / "bridge/app"
    html_path = app / "src/main/assets/furinahub/index.html"
    gradle_path = app / "build.gradle"
    hub_path = root / "core/furina_agent/hub.py"
    updater_path = app / "src/main/java/com/wynndev/furinaagentbridge/BridgeUpdater.java"
    for path in (html_path, gradle_path, hub_path, updater_path):
        if not path.is_file():
            raise SystemExit(f"Android RC42 source missing: {path}")

    gradle = gradle_path.read_text(encoding="utf-8")
    gradle = replace_once(gradle, "versionCode 10041", "versionCode 10042", "versionCode")
    gradle = replace_once(gradle, "versionName '1.0.0-rc41'", "versionName '1.0.0-rc42'", "versionName")
    gradle_path.write_text(gradle, encoding="utf-8")

    hub = hub_path.read_text(encoding="utf-8")
    hub = replace_once(hub, '"bridge_target": "1.0.0-rc41"', '"bridge_target": "1.0.0-rc42"', "bridge target")
    hub_path.write_text(hub, encoding="utf-8")

    updater = updater_path.read_text(encoding="utf-8")
    updater = replace_once(updater, "FurinaHub-Updater/7", "FurinaHub-Updater/8", "updater agent")
    updater_path.write_text(updater, encoding="utf-8")

    html = html_path.read_text(encoding="utf-8")
    css = r'''
/* RC42: deterministic mobile crop geometry and larger WhatsApp-like touch targets. */
.editorStage{overscroll-behavior:contain!important;-webkit-user-select:none!important;user-select:none!important}
.cropOverlay{
  touch-action:none!important;
  -webkit-user-select:none!important;
  user-select:none!important;
  pointer-events:auto!important;
  box-sizing:border-box!important;
  border:2px solid #fff!important;
  background-color:transparent!important;
  box-shadow:0 0 0 9999px rgba(0,0,0,.42)!important;
  will-change:left,top,width,height!important;
}
.cropHandle{width:46px!important;height:46px!important;touch-action:none!important}
.cropHandle.nw{left:-18px!important;top:-18px!important}.cropHandle.ne{right:-18px!important;top:-18px!important}.cropHandle.sw{left:-18px!important;bottom:-18px!important}.cropHandle.se{right:-18px!important;bottom:-18px!important}
.cropHandle.edge.n{top:-21px!important}.cropHandle.edge.s{bottom:-21px!important}.cropHandle.edge.w{left:-21px!important}.cropHandle.edge.e{right:-21px!important}
.cropHandle.edge.n:after,.cropHandle.edge.s:after{width:38px!important;left:4px!important}.cropHandle.edge.w:after,.cropHandle.edge.e:after{height:38px!important;top:4px!important}
'''
    html = replace_once(html, "</style>", css + "\n</style>", "RC42 crop CSS")

    sync_layers = r'''function cropCanvasPoint(c,e){const r=c.getBoundingClientRect(),rw=Math.max(1,r.width),rh=Math.max(1,r.height);return{x:Math.max(0,Math.min(c.width,(Number(e.clientX)-r.left)*c.width/rw)),y:Math.max(0,Math.min(c.height,(Number(e.clientY)-r.top)*c.height/rh))}}
function cropHitMode(c,e,r){const p=cropCanvasPoint(c,e),cr=c.getBoundingClientRect(),hx=Math.max(18,Math.min(c.width*.22,54*c.width/Math.max(1,cr.width))),hy=Math.max(18,Math.min(c.height*.22,54*c.height/Math.max(1,cr.height))),w=Math.abs(p.x-r.x)<=hx,east=Math.abs(p.x-(r.x+r.w))<=hx,n=Math.abs(p.y-r.y)<=hy,s=Math.abs(p.y-(r.y+r.h))<=hy,insideX=p.x>=r.x-hx&&p.x<=r.x+r.w+hx,insideY=p.y>=r.y-hy&&p.y<=r.y+r.h+hy;if(n&&w)return'nw';if(n&&east)return'ne';if(s&&w)return'sw';if(s&&east)return'se';if(n&&insideX)return'n';if(s&&insideX)return's';if(w&&insideY)return'w';if(east&&insideY)return'e';return'move'}
function syncEditorLayers(){const c=document.getElementById('editorCanvas'),d=document.getElementById('drawCanvas'),o=document.getElementById('cropOverlay'),stage=document.getElementById('editorStage');if(!c||!d||!stage)return;const cr=c.getBoundingClientRect(),sr=stage.getBoundingClientRect(),originX=sr.left+(stage.clientLeft||0),originY=sr.top+(stage.clientTop||0),left=cr.left-originX,top=cr.top-originY;d.style.left=left+'px';d.style.top=top+'px';d.style.width=cr.width+'px';d.style.height=cr.height+'px';if(editorCrop&&o&&c.width&&c.height&&cr.width>0&&cr.height>0){const sx=cr.width/c.width,sy=cr.height/c.height;o.style.left=(left+editorCrop.x*sx)+'px';o.style.top=(top+editorCrop.y*sy)+'px';o.style.width=Math.max(1,editorCrop.w*sx)+'px';o.style.height=Math.max(1,editorCrop.h*sy)+'px';o.style.pointerEvents=editorTool==='crop'?'auto':'none'}redrawDrawCanvas()}'''
    html = replace_js_function(html, "syncEditorLayers", "syncCropOverlay", sync_layers)

    crop_handler = r'''function wireCropOverlay(){const o=document.getElementById('cropOverlay'),c=document.getElementById('editorCanvas'),stage=document.getElementById('editorStage');if(!o||!c||!stage)return;let drag=null;const finish=e=>{if(!drag)return;const id=drag.pointerId;drag=null;try{if(o.hasPointerCapture?.(id))o.releasePointerCapture(id)}catch(_){}if(e?.preventDefault)e.preventDefault()};o.onpointerdown=e=>{if(editorTool!=='crop'||!editorCrop)return;if(e.pointerType==='mouse'&&e.button!==0)return;if(drag&&drag.pointerId!==e.pointerId)return;const target=e.target?.closest?.('[data-handle]'),mode=target?.dataset?.handle||cropHitMode(c,e,editorCrop);drag={mode,start:cropCanvasPoint(c,e),rect:{...editorCrop},pointerId:e.pointerId};try{o.setPointerCapture(e.pointerId)}catch(_){}e.preventDefault();e.stopPropagation()};o.onpointermove=e=>{if(!drag||editorTool!=='crop'||e.pointerId!==drag.pointerId)return;const p=cropCanvasPoint(c,e),dx=p.x-drag.start.x,dy=p.y-drag.start.y,base=drag.rect,cr=c.getBoundingClientRect(),minW=Math.max(24,Math.min(c.width*.35,64*c.width/Math.max(1,cr.width))),minH=Math.max(24,Math.min(c.height*.35,64*c.height/Math.max(1,cr.height)));let x1=base.x,y1=base.y,x2=base.x+base.w,y2=base.y+base.h;if(drag.mode==='move'){const nx=Math.max(0,Math.min(c.width-base.w,base.x+dx)),ny=Math.max(0,Math.min(c.height-base.h,base.y+dy));editorCrop={x:nx,y:ny,w:base.w,h:base.h}}else{if(drag.mode.includes('w'))x1=Math.max(0,Math.min(x2-minW,base.x+dx));if(drag.mode.includes('e'))x2=Math.min(c.width,Math.max(x1+minW,base.x+base.w+dx));if(drag.mode.includes('n'))y1=Math.max(0,Math.min(y2-minH,base.y+dy));if(drag.mode.includes('s'))y2=Math.min(c.height,Math.max(y1+minH,base.y+base.h+dy));editorCrop={x:x1,y:y1,w:Math.max(minW,x2-x1),h:Math.max(minH,y2-y1)}}syncEditorLayers();e.preventDefault();e.stopPropagation()};o.onpointerup=finish;o.onpointercancel=finish;o.onlostpointercapture=()=>{drag=null};if(o._cropResizeObserver)o._cropResizeObserver.disconnect();if('ResizeObserver'in window){o._cropResizeObserver=new ResizeObserver(()=>requestAnimationFrame(syncEditorLayers));o._cropResizeObserver.observe(c);o._cropResizeObserver.observe(stage)}if(o._cropResizeHandler)window.removeEventListener('resize',o._cropResizeHandler);o._cropResizeHandler=()=>requestAnimationFrame(syncEditorLayers);window.addEventListener('resize',o._cropResizeHandler,{passive:true});requestAnimationFrame(()=>requestAnimationFrame(syncEditorLayers))}'''
    html = replace_js_function(html, "wireCropOverlay", "wireEditorCanvas", crop_handler)

    apply_editor = r'''function applyImageEdit(){const src=document.getElementById('editorCanvas'),draw=document.getElementById('drawCanvas');if(!src||!draw||!src.width||!src.height)return;const merged=document.createElement('canvas');merged.width=src.width;merged.height=src.height;const m=merged.getContext('2d');m.clearRect(0,0,merged.width,merged.height);m.drawImage(src,0,0);redrawDrawCanvas();m.drawImage(draw,0,0);const r=editorCrop||{x:0,y:0,w:src.width,h:src.height},sx=Math.max(0,Math.min(src.width-1,Math.floor(r.x))),sy=Math.max(0,Math.min(src.height-1,Math.floor(r.y))),ex=Math.max(sx+1,Math.min(src.width,Math.ceil(r.x+r.w))),ey=Math.max(sy+1,Math.min(src.height,Math.ceil(r.y+r.h))),sw=ex-sx,sh=ey-sy,out=document.createElement('canvas');out.width=sw;out.height=sh;const outCtx=out.getContext('2d');outCtx.clearRect(0,0,sw,sh);outCtx.drawImage(merged,sx,sy,sw,sh,0,0,sw,sh);const sourceMime=(editorSource?.mime||'image/jpeg').toLowerCase(),preserveAlpha=sourceMime==='image/png'||sourceMime==='image/webp';let mime=preserveAlpha?'image/png':'image/jpeg',data=out.toDataURL(mime,.94),base64=data.split(',')[1];if(Math.floor(base64.length*.75)>5800000){const flat=document.createElement('canvas');flat.width=out.width;flat.height=out.height;const f=flat.getContext('2d');f.fillStyle='#fff';f.fillRect(0,0,flat.width,flat.height);f.drawImage(out,0,0);mime='image/jpeg';data=flat.toDataURL(mime,.9);base64=data.split(',')[1]}const ext=mime==='image/png'?'.png':'.jpg';selectedAttachment={kind:'image',name:(editorSource?.name||'gambar').replace(/\.[^.]+$/,'')+'-edit'+ext,mime,base64,size:Math.floor(base64.length*.75)};showAttachment();closeImageEditor()}'''
    html = replace_js_function(html, "applyImageEdit", "autoGrow", apply_editor)
    html_path.write_text(html, encoding="utf-8")

    combined = gradle + "\n" + hub + "\n" + updater + "\n" + html
    checks = (
        "versionCode 10042",
        "versionName '1.0.0-rc42'",
        '"bridge_target": "1.0.0-rc42"',
        "FurinaHub-Updater/8",
        "RC42: deterministic mobile crop geometry",
        "function cropCanvasPoint(c,e)",
        "function cropHitMode(c,e,r)",
        "new ResizeObserver",
        "Math.floor(r.x)",
        "Math.ceil(r.x+r.w)",
        "preserveAlpha=sourceMime==='image/png'||sourceMime==='image/webp'",
    )
    missing = [item for item in checks if item not in combined]
    if missing:
        raise SystemExit(f"Android RC42 marker hilang: {missing}")
    print("FURINAHUB_ANDROID_RC42_CROP_OK")


if __name__ == "__main__":
    main()
