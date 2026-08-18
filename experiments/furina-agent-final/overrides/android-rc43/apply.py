#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text and old not in text:
        return text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"Android RC43 marker mismatch: {label} ({count})")
    return text.replace(old, new, 1)


def replace_js_function(text: str, name: str, next_name: str, replacement: str) -> str:
    start = text.find(f"function {name}(")
    end = text.find(f"function {next_name}(", max(start, 0) + 1)
    if start < 0 or end < 0 or end <= start:
        raise SystemExit(f"Android RC43 JS boundary mismatch: {name} -> {next_name}")
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
            raise SystemExit(f"Android RC43 source missing: {path}")

    gradle = gradle_path.read_text(encoding="utf-8")
    gradle = replace_once(gradle, "versionCode 10042", "versionCode 10043", "versionCode")
    gradle = replace_once(gradle, "versionName '1.0.0-rc42'", "versionName '1.0.0-rc43'", "versionName")
    gradle_path.write_text(gradle, encoding="utf-8")

    hub = hub_path.read_text(encoding="utf-8")
    old_target='"bridge_target": "1.0.0-rc42"'
    new_target='"bridge_target": "1.0.0-rc43"'
    if old_target in hub:
        hub = hub.replace(old_target, new_target)
    if new_target not in hub or old_target in hub:
        raise SystemExit("Android RC43 bridge target tidak lengkap")
    hub_path.write_text(hub, encoding="utf-8")

    updater = updater_path.read_text(encoding="utf-8")
    updater = replace_once(updater, "FurinaHub-Updater/8", "FurinaHub-Updater/9", "updater agent")
    updater_path.write_text(updater, encoding="utf-8")

    html = html_path.read_text(encoding="utf-8")
    css = r'''
/* RC43: decoded IMG preview is the visible layer; canvas stays as pixel source. */
.editorPreviewImage{position:absolute!important;z-index:1!important;display:block!important;pointer-events:none!important;user-select:none!important;-webkit-user-select:none!important;object-fit:fill!important;max-width:none!important;max-height:none!important;background:transparent!important}
.editorStage #editorCanvas{opacity:0!important;visibility:visible!important;filter:none!important;z-index:0!important}
.drawCanvas{z-index:3!important}.cropOverlay{z-index:4!important}
'''
    html = replace_once(html, "</style>", css + "\n</style>", "RC43 preview CSS")

    open_editor = r'''function editorMimeFromBytes(binary,fallback){const code=i=>binary.charCodeAt(i)&255;if(binary.length>=4&&code(0)===0xff&&code(1)===0xd8&&code(2)===0xff)return'image/jpeg';if(binary.length>=8&&code(0)===0x89&&binary.slice(1,4)==='PNG')return'image/png';if(binary.length>=12&&binary.slice(0,4)==='RIFF'&&binary.slice(8,12)==='WEBP')return'image/webp';if(binary.length>=6&&(binary.slice(0,6)==='GIF87a'||binary.slice(0,6)==='GIF89a'))return'image/gif';const f=String(fallback||'').toLowerCase();return/^image\/[a-z0-9.+-]+$/.test(f)?f:'image/jpeg'}
function editorBlobFromAttachment(source){const b64=String(source?.base64||'').replace(/\s+/g,'');if(!b64)throw new Error('Data gambar kosong');const binary=atob(b64),bytes=new Uint8Array(binary.length);for(let i=0;i<binary.length;i++)bytes[i]=binary.charCodeAt(i)&255;return new Blob([bytes],{type:editorMimeFromBytes(binary,source?.mime)})}
function waitEditorImageLoad(img){return new Promise((resolve,reject)=>{if(img.complete&&img.naturalWidth>0){resolve();return}img.onload=()=>resolve();img.onerror=()=>reject(new Error('Gambar gagal dimuat'))})}
async function decodeEditorImage(source){const blob=editorBlobFromAttachment(source),url=URL.createObjectURL(blob),img=new Image();img.decoding='sync';img.src=url;try{if(typeof img.decode==='function')await img.decode();else await waitEditorImageLoad(img);if(!img.naturalWidth||!img.naturalHeight)throw new Error('Dimensi gambar tidak valid');return{img,url}}catch(err){URL.revokeObjectURL(url);throw err}}
function revokeEditorPreview(){const old=window.__furinaEditorPreviewUrl;if(old){try{URL.revokeObjectURL(old)}catch(_){}}window.__furinaEditorPreviewUrl='';const p=document.getElementById('editorPreviewImage');if(p){p.removeAttribute('src');p.remove()}}
async function openImageEditor(){if(selectedAttachment?.kind!=='image')return;const token=(Number(window.__furinaEditorLoadToken)||0)+1;window.__furinaEditorLoadToken=token;editorSource={...selectedAttachment};editorTool='crop';drawStrokes=[];drawStroke=null;revokeEditorPreview();try{const decoded=await decodeEditorImage(editorSource);if(window.__furinaEditorLoadToken!==token){URL.revokeObjectURL(decoded.url);return}const img=decoded.img,c=document.getElementById('editorCanvas'),stage=document.getElementById('editorStage'),scale=Math.min(1,1800/Math.max(img.naturalWidth,img.naturalHeight));c.width=Math.max(1,Math.round(img.naturalWidth*scale));c.height=Math.max(1,Math.round(img.naturalHeight*scale));const ctx=c.getContext('2d',{alpha:true});ctx.setTransform(1,0,0,1,0,0);ctx.globalAlpha=1;ctx.globalCompositeOperation='source-over';ctx.imageSmoothingEnabled=true;if('imageSmoothingQuality'in ctx)ctx.imageSmoothingQuality='high';ctx.clearRect(0,0,c.width,c.height);ctx.drawImage(img,0,0,c.width,c.height);let preview=document.getElementById('editorPreviewImage');if(!preview){preview=document.createElement('img');preview.id='editorPreviewImage';preview.className='editorPreviewImage';preview.alt='';stage.insertBefore(preview,c.nextSibling)}preview.src=decoded.url;window.__furinaEditorPreviewUrl=decoded.url;editorCrop={x:0,y:0,w:c.width,h:c.height};const d=document.getElementById('drawCanvas');d.width=c.width;d.height=c.height;wireEditorCanvas();wireCropOverlay();wireColorRail();setEditorTool('crop');document.getElementById('imageEditor').classList.add('show');requestAnimationFrame(()=>{syncEditorLayers();requestAnimationFrame(syncEditorLayers)})}catch(err){console.error('FurinaHub image decode failed',err);window.__furinaEditorLoadToken=token+1;revokeEditorPreview()}}'''
    html = replace_js_function(html, "openImageEditor", "closeImageEditor", open_editor)

    close_editor = r'''function closeImageEditor(){window.__furinaEditorLoadToken=(Number(window.__furinaEditorLoadToken)||0)+1;revokeEditorPreview();const layer=document.getElementById('imageEditor');layer.classList.remove('show','drawMode');editorTool='crop';editorCrop=null;drawStrokes=[];drawStroke=null}'''
    html = replace_js_function(html, "closeImageEditor", "setEditorTool", close_editor)

    sync_layers = r'''function syncEditorLayers(){const c=document.getElementById('editorCanvas'),d=document.getElementById('drawCanvas'),o=document.getElementById('cropOverlay'),stage=document.getElementById('editorStage'),preview=document.getElementById('editorPreviewImage');if(!c||!d||!stage)return;const cr=c.getBoundingClientRect(),sr=stage.getBoundingClientRect(),originX=sr.left+(stage.clientLeft||0),originY=sr.top+(stage.clientTop||0),left=cr.left-originX,top=cr.top-originY;d.style.left=left+'px';d.style.top=top+'px';d.style.width=cr.width+'px';d.style.height=cr.height+'px';if(preview){preview.style.left=left+'px';preview.style.top=top+'px';preview.style.width=cr.width+'px';preview.style.height=cr.height+'px'}if(editorCrop&&o&&c.width&&c.height&&cr.width>0&&cr.height>0){const sx=cr.width/c.width,sy=cr.height/c.height;o.style.left=(left+editorCrop.x*sx)+'px';o.style.top=(top+editorCrop.y*sy)+'px';o.style.width=Math.max(1,editorCrop.w*sx)+'px';o.style.height=Math.max(1,editorCrop.h*sy)+'px';o.style.pointerEvents=editorTool==='crop'?'auto':'none'}redrawDrawCanvas()}'''
    html = replace_js_function(html, "syncEditorLayers", "syncCropOverlay", sync_layers)

    html_path.write_text(html, encoding="utf-8")

    combined = gradle + "\n" + hub + "\n" + updater + "\n" + html
    checks = (
        "versionCode 10043",
        "versionName '1.0.0-rc43'",
        '"bridge_target": "1.0.0-rc43"',
        "FurinaHub-Updater/9",
        "RC43: decoded IMG preview",
        "async function decodeEditorImage(source)",
        "await img.decode()",
        "editorMimeFromBytes",
        "editorPreviewImage",
        "ctx.drawImage(img,0,0,c.width,c.height)",
        "preview.style.width=cr.width+'px'",
    )
    missing = [item for item in checks if item not in combined]
    if missing:
        raise SystemExit(f"Android RC43 marker hilang: {missing}")
    print("FURINAHUB_ANDROID_RC43_IMAGE_PREVIEW_OK")


if __name__ == "__main__":
    main()
