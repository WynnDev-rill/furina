#!/usr/bin/env python3
"""Render settings from the paired Termux Core without retired-agent DOM calls."""
from __future__ import annotations
import sys
from pathlib import Path

ROOT=Path(sys.argv[1] if len(sys.argv)>1 else '/tmp/furina-agent-rc54-validate/termux')
APP=ROOT/'bridge/app'; BUILD=APP/'build.gradle'; HTML=APP/'src/main/assets/furinahub/index.html'; MAIN=APP/'src/main/java/com/wynndev/furinaagentbridge/MainActivity.java'
text=BUILD.read_text(encoding='utf-8')
if 'versionCode 10082' not in text or "versionName '1.1.14'" not in text: raise SystemExit('expected Android 1.1.14')
BUILD.write_text(text.replace('versionCode 10082','versionCode 10083',1).replace("versionName '1.1.14'","versionName '1.1.15'",1),encoding='utf-8')
text=MAIN.read_text(encoding='utf-8')
for old,new,label in (
 ('private static final String EXPECTED_BUNDLE_ID = "furina-2026.08.25-private-1.1.14";', 'private static final String EXPECTED_BUNDLE_ID = "furina-2026.08.25-private-1.1.15";', 'bundle'),
 ('private static final String EXPECTED_CORE_VERSION = "1.1.14";', 'private static final String EXPECTED_CORE_VERSION = "1.1.15";', 'core'),
 ('private static final String EXPECTED_DEPENDENCY_REVISION = "2026.08.25-r64";', 'private static final String EXPECTED_DEPENDENCY_REVISION = "2026.08.25-r65";', 'revision'),
):
    if old not in text: raise SystemExit(f'{label} marker missing')
    text=text.replace(old,new,1)
MAIN.write_text(text,encoding='utf-8')

page=HTML.read_text(encoding='utf-8')
if 'FURINA_FINAL_116_TERMUX_STATE_RENDER' in page: raise SystemExit('render repair already applied')
for old,new,label in (
 ('<div id="modelsOnline" class="hidden">', '<div id="modelsOnline" class="hidden"><div id="modelsTermuxState116" class="sub" aria-live="polite"></div>', 'model state marker'),
 ('<div id="personalOnline" class="hidden">', '<div id="personalOnline" class="hidden"><div id="personalTermuxState116" class="sub" aria-live="polite"></div>', 'personal state marker'),
):
    if old not in page: raise SystemExit(f'{label} missing')
    page=page.replace(old,new,1)
insert=r'''
/* FURINA_FINAL_116_TERMUX_STATE_RENDER */
function renderTermuxState116(){
 const at=new Date().toLocaleTimeString('id-ID',{hour:'2-digit',minute:'2-digit'});
 ['modelsTermuxState116','personalTermuxState116'].forEach(id=>{const el=document.getElementById(id);if(el)el.textContent='Data aktif dibaca langsung dari Furina di Termux · diperbarui '+at+'.'});
}
function renderModels(){
 if(!settingsData)return;
 const c=settingsData.core||{},catalog=Array.isArray(settingsData.model_catalog)?settingsData.model_catalog:[];
 const localActive=c.routing_mode==='local'&&catalog.some(x=>x.active&&x.installed);
 const routing=document.getElementById('routingSeg');
 if(routing)routing.innerHTML=`<button class="${c.routing_mode==='online'?'on':''}" onclick="selectOnlineModel()">Online${c.routing_mode==='online'?' · Aktif':' · Pilih'}</button>${localActive?'<button class="on" disabled>Model lokal · Aktif</button>':''}`;
 const locals=document.getElementById('localModelRows');
 if(locals)locals.innerHTML=catalog.map(x=>modelRow(x,c)).join('')||'<div class="empty">Katalog model lokal belum tersedia di Termux.</div>';
 const providers=document.getElementById('providerRows');
 if(providers){const rows=Array.isArray(settingsData.providers)?settingsData.providers:[];providers.innerHTML=rows.length?rows.map(p=>`<div class="row"><div class="rowmain"><div class="rowtitle">${esc(p.label)}</div><div class="rowdesc">${p.configured?'API key tersimpan: '+esc(p.masked||'••••'):'Belum dikonfigurasi di Termux'}</div></div><div class="stack"><button class="btn" onclick="configureProvider('${p.id}',${p.configured})">${p.configured?'Ubah':'Atur'}</button>${p.configured?`<button class="btn" onclick="testProvider('${p.id}')">Tes koneksi</button>`:''}</div></div>`).join(''):'<div class="empty">Tidak ada provider yang dikenali oleh Core Termux.</div>'}
 paintModelProgress(settingsData.model_status||{});renderTermuxState116();
}
function renderAgent(){} // Agent/device controls were removed; never touch their retired DOM.
function renderSystem(){} // System details are connection-only in this final build.
async function refreshSharedSettings(){try{settingsData=await core('GET','/api/settings');renderSettings();renderModels();const brand=document.getElementById('brand');if(brand)brand.textContent=settingsData.hub?.assistant_name||'FurinaHub'}catch(e){toast(e.message)}}
async function syncCore(){if(!connection.connected)return;try{[bootData,settingsData,systemData,memoryData]=await Promise.all([core('GET','/api/bootstrap'),core('GET','/api/settings'),core('GET','/api/system'),core('GET','/api/memory')]);renderBoot();renderSettings();renderModels();renderMemory();renderTermuxState116();loadWorkspaceExtras();loadRelationship()}catch(e){toast(e.message)}}
function go(id){closeSheets();document.querySelectorAll('.view,.chatview').forEach(x=>x.classList.remove('active'));const view=document.getElementById(id);if(view)view.classList.add('active');document.querySelectorAll('.nav').forEach(x=>x.classList.toggle('on',x.dataset.view===id));drawer(false);if(connection.connected){if(id==='memory')loadMemory();if(id==='relationship')loadRelationship();if(id==='personalization'||id==='models')refreshSharedSettings()}}
'''
marker=page.rfind('</script>')
if marker < 0: raise SystemExit('script marker missing')
# Earlier overlays append multiple script blocks.  This guard must be in the
# final block, otherwise a later legacy renderer overrides it again.
HTML.write_text(page[:marker]+insert+page[marker:],encoding='utf-8')
print('FURINA_FINAL_116_ANDROID_OK')
