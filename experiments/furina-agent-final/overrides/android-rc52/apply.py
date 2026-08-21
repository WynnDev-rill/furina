#!/usr/bin/env python3
from pathlib import Path
import shutil,sys

OLD_BUNDLE='furina-2026.08.21-rc63-rc51'
NEW_BUNDLE='furina-2026.08.21-rc64-rc52'

def once(text, old, new, label):
    if old not in text:
        if new in text: return text
        raise SystemExit(f'RC52 marker missing: {label}')
    return text.replace(old,new,1)

def main():
    if len(sys.argv)!=2: raise SystemExit('usage: apply.py <furina-root>')
    root=Path(sys.argv[1]).resolve(); app=root/'bridge/app'; java=app/'src/main/java/com/wynndev/furinaagentbridge'; html=app/'src/main/assets/furinahub/index.html'
    gradle=app/'build.gradle'; main_path=java/'MainActivity.java'; runtime=java/'BridgeRuntime.java'
    for path in (gradle,main_path,runtime,html):
        if not path.is_file(): raise SystemExit(f'RC52 source missing: {path}')
    g=once(gradle.read_text(),'versionCode 10051','versionCode 10052','version code')
    g=once(g,"versionName '1.0.0-rc51'","versionName '1.0.0-rc52'",'version name')
    m=main_path.read_text().replace(OLD_BUNDLE,NEW_BUNDLE)
    m=once(m,'EXPECTED_CORE_VERSION = "1.0.0-rc63"','EXPECTED_CORE_VERSION = "1.0.0-rc64"','core target')
    r=runtime.read_text().replace(OLD_BUNDLE,NEW_BUNDLE)
    page=html.read_text(encoding='utf-8')
    focus_section='''<section id="focus" class="view"><div class="sectionhead"><h1>Fokus</h1><div class="sub">Tujuan dan hal yang ingin kamu tindaklanjuti. Furina hanya membuatnya saat kamu menyetujui.</div></div><div id="focusOffline" class="card"></div><div id="focusOnline" class="hidden"><button class="btn primary full" onclick="addFocus()">+ Tambah fokus</button><div class="card"><h3>Aktif</h3><div id="focusRows"></div></div></div></section>'''
    page=once(page,'<section id="models" class="view">',focus_section+'<section id="models" class="view">','focus section')
    nav='<button class="nav" data-view="focus" onclick="go(\'focus\')"><svg viewBox="0 0 24 24"><path d="M12 3v18M3 12h18"/><circle cx="12" cy="12" r="7"/></svg>Fokus</button>'
    page=once(page,'<button class="nav" data-view="models"',nav+'<button class="nav" data-view="models"','focus navigation')
    inbox='<div class="card"><h3>Kotak Masuk Memori</h3><div class="sub">Usulan baru menunggu keputusanmu sebelum menjadi ingatan.</div><div id="memoryInboxRows"></div></div>'
    page=once(page,'<div class="card"><h3>Memori penting</h3>',inbox+'<div class="card"><h3>Memori penting</h3>','memory inbox')
    profile='<div class="card"><h3>Profil respons</h3><div class="sub">Mengatur kualitas, kecepatan, dan privasi tanpa memilih parameter model.</div><div id="responseProfiles" class="seg" style="margin-top:10px"></div></div>'
    page=once(page,'<div id="personalOnline" class="hidden">','<div id="personalOnline" class="hidden">'+profile,'response profiles')
    page=once(page,"if(id==='memory')loadMemory();","if(id==='memory')loadMemory();if(id==='focus')loadFocus();",'focus loader')
    page=once(page,"async function addMemoryPrompt(){const text=await askText('Tambah memori','Informasi ini disimpan langsung di Core Termux.',{multiline:true});if(!text?.trim())return;memoryData=await core('POST','/api/memory',{action:'add',text:text.trim()});renderMemory();toast('Memori ditambahkan.')}","async function addMemoryPrompt(){const text=await askText('Usulkan memori','Kamu dapat meninjau dan menerimanya sebelum menjadi ingatan Furina.',{multiline:true});if(!text?.trim())return;await core('POST','/api/memory/inbox',{action:'propose',text:text.trim(),source_ref:'FurinaHub'});await loadMemory();await loadWorkspaceExtras();toast('Usulan masuk ke Kotak Masuk Memori.')}",'memory inbox action')
    extra=r'''
async function loadFocus(){try{const d=await core('GET','/api/workspace');renderFocus(d)}catch(e){toast(e.message)}}
function renderFocus(data){const online=document.getElementById('focusOnline'),offline=document.getElementById('focusOffline');if(!connection.connected){online.classList.add('hidden');offline.innerHTML=iconOffline('Fokus membutuhkan Core','Hubungkan Furina Lite di Termux untuk menyimpan rencana bersama.');return}offline.innerHTML='';online.classList.remove('hidden');const rows=Array.isArray(data?.focus)?data.focus:[];document.getElementById('focusRows').innerHTML=rows.length?rows.map(x=>{const due=Number(x.due_at||0);const when=due?new Date(due*1000).toLocaleString('id-ID',{dateStyle:'medium',timeStyle:'short'}):'tanpa waktu';return `<div class="row"><div class="rowmain"><div class="rowtitle">${esc(x.text)}</div><div class="rowdesc">${esc(when)}</div></div><button class="btn" onclick="finishFocus(${Number(x.id)})">Selesai</button></div>`}).join(''):'<div class="empty">Belum ada Fokus aktif.</div>'}
async function addFocus(){const text=await askText('Tambah Fokus','Apa yang ingin kamu lanjutkan?',{multiline:true});if(!text?.trim())return;const when=await askText('Waktu (opsional)','Contoh: besok sore atau 24 Agustus 19:00');try{const d=await core('POST','/api/focus',{action:'add',text:text.trim(),when:(when||'').trim()});renderFocus(d);toast('Fokus disimpan di Furina Lite dan FurinaHub.')}catch(e){toast(e.message)}}
async function finishFocus(id){try{const d=await core('POST','/api/focus',{action:'done',id});renderFocus(d);toast('Fokus diselesaikan.')}catch(e){toast(e.message)}}
async function loadWorkspaceExtras(){if(!connection.connected)return;try{const d=await core('GET','/api/workspace');renderFocus(d);renderResponseProfiles(d.profile);const inbox=Array.isArray(d.memory_inbox)?d.memory_inbox:[];const el=document.getElementById('memoryInboxRows');if(el)el.innerHTML=inbox.length?inbox.map(x=>`<div class="row"><div class="rowmain"><div class="rowtitle">${esc(x.text)}</div><div class="rowdesc">Perlu ditinjau</div></div><button class="btn primary" onclick="decideInbox(${Number(x.id)},'accept')">Terima</button><button class="btn" onclick="decideInbox(${Number(x.id)},'reject')">Tolak</button></div>`).join(''):'<div class="empty">Tidak ada usulan baru.</div>'}catch(e){}}
function renderResponseProfiles(profile){const el=document.getElementById('responseProfiles');if(!el||!profile)return;el.innerHTML=(profile.profiles||[]).map(x=>`<button class="${x.id===profile.current?'on':''}" onclick="setResponseProfile('${esc(x.id)}')">${esc(x.label)}</button>`).join('')}
async function setResponseProfile(profile){try{const data=await core('POST','/api/profile',{profile});renderResponseProfiles(data);toast('Profil respons disimpan untuk Furina Lite dan FurinaHub.')}catch(e){toast(e.message)}}
async function decideInbox(id,action){try{await core('POST','/api/memory/inbox',{id,action});await loadMemory();await loadWorkspaceExtras();toast(action==='accept'?'Memori disimpan.':'Usulan ditolak.')}catch(e){toast(e.message)}}
'''
    if 'async function loadFocus()' not in page:
        pos=page.rfind('</script>')
        if pos<0: raise SystemExit('RC52 marker missing: script close')
        page=page[:pos]+extra+page[pos:]
    # Workspace cards need a fresh draw when the existing screen is opened.
    page=once(page,'renderMemory();}','renderMemory();loadWorkspaceExtras();}','memory workspace refresh')
    gradle.write_text(g);main_path.write_text(m);runtime.write_text(r);html.write_text(page,encoding='utf-8')
    combined='\n'.join((g,m,r,page))
    for marker in ('versionCode 10052',"versionName '1.0.0-rc52'",NEW_BUNDLE,'EXPECTED_CORE_VERSION = "1.0.0-rc64"','id="focus"','Kotak Masuk Memori','async function loadFocus()','Profil respons'):
        if marker not in combined: raise SystemExit(f'RC52 integration incomplete: {marker}')
    print('FURINAHUB_ANDROID_RC52_LITE_FULL_OK')

if __name__=='__main__': main()
