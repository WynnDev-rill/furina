#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


def once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        if new in text: return text
        raise SystemExit(f"Android RC55 marker missing: {label}")
    return text.replace(old, new, 1)


def main() -> None:
    if len(sys.argv) != 2: raise SystemExit("usage: apply.py <furina-root>")
    root=Path(sys.argv[1]).resolve(); app=root/"bridge"/"app"
    java=app/"src"/"main"/"java"/"com"/"wynndev"/"furinaagentbridge"
    gradle=app/"build.gradle"; main=java/"MainActivity.java"; runtime=java/"BridgeRuntime.java"; html=app/"src"/"main"/"assets"/"furinahub"/"index.html"
    for path in (gradle,main,runtime,html):
        if not path.is_file(): raise SystemExit(f"Android RC55 source missing: {path}")
    build=once(gradle.read_text(),"versionCode 10054","versionCode 10055","version code")
    build=once(build,"versionName '1.0.0-rc54'","versionName '1.0.0-rc55'","version name")
    main_text=main.read_text().replace("furina-2026.08.22-rc66-rc54","furina-2026.08.22-rc67-rc55").replace('EXPECTED_CORE_VERSION = "1.0.0-rc66"','EXPECTED_CORE_VERSION = "1.0.0-rc67"')
    runtime_text=runtime.read_text().replace("furina-2026.08.22-rc66-rc54","furina-2026.08.22-rc67-rc55")
    page=html.read_text()
    start=page.find('<section id="relationship"')
    end=page.find('<section id="focus"',start)
    if start<0 or end<0: raise SystemExit("Android RC55 relationship section missing")
    section='''<section id="relationship" class="view"><div class="sectionhead"><h1>Kita</h1><div class="sub">Ruang untuk hubungan kalian sebagai pasangan—tanpa skor, streak, atau mode pertemanan.</div></div><div id="relationshipOffline" class="card"></div><div id="relationshipOnline" class="hidden"><div class="card relationshipHero"><div class="row"><div class="rowmain"><div id="relationshipStage" class="rowtitle">Pasangan baru</div><div id="relationshipTone" class="rowdesc">Tenang & hangat</div></div><span id="relationshipModeBadge" class="badge">Pasangan</span></div><div id="relationshipBaseline" class="sub relationshipNote">Ingatan awal hanya nama kalian dan hubungan ini.</div></div><div class="card"><h3>Cara kita berbicara</h3><div class="relationshipGrid"><div class="field"><label>Ritme kedekatan</label><select id="relationshipPace"><option value="slow">Pelan</option><option value="natural">Natural</option><option value="direct">Terbuka</option></select></div><div class="field"><label>Gaya afeksi</label><select id="relationshipAffection"><option value="gentle">Lembut</option><option value="playful">Playful</option><option value="expressive">Ekspresif</option></select></div><div class="field"><label>Inisiatif Furina</label><select id="relationshipInitiative"><option value="reserved">Tenang</option><option value="balanced">Seimbang</option><option value="expressive">Aktif</option></select></div><div class="field"><label>Ritual percakapan</label><select id="relationshipRitual"><option value="none">Tanpa ritual</option><option value="reconnect">Sambut kembali</option><option value="daybook">Pagi & malam</option></select></div></div><div class="field"><label>Catatan bersama</label><textarea id="relationshipNote" placeholder="Batas atau hal penting yang kalian pilih sendiri"></textarea></div><button class="btn primary full" onclick="saveRelationshipPreferences()">Simpan cara kita</button></div><div class="card"><div class="row"><div class="rowmain"><div class="rowtitle">Momen kita</div><div class="rowdesc">Hanya momen yang kamu pilih sendiri yang disimpan.</div></div><button class="btn" onclick="addMoment()">Tambah</button></div><div id="relationshipMoments"></div></div><div id="relationshipGuard" class="sub relationshipGuard"></div></div></section>'''
    page=page[:start]+section+page[end:]
    js_start=page.find("function renderRelationship(data)")
    js_end=page.find("async function saveRelationshipPreferences()",js_start)
    if js_start<0 or js_end<0: raise SystemExit("Android RC55 relationship script missing")
    render="""function renderRelationship(data){const online=document.getElementById('relationshipOnline'),offline=document.getElementById('relationshipOffline');if(!connection.connected||!data){online.classList.add('hidden');offline.innerHTML=iconOffline('Kita membutuhkan Core','Hubungkan Furina Lite di Termux agar hubungan dan momen memakai data lokal yang sama.');return}offline.innerHTML='';online.classList.remove('hidden');relationshipData=data;const p=data.preferences||{},rel=data.relationship||data.mode||{},base=data.baseline||{};document.getElementById('relationshipStage').textContent=data.state?.stage||'Pasangan baru';document.getElementById('relationshipTone').textContent=data.state?.tone||'Tenang & hangat';document.getElementById('relationshipModeBadge').textContent=rel.label||'Pasangan';document.getElementById('relationshipBaseline').textContent=base.fresh?`Ingatan awal: Furina, ${base.user_name||'namamu'}, dan fakta bahwa kalian pasangan.`:'Hubungan kalian memakai memori dan momen yang sudah kamu pilih.';document.getElementById('relationshipPace').value=p.pace||'natural';document.getElementById('relationshipAffection').value=p.affection_style||'playful';document.getElementById('relationshipInitiative').value=p.initiative||'balanced';document.getElementById('relationshipRitual').value=p.ritual||'reconnect';document.getElementById('relationshipNote').value=p.shared_note||'';document.getElementById('relationshipGuard').textContent=data.guardrails||'';const rows=Array.isArray(data.moments)?data.moments:[];document.getElementById('relationshipMoments').innerHTML=rows.length?rows.map(x=>`<div class=\"row relationshipMoment\"><div class=\"rowmain\"><div class=\"rowtitle\">${x.pinned?'Disematkan · ':''}${esc(x.title)}</div><div class=\"rowdesc momentNote\">${esc(x.note)}</div></div><button class=\"btn\" onclick=\"toggleMoment(${Number(x.id)},${x.pinned?'false':'true'})\">${x.pinned?'Lepas':'Sematkan'}</button><button class=\"btn\" onclick=\"deleteMoment(${Number(x.id)})\">Hapus</button></div>`).join(''):'<div class=\"empty\">Belum ada momen. Hubungan dimulai tanpa ingatan buatan.</div>'}\n"""
    page=page[:js_start]+render+page[js_end:]
    page=page.replace("#relationshipMode{grid-template-columns:repeat(2,1fr)}","")
    gradle.write_text(build); main.write_text(main_text); runtime.write_text(runtime_text); html.write_text(page)
    combined='\n'.join((build,main_text,runtime_text,page))
    required=("versionCode 10055","versionName '1.0.0-rc55'","furina-2026.08.22-rc67-rc55",'EXPECTED_CORE_VERSION = "1.0.0-rc67"','id="relationshipBaseline"',"base.fresh","Pasangan")
    missing=[x for x in required if x not in combined]
    forbidden=("setRelationshipMode(","Mode Dekat aktif","Aktifkan hubungan romantis?",'id="relationshipMode"')
    if missing or any(x in page for x in forbidden): raise SystemExit("Android RC55 contract failed: "+", ".join(missing or forbidden))
    print("FURINAHUB_ANDROID_RC55_PARTNER_FIRST_OK")


if __name__ == "__main__": main()
