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
        raise SystemExit(f"RC34 marker mismatch: {label} ({count})")
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
        raise SystemExit(f"RC34 JS boundary mismatch: {name} -> {next_name}")
    return text[:start] + replacement.rstrip() + "\n" + text[end:]


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("usage: apply.py <termux-root>")
    root = Path(sys.argv[1]).resolve()
    app = root / "bridge/app"
    html_path = app / "src/main/assets/furinahub/index.html"
    gradle = app / "build.gradle"
    main_activity = app / "src/main/java/com/wynndev/furinaagentbridge/MainActivity.java"
    for path in (html_path, gradle, main_activity):
        if not path.is_file():
            raise SystemExit(f"RC34 source missing: {path}")

    java = main_activity.read_text(encoding="utf-8")
    java = replace_once(
        java,
        "private final ExecutorService io = Executors.newSingleThreadExecutor();",
        "private final ExecutorService io = Executors.newFixedThreadPool(3);",
        "parallel local bridge requests",
    )
    old_picker = '''    private void pickImage() {
        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        intent.addCategory(Intent.CATEGORY_OPENABLE);
        intent.setType("image/*");
        intent.putExtra(Intent.EXTRA_MIME_TYPES, new String[]{"image/jpeg", "image/png", "image/webp"});
        startActivityForResult(intent, REQ_PICK_IMAGE);
    }
'''
    new_picker = '''    private void pickImage() {
        Intent intent;
        if (Build.VERSION.SDK_INT >= 33) {
            intent = new Intent(MediaStore.ACTION_PICK_IMAGES);
            intent.setType("image/*");
        } else {
            intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
            intent.addCategory(Intent.CATEGORY_OPENABLE);
            intent.setType("image/*");
            intent.putExtra(Intent.EXTRA_MIME_TYPES, new String[]{"image/jpeg", "image/png", "image/webp"});
        }
        startActivityForResult(intent, REQ_PICK_IMAGE);
    }
'''
    java = replace_once(java, old_picker, new_picker, "system photo picker")
    main_activity.write_text(java, encoding="utf-8")

    html = html_path.read_text(encoding="utf-8")
    css = r'''
/* RC34: companion feedback, conversation management, unified updates, image-first UX */
.thinkingWrap{margin:8px 0 12px;max-width:min(88%,690px)}.thinkingToggle{display:flex;align-items:center;gap:9px;min-height:38px;border:0;background:transparent;color:var(--muted);padding:4px 2px;font-weight:650}.thinkingDots{display:flex;gap:3px}.thinkingDots i{display:block;width:5px;height:5px;border-radius:50%;background:currentColor;animation:thinkDot 1.05s infinite ease-in-out}.thinkingDots i:nth-child(2){animation-delay:.14s}.thinkingDots i:nth-child(3){animation-delay:.28s}.thinkingChevron{font-size:15px;transition:transform .18s}.thinkingWrap.open .thinkingChevron{transform:rotate(180deg)}.thinkingDetails{display:none;margin:3px 0 0 2px;padding:10px 12px;border-left:2px solid var(--line);color:var(--muted);font-size:12px;line-height:1.55}.thinkingWrap.open .thinkingDetails{display:block}.thinkingEvent{display:flex;gap:8px;align-items:flex-start}.thinkingEvent+.thinkingEvent{margin-top:5px}.thinkingEvent:before{content:'';width:6px;height:6px;margin-top:6px;border-radius:50%;background:var(--muted);flex:none}.thinkingEvent.current:before{background:var(--accent);box-shadow:0 0 0 4px color-mix(in srgb,var(--accent) 12%,transparent)}
.historyRow{position:relative}.historyRow .historyOpen{padding-right:10px}.historyPin{width:16px;height:16px;flex:none;color:var(--accent)}.historyPin.hiddenPin{visibility:hidden}.historyHint{padding:4px 12px 8px;color:var(--muted);font-size:10px}.conversationMenuTitle{padding:8px 12px 5px;font-size:13px;font-weight:750;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.conversationDanger{color:var(--danger)!important}
.updateUnit{padding:11px 0;border-bottom:1px solid var(--line)}.updateUnit:last-of-type{border-bottom:0}.updateUnitHead{display:flex;align-items:center;gap:10px}.updateUnitHead strong{font-size:14px;flex:1}.updateStatus{margin-top:5px;color:var(--muted);font-size:12px;line-height:1.45}.updateBadge{padding:4px 8px;border-radius:999px;background:var(--surface2);font-size:10px;color:var(--muted)}
.attachmentbar{margin:0 12px 6px;padding:7px;border-radius:17px}.attachmentPreview{width:54px;height:54px;border-radius:13px;cursor:pointer}.msg.user .imageBubble{background:transparent!important;padding:0!important;max-width:min(78vw,390px)}.msg.user .imageBubble .messageImage{width:100%;max-width:390px;border-radius:20px}.msg.user .imageCaption{display:inline-block;margin-top:7px;padding:8px 11px;border-radius:15px;background:var(--accent-soft)}
.editorLayer{background:var(--bg)!important;color:var(--ink)!important}.editorStage{padding:12px 12px 8px!important;background:var(--bg)!important;align-items:center}.editorStage canvas{max-width:100%;max-height:100%;border-radius:18px;background:var(--surface2)!important;box-shadow:0 8px 30px #0003}.editorHeader{display:flex;align-items:center;gap:10px;padding:10px 12px}.editorHeader strong{flex:1;font-size:17px}.editorHeader .btn{min-width:72px}.editorTools{display:flex!important;gap:7px!important;padding:8px 12px!important;background:var(--bg);border-top:1px solid var(--line)}.editorTools button{min-height:42px!important;border:1px solid var(--line)!important;border-radius:13px!important;background:var(--surface)!important;color:var(--ink)!important;padding:0 13px!important}.editorTools button.on{background:var(--accent-soft)!important;color:var(--accent)!important;border-color:var(--accent)!important}.editorBottom{padding:8px 12px 12px!important;background:var(--bg)}
@keyframes thinkDot{0%,70%,100%{opacity:.25;transform:translateY(0)}35%{opacity:1;transform:translateY(-3px)}}
'''
    html = replace_once(html, "</style>", css + "\n</style>", "RC34 CSS")

    update_start = html.find('<div class="card"><h3>Update FurinaHub</h3>')
    advanced_start = html.find('<div id="advancedCard"', update_start)
    if update_start < 0 or advanced_start < 0:
        raise SystemExit("RC34 update-card boundaries missing")
    unified_update = '''<div class="card"><h3>Pembaruan</h3><div class="sub">Satu pemeriksaan untuk FurinaHub, Furina Core, dan dependency runtime.</div><div class="updateUnit"><div class="updateUnitHead"><strong>FurinaHub APK</strong><span class="updateBadge">Aplikasi</span></div><div id="apkUpdateStatus" class="updateStatus">Belum diperiksa.</div></div><div class="updateUnit"><div class="updateUnitHead"><strong>Core & dependency</strong><span class="updateBadge">Runtime</span></div><div id="coreUpdateStatus" class="updateStatus">Belum diperiksa.</div><div class="percentHero"><div id="coreUpdateStage" class="small">Siap diperiksa</div><strong id="coreUpdatePercent">0%</strong></div><div id="coreUpdateProgress" class="determinate hidden"><span></span></div></div><button id="allUpdateBtn" class="btn primary full" style="margin-top:13px" onclick="checkAllUpdates()">Periksa pembaruan</button><button id="coreUpdateBtn" class="hidden" aria-hidden="true"></button></div>'''
    html = html[:update_start] + unified_update + html[advanced_start:]

    html = replace_once(
        html,
        '<div id="messageMenu" class="sheet"></div>',
        '<div id="messageMenu" class="sheet"></div><div id="conversationMenu" class="sheet"></div>',
        "conversation action sheet",
    )

    old_editor = '''<div id="imageEditor" class="editorLayer" role="dialog" aria-modal="true"><div class="viewerTop"><strong>Edit gambar</strong></div><div class="editorStage"><canvas id="editorCanvas"></canvas></div><div class="editorTools"><button id="toolCrop" onclick="setEditorTool('crop')">Pangkas</button><button id="toolDraw" onclick="setEditorTool('draw')">Coret</button><button onclick="setCropRatio(0)">Bebas</button><button onclick="setCropRatio(1)">1:1</button><button onclick="setCropRatio(1.7778)">16:9</button><button onclick="resetEditor()">Reset</button></div><div class="editorBottom"><button class="btn" onclick="closeImageEditor()">Batal</button><button class="btn primary" onclick="applyImageEdit()">Terapkan</button></div></div>'''
    new_editor = '''<div id="imageEditor" class="editorLayer" role="dialog" aria-modal="true"><div class="editorHeader"><button class="btn" onclick="closeImageEditor()">Batal</button><strong>Edit gambar</strong><button class="btn primary" onclick="applyImageEdit()">Selesai</button></div><div class="editorStage"><canvas id="editorCanvas"></canvas></div><div class="editorTools"><button id="ratioOriginal" class="on" onclick="setCropRatio(0,this)">Asli</button><button onclick="setCropRatio(1,this)">1:1</button><button onclick="setCropRatio(1.3333,this)">4:3</button><button onclick="setCropRatio(1.7778,this)">16:9</button><button onclick="rotateEditor()">Putar</button><button onclick="flipEditor()">Balik</button><button id="toolDraw" onclick="setEditorTool('draw')">Coret</button><button onclick="resetEditor()">Reset</button></div><div class="editorBottom"><div class="sub">Rasio diterapkan saat selesai. Coretan hanya dibuat saat mode Coret aktif.</div></div></div>'''
    html = replace_once(html, old_editor, new_editor, "image editor layout")

    html = replace_once(
        html,
        "onMediaPicked(raw){try{selectedAttachment=JSON.parse(raw);showAttachment();if(selectedAttachment.kind==='image')openImageEditor()}catch(e){toast('Lampiran tidak dapat dibaca.')}}",
        "onMediaPicked(raw){try{selectedAttachment=JSON.parse(raw);showAttachment();document.getElementById('chatInput').focus()}catch(e){toast('Lampiran tidak dapat dibaca.')}}",
        "image pick behavior",
    )

    old_show_attachment = "function showAttachment(){const preview=document.getElementById('attachmentPreview'),edit=document.getElementById('editAttachmentBtn');if(!selectedAttachment){preview.removeAttribute('src');preview.classList.remove('show');document.getElementById('attachmentBar').classList.remove('show');return}document.getElementById('attachmentName').textContent=selectedAttachment.name+' · '+Math.ceil((selectedAttachment.size||0)/1024)+' KB';edit.classList.toggle('hidden',selectedAttachment.kind!=='image');if(selectedAttachment.kind==='image'){preview.src='data:'+selectedAttachment.mime+';base64,'+selectedAttachment.base64;preview.classList.add('show')}else{preview.removeAttribute('src');preview.classList.remove('show')}document.getElementById('attachmentBar').classList.add('show')}"
    show_attachment = "function showAttachment(){const preview=document.getElementById('attachmentPreview'),edit=document.getElementById('editAttachmentBtn');if(!selectedAttachment){preview.removeAttribute('src');preview.onclick=null;preview.classList.remove('show');document.getElementById('attachmentBar').classList.remove('show');return}document.getElementById('attachmentName').textContent=selectedAttachment.name+' · '+Math.ceil((selectedAttachment.size||0)/1024)+' KB';edit.classList.toggle('hidden',selectedAttachment.kind!=='image');if(selectedAttachment.kind==='image'){const src='data:'+selectedAttachment.mime+';base64,'+selectedAttachment.base64;preview.src=src;preview.onclick=()=>openImageViewer(src,selectedAttachment.name);preview.classList.add('show')}else{preview.removeAttribute('src');preview.onclick=null;preview.classList.remove('show')}document.getElementById('attachmentBar').classList.add('show')}"
    html = replace_once(html, old_show_attachment, show_attachment, "attachment preview behavior")

    render_conversations = r'''function renderConversations(items,active){const target=document.getElementById('conversationRows');target.innerHTML=items.length?items.map(x=>`<div class="historyRow"><button class="nav historyOpen ${Number(x.id)===Number(active)?'on':''}" data-conversation-id="${Number(x.id)}" onpointerdown="historyHoldStart(event,${Number(x.id)})" onpointerup="historyHoldEnd(event,${Number(x.id)})" onpointercancel="historyHoldCancel()" oncontextmenu="historyContext(event,${Number(x.id)})" onclick="historyTap(event,${Number(x.id)})"><svg class="historyPin ${x.pinned?'':'hiddenPin'}" viewBox="0 0 24 24"><path d="m9 4 6 0 0 5 3 3-6 1-6-1 3-3Z M12 13v7"/></svg><span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(x.title||'Percakapan baru')}</span></button></div>`).join(''):'<div class="empty" style="padding:8px 12px">Belum ada riwayat.</div>';target.dataset.ready='1'}'''
    html = replace_js_function(html, "renderConversations", "addMsg", render_conversations)

    send_message = r'''async function sendMessage(forcedText){const input=document.getElementById('chatInput'),plain=String(forcedText??input.value).trim(),attachment=selectedAttachment;if((!plain&&!attachment)||!connection.connected)return;let text=plain,requestId='chat-'+Date.now().toString(36)+'-'+Math.random().toString(36).slice(2,9),body={message:plain,request_id:requestId};if(attachment?.kind==='text')text=`${plain}\n\n[Lampiran teks: ${attachment.name}]\n${attachment.content}`;if(attachment?.kind==='image')body.image={name:attachment.name,mime:attachment.mime,base64:attachment.base64};body.message=text;clearAttachment();closeSheets();input.value='';autoGrow(input);const pendingUser=addMsg('user',plain||(attachment?.kind==='text'?'File: '+attachment.name:'Gambar'),null,attachment),thinking=addThinking(requestId);document.getElementById('sendBtn').disabled=true;pollThinking(requestId,thinking);try{const result=await core('POST','/api/chat',body);if(result.mode==='plugin_confirmation')renderPluginConfirmation(result);else if(result.mode==='device'&&result.job)renderJob(result.job);else await refreshConversation();thinking.remove();setTimeout(refreshConversationTitles,900);setTimeout(refreshConversationTitles,3200)}catch(e){thinking.remove();pendingUser.remove();if(forcedText===undefined){input.value=plain;autoGrow(input);if(attachment){selectedAttachment=attachment;showAttachment()}}addMsg('assistant','Tidak bisa menghubungi Core: '+e.message)}finally{document.getElementById('sendBtn').disabled=!connection.connected}}'''
    html = replace_js_function(html, "sendMessage", "renderPluginConfirmation", send_message)

    thinking_funcs = r'''function addThinking(requestId){const m=document.getElementById('messages'),d=document.createElement('div');d.className='thinkingWrap';d.dataset.requestId=requestId;d.innerHTML=`<button class="thinkingToggle" onclick="this.parentElement.classList.toggle('open')"><span class="thinkingDots"><i></i><i></i><i></i></span><span class="thinkingLabel">Berfikir…</span><span class="thinkingChevron">⌄</span></button><div class="thinkingDetails"><div class="thinkingEvent current">Menyiapkan…</div></div>`;m.appendChild(d);m.scrollTop=m.scrollHeight;return d}
function paintThinking(el,state){if(!el?.isConnected)return;const label=el.querySelector('.thinkingLabel'),details=el.querySelector('.thinkingDetails'),events=Array.isArray(state?.events)?state.events:[];label.textContent=state?.done?'Selesai':(state?.label||'Berfikir…');details.innerHTML=(events.length?events:[{label:state?.label||'Menyiapkan…'}]).map((x,i)=>`<div class="thinkingEvent ${i===events.length-1&&!state?.done?'current':''}">${esc(x.label||x.phase||'Memproses')}</div>`).join('')}
async function pollThinking(requestId,el){for(let i=0;i<1200&&el?.isConnected;i++){try{const state=await core('GET','/api/chat/progress/'+encodeURIComponent(requestId));paintThinking(el,state);if(state.done)return}catch(e){}await new Promise(r=>setTimeout(r,420))}}
async function refreshConversationTitles(){if(!connection.connected)return;try{const latest=await core('GET','/api/bootstrap');bootData={...(bootData||{}),conversations:latest.conversations||[],active_conversation_id:latest.active_conversation_id};renderConversations(bootData.conversations,bootData.active_conversation_id)}catch(e){}}
'''
    html = html.replace("function renderPluginConfirmation(result){", thinking_funcs + "function renderPluginConfirmation(result){", 1)

    conversation_block = r'''async function newConversation(){drawer(false);if(!connection.connected){go('chat');return}bootData=await core('POST','/api/conversations',{action:'create'});renderBoot();go('chat')}
async function switchConversation(id){if(!connection.connected)return;drawer(false);bootData=await core('POST','/api/conversations',{action:'switch',id});renderBoot();go('chat')}
let historyHoldTimer=null,historyHoldFired=false;
function historyHoldStart(event,id){historyHoldFired=false;clearTimeout(historyHoldTimer);historyHoldTimer=setTimeout(()=>{historyHoldFired=true;openConversationMenu(id)},520)}
function historyHoldEnd(){clearTimeout(historyHoldTimer)}function historyHoldCancel(){clearTimeout(historyHoldTimer)}
function historyContext(event,id){event.preventDefault();historyHoldFired=true;openConversationMenu(id)}
function historyTap(event,id){if(historyHoldFired){event.preventDefault();historyHoldFired=false;return}switchConversation(id)}
function openConversationMenu(id){clearTimeout(historyHoldTimer);const item=(bootData?.conversations||[]).find(x=>Number(x.id)===Number(id));if(!item)return;const menu=document.getElementById('conversationMenu');menu.innerHTML=`<div class="conversationMenuTitle">${esc(item.title||'Percakapan')}</div><button onclick="pinConversation(${Number(id)},${item.pinned?'false':'true'})">${item.pinned?'Lepas sematan':'Sematkan'}</button><button onclick="renameConversation(${Number(id)})">Ganti nama</button><button class="conversationDanger" onclick="deleteConversation(${Number(id)})">Hapus</button>`;showSheet('conversationMenu')}
async function pinConversation(id,pinned){closeSheets();try{bootData=await core('POST','/api/conversations',{action:'pin',id,pinned});renderConversations(bootData.conversations||[],bootData.active_conversation_id)}catch(e){toast(e.message)}}
async function renameConversation(id){const item=(bootData?.conversations||[]).find(x=>Number(x.id)===Number(id));closeSheets();const title=await askText('Ganti nama percakapan','Judul manual tidak akan ditimpa judul otomatis.',{value:item?.title||''});if(title===null||!title.trim())return;try{bootData=await core('POST','/api/conversations',{action:'rename',id,title:title.trim()});renderConversations(bootData.conversations||[],bootData.active_conversation_id)}catch(e){toast(e.message)}}
async function deleteConversation(id){closeSheets();if(!await askConfirm('Hapus percakapan?','Riwayat percakapan ini akan dihapus permanen. Memori penting tetap disimpan.'))return;bootData=await core('POST','/api/conversations',{action:'delete',id});renderBoot()}
'''
    html = replace_js_function(html, "newConversation", "renderJob", conversation_block)

    close_sheets = r'''function closeSheets(){document.getElementById('sheetBack').classList.remove('show');['messageMenu','conversationMenu','plusMenu'].forEach(id=>document.getElementById(id)?.classList.remove('show'))}'''
    html = replace_js_function(html, "closeSheets", "showSheet", close_sheets)

    editor_funcs = r'''function openImageEditor(){if(selectedAttachment?.kind!=='image')return;editorSource={...selectedAttachment};cropRatio=0;editorTool='crop';const img=new Image();img.onload=()=>{const c=document.getElementById('editorCanvas'),scale=Math.min(1,1800/Math.max(img.naturalWidth,img.naturalHeight));c.width=Math.max(1,Math.round(img.naturalWidth*scale));c.height=Math.max(1,Math.round(img.naturalHeight*scale));c.getContext('2d').drawImage(img,0,0,c.width,c.height);wireEditorCanvas();document.querySelectorAll('.editorTools button').forEach(b=>b.classList.remove('on'));document.getElementById('ratioOriginal')?.classList.add('on');document.getElementById('imageEditor').classList.add('show')};img.src='data:'+editorSource.mime+';base64,'+editorSource.base64}
function closeImageEditor(){document.getElementById('imageEditor').classList.remove('show');editorTool='crop'}
function setEditorTool(tool){editorTool=tool;document.getElementById('toolDraw')?.classList.toggle('on',tool==='draw')}
function setCropRatio(ratio,button){cropRatio=Number(ratio)||0;editorTool='crop';document.getElementById('toolDraw')?.classList.remove('on');document.querySelectorAll('.editorTools button').forEach(b=>{if(['Asli','1:1','4:3','16:9'].includes(b.textContent.trim()))b.classList.remove('on')});button?.classList.add('on')}
function rotateEditor(){const c=document.getElementById('editorCanvas'),tmp=document.createElement('canvas');tmp.width=c.height;tmp.height=c.width;const ctx=tmp.getContext('2d');ctx.translate(tmp.width/2,tmp.height/2);ctx.rotate(Math.PI/2);ctx.drawImage(c,-c.width/2,-c.height/2);c.width=tmp.width;c.height=tmp.height;c.getContext('2d').drawImage(tmp,0,0)}
function flipEditor(){const c=document.getElementById('editorCanvas'),tmp=document.createElement('canvas');tmp.width=c.width;tmp.height=c.height;const ctx=tmp.getContext('2d');ctx.translate(tmp.width,0);ctx.scale(-1,1);ctx.drawImage(c,0,0);c.getContext('2d').clearRect(0,0,c.width,c.height);c.getContext('2d').drawImage(tmp,0,0)}
function wireEditorCanvas(){const c=document.getElementById('editorCanvas');let drawing=false;c.onpointerdown=e=>{if(editorTool!=='draw')return;drawing=true;c.setPointerCapture(e.pointerId);const p=canvasPoint(c,e),ctx=c.getContext('2d');ctx.beginPath();ctx.moveTo(p.x,p.y)};c.onpointermove=e=>{if(!drawing||editorTool!=='draw')return;const p=canvasPoint(c,e),ctx=c.getContext('2d');ctx.lineWidth=Math.max(4,c.width/180);ctx.lineCap='round';ctx.lineJoin='round';ctx.strokeStyle=getComputedStyle(document.documentElement).getPropertyValue('--accent').trim()||'#8d7cff';ctx.lineTo(p.x,p.y);ctx.stroke()};c.onpointerup=c.onpointercancel=()=>{drawing=false}}
'''
    html = replace_js_function(html, "openImageEditor", "canvasPoint", editor_funcs)

    old_reset_start = "function resetEditor(){"
    reset_pos = html.find(old_reset_start)
    apply_pos = html.find("function applyImageEdit(){", reset_pos)
    if reset_pos < 0 or apply_pos < 0:
        raise SystemExit("RC34 reset editor boundary missing")
    reset_fn = r'''function resetEditor(){if(!editorSource)return;cropRatio=0;editorTool='crop';document.querySelectorAll('.editorTools button').forEach(b=>b.classList.remove('on'));document.getElementById('ratioOriginal')?.classList.add('on');const img=new Image();img.onload=()=>{const c=document.getElementById('editorCanvas'),scale=Math.min(1,1800/Math.max(img.naturalWidth,img.naturalHeight));c.width=Math.max(1,Math.round(img.naturalWidth*scale));c.height=Math.max(1,Math.round(img.naturalHeight*scale));c.getContext('2d').drawImage(img,0,0,c.width,c.height);wireEditorCanvas()};img.src='data:'+editorSource.mime+';base64,'+editorSource.base64}
'''
    html = html[:reset_pos] + reset_fn + html[apply_pos:]

    unified_js = r'''async function checkAllUpdates(){const btn=document.getElementById('allUpdateBtn');if(btn.disabled)return;btn.disabled=true;btn.textContent='Memeriksa pembaruan…';try{if(connection.termux_installed){if(connection.connected){try{let state=await core('POST','/api/update/core',{});paintCoreUpdate(state);for(let i=0;i<900&&!['done','error'].includes(state.state);i++){await new Promise(r=>setTimeout(r,1000));state=await core('GET','/api/update/status');paintCoreUpdate(state)}}catch(e){document.getElementById('coreUpdateStatus').textContent='Core: '+e.message}}else if(NATIVE?.startCoreUpdate){NATIVE.startCoreUpdate();for(let i=0;i<900&&NATIVE.coreUpdateBusy();i++){refreshNativeCoreUpdate();await new Promise(r=>setTimeout(r,1000))}refreshNativeCoreUpdate()}}if(NATIVE){NATIVE.checkAppUpdate();refreshAppUpdate();for(let i=0;i<240&&NATIVE.appUpdateBusy();i++)await new Promise(r=>setTimeout(r,500));refreshAppUpdate()}}finally{btn.disabled=false;btn.textContent='Periksa pembaruan'}}
'''
    html = html.replace("function nativeAppUpdate(){", unified_js + "function nativeAppUpdate(){", 1)

    html_path.write_text(html, encoding="utf-8")

    gradle_text = gradle.read_text(encoding="utf-8")
    gradle_text = replace_once(gradle_text, "versionCode 10033", "versionCode 10034", "versionCode")
    gradle_text = replace_once(gradle_text, "versionName '1.0.0-rc33'", "versionName '1.0.0-rc34'", "versionName")
    gradle.write_text(gradle_text, encoding="utf-8")

    checks = (
        "Executors.newFixedThreadPool(3)",
        "MediaStore.ACTION_PICK_IMAGES",
        "RC34: companion feedback",
        'id="allUpdateBtn"',
        'id="conversationMenu"',
        "function addThinking(",
        "/api/chat/progress/",
        "function openConversationMenu(",
        "action:'rename'",
        "action:'pin'",
        "function rotateEditor(",
        "function flipEditor(",
        "setCropRatio(1.3333",
        "versionCode 10034",
        "versionName '1.0.0-rc34'",
    )
    combined = java + "\n" + html + "\n" + gradle_text
    missing = [m for m in checks if m not in combined]
    if missing:
        raise SystemExit(f"RC34 marker hilang: {missing}")
    if "if(selectedAttachment.kind==='image')openImageEditor()" in html:
        raise SystemExit("RC34 masih memaksa editor setelah memilih gambar")
    print("FURINAHUB_ANDROID_RC34_COMPANION_UX_OK")


if __name__ == "__main__":
    main()
