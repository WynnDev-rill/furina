#!/usr/bin/env python3
from __future__ import annotations
import re
import sys
from pathlib import Path

ROOT=Path(sys.argv[1] if len(sys.argv)>1 else '/tmp/furina-final-impl/termux')
APP=ROOT/'bridge/app'; BUILD=APP/'build.gradle'; MAIN=APP/'src/main/java/com/wynndev/furinaagentbridge/MainActivity.java'; HTML=APP/'src/main/assets/furinahub/index.html'; MANIFEST=APP/'src/main/AndroidManifest.xml'

text=BUILD.read_text(encoding='utf-8')
if 'versionCode 10077' not in text or "versionName '1.1.9'" not in text: raise SystemExit('expected Android 1.1.9')
BUILD.write_text(text.replace('versionCode 10077','versionCode 10079',1).replace("versionName '1.1.9'","versionName '1.1.11'",1),encoding='utf-8')

# Accessibility, root/Shizuku capability, persistent service and boot receiver
# belong to the retired agent. APK keeps only Termux launch, chat and APK install.
text=MANIFEST.read_text(encoding='utf-8')
for exact in ('    <uses-permission android:name="android.permission.FOREGROUND_SERVICE" />\n','    <uses-permission android:name="android.permission.FOREGROUND_SERVICE_SPECIAL_USE" />\n','    <uses-permission android:name="android.permission.RECEIVE_BOOT_COMPLETED" />\n','    <uses-permission android:name="android.permission.POST_NOTIFICATIONS" />\n','    <uses-permission android:name="android.permission.SCHEDULE_EXACT_ALARM" />\n'):
    text=text.replace(exact,'')
text=re.sub(r'\n        <provider\n            android:name="rikka\.shizuku\.ShizukuProvider".*?/>\n','\n',text,flags=re.S)
text=re.sub(r'\n        <service\n            android:name="\.BridgeForegroundService".*?</service>\n','\n',text,flags=re.S)
text=re.sub(r'\n        <service\n            android:name="\.FurinaAccessibilityService".*?</service>\n','\n',text,flags=re.S)
text=re.sub(r'\n        <receiver\n            android:name="\.ReminderReceiver".*?/>\n','\n',text,flags=re.S)
text=re.sub(r'\n        <receiver\n            android:name="\.BootReceiver".*?</receiver>\n','\n',text,flags=re.S)
if 'AccessibilityService' in text or 'Shizuku' in text or 'BridgeForegroundService' in text: raise SystemExit('agent manifest residue')
MANIFEST.write_text(text,encoding='utf-8')

