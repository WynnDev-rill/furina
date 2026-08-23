#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/furina-agent-rc54-validate/termux")
APP = ROOT / "bridge/app"
HTML = APP / "src/main/assets/furinahub/index.html"
BUILD = APP / "build.gradle"
MAIN = APP / "src/main/java/com/wynndev/furinaagentbridge/MainActivity.java"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one match, got {count}")
    return text.replace(old, new, 1)


build = BUILD.read_text(encoding="utf-8")
build = replace_once(build, "versionCode 10058", "versionCode 10059", "version code")
build = replace_once(build, "versionName '1.0.0'", "versionName '1.0.1'", "version name")
BUILD.write_text(build, encoding="utf-8")

main = MAIN.read_text(encoding="utf-8")
main = main.replace('EXPECTED_CORE_VERSION = "1.0.0"', 'EXPECTED_CORE_VERSION = "1.0.1"')
main = main.replace('furina-2026.08.23-private-1.0.0', 'furina-2026.08.23-private-1.0.1')
MAIN.write_text(main, encoding="utf-8")

page = HTML.read_text(encoding="utf-8")

# Memory remains available to the engine/API but is no longer a product screen.
page, nav_count = re.subn(r'<button class="nav" data-view="memory".*?</button>\n?', '', page, count=1)
if nav_count != 1:
    raise SystemExit(f"memory nav: expected one match, got {nav_count}")
page = replace_once(page, '<section id="memory" class="view">', '<section id="memory" class="view hidden" aria-hidden="true">', "memory view")

# Provider & Model now owns the two explicit on-demand local models. There is
# no AUTO routing switch and no local model is downloaded during installation.
models = '''<section id="models" class="view"><div class="sectionhead"><h1>Model & Provider</h1><div class="sub">Pilih Online atau satu model lokal. Model lokal hanya diunduh ketika kamu menekan Unduh.</div></div><div id="modelsOffline" class="card"></div><div id="modelsOnline" class="hidden"><div class="card"><h3>Dipakai untuk chat</h3><div id="routingSeg" class="seg"></div></div><div class="card"><h3>Model lokal</h3><div class="sub">Hanya satu model lokal aktif pada satu waktu. Setelah unduhan selesai, tekan Pilih.</div><div id="localModelRows"></div><div id="modelProgress"></div></div><div class="card"><h3>Provider online</h3><div class="sub">Saat Online dipilih, pergantian antar provider/model API yang tersedia tetap otomatis.</div><div id="providerRows"></div><div id="providerTestResult" class="resultCard"></div></div></div></section>
<section id="personalization"'''
page, section_count = re.subn(r'<section id="models" class="view">.*?</section>\n<section id="personalization"', models, page, count=1, flags=re.S)
if section_count != 1:
    raise SystemExit(f"model section: expected one match, got {section_count}")

