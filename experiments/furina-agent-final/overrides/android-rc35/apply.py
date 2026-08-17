#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import re
import sys


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text and old not in text:
        return text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"RC35 marker mismatch: {label} ({count})")
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
        raise SystemExit(f"RC35 JS boundary mismatch: {name} -> {next_name}")
    return text[:start] + replacement.rstrip() + "\n" + text[end:]


def replace_java_method(text: str, start_marker: str, next_marker: str, replacement: str, label: str) -> str:
    start = text.find(start_marker)
    end = text.find(next_marker, max(start, 0) + 1)
    if start < 0 or end < 0 or end <= start:
        raise SystemExit(f"RC35 Java boundary mismatch: {label}")
    return text[:start] + replacement.rstrip() + "\n\n" + text[end:]


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("usage: apply.py <termux-root>")
    root = Path(sys.argv[1]).resolve()
    app = root / "bridge/app"
    html_path = app / "src/main/assets/furinahub/index.html"
    gradle = app / "build.gradle"
    updater_path = app / "src/main/java/com/wynndev/furinaagentbridge/BridgeUpdater.java"
    for path in (html_path, gradle, updater_path):
        if not path.is_file():
            raise SystemExit(f"RC35 source missing: {path}")

    html = html_path.read_text(encoding="utf-8")

    css = r'''
/* RC35: persistent response activity + WhatsApp-like two-tool image editor */
.thinkingWrap.done .thinkingDots{display:none}.thinkingWrap.done .thinkingToggle{color:var(--muted)}.thinkingWrap.done .thinkingEvent.current:before{background:var(--muted);box-shadow:none}
.editorLayer{background:#050506!important}.editorStage{position:relative!important;padding:0 10px 12px!important;background:#050506!important}.editorStage canvas{border-radius:0!important;box-shadow:none!important;background:#000!important}
.editorWhatsTop{display:flex;align-items:center;gap:9px;padding:11px 14px;z-index:3;background:#050506;color:#fff}.editorWhatsSpacer{flex:1}.editorIcon{width:48px;height:48px;min-width:48px;border:0;border-radius:50%;display:grid;place-items:center;background:#11161a;color:#fff}.editorIcon svg{width:24px;height:24px}.editorIcon.on{background:#252b30;color:#fff}.editorDone{min-height:44px;border:0;border-radius:22px;padding:0 16px;background:var(--accent);color:var(--accent-ink);font-weight:750}
.cropOverlay{position:absolute;display:none;border:2px solid #fff;box-shadow:0 0 0 9999px #0008;touch-action:none;z-index:4;background-image:linear-gradient(to right,transparent 33.1%,#ffffff65 33.3%,#ffffff65 33.6%,transparent 33.8%,transparent 66.1%,#ffffff65 66.3%,#ffffff65 66.6%,transparent 66.8%),linear-gradient(to bottom,transparent 33.1%,#ffffff65 33.3%,#ffffff65 33.6%,transparent 33.8%,transparent 66.1%,#ffffff65 66.3%,#ffffff65 66.6%,transparent 66.8%)}.cropOverlay.show{display:block}.cropHandle{position:absolute;width:30px;height:30px}.cropHandle:after{content:'';position:absolute;width:16px;height:16px;border-color:#fff}.cropHandle.nw{left:-3px;top:-3px}.cropHandle.ne{right:-3px;top:-3px}.cropHandle.sw{left:-3px;bottom:-3px}.cropHandle.se{right:-3px;bottom:-3px}.cropHandle.nw:after{left:0;top:0;border-left:4px solid;border-top:4px solid}.cropHandle.ne:after{right:0;top:0;border-right:4px solid;border-top:4px solid}.cropHandle.sw:after{left:0;bottom:0;border-left:4px solid;border-bottom:4px solid}.cropHandle.se:after{right:0;bottom:0;border-right:4px solid;border-bottom:4px solid}
'''
    html = replace_once(html, "</style>", css + "\n</style>", "RC35 CSS")

    old_editor = '''<div id="imageEditor" class="editorLayer" role="dialog" aria-modal="true"><div class="editorHeader"><button class="btn" onclick="closeImageEditor()">Batal</button><strong>Edit gambar</strong><button class="btn primary" onclick="applyImageEdit()">Selesai</button></div><div class="editorStage"><canvas id="editorCanvas"></canvas></div><div class="editorTools"><button id="ratioOriginal" class="on" onclick="setCropRatio(0,this)">Asli</button><button onclick="setCropRatio(1,this)">1:1</button><button onclick="setCropRatio(1.3333,this)">4:3</button><button onclick="setCropRatio(1.7778,this)">16:9</button><button onclick="rotateEditor()">Putar</button><button onclick="flipEditor()">Balik</button><button id="toolDraw" onclick="setEditorTool('draw')">Coret</button><button onclick="resetEditor()">Reset</button></div><div class="editorBottom"><div class="sub">Rasio diterapkan saat selesai. Coretan hanya dibuat saat mode Coret aktif.</div></div></div>'''
    new_editor = '''<div id="imageEditor" class="editorLayer" role="dialog" aria-modal="true"><div class="editorWhatsTop"><button class="editorIcon" aria-label="Batal" onclick="closeImageEditor()"><svg viewBox="0 0 24 24"><path d="M6 6l12 12M18 6 6 18"/></svg></button><div class="editorWhatsSpacer"></div><button id="toolCrop" class="editorIcon on" aria-label="Pangkas" onclick="setEditorTool('crop')"><svg viewBox="0 0 24 24"><path d="M7 3v14a2 2 0 0 0 2 2h12M3 7h14a2 2 0 0 1 2 2v12M7 7h10v10"/></svg></button><button id="toolDraw" class="editorIcon" aria-label="Coret" onclick="setEditorTool('draw')"><svg viewBox="0 0 24 24"><path d="m4 20 4.5-1 10-10a2.1 2.1 0 0 0-3-3l-10 10L4 20Z"/><path d="m14 7 3 3"/></svg></button><button class="editorDone" onclick="applyImageEdit()">Selesai</button></div><div id="editorStage" class="editorStage"><canvas id="editorCanvas"></canvas><div id="cropOverlay" class="cropOverlay"><i class="cropHandle nw" data-handle="nw"></i><i class="cropHandle ne" data-handle="ne"></i><i class="cropHandle sw" data-handle="sw"></i><i class="cropHandle se" data-handle="se"></i></div></div></div>'''
    html = replace_once(html, old_editor, new_editor, "two-tool image editor")

    render_boot = r'''function renderBoot(){if(!bootData)return;const name=bootData.assistant_name||'FurinaHub';document.getElementById('brand').textContent=name;if(NATIVE?.setNativeTitle)NATIVE.setNativeTitle(name);renderConversations(bootData.conversations||[],bootData.active_conversation_id);const m=document.getElementById('messages');m.innerHTML='';const history=Array.isArray(bootData.history)?bootData.history:[];if(!history.length)addMsg('assistant','Aku sudah terhubung. Ada yang ingin kamu bicarakan atau kerjakan?');else history.forEach(x=>addMsg(String(x.role||x.kind||'assistant').includes('user')?'user':'assistant',x.content||x.text||'',x.id,x.attachment));restoreThinkingArchive(history);(bootData.jobs||[]).forEach(renderJob);}'''
    html = replace_js_function(html, "renderBoot", "renderConversations", render_boot)

    send_message = r'''async function sendMessage(forcedText){const input=document.getElementById('chatInput'),plain=String(forcedText??input.value).trim(),attachment=selectedAttachment;if((!plain&&!attachment)||!connection.connected)return;let text=plain,requestId='chat-'+Date.now().toString(36)+'-'+Math.random().toString(36).slice(2,9),body={message:plain,request_id:requestId};if(attachment?.kind==='text')text=`${plain}\n\n[Lampiran teks: ${attachment.name}]\n${attachment.content}`;if(attachment?.kind==='image')body.image={name:attachment.name,mime:attachment.mime,base64:attachment.base64};body.message=text;clearAttachment();closeSheets();input.value='';autoGrow(input);const pendingUser=addMsg('user',plain||(attachment?.kind==='text'?'File: '+attachment.name:'Gambar'),null,attachment),thinking=addThinking(requestId);document.getElementById('sendBtn').disabled=true;pollThinking(requestId,thinking);try{const result=await core('POST','/api/chat',body);if(result.mode==='plugin_confirmation'){await finishThinking(requestId,thinking);renderPluginConfirmation(result)}else if(result.mode==='device'&&result.job){await finishThinking(requestId,thinking);renderJob(result.job)}else{await refreshConversation();await finishThinking(requestId,thinking);const assistantId=latestAssistantId();if(assistantId){archiveThinking(thinking,assistantId);placeThinkingBeforeAssistant(thinking,assistantId)}else document.getElementById('messages').appendChild(thinking)}setTimeout(refreshConversationTitles,900);setTimeout(refreshConversationTitles,3200)}catch(e){thinking.remove();pendingUser.remove();if(forcedText===undefined){input.value=plain;autoGrow(input);if(attachment){selectedAttachment=attachment;showAttachment()}}addMsg('assistant','Tidak bisa menghubungi Core: '+e.message)}finally{document.getElementById('sendBtn').disabled=!connection.connected}}'''
    html = replace_js_function(html, "sendMessage", "renderPluginConfirmation", send_message)

    thinking_block = r'''function thinkingArchiveKey(){return'furinahub-thinking-v1:'+(bootData?.active_conversation_id||'none')}
function formatThinkSeconds(ms){const s=Math.max(0,Number(ms||0))/1000;return(s<10?s.toFixed(1):Math.round(s).toString()).replace('.',',')+' detik'}
function addThinking(requestId){const m=document.getElementById('messages'),d=document.createElement('div');d.className='thinkingWrap';d.dataset.requestId=requestId;d.dataset.startedAt=String(Date.now());d.innerHTML=`<button class="thinkingToggle" onclick="this.parentElement.classList.toggle('open')"><span class="thinkingDots"><i></i><i></i><i></i></span><span class="thinkingLabel">Berpikir…</span><span class="thinkingChevron">⌄</span></button><div class="thinkingDetails"><div class="thinkingEvent current">Menyiapkan…</div></div>`;m.appendChild(d);m.scrollTop=m.scrollHeight;return d}
function paintThinking(el,state){if(!el)return;const label=el.querySelector('.thinkingLabel'),details=el.querySelector('.thinkingDetails'),events=Array.isArray(state?.events)?state.events:[];if(state?.created_at)el.dataset.startedAt=String(Math.round(Number(state.created_at)*1000));if(state?.updated_at)el.dataset.endedAt=String(Math.round(Number(state.updated_at)*1000));const started=Number(el.dataset.startedAt||Date.now()),ended=state?.done?Number(el.dataset.endedAt||Date.now()):Date.now();label.textContent=state?.done?'Berpikir selama '+formatThinkSeconds(ended-started):(state?.label||'Berpikir…');el.classList.toggle('done',!!state?.done);const safe=(events.length?events:[{label:state?.label||'Menyiapkan…'}]).map(x=>({label:String(x.label||x.phase||'Memproses').slice(0,120)}));el.dataset.events=JSON.stringify(safe);details.innerHTML=safe.map((x,i)=>`<div class="thinkingEvent ${i===safe.length-1&&!state?.done?'current':''}">${esc(x.label)}</div>`).join('')}
async function pollThinking(requestId,el){for(let i=0;i<1200&&el;i++){if(!el.isConnected&&!document.getElementById('messages'))return;try{const state=await core('GET','/api/chat/progress/'+encodeURIComponent(requestId));paintThinking(el,state);if(state.done)return}catch(e){}await new Promise(r=>setTimeout(r,420))}}
async function finishThinking(requestId,el){try{const state=await core('GET','/api/chat/progress/'+encodeURIComponent(requestId));paintThinking(el,{...state,done:true,updated_at:state.updated_at||Date.now()/1000})}catch(e){paintThinking(el,{done:true,label:'Selesai',created_at:Number(el.dataset.startedAt||Date.now())/1000,updated_at:Date.now()/1000,events:JSON.parse(el.dataset.events||'[]')})}}
function latestAssistantId(){const h=Array.isArray(bootData?.history)?bootData.history:[];for(let i=h.length-1;i>=0;i--){if(!String(h[i].role||h[i].kind||'').includes('user')&&Number(h[i].id)>0)return Number(h[i].id)}return 0}
function archiveThinking(el,assistantId){if(!el||!assistantId)return;const item={assistantId:Number(assistantId),requestId:el.dataset.requestId||'',startedAt:Number(el.dataset.startedAt||Date.now()),endedAt:Number(el.dataset.endedAt||Date.now()),events:JSON.parse(el.dataset.events||'[]')};let list=[];try{list=JSON.parse(localStorage.getItem(thinkingArchiveKey())||'[]')}catch(e){}list=(Array.isArray(list)?list:[]).filter(x=>Number(x.assistantId)!==item.assistantId);list.push(item);localStorage.setItem(thinkingArchiveKey(),JSON.stringify(list.slice(-40)))}
function thinkingFromArchive(item){const d=addThinking(item.requestId||('archived-'+item.assistantId));d.remove();d.dataset.assistantId=String(item.assistantId);d.dataset.startedAt=String(item.startedAt||Date.now());d.dataset.endedAt=String(item.endedAt||item.startedAt||Date.now());paintThinking(d,{done:true,created_at:Number(d.dataset.startedAt)/1000,updated_at:Number(d.dataset.endedAt)/1000,events:Array.isArray(item.events)?item.events:[]});return d}
function placeThinkingBeforeAssistant(el,assistantId){const target=document.querySelector(`.msg[data-id="${Number(assistantId)}"]`);if(!target||!el)return;el.dataset.assistantId=String(assistantId);target.parentNode.insertBefore(el,target);target.parentNode.scrollTop=target.parentNode.scrollHeight}
function restoreThinkingArchive(history){const ids=new Set((Array.isArray(history)?history:[]).filter(x=>!String(x.role||x.kind||'').includes('user')).map(x=>Number(x.id)).filter(Boolean));let list=[];try{list=JSON.parse(localStorage.getItem(thinkingArchiveKey())||'[]')}catch(e){}list=(Array.isArray(list)?list:[]).filter(x=>ids.has(Number(x.assistantId))).slice(-40);localStorage.setItem(thinkingArchiveKey(),JSON.stringify(list));for(const item of list){if(document.querySelector(`.thinkingWrap[data-assistant-id="${Number(item.assistantId)}"]`))continue;const el=thinkingFromArchive(item);placeThinkingBeforeAssistant(el,Number(item.assistantId))}}
'''
    html = replace_js_function(html, "addThinking", "refreshConversationTitles", thinking_block)

    editor_funcs = r'''let editorCrop=null;
function openImageEditor(){if(selectedAttachment?.kind!=='image')return;editorSource={...selectedAttachment};editorTool='crop';const img=new Image();img.onload=()=>{const c=document.getElementById('editorCanvas'),scale=Math.min(1,1800/Math.max(img.naturalWidth,img.naturalHeight));c.width=Math.max(1,Math.round(img.naturalWidth*scale));c.height=Math.max(1,Math.round(img.naturalHeight*scale));c.getContext('2d').drawImage(img,0,0,c.width,c.height);editorCrop={x:0,y:0,w:c.width,h:c.height};wireEditorCanvas();wireCropOverlay();setEditorTool('crop');document.getElementById('imageEditor').classList.add('show');requestAnimationFrame(syncCropOverlay)};img.src='data:'+editorSource.mime+';base64,'+editorSource.base64}
function closeImageEditor(){document.getElementById('imageEditor').classList.remove('show');editorTool='crop';editorCrop=null}
function setEditorTool(tool){editorTool=tool;document.getElementById('toolCrop')?.classList.toggle('on',tool==='crop');document.getElementById('toolDraw')?.classList.toggle('on',tool==='draw');document.getElementById('cropOverlay')?.classList.toggle('show',tool==='crop');if(tool==='crop')requestAnimationFrame(syncCropOverlay)}
function syncCropOverlay(){const c=document.getElementById('editorCanvas'),o=document.getElementById('cropOverlay'),stage=document.getElementById('editorStage');if(!c||!o||!stage||!editorCrop)return;const cr=c.getBoundingClientRect(),sr=stage.getBoundingClientRect(),sx=cr.width/c.width,sy=cr.height/c.height;o.style.left=(cr.left-sr.left+editorCrop.x*sx)+'px';o.style.top=(cr.top-sr.top+editorCrop.y*sy)+'px';o.style.width=(editorCrop.w*sx)+'px';o.style.height=(editorCrop.h*sy)+'px'}
function wireCropOverlay(){const o=document.getElementById('cropOverlay'),c=document.getElementById('editorCanvas');if(!o||!c)return;let drag=null;o.onpointerdown=e=>{if(editorTool!=='crop')return;const h=e.target?.dataset?.handle||'move';drag={mode:h,start:canvasPoint(c,e),rect:{...editorCrop}};o.setPointerCapture(e.pointerId);e.preventDefault()};o.onpointermove=e=>{if(!drag||editorTool!=='crop')return;const p=canvasPoint(c,e),dx=p.x-drag.start.x,dy=p.y-drag.start.y,r={...drag.rect},min=Math.max(28,Math.min(c.width,c.height)*.08);if(drag.mode==='move'){r.x=Math.max(0,Math.min(c.width-r.w,r.x+dx));r.y=Math.max(0,Math.min(c.height-r.h,r.y+dy))}else{let x1=r.x,y1=r.y,x2=r.x+r.w,y2=r.y+r.h;if(drag.mode.includes('w'))x1=Math.max(0,Math.min(x2-min,x1+dx));if(drag.mode.includes('e'))x2=Math.min(c.width,Math.max(x1+min,x2+dx));if(drag.mode.includes('n'))y1=Math.max(0,Math.min(y2-min,y1+dy));if(drag.mode.includes('s'))y2=Math.min(c.height,Math.max(y1+min,y2+dy));r={x:x1,y:y1,w:x2-x1,h:y2-y1}}editorCrop=r;syncCropOverlay();e.preventDefault()};o.onpointerup=o.onpointercancel=()=>{drag=null}}
function wireEditorCanvas(){const c=document.getElementById('editorCanvas');let drawing=false;c.onpointerdown=e=>{if(editorTool!=='draw')return;drawing=true;c.setPointerCapture(e.pointerId);const p=canvasPoint(c,e),ctx=c.getContext('2d');ctx.beginPath();ctx.moveTo(p.x,p.y)};c.onpointermove=e=>{if(!drawing||editorTool!=='draw')return;const p=canvasPoint(c,e),ctx=c.getContext('2d');ctx.lineWidth=Math.max(4,c.width/180);ctx.lineCap='round';ctx.lineJoin='round';ctx.strokeStyle=getComputedStyle(document.documentElement).getPropertyValue('--accent').trim()||'#8d7cff';ctx.lineTo(p.x,p.y);ctx.stroke()};c.onpointerup=c.onpointercancel=()=>{drawing=false}}
'''
    html = replace_js_function(html, "openImageEditor", "canvasPoint", editor_funcs)

    apply_editor = r'''function applyImageEdit(){const src=document.getElementById('editorCanvas'),out=document.createElement('canvas'),r=editorCrop||{x:0,y:0,w:src.width,h:src.height},sx=Math.max(0,Math.round(r.x)),sy=Math.max(0,Math.round(r.y)),sw=Math.max(1,Math.min(src.width-sx,Math.round(r.w))),sh=Math.max(1,Math.min(src.height-sy,Math.round(r.h)));out.width=sw;out.height=sh;out.getContext('2d').drawImage(src,sx,sy,sw,sh,0,0,sw,sh);const data=out.toDataURL('image/jpeg',.9),base64=data.split(',')[1];selectedAttachment={kind:'image',name:(editorSource?.name||'gambar').replace(/\.[^.]+$/,'')+'-edit.jpg',mime:'image/jpeg',base64,size:Math.floor(base64.length*.75)};showAttachment();closeImageEditor()}'''
    reset_start = html.find("function resetEditor(){")
    apply_start = html.find("function applyImageEdit(){", reset_start)
    auto_grow = html.find("function autoGrow(", apply_start)
    if reset_start < 0 or apply_start < 0 or auto_grow < 0:
        raise SystemExit("RC35 editor apply boundary missing")
    html = html[:reset_start] + apply_editor + "\n" + html[auto_grow:]

    update_flow = r'''async function reconnectCoreAfterUpdate(){if(!NATIVE?.connectCore)return false;NATIVE.connectCore();await new Promise(r=>setTimeout(r,700));for(let i=0;i<90;i++){if(connection.connected&&!connection.busy){try{await loadSystem()}catch(e){}return true}await new Promise(r=>setTimeout(r,500))}return false}
async function nativeCoreRecoveryFlow(){if(!NATIVE?.startCoreUpdate)return false;NATIVE.startCoreUpdate();refreshNativeCoreUpdate();for(let i=0;i<1800;i++){await new Promise(r=>setTimeout(r,500));if(!NATIVE.coreUpdateBusy()){refreshNativeCoreUpdate();return !/gagal|error|berhenti|kode [1-9]/i.test(NATIVE.coreUpdateStatus()||'')}}return false}
async function updateConnectedCore(){let state=await core('POST','/api/update/core',{});paintCoreUpdate(state);for(let i=0;i<900&&!['done','error'].includes(state.state);i++){await new Promise(r=>setTimeout(r,1000));state=await core('GET','/api/update/status');paintCoreUpdate(state)}if(state.state!=='done')throw new Error(state.message||'Update Core gagal');document.getElementById('coreUpdateStatus').textContent='Core & dependency diperbarui. Menghubungkan ulang Core…';if(!await reconnectCoreAfterUpdate())throw new Error('Core diperbarui tetapi belum tersambung kembali.');document.getElementById('coreUpdateStatus').textContent='Core & dependency terbaru dan sudah terhubung.';return true}
async function checkAllUpdates(){const btn=document.getElementById('allUpdateBtn');if(btn.disabled)return;btn.disabled=true;btn.textContent='Memeriksa pembaruan…';try{if(connection.termux_installed){let ok=false;if(connection.connected){try{ok=await updateConnectedCore()}catch(e){document.getElementById('coreUpdateStatus').textContent='Jalur Core aktif terputus. Menjalankan recovery updater…'}}if(!ok){ok=await nativeCoreRecoveryFlow();if(!ok)document.getElementById('coreUpdateStatus').textContent=NATIVE?.coreUpdateStatus?.()||'Update Core tidak selesai.'}}if(NATIVE){NATIVE.checkAppUpdate();refreshAppUpdate();for(let i=0;i<240&&NATIVE.appUpdateBusy();i++)await new Promise(r=>setTimeout(r,500));refreshAppUpdate()}}finally{btn.disabled=false;btn.textContent='Periksa pembaruan'}}'''
    html = replace_js_function(html, "checkAllUpdates", "nativeAppUpdate", update_flow)

    html_path.write_text(html, encoding="utf-8")

    updater = updater_path.read_text(encoding="utf-8")
    download_retry = r'''    private static void downloadFile(String url, File target) throws Exception {
        Throwable last = null;
        for (int attempt = 1; attempt <= 3; attempt++) {
            HttpURLConnection conn = null;
            try {
                conn = open(url);
                long declared = conn.getContentLengthLong();
                if (declared > MAX_APK_BYTES) throw new IllegalStateException("APK terlalu besar");
                long total = 0;
                try (InputStream in = conn.getInputStream(); FileOutputStream out = new FileOutputStream(target, false)) {
                    byte[] buf = new byte[32 * 1024];
                    int n;
                    while ((n = in.read(buf)) >= 0) {
                        if (n == 0) continue;
                        total += n;
                        if (total > MAX_APK_BYTES) throw new IllegalStateException("APK melewati batas ukuran");
                        out.write(buf, 0, n);
                    }
                    out.getFD().sync();
                }
                if (total <= 0) throw new IllegalStateException("APK kosong");
                return;
            } catch (Throwable error) {
                last = error;
                if (attempt < 3) Thread.sleep(650L * attempt);
            } finally {
                if (conn != null) conn.disconnect();
            }
        }
        if (last instanceof Exception) throw (Exception) last;
        throw new IllegalStateException(String.valueOf(last));
    }'''
    updater = replace_java_method(
        updater,
        "    private static void downloadFile(String url, File target) throws Exception {",
        "    private static String readText(String url, int limit) throws Exception {",
        download_retry,
        "download retry",
    )
    metadata_retry = r'''    private static String readText(String url, int limit) throws Exception {
        Throwable last = null;
        for (int attempt = 1; attempt <= 3; attempt++) {
            HttpURLConnection conn = null;
            try {
                conn = open(url);
                try (InputStream in = conn.getInputStream(); ByteArrayOutputStream out = new ByteArrayOutputStream()) {
                    byte[] buf = new byte[8192];
                    int total = 0;
                    int n;
                    while ((n = in.read(buf)) >= 0) {
                        if (n == 0) continue;
                        total += n;
                        if (total > limit) throw new IllegalStateException("respons metadata terlalu besar");
                        out.write(buf, 0, n);
                    }
                    return out.toString("UTF-8");
                }
            } catch (Throwable error) {
                last = error;
                if (attempt < 3) Thread.sleep(650L * attempt);
            } finally {
                if (conn != null) conn.disconnect();
            }
        }
        if (last instanceof Exception) throw (Exception) last;
        throw new IllegalStateException(String.valueOf(last));
    }'''
    updater = replace_java_method(
        updater,
        "    private static String readText(String url, int limit) throws Exception {",
        "    private static HttpURLConnection open(String value) throws Exception {",
        metadata_retry,
        "metadata retry",
    )
    updater_path.write_text(updater, encoding="utf-8")

    gradle_text = gradle.read_text(encoding="utf-8")
    gradle_text = replace_once(gradle_text, "versionCode 10034", "versionCode 10035", "versionCode")
    gradle_text = replace_once(gradle_text, "versionName '1.0.0-rc34'", "versionName '1.0.0-rc35'", "versionName")
    gradle.write_text(gradle_text, encoding="utf-8")

    editor_section = html[html.index('<div id="imageEditor"'):html.index('<script>')]
    checks = (
        "RC35: persistent response activity",
        "Berpikir selama",
        "function archiveThinking(",
        "function restoreThinkingArchive(",
        "function finishThinking(",
        "placeThinkingBeforeAssistant",
        "function reconnectCoreAfterUpdate(",
        "function nativeCoreRecoveryFlow(",
        "Core & dependency terbaru dan sudah terhubung.",
        'id="toolCrop"',
        'id="toolDraw"',
        'id="cropOverlay"',
        "function wireCropOverlay(",
        "editorCrop",
        "for (int attempt = 1; attempt <= 3; attempt++)",
        "versionCode 10035",
        "versionName '1.0.0-rc35'",
    )
    combined = html + "\n" + updater + "\n" + gradle_text
    missing = [item for item in checks if item not in combined]
    if missing:
        raise SystemExit(f"RC35 marker hilang: {missing}")
    for forbidden in ("Asli", ">1:1<", ">4:3<", ">16:9<", ">Putar<", ">Balik<", ">Reset<", "Rasio diterapkan"):
        if forbidden in editor_section:
            raise SystemExit(f"RC35 editor masih memuat kontrol lama: {forbidden}")
    send_section = html[html.index("async function sendMessage("):html.index("function renderPluginConfirmation(")]
    if "thinking.remove()" in send_section.split("catch(e){", 1)[0]:
        raise SystemExit("RC35 masih menghapus aktivitas berpikir setelah respons sukses")
    print("FURINAHUB_ANDROID_RC35_COMPANION_POLISH_OK")


if __name__ == "__main__":
    main()