text=MAIN.read_text(encoding='utf-8')
text=text.replace('private static final int MAX_IMAGE_BYTES = 6_000_000;', 'private static final int MAX_IMAGE_BYTES = 2_000_000;\n    private static final int MAX_IMAGE_EDGE = 1600;',1)
text=text.replace('private static final String EXPECTED_BUNDLE_ID = "furina-2026.08.25-private-1.1.9";', 'private static final String EXPECTED_BUNDLE_ID = "furina-2026.08.25-private-1.1.11";',1)
text=text.replace('private static final String EXPECTED_CORE_VERSION = "1.1.9";', 'private static final String EXPECTED_CORE_VERSION = "1.1.11";',1)
text=text.replace('private static final String EXPECTED_DEPENDENCY_REVISION = "2026.08.25-r59";', 'private static final String EXPECTED_DEPENDENCY_REVISION = "2026.08.25-r61";',1)
text=text.replace('        BridgeForegroundService.start(this);\n','',1)
text=text.replace('runFixedTermux("/data/data/com.termux/files/usr/bin/furina-apk-confirm", new String[]{"furina-2026.08.25-private-1.1.9"});','runFixedTermux("/data/data/com.termux/files/usr/bin/furina-apk-confirm", new String[]{"furina-2026.08.25-private-1.1.11"});',1)
needle='        BridgePrefs.openBootstrapWindow(this, 120_000L);\n'
if needle not in text: raise SystemExit('resume marker missing')
text=text.replace(needle, needle+'        probeSavedCore();\n',1)
# Browser-selected images are decoded/downscaled before Base64 reaches WebView.
start=text.find('    private void readImage(Uri uri) {'); end=text.find('    private void emitImage(',start)
if start<0 or end<0: raise SystemExit('readImage marker missing')
replacement='''    private byte[] prepareImage(Uri uri) throws Exception {
        ImageDecoder.Source source = ImageDecoder.createSource(getContentResolver(), uri);
        Bitmap bitmap = ImageDecoder.decodeBitmap(source, (decoder, info, ignored) -> {
            int width=info.getSize().getWidth(), height=info.getSize().getHeight(), longest=Math.max(width,height);
            if(longest>MAX_IMAGE_EDGE){float scale=(float)MAX_IMAGE_EDGE/longest; decoder.setTargetSize(Math.max(1,Math.round(width*scale)),Math.max(1,Math.round(height*scale)));}
            decoder.setAllocator(ImageDecoder.ALLOCATOR_SOFTWARE);
        });
        ByteArrayOutputStream out=new ByteArrayOutputStream(); bitmap.compress(Bitmap.CompressFormat.JPEG,88,out);
        if(out.size()>MAX_IMAGE_BYTES){out.reset();bitmap.compress(Bitmap.CompressFormat.JPEG,76,out);}
        if(out.size()>MAX_IMAGE_BYTES) throw new IllegalArgumentException("Gambar terlalu besar setelah dioptimalkan.");
        return out.toByteArray();
    }

    private void readImage(Uri uri) {
        io.execute(() -> { try {
            String name="gambar"; try(Cursor cursor=getContentResolver().query(uri,new String[]{OpenableColumns.DISPLAY_NAME},null,null,null)){if(cursor!=null&&cursor.moveToFirst()){int i=cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME);if(i>=0)name=cursor.getString(i);}}
            emitImage(name==null?"gambar":name,"image/jpeg",prepareImage(uri));
        } catch(Throwable error){handler.post(() -> Toast.makeText(MainActivity.this,String.valueOf(error.getMessage()),Toast.LENGTH_LONG).show());} });
    }

'''
text=text[:start]+replacement+text[end:]
# Camera uses the same bounded transport path.
cam_start=text.find('    private void readCameraImage(Uri uri) {'); cam_end=text.find('    private void editImage(',cam_start)
if cam_start<0 or cam_end<0: raise SystemExit('camera marker missing')
text=text[:cam_start]+'''    private void readCameraImage(Uri uri) { io.execute(() -> { try { emitImage("kamera.jpg", "image/jpeg", prepareImage(uri)); } catch(Throwable error) { handler.post(() -> Toast.makeText(MainActivity.this,String.valueOf(error.getMessage()),Toast.LENGTH_LONG).show()); } }); }

'''+text[cam_end:]
MAIN.write_text(text,encoding='utf-8')

