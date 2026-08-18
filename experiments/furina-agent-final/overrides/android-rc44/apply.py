#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text and old not in text:
        return text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"Android RC44 marker mismatch: {label} ({count})")
    return text.replace(old, new, 1)


def replace_js_function(text: str, name: str, next_name: str, replacement: str) -> str:
    start = text.find(f"function {name}(")
    end = text.find(f"function {next_name}(", max(start, 0) + 1)
    if start < 0 or end < 0 or end <= start:
        raise SystemExit(f"Android RC44 JS boundary mismatch: {name} -> {next_name}")
    return text[:start] + replacement.rstrip() + "\n" + text[end:]


def replace_between(text: str, start_marker: str, end_marker: str, replacement: str) -> str:
    start = text.find(start_marker)
    end = text.find(end_marker, max(start, 0) + len(start_marker))
    if start < 0 or end < 0 or end <= start:
        raise SystemExit(f"Android RC44 boundary mismatch: {start_marker} -> {end_marker}")
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
            raise SystemExit(f"Android RC44 source missing: {path}")

    gradle = gradle_path.read_text(encoding="utf-8")
    gradle = replace_once(gradle, "versionCode 10043", "versionCode 10044", "versionCode")
    gradle = replace_once(gradle, "versionName '1.0.0-rc43'", "versionName '1.0.0-rc44'", "versionName")
    gradle_path.write_text(gradle, encoding="utf-8")

    hub = hub_path.read_text(encoding="utf-8")
    hub = replace_once(hub, '"bridge_target": "1.0.0-rc43"', '"bridge_target": "1.0.0-rc44"', "bridge target")
    hub_path.write_text(hub, encoding="utf-8")

    updater = updater_path.read_text(encoding="utf-8")
    updater = replace_once(updater, "FurinaHub-Updater/9", "FurinaHub-Updater/10", "updater agent")
    updater_path.write_text(updater, encoding="utf-8")

    html = html_path.read_text(encoding="utf-8")
    old_css = r'''
/* RC43: decoded IMG preview is the visible layer; canvas stays as pixel source. */
.editorPreviewImage{position:absolute!important;z-index:1!important;display:block!important;pointer-events:none!important;user-select:none!important;-webkit-user-select:none!important;object-fit:fill!important;max-width:none!important;max-height:none!important;background:transparent!important}
.editorStage #editorCanvas{opacity:0!important;visibility:visible!important;filter:none!important;z-index:0!important}
.drawCanvas{z-index:3!important}.cropOverlay{z-index:4!important}
'''
    new_css = r'''
/* RC44: one visible canvas is the source of truth. No second IMG/GPU layer. */
.editorStage #editorCanvas{
  opacity:1!important;visibility:visible!important;display:block!important;z-index:1!important;
  background-color:#171b20!important;
  background-image:linear-gradient(45deg,#242a31 25%,transparent 25%),linear-gradient(-45deg,#242a31 25%,transparent 25%),linear-gradient(45deg,transparent 75%,#242a31 75%),linear-gradient(-45deg,transparent 75%,#242a31 75%)!important;
  background-size:20px 20px!important;background-position:0 0,0 10px,10px -10px,-10px 0!important;
}
.editorPreviewImage{display:none!important}
.editorDecodeStatus{position:absolute;inset:18px;z-index:7;display:flex;align-items:center;justify-content:center;text-align:center;padding:20px;border-radius:18px;background:rgba(12,15,19,.88);color:#dbe5ec;font-size:14px;line-height:1.45;pointer-events:none}
.editorDecodeStatus.error{color:#ffb7c5;border:1px solid rgba(255,112,143,.35)}
.drawCanvas{z-index:3!important}.cropOverlay{z-index:4!important}
'''
    html = replace_once(html, old_css, new_css, "RC44 editor CSS")

    editor_open = r'''function editorMimeFromBytes(binary,fallback){const code=i=>binary.charCodeAt(i)&255;if(binary.length>=4&&code(0)===0xff&&code(1)===0xd8&&code(2)===0xff)return'image/jpeg';if(binary.length>=8&&code(0)===0x89&&binary.slice(1,4)==='PNG')return'image/png';if(binary.length>=12&&binary.slice(0,4)==='RIFF'&&binary.slice(8,12)==='WEBP')return'image/webp';if(binary.length>=6&&(binary.slice(0,6)==='GIF87a'||binary.slice(0,6)==='GIF89a'))return'image/gif';const f=String(fallback||'').toLowerCase();return/^image\/[a-z0-9.+-]+$/.test(f)?f:'image/jpeg'}
function editorBlobFromAttachment(source){const b64=String(source?.base64||'').replace(/\s+/g,'');if(!b64)throw new Error('Data gambar kosong');const binary=atob(b64),bytes=new Uint8Array(binary.length);for(let i=0;i<binary.length;i++)bytes[i]=binary.charCodeAt(i)&255;return{blob:new Blob([bytes],{type:editorMimeFromBytes(binary,source?.mime)}),base64:b64}}
function editorSetStatus(text,kind){const stage=document.getElementById('editorStage');if(!stage)return;let el=document.getElementById('editorDecodeStatus');if(!text){el?.remove();return}if(!el){el=document.createElement('div');el.id='editorDecodeStatus';stage.appendChild(el)}el.className='editorDecodeStatus'+(kind==='error'?' error':'');el.textContent=text}
function waitEditorImageLoad(img,timeoutMs=8000){return new Promise((resolve,reject)=>{if(img.complete){if(img.naturalWidth>0)resolve();else reject(new Error('Gambar gagal dimuat'));return}let timer=0;const finish=fn=>{if(timer)clearTimeout(timer);img.onload=null;img.onerror=null;fn()};img.onload=()=>finish(resolve);img.onerror=()=>finish(()=>reject(new Error('Gambar gagal dimuat')));timer=setTimeout(()=>finish(()=>reject(new Error('Decode gambar melewati batas waktu'))),timeoutMs)})}
async function decodeEditorBitmap(source){const packed=editorBlobFromAttachment(source);if(typeof createImageBitmap==='function'){try{const bitmap=await createImageBitmap(packed.blob);if(bitmap.width>0&&bitmap.height>0)return{image:bitmap,width:bitmap.width,height:bitmap.height,release:()=>{try{bitmap.close?.()}catch(_){}}}}catch(err){console.warn('createImageBitmap fallback',err)}}const img=new Image();img.decoding='async';img.src='data:'+packed.blob.type+';base64,'+packed.base64;if(typeof img.decode==='function'){try{await img.decode()}catch(_){await waitEditorImageLoad(img)}}else await waitEditorImageLoad(img);if(!img.naturalWidth||!img.naturalHeight)throw new Error('Dimensi gambar tidak valid');return{image:img,width:img.naturalWidth,height:img.naturalHeight,release:()=>{img.src=''}}}
async function openImageEditor(){if(selectedAttachment?.kind!=='image')return;const token=(Number(window.__furinaEditorLoadToken)||0)+1;window.__furinaEditorLoadToken=token;editorSource={...selectedAttachment};editorTool='crop';drawStrokes=[];drawStroke=null;const layer=document.getElementById('imageEditor'),c=document.getElementById('editorCanvas'),d=document.getElementById('drawCanvas');layer.classList.add('show');editorSetStatus('Menyiapkan gambar…');try{const decoded=await decodeEditorBitmap(editorSource);if(window.__furinaEditorLoadToken!==token){decoded.release();return}const scale=Math.min(1,1800/Math.max(decoded.width,decoded.height));c.width=Math.max(1,Math.round(decoded.width*scale));c.height=Math.max(1,Math.round(decoded.height*scale));const ctx=c.getContext('2d',{alpha:true});if(!ctx)throw new Error('Canvas editor tidak tersedia');ctx.setTransform(1,0,0,1,0,0);ctx.globalAlpha=1;ctx.globalCompositeOperation='source-over';ctx.imageSmoothingEnabled=true;if('imageSmoothingQuality'in ctx)ctx.imageSmoothingQuality='high';ctx.clearRect(0,0,c.width,c.height);ctx.drawImage(decoded.image,0,0,c.width,c.height);decoded.release();editorCrop={x:0,y:0,w:c.width,h:c.height};d.width=c.width;d.height=c.height;wireEditorCanvas();wireCropOverlay();wireColorRail();setEditorTool('crop');editorSetStatus('');requestAnimationFrame(()=>{syncEditorLayers();requestAnimationFrame(syncEditorLayers)})}catch(err){console.error('FurinaHub image decode failed',err);window.__furinaEditorLoadToken=token+1;editorSetStatus('Gambar tidak dapat ditampilkan. Tutup editor lalu pilih gambar lagi.','error')}}'''
    html = replace_between(html, "function editorMimeFromBytes(", "function closeImageEditor(", editor_open)

    close_editor = r'''function closeImageEditor(){window.__furinaEditorLoadToken=(Number(window.__furinaEditorLoadToken)||0)+1;editorSetStatus('');const layer=document.getElementById('imageEditor');layer.classList.remove('show','drawMode');editorTool='crop';editorCrop=null;drawStrokes=[];drawStroke=null}'''
    html = replace_js_function(html, "closeImageEditor", "setEditorTool", close_editor)

    sync_layers = r'''function syncEditorLayers(){const c=document.getElementById('editorCanvas'),d=document.getElementById('drawCanvas'),o=document.getElementById('cropOverlay'),stage=document.getElementById('editorStage');if(!c||!d||!stage)return;const cr=c.getBoundingClientRect(),sr=stage.getBoundingClientRect(),originX=sr.left+(stage.clientLeft||0),originY=sr.top+(stage.clientTop||0),left=cr.left-originX,top=cr.top-originY;d.style.left=left+'px';d.style.top=top+'px';d.style.width=cr.width+'px';d.style.height=cr.height+'px';if(editorCrop&&o&&c.width&&c.height&&cr.width>0&&cr.height>0){const sx=cr.width/c.width,sy=cr.height/c.height;o.style.left=(left+editorCrop.x*sx)+'px';o.style.top=(top+editorCrop.y*sy)+'px';o.style.width=Math.max(1,editorCrop.w*sx)+'px';o.style.height=Math.max(1,editorCrop.h*sy)+'px';o.style.pointerEvents=editorTool==='crop'?'auto':'none'}redrawDrawCanvas()}'''
    html = replace_js_function(html, "syncEditorLayers", "syncCropOverlay", sync_layers)

    apply_editor = r'''function canvasBlob(c,mime,quality){return new Promise((resolve,reject)=>c.toBlob(b=>b?resolve(b):reject(new Error('Gagal membuat hasil gambar')),mime,quality))}
function blobBase64(blob){return new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(String(r.result||'').split(',')[1]||'');r.onerror=()=>reject(r.error||new Error('Gagal membaca hasil gambar'));r.readAsDataURL(blob)})}
async function applyImageEdit(){const src=document.getElementById('editorCanvas'),draw=document.getElementById('drawCanvas');if(!src||!draw||!src.width||!src.height)return;editorSetStatus('Menyimpan hasil…');try{redrawDrawCanvas();const r=editorCrop||{x:0,y:0,w:src.width,h:src.height},sx=Math.max(0,Math.min(src.width-1,Math.floor(r.x))),sy=Math.max(0,Math.min(src.height-1,Math.floor(r.y))),ex=Math.max(sx+1,Math.min(src.width,Math.ceil(r.x+r.w))),ey=Math.max(sy+1,Math.min(src.height,Math.ceil(r.y+r.h))),sw=ex-sx,sh=ey-sy,out=document.createElement('canvas');out.width=sw;out.height=sh;const o=out.getContext('2d',{alpha:true});if(!o)throw new Error('Canvas hasil tidak tersedia');o.clearRect(0,0,sw,sh);o.drawImage(src,sx,sy,sw,sh,0,0,sw,sh);o.drawImage(draw,sx,sy,sw,sh,0,0,sw,sh);const sourceMime=(editorSource?.mime||'image/jpeg').toLowerCase(),preserveAlpha=sourceMime==='image/png'||sourceMime==='image/webp';let mime=preserveAlpha?'image/png':'image/jpeg',blob=await canvasBlob(out,mime,preserveAlpha?undefined:.94);if(blob.size>5800000){const flat=document.createElement('canvas');flat.width=out.width;flat.height=out.height;const f=flat.getContext('2d');f.fillStyle='#fff';f.fillRect(0,0,flat.width,flat.height);f.drawImage(out,0,0);mime='image/jpeg';blob=await canvasBlob(flat,mime,.9)}const base64=await blobBase64(blob),ext=mime==='image/png'?'.png':'.jpg';if(!base64)throw new Error('Hasil gambar kosong');selectedAttachment={kind:'image',name:(editorSource?.name||'gambar').replace(/\.[^.]+$/,'')+'-edit'+ext,mime,base64,size:blob.size};showAttachment();closeImageEditor()}catch(err){console.error('FurinaHub image apply failed',err);editorSetStatus('Edit gambar gagal disimpan. Coba lagi.','error')}}'''
    html = replace_js_function(html, "applyImageEdit", "autoGrow", apply_editor)
    html_path.write_text(html, encoding="utf-8")

    combined = gradle + "\n" + hub + "\n" + updater + "\n" + html
    checks = (
        "versionCode 10044",
        "versionName '1.0.0-rc44'",
        '"bridge_target": "1.0.0-rc44"',
        "FurinaHub-Updater/10",
        "RC44: one visible canvas is the source of truth",
        "async function decodeEditorBitmap(source)",
        "createImageBitmap(packed.blob)",
        "ctx.drawImage(decoded.image,0,0,c.width,c.height)",
        "async function applyImageEdit()",
        "o.drawImage(src,sx,sy,sw,sh,0,0,sw,sh)",
        "o.drawImage(draw,sx,sy,sw,sh,0,0,sw,sh)",
        "editorSetStatus('Menyiapkan gambar…')",
        "if(img.complete){if(img.naturalWidth>0)resolve();else reject",
        "Decode gambar melewati batas waktu",
    )
    missing = [item for item in checks if item not in combined]
    if missing:
        raise SystemExit(f"Android RC44 marker hilang: {missing}")
    forbidden = (
        "URL.createObjectURL",
        "revokeEditorPreview",
        "preview.id='editorPreviewImage'",
        ".editorStage #editorCanvas{opacity:0",
    )
    present = [item for item in forbidden if item in html]
    if present:
        raise SystemExit(f"Android RC44 obsolete image layer masih ada: {present}")
    print("FURINAHUB_ANDROID_RC44_CANVAS_EDITOR_OK")


if __name__ == "__main__":
    main()
