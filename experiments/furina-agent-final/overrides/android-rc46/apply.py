#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import sys


def once(text, old, new, label):
    if old not in text:
        if new in text: return text
        raise SystemExit(f"RC46 marker missing: {label}")
    return text.replace(old,new,1)

def fstart(text,name,after=0):
    hits=[text.find(p+name+"(",after) for p in ("async function ","function ")]
    hits=[x for x in hits if x>=0]
    return min(hits) if hits else -1

def replace_fn(text,name,next_name,repl):
    a=fstart(text,name); b=fstart(text,next_name,max(a,0)+1)
    if a<0 or b<0 or b<=a: raise SystemExit(f"RC46 JS boundary: {name}->{next_name}")
    return text[:a]+repl.rstrip()+"\n"+text[b:]

def replace_between(text,start,end,repl):
    a=text.find(start); b=text.find(end,max(a,0)+1)
    if a<0 or b<0 or b<=a: raise SystemExit(f"RC46 boundary: {start}->{end}")
    return text[:a]+repl.rstrip()+"\n"+text[b:]


def main():
    root=Path(sys.argv[1]).resolve(); app=root/'bridge/app'
    htmlp=app/'src/main/assets/furinahub/index.html'; gradlep=app/'build.gradle'
    hubp=root/'core/furina_agent/hub.py'; updaterp=app/'src/main/java/com/wynndev/furinaagentbridge/BridgeUpdater.java'
    for p in (htmlp,gradlep,hubp,updaterp):
        if not p.is_file(): raise SystemExit(f"RC46 source missing: {p}")
    gradle=gradlep.read_text(); gradle=once(gradle,'versionCode 10045','versionCode 10046','versionCode'); gradle=once(gradle,"versionName '1.0.0-rc45'","versionName '1.0.0-rc46'",'versionName')
    hub=hubp.read_text(); hub=once(hub,'"bridge_target": "1.0.0-rc45"','"bridge_target": "1.0.0-rc46"','bridge target')
    updater=updaterp.read_text(); updater=once(updater,'FurinaHub-Updater/11','FurinaHub-Updater/12','updater agent')
    html=htmlp.read_text()
    html=once(html,'</style>',r'''
/* RC46: direct decoded IMG preview. Canvas is geometry/output only. */
.editorStage #editorCanvas{opacity:0!important;background:none!important;z-index:0!important}
.editorPreviewImage{position:absolute!important;z-index:1!important;display:block!important;opacity:1!important;visibility:visible!important;pointer-events:none!important;user-select:none!important;-webkit-user-select:none!important;object-fit:fill!important;max-width:none!important;max-height:none!important;background:transparent!important}
.drawCanvas{z-index:3!important}.cropOverlay{z-index:4!important}
</style>''','editor CSS')

    open_block=r'''function editorDataUrl(source){const b64=String(source?.base64||'').replace(/\s+/g,'');if(!b64)throw new Error('Data gambar kosong');const mime=/^image\/[a-z0-9.+-]+$/i.test(String(source?.mime||''))?String(source.mime).toLowerCase():'image/jpeg';return'data:'+mime+';base64,'+b64}
function waitEditorImageLoad(img,timeoutMs=10000){return new Promise((resolve,reject)=>{if(img.complete&&img.naturalWidth>0){resolve();return}let done=false,timer=0;const finish=(ok,err)=>{if(done)return;done=true;if(timer)clearTimeout(timer);img.onload=null;img.onerror=null;ok?resolve():reject(err||new Error('Gambar gagal dimuat'))};img.onload=()=>finish(img.naturalWidth>0,new Error('Dimensi gambar tidak valid'));img.onerror=()=>finish(false,new Error('Gambar gagal dimuat'));timer=setTimeout(()=>finish(false,new Error('Decode gambar melewati batas waktu')),timeoutMs)})}
function removeEditorPreview(){const p=document.getElementById('editorPreviewImage');if(p){p.removeAttribute('src');p.remove()}}
async function openImageEditor(){if(selectedAttachment?.kind!=='image')return;const token=(Number(window.__furinaEditorLoadToken)||0)+1;window.__furinaEditorLoadToken=token;editorSource={...selectedAttachment};editorTool='crop';drawStrokes=[];drawStroke=null;removeEditorPreview();editorSetStatus('Menyiapkan gambar…');try{const img=new Image();img.id='editorPreviewImage';img.className='editorPreviewImage';img.alt='';img.decoding='sync';img.src=editorDataUrl(editorSource);await waitEditorImageLoad(img);if(window.__furinaEditorLoadToken!==token)return;const layer=document.getElementById('imageEditor'),stage=document.getElementById('editorStage'),c=document.getElementById('editorCanvas'),d=document.getElementById('drawCanvas');const scale=Math.min(1,1800/Math.max(img.naturalWidth,img.naturalHeight));c.width=Math.max(1,Math.round(img.naturalWidth*scale));c.height=Math.max(1,Math.round(img.naturalHeight*scale));const ctx=c.getContext('2d');if(ctx)ctx.clearRect(0,0,c.width,c.height);d.width=c.width;d.height=c.height;stage.insertBefore(img,c.nextSibling);editorCrop={x:0,y:0,w:c.width,h:c.height};wireEditorCanvas();wireCropOverlay();wireColorRail();setEditorTool('crop');layer.classList.add('show');editorSetStatus('');requestAnimationFrame(()=>{syncEditorLayers();requestAnimationFrame(syncEditorLayers)})}catch(err){console.error('FurinaHub direct image preview failed',err);window.__furinaEditorLoadToken=token+1;removeEditorPreview();editorSetStatus('Gambar tidak dapat ditampilkan. Pilih gambar lagi.','error')}}'''
    html=replace_between(html,'function editorMimeFromBytes(','function closeImageEditor(',open_block)
    close=r'''function closeImageEditor(){window.__furinaEditorLoadToken=(Number(window.__furinaEditorLoadToken)||0)+1;editorSetStatus('');removeEditorPreview();const layer=document.getElementById('imageEditor');layer.classList.remove('show','drawMode');editorTool='crop';editorCrop=null;drawStrokes=[];drawStroke=null}'''
    html=replace_fn(html,'closeImageEditor','setEditorTool',close)
    sync=r'''function syncEditorLayers(){const c=document.getElementById('editorCanvas'),d=document.getElementById('drawCanvas'),o=document.getElementById('cropOverlay'),stage=document.getElementById('editorStage'),preview=document.getElementById('editorPreviewImage');if(!c||!d||!stage)return;const cr=c.getBoundingClientRect(),sr=stage.getBoundingClientRect(),originX=sr.left+(stage.clientLeft||0),originY=sr.top+(stage.clientTop||0),left=cr.left-originX,top=cr.top-originY;d.style.left=left+'px';d.style.top=top+'px';d.style.width=cr.width+'px';d.style.height=cr.height+'px';if(preview){preview.style.left=left+'px';preview.style.top=top+'px';preview.style.width=cr.width+'px';preview.style.height=cr.height+'px'}if(editorCrop&&o&&c.width&&c.height&&cr.width>0&&cr.height>0){const sx=cr.width/c.width,sy=cr.height/c.height;o.style.left=(left+editorCrop.x*sx)+'px';o.style.top=(top+editorCrop.y*sy)+'px';o.style.width=Math.max(1,editorCrop.w*sx)+'px';o.style.height=Math.max(1,editorCrop.h*sy)+'px';o.style.pointerEvents=editorTool==='crop'?'auto':'none'}redrawDrawCanvas()}'''
    html=replace_fn(html,'syncEditorLayers','syncCropOverlay',sync)
    apply=r'''function canvasBlob(c,mime,quality){return new Promise((resolve,reject)=>c.toBlob(b=>b?resolve(b):reject(new Error('Gagal membuat hasil gambar')),mime,quality))}
function blobBase64(blob){return new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(String(r.result||'').split(',')[1]||'');r.onerror=()=>reject(r.error||new Error('Gagal membaca hasil gambar'));r.readAsDataURL(blob)})}
async function applyImageEdit(){const src=document.getElementById('editorCanvas'),preview=document.getElementById('editorPreviewImage'),draw=document.getElementById('drawCanvas');if(!src||!preview||!draw||!src.width||!src.height||!preview.naturalWidth)return;editorSetStatus('Menyimpan hasil…');try{redrawDrawCanvas();const r=editorCrop||{x:0,y:0,w:src.width,h:src.height},sx=Math.max(0,Math.min(src.width-1,Math.floor(r.x))),sy=Math.max(0,Math.min(src.height-1,Math.floor(r.y))),ex=Math.max(sx+1,Math.min(src.width,Math.ceil(r.x+r.w))),ey=Math.max(sy+1,Math.min(src.height,Math.ceil(r.y+r.h))),sw=ex-sx,sh=ey-sy,out=document.createElement('canvas');out.width=sw;out.height=sh;const o=out.getContext('2d',{alpha:true});if(!o)throw new Error('Canvas hasil tidak tersedia');const nx=preview.naturalWidth/src.width,ny=preview.naturalHeight/src.height;o.clearRect(0,0,sw,sh);o.drawImage(preview,sx*nx,sy*ny,sw*nx,sh*ny,0,0,sw,sh);o.drawImage(draw,sx,sy,sw,sh,0,0,sw,sh);const sourceMime=(editorSource?.mime||'image/jpeg').toLowerCase(),preserveAlpha=sourceMime==='image/png'||sourceMime==='image/webp';let mime=preserveAlpha?'image/png':'image/jpeg',blob=await canvasBlob(out,mime,preserveAlpha?undefined:.94);if(blob.size>5800000){const flat=document.createElement('canvas');flat.width=out.width;flat.height=out.height;const f=flat.getContext('2d');f.fillStyle='#fff';f.fillRect(0,0,flat.width,flat.height);f.drawImage(out,0,0);mime='image/jpeg';blob=await canvasBlob(flat,mime,.9)}const base64=await blobBase64(blob),ext=mime==='image/png'?'.png':'.jpg';if(!base64)throw new Error('Hasil gambar kosong');selectedAttachment={kind:'image',name:(editorSource?.name||'gambar').replace(/\.[^.]+$/,'')+'-edit'+ext,mime,base64,size:blob.size};showAttachment();closeImageEditor()}catch(err){console.error('FurinaHub image apply failed',err);editorSetStatus('Edit gambar gagal disimpan: '+(err?.message||'error'),'error')}}'''
    html=replace_fn(html,'canvasBlob','autoGrow',apply)

    combined='\n'.join((gradle,hub,updater,html))
    checks=('versionCode 10046',"versionName '1.0.0-rc46'",'"bridge_target": "1.0.0-rc46"','FurinaHub-Updater/12','function editorDataUrl(source)','img.src=editorDataUrl(editorSource)','editorPreviewImage','o.drawImage(preview,sx*nx','RC46: direct decoded IMG preview')
    missing=[x for x in checks if x not in combined]
    if missing: raise SystemExit('RC46 markers missing: '+', '.join(missing))
    forbidden=('createImageBitmap(packed.blob)','URL.createObjectURL(blob)','ctx.drawImage(decoded.image')
    present=[x for x in forbidden if x in html]
    if present: raise SystemExit('RC46 obsolete decode path remains: '+', '.join(present))
    gradlep.write_text(gradle); hubp.write_text(hub); updaterp.write_text(updater); htmlp.write_text(html)
    print('FURINAHUB_ANDROID_RC46_DIRECT_IMAGE_PREVIEW_OK')

if __name__=='__main__': main()