page=HTML.read_text(encoding='utf-8')
page=page.replace('<button class="send" id="sendBtn" aria-label="Kirim pesan" onclick="sendMessage()" disabled>', '<button class="send hidden" id="stopBtn" aria-label="Hentikan jawaban" onclick="stopActiveChat()">■</button><button class="send" id="sendBtn" aria-label="Kirim pesan" onclick="sendMessage()" disabled>',1)
insert=r'''
/* FURINA_FINAL_112_UI */
let finalActiveChatId='';
function go(id){closeSheets();document.querySelectorAll('.view,.chatview').forEach(x=>x.classList.remove('active'));const view=document.getElementById(id);if(view)view.classList.add('active');document.querySelectorAll('.nav').forEach(x=>x.classList.toggle('on',x.dataset.view===id));drawer(false);if(connection.connected){if(id==='memory')loadMemory();if(id==='settings')loadSystem();if(id==='relationship')loadRelationship();if(id==='personalization')refreshSharedSettings();if(id==='plugins')loadPlugins()}}
function applyConnection(){const dot=document.getElementById('topDot'),top=document.getElementById('topStatus'),msg=document.getElementById('connectionMessage'),badge=document.getElementById('connectionBadge'),btn=document.getElementById('connectBtn'),input=document.getElementById('chatInput'),send=document.getElementById('sendBtn');if(dot)dot.className='dot '+(connection.connected?'ok':connection.busy?'busy':'');if(top)top.textContent=connection.connected?'Siap':connection.busy?'Menghubungkan…':'Offline';if(msg)msg.textContent=connection.message||'';if(badge){badge.textContent=connection.connected?'Terhubung':connection.state==='permission_required'?'Perlu izin':'Offline';badge.className='badge '+(connection.connected?'ok':connection.state==='permission_required'?'warn':'')}if(btn){btn.disabled=!!connection.busy;btn.textContent=connection.connected?'Hubungkan ulang':connection.busy?'Menghubungkan…':'Hubungkan ke Termux'}if(input){input.disabled=!connection.connected;input.placeholder=connection.connected?'Ketik pesan…':'Hubungkan Core untuk mulai…'}if(send)send.disabled=!connection.connected||!!finalActiveChatId;const advanced=document.getElementById('advancedCard');if(advanced)advanced.classList.add('hidden');['memory','models','personal'].forEach(k=>{const off=document.getElementById(k+'Offline'),on=document.getElementById(k+'Online');if(off)off.classList.toggle('hidden',connection.connected);if(on)on.classList.toggle('hidden',!connection.connected)});if(!connection.connected)renderDisconnectedChat()}
function renderAgent(){}
async function stopActiveChat(){const id=finalActiveChatId;if(!id)return;try{await core('POST','/api/chat/cancel',{request_id:id});toast('Jawaban dihentikan.')}catch(e){toast(e.message)}finally{finalActiveChatId='';document.getElementById('stopBtn')?.classList.add('hidden');applyConnection()}}
async function sendMessage(forcedText){const input=document.getElementById('chatInput'),plain=String(forcedText??input.value).trim(),attachment=selectedAttachment;if((!plain&&!attachment)||!connection.connected||finalActiveChatId)return;const requestId='chat-'+Date.now().toString(36)+'-'+Math.random().toString(36).slice(2,9),body={message:plain,request_id:requestId};if(attachment?.kind==='text')body.message=`${plain}\n\n[Lampiran teks: ${attachment.name}]\n${attachment.content}`;if(attachment?.kind==='image')body.image={name:attachment.name,mime:attachment.mime,base64:attachment.base64};clearAttachment();input.value='';autoGrow(input);const pendingUser=addMsg('user',plain||(attachment?.kind==='text'?'File: '+attachment.name:'Gambar'),null,attachment),thinking=addThinking(requestId);let assistant=null,lastPartial='';finalActiveChatId=requestId;document.getElementById('stopBtn')?.classList.remove('hidden');applyConnection();try{await core('POST','/api/chat/start',body);for(let i=0;i<3600&&finalActiveChatId===requestId;i++){const state=await core('GET','/api/chat/progress/'+encodeURIComponent(requestId));paintThinking(thinking,state);const partial=String(state.partial||'');if(partial&&partial!==lastPartial){if(!assistant)assistant=addMsg('assistant','');assistant.querySelector('.bubble').textContent=partial;lastPartial=partial}if(state.done){if(state.cancelled){thinking.remove();assistant?.remove();pendingUser.remove();break}if(state.error)throw new Error(state.error);const result=state.result||{},answer=String(result.answer||partial||'');if(!assistant)assistant=addMsg('assistant',answer);else assistant.querySelector('.bubble').textContent=answer;if(Number(result.user_message_id)>0)pendingUser.dataset.id=String(result.user_message_id);if(Number(result.assistant_message_id)>0)assistant.dataset.id=String(result.assistant_message_id);thinking.remove();break}await new Promise(r=>setTimeout(r,110))}}catch(e){thinking.remove();assistant?.remove();pendingUser.remove();if(forcedText===undefined){input.value=plain;autoGrow(input)}addMsg('assistant','Tidak bisa menghubungi Core: '+e.message)}finally{if(finalActiveChatId===requestId)finalActiveChatId='';document.getElementById('stopBtn')?.classList.add('hidden');applyConnection();setTimeout(refreshConversationTitles,400)}}
'''
if '</script>' not in page: raise SystemExit('script marker missing')
page=page.replace('</script>',insert+'</script>',1)
HTML.write_text(page,encoding='utf-8')
print('FURINA_FINAL_112_ANDROID_OK')