old_model_row = '''function modelRow(x,selectable){return `<div class="row"><div class="rowmain"><div class="rowtitle">${esc(x.name)}</div><div class="rowdesc">${esc(x.purpose||'Model lokal')} · ${(Number(x.size_bytes||0)/1073741824).toFixed(1)} GB</div></div><div class="modelActions">${selectable?`<button class="btn" ${x.active?'disabled':''} onclick="saveCore({model_path:${JSON.stringify(x.path)}})">${x.active?'Aktif':'Pilih'}</button>`:''}<button class="btn" onclick="deleteModel(${JSON.stringify(x.path)})">Hapus</button></div></div>`}'''
new_model_row = '''function modelRow(x,c){const active=c.routing_mode==='local'&&x.active,installed=!!x.installed,label=active?'Aktif':(installed?'Pilih':'Unduh'),action=active?'':(installed?`selectLocalModel(${JSON.stringify(x.path)})`:`downloadLocalModel(${JSON.stringify(x.id)})`);return `<div class="row"><div class="rowmain"><div class="rowtitle">${esc(x.name)}</div><div class="rowdesc">${esc(x.purpose||x.description||'Model lokal')} · ${esc(x.size_label||((Number(x.size_bytes||0)/1073741824).toFixed(1)+' GB'))}</div></div><div class="modelActions"><button class="btn ${active?'primary':''}" ${active?'disabled':''} onclick="${action}">${label}</button>${installed&&!active?`<button class="btn" onclick="deleteModel(${JSON.stringify(x.path)})">Hapus</button>`:''}</div></div>`}'''
page = replace_once(page, old_model_row, new_model_row, "model row")
old_render = '''function renderModels(){if(!settingsData)return;const c=settingsData.core||{};document.getElementById('routingSeg').innerHTML=['local','auto','online'].map(x=>`<button class="${c.routing_mode===x?'on':''}" onclick="saveCore({routing_mode:'${x}'})">${{local:'Lokal',auto:'Auto',online:'Online'}[x]}</button>`).join('');document.getElementById('providerRows').innerHTML=(settingsData.providers||[]).map(p=>`<div class="row"><div class="rowmain"><div class="rowtitle">${esc(p.label)}</div><div class="rowdesc">${p.configured?'API key tersimpan: '+esc(p.masked||'••••'):'Belum dikonfigurasi'}</div></div><div class="stack"><button class="btn" onclick="configureProvider('${p.id}',${p.configured})">${p.configured?'Ubah':'Atur'}</button>${p.configured?`<button class="btn" onclick="testProvider('${p.id}')">Tes koneksi</button>`:''}</div></div>`).join('')}'''
new_render = '''function renderModels(){if(!settingsData)return;const c=settingsData.core||{},catalog=settingsData.model_catalog||[];const localActive=c.routing_mode==='local'&&catalog.some(x=>x.active&&x.installed);document.getElementById('routingSeg').innerHTML=`<button class="${c.routing_mode==='online'?'on':''}" onclick="selectOnlineModel()">Online${c.routing_mode==='online'?' · Aktif':' · Pilih'}</button>${localActive?'<button class="on" disabled>Model lokal · Aktif</button>':''}`;document.getElementById('localModelRows').innerHTML=catalog.map(x=>modelRow(x,c)).join('')||'<div class="empty">Katalog model lokal belum tersedia.</div>';document.getElementById('providerRows').innerHTML=(settingsData.providers||[]).map(p=>`<div class="row"><div class="rowmain"><div class="rowtitle">${esc(p.label)}</div><div class="rowdesc">${p.configured?'API key tersimpan: '+esc(p.masked||'••••'):'Belum dikonfigurasi'}</div></div><div class="stack"><button class="btn" onclick="configureProvider('${p.id}',${p.configured})">${p.configured?'Ubah':'Atur'}</button>${p.configured?`<button class="btn" onclick="testProvider('${p.id}')">Tes koneksi</button>`:''}</div></div>`).join('')}'''
page = replace_once(page, old_render, new_render, "render models")
old_download = '''async function downloadQwen(catalogId){try{await core('POST','/api/models',{action:'download',catalog_id:catalogId});pollModelStatus()}catch(e){toast(e.message)}}'''
new_download = '''async function selectOnlineModel(){await saveCore({routing_mode:'online',auto_start:false})}
async function selectLocalModel(path){await saveCore({routing_mode:'local',model_path:path,auto_start:false})}
async function downloadLocalModel(catalogId){try{await core('POST','/api/models',{action:'download',catalog_id:catalogId});paintModelProgress({state:'starting',message:'Menyiapkan unduhan…',percent:0});pollModelStatus()}catch(e){toast(e.message)}}
async function downloadQwen(catalogId){return downloadLocalModel(catalogId)}'''
page = replace_once(page, old_download, new_download, "download model js")
# Remove obsolete copy that claims local models are hidden/automatic if a later
# historical patch left it elsewhere.
page = page.replace("Model offline dikelola otomatis di Core dan tidak ditampilkan di FurinaHub.", "Model lokal diunduh hanya saat kamu memilih Unduh.")
page = page.replace("AUTO", "") if "AUTO · online" in page else page
HTML.write_text(page, encoding="utf-8")

print("FURINAHUB_PRIVATE_1_0_1_MODEL_UI_OK")
