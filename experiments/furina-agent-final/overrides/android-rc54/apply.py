#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path


OLD_BUNDLE = "furina-2026.08.22-rc65-rc53"
NEW_BUNDLE = "furina-2026.08.22-rc66-rc54"


def once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        if new in text:
            return text
        raise SystemExit(f"Android RC54 marker missing: {label}")
    return text.replace(old, new, 1)


def regex_once(text: str, pattern: str, replacement: str, label: str) -> str:
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.S)
    if count != 1:
        raise SystemExit(f"Android RC54 regex marker mismatch: {label} ({count})")
    return updated


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: apply.py <furina-root>")
    root = Path(sys.argv[1]).resolve()
    app = root / "bridge" / "app"
    java = app / "src" / "main" / "java" / "com" / "wynndev" / "furinaagentbridge"
    gradle = app / "build.gradle"
    main = java / "MainActivity.java"
    runtime = java / "BridgeRuntime.java"
    html = app / "src" / "main" / "assets" / "furinahub" / "index.html"
    for path in (gradle, main, runtime, html):
        if not path.is_file():
            raise SystemExit(f"Android RC54 source missing: {path}")

    original_build = gradle.read_text(encoding="utf-8")
    original_main = main.read_text(encoding="utf-8")
    original_runtime = runtime.read_text(encoding="utf-8")
    original_page = html.read_text(encoding="utf-8")
    if "versionCode 10054" in original_build and "versionName '1.0.0-rc54'" in original_build:
        installed = "\n".join((original_build, original_main, original_runtime, original_page))
        required = (
            NEW_BUNDLE, 'EXPECTED_CORE_VERSION = "1.0.0-rc66"', 'id="relationship"',
            'data-view="relationship"', "async function loadRelationship()",
            "/api/relationship/preferences", "/api/relationship/moments",
            "Simpan sebagai Momen kita", "relationshipData",
        )
        missing = [marker for marker in required if marker not in installed]
        if missing or 'data-view="focus"' in original_page or "Jadikan Fokus" in original_page:
            raise SystemExit("Android RC54 existing install is incomplete: " + ", ".join(missing or ["legacy Focus action"]))
        print("FURINAHUB_ANDROID_RC54_ALREADY_APPLIED_OK")
        return

    build = once(original_build, "versionCode 10053", "versionCode 10054", "version code")
    build = once(build, "versionName '1.0.0-rc53'", "versionName '1.0.0-rc54'", "version name")
    main_text = original_main.replace(OLD_BUNDLE, NEW_BUNDLE)
    main_text = once(main_text, 'EXPECTED_CORE_VERSION = "1.0.0-rc65"', 'EXPECTED_CORE_VERSION = "1.0.0-rc66"', "Core target")
    runtime_text = original_runtime.replace(OLD_BUNDLE, NEW_BUNDLE)
    page = original_page

    old_today = '''<section id="today" class="view"><div class="sectionhead"><h1>Hari ini</h1><div class="sub">Yang perlu kamu lihat sekarang—bukan dashboard yang penuh angka.</div></div><div id="todayOffline" class="card"></div><div id="todayOnline" class="hidden"><div class="card"><h3>Berikutnya</h3><div id="todayFocus"></div></div><div class="card"><h3>Ruang kerja Furina</h3><div id="todaySignals"></div></div><div class="actions"><button class="btn primary" onclick="go('chat')">Lanjut chat</button><button class="btn" onclick="go('focus')">Kelola fokus</button></div></div></section>'''
    relationship = '''<section id="relationship" class="view"><div class="sectionhead"><h1>Kita</h1><div class="sub">Tempat hubungan kalian tumbuh—tanpa skor, streak, atau tuntutan untuk selalu kembali.</div></div><div id="relationshipOffline" class="card"></div><div id="relationshipOnline" class="hidden"><div class="card relationshipHero"><div class="row"><div class="rowmain"><div id="relationshipStage" class="rowtitle">Makin akrab</div><div id="relationshipTone" class="rowdesc">Tenang & hangat</div></div><span id="relationshipModeBadge" class="badge">Dekat</span></div><div id="relationshipMode" class="seg"><button onclick="setRelationshipMode('close')">Dekat</button><button onclick="setRelationshipMode('romantic')">Romantis</button></div><div id="relationshipModeNote" class="sub relationshipNote"></div></div><div class="card"><h3>Cara kita berbicara</h3><div class="relationshipGrid"><div class="field"><label>Ritme kedekatan</label><select id="relationshipPace"><option value="slow">Pelan</option><option value="natural">Natural</option><option value="direct">Terbuka</option></select></div><div class="field"><label>Gaya afeksi</label><select id="relationshipAffection"><option value="gentle">Lembut</option><option value="playful">Playful</option><option value="expressive">Ekspresif</option></select></div><div class="field"><label>Inisiatif Furina</label><select id="relationshipInitiative"><option value="reserved">Tenang</option><option value="balanced">Seimbang</option><option value="expressive">Aktif</option></select></div><div class="field"><label>Ritual percakapan</label><select id="relationshipRitual"><option value="none">Tanpa ritual</option><option value="reconnect">Sambut kembali</option><option value="daybook">Pagi & malam</option></select></div></div><div class="field"><label>Catatan bersama</label><textarea id="relationshipNote" placeholder="Hal penting tentang hubungan, batas, atau cara kalian ingin berbicara"></textarea></div><button class="btn primary full" onclick="saveRelationshipPreferences()">Simpan cara kita</button></div><div class="card"><div class="row"><div class="rowmain"><div class="rowtitle">Momen kita</div><div class="rowdesc">Hanya momen yang kamu pilih sendiri yang disimpan di sini.</div></div><button class="btn" onclick="addMoment()">Tambah</button></div><div id="relationshipMoments"></div></div><div id="relationshipGuard" class="sub relationshipGuard"></div></div></section>'''
    page = once(page, old_today, relationship, "relationship section")

    old_nav = '''<button class="nav" data-view="today" onclick="go('today')"><svg viewBox="0 0 24 24"><path d="M4 12h16M12 4v16"/><path d="M5 5l14 14M19 5L5 19"/></svg>Hari ini</button>'''
    new_nav = '''<button class="nav" data-view="relationship" onclick="go('relationship')"><svg viewBox="0 0 24 24"><path d="M4 12h16M12 4v16"/><path d="M5 5l14 14M19 5L5 19"/></svg>Kita</button>'''
    page = once(page, old_nav, new_nav, "relationship navigation")
    page = regex_once(page, r'<button class="nav" data-view="focus"[^>]*>.*?</button>', "", "remove Focus primary navigation")

    # RC53 appended Today + capture helpers as the final script block. Remove
    # that obsolete product surface before adding the relationship handlers so
    # the source no longer carries a second, task-first implementation.
    legacy_start = page.find("\nasync function loadToday()")
    legacy_end = page.find("</script>", legacy_start)
    if legacy_start < 0 or legacy_end < 0:
        raise SystemExit("Android RC54 marker missing: legacy Today helpers")
    legacy = page[legacy_start:legacy_end]
    if "function renderToday(" not in legacy or "async function captureSelected(action)" not in legacy:
        raise SystemExit("Android RC54 legacy Today helper contract changed")
    page = page[:legacy_start] + "\n" + page[legacy_end:]

    css = '''.relationshipHero{background:linear-gradient(145deg,var(--surface),color-mix(in srgb,var(--accent-soft) 46%,var(--surface)));border-color:color-mix(in srgb,var(--accent) 24%,var(--line))}#relationshipMode{grid-template-columns:repeat(2,1fr)}.relationshipNote{margin-top:10px}.relationshipGrid{display:grid;grid-template-columns:1fr 1fr;gap:0 10px}.relationshipGuard{margin:15px 3px 0}.momentNote{white-space:pre-wrap}.relationshipMoment{align-items:flex-start;flex-wrap:wrap}.relationshipMoment .rowmain{flex-basis:100%}.relationshipMoment .btn{flex:1}@media(max-width:520px){.relationshipGrid{grid-template-columns:1fr}}'''
    if ".relationshipHero{" not in page:
        page = once(page, "</style>", css + "</style>", "relationship CSS")

    old_go = "function go(id){closeSheets();document.querySelectorAll('.view,.chatview').forEach(x=>x.classList.remove('active'));document.getElementById(id).classList.add('active');document.querySelectorAll('.nav').forEach(x=>x.classList.toggle('on',x.dataset.view===id));drawer(false);if(id==='settings')refreshAppUpdate();if(connection.connected){if(id==='memory')loadMemory();if(id==='today')loadToday();if(id==='focus')loadFocus();if(id==='settings'||id==='agent')loadSystem();if(id==='personalization')refreshSharedSettings();if(id==='plugins')loadPlugins()}}"
    new_go = "function go(id){closeSheets();document.querySelectorAll('.view,.chatview').forEach(x=>x.classList.remove('active'));document.getElementById(id).classList.add('active');document.querySelectorAll('.nav').forEach(x=>x.classList.toggle('on',x.dataset.view===id));drawer(false);if(id==='settings')refreshAppUpdate();if(id==='relationship'){if(connection.connected)loadRelationship();else renderRelationship(null)}if(connection.connected){if(id==='memory')loadMemory();if(id==='settings'||id==='agent')loadSystem();if(id==='personalization')refreshSharedSettings();if(id==='plugins')loadPlugins()}}"
    page = once(page, old_go, new_go, "relationship route")

    old_sync = "async function syncCore(){try{[bootData,settingsData,systemData,memoryData]=await Promise.all([core('GET','/api/bootstrap'),core('GET','/api/settings'),core('GET','/api/system'),core('GET','/api/memory')]);renderBoot();renderSettings();renderModels();renderAgent();renderMemory();loadWorkspaceExtras();}catch(e){toast(e.message)}}"
    new_sync = "async function syncCore(){try{[bootData,settingsData,systemData,memoryData]=await Promise.all([core('GET','/api/bootstrap'),core('GET','/api/settings'),core('GET','/api/system'),core('GET','/api/memory')]);renderBoot();renderSettings();renderModels();renderAgent();renderMemory();loadWorkspaceExtras();loadRelationship();}catch(e){toast(e.message)}}"
    page = once(page, old_sync, new_sync, "relationship initial sync")
    page = once(
        page,
        "if(!history.length)addMsg('assistant','Aku sudah terhubung. Ada yang ingin kamu bicarakan atau kerjakan?');",
        "if(!history.length)addMsg('assistant','Aku di sini. Tidak harus topik besar—hal kecil pun boleh.');",
        "relationship-first empty greeting",
    )

    old_menu = "<button onclick=\"copySelected()\">Salin teks</button>${selectedMessage.text?.trim()?'<button onclick=\"captureSelected(\\'memory\\')\">Usulkan sebagai memori</button><button onclick=\"captureSelected(\\'focus\\')\">Jadikan Fokus</button>':''}${selectedMessage.role==='user'&&canBranch?'<button onclick=\"editSelected()\">Edit & kirim ulang dari sini</button>':''}${selectedMessage.role==='assistant'&&canBranch?'<button onclick=\"regenerateSelected()\">Buat ulang jawaban</button>':''}${canBranch?'<button style=\"color:var(--danger)\" onclick=\"deleteSelectedBranch()\">Hapus dari pesan ini</button>':''}<button onclick=\"closeSheets()\">Batal</button>"
    new_menu = "<button onclick=\"copySelected()\">Salin teks</button>${selectedMessage.text?.trim()?'<button onclick=\"captureSelected(\\'moment\\')\">Simpan sebagai Momen kita</button><button onclick=\"captureSelected(\\'memory\\')\">Usulkan sebagai memori</button>':''}${selectedMessage.role==='user'&&canBranch?'<button onclick=\"editSelected()\">Edit & kirim ulang dari sini</button>':''}${selectedMessage.role==='assistant'&&canBranch?'<button onclick=\"regenerateSelected()\">Buat ulang jawaban</button>':''}${canBranch?'<button style=\"color:var(--danger)\" onclick=\"deleteSelectedBranch()\">Hapus dari pesan ini</button>':''}<button onclick=\"closeSheets()\">Batal</button>"
    page = once(page, old_menu, new_menu, "relationship capture menu")
    page = once(
        page,
        "const d=await core('GET','/api/workspace');renderFocus(d);renderResponseProfiles(d.profile);",
        "const d=await core('GET','/api/workspace');renderResponseProfiles(d.profile);",
        "demote Focus workspace rendering",
    )

    relationship_js = r'''

let relationshipData=null;
async function loadRelationship(){try{relationshipData=await core('GET','/api/relationship');renderRelationship(relationshipData)}catch(e){toast(e.message)}}
function renderRelationship(data){const online=document.getElementById('relationshipOnline'),offline=document.getElementById('relationshipOffline');if(!connection.connected||!data){online.classList.add('hidden');offline.innerHTML=iconOffline('Kita membutuhkan Core','Hubungkan Furina Lite di Termux agar hubungan, batas, dan momen memakai data lokal yang sama.');return}offline.innerHTML='';online.classList.remove('hidden');relationshipData=data;const p=data.preferences||{},mode=data.mode||{};document.getElementById('relationshipStage').textContent=data.state?.stage||'Makin akrab';document.getElementById('relationshipTone').textContent=data.state?.tone||'Tenang & hangat';document.getElementById('relationshipModeBadge').textContent=mode.label||'Dekat';document.getElementById('relationshipModeNote').textContent=mode.description||'';document.querySelectorAll('#relationshipMode button').forEach(x=>x.classList.toggle('on',x.textContent.toLowerCase()===(mode.label||'').toLowerCase()));document.getElementById('relationshipPace').value=p.pace||'natural';document.getElementById('relationshipAffection').value=p.affection_style||'playful';document.getElementById('relationshipInitiative').value=p.initiative||'balanced';document.getElementById('relationshipRitual').value=p.ritual||'reconnect';document.getElementById('relationshipNote').value=p.shared_note||'';document.getElementById('relationshipGuard').textContent=data.guardrails||'';const rows=Array.isArray(data.moments)?data.moments:[];document.getElementById('relationshipMoments').innerHTML=rows.length?rows.map(x=>`<div class="row relationshipMoment"><div class="rowmain"><div class="rowtitle">${x.pinned?'Disematkan · ':''}${esc(x.title)}</div><div class="rowdesc momentNote">${esc(x.note)}</div></div><button class="btn" onclick="toggleMoment(${Number(x.id)},${x.pinned?'false':'true'})">${x.pinned?'Lepas':'Sematkan'}</button><button class="btn" onclick="deleteMoment(${Number(x.id)})">Hapus</button></div>`).join(''):'<div class="empty">Belum ada momen. Simpan satu dari pesan yang benar-benar berarti.</div>'}
async function setRelationshipMode(mode){let patch={relationship_mode:mode};if(mode==='romantic'&&!relationshipData?.preferences?.adult_confirmed){const ok=await askConfirm('Aktifkan hubungan romantis?','Konfirmasikan bahwa kamu berusia 18+ dan ingin Furina merespons secara romantis. Tidak ada eskalasi seksual otomatis.');if(!ok)return;patch.adult_confirmed=true}try{relationshipData=await core('POST','/api/relationship/preferences',patch);renderRelationship(relationshipData);toast(mode==='romantic'?'Mode romantis aktif.':'Mode Dekat aktif.')}catch(e){toast(e.message)}}
async function saveRelationshipPreferences(){const patch={pace:document.getElementById('relationshipPace').value,affection_style:document.getElementById('relationshipAffection').value,initiative:document.getElementById('relationshipInitiative').value,ritual:document.getElementById('relationshipRitual').value,shared_note:document.getElementById('relationshipNote').value};try{relationshipData=await core('POST','/api/relationship/preferences',patch);renderRelationship(relationshipData);toast('Cara kalian berbicara sudah disimpan.')}catch(e){toast(e.message)}}
async function addMoment(){const note=await askText('Tambah Momen kita','Simpan hanya sesuatu yang memang ingin kalian bawa ke percakapan berikutnya.',{multiline:true});if(!note?.trim())return;try{relationshipData=await core('POST','/api/relationship/moments',{action:'add',note:note.trim(),source_ref:'FurinaHub'});renderRelationship(relationshipData);toast('Momen disimpan.')}catch(e){toast(e.message)}}
async function toggleMoment(id,pin){try{relationshipData=await core('POST','/api/relationship/moments',{action:pin?'pin':'unpin',id});renderRelationship(relationshipData)}catch(e){toast(e.message)}}
async function deleteMoment(id){if(!await askConfirm('Hapus momen?','Momen ini tidak lagi masuk ke konteks hubungan Furina.'))return;try{relationshipData=await core('POST','/api/relationship/moments',{action:'delete',id});renderRelationship(relationshipData);toast('Momen dihapus.')}catch(e){toast(e.message)}}
async function captureSelected(action){const message=selectedMessage;closeSheets();if(!message?.text?.trim())return;if(action==='moment'){const note=await askText('Simpan sebagai Momen kita','Edit bila perlu. Momen ini akan menjadi bagian dari continuity hubungan kalian.',{value:message.text,multiline:true});if(!note?.trim())return;try{relationshipData=await core('POST','/api/relationship/moments',{action:'add',note:note.trim(),source_ref:`pesan:${message.id||'baru'}`});renderRelationship(relationshipData);toast('Momen kita disimpan.')}catch(e){toast(e.message)}return}const text=await askText('Usulkan sebagai memori','Edit bila perlu. Usulan harus kamu terima di Kotak Masuk Memori.',{value:message.text,multiline:true});if(!text?.trim())return;try{await core('POST','/api/capture',{action:'memory',text:text.trim(),source_ref:`pesan:${message.id||'baru'}`});await loadMemory();await loadWorkspaceExtras();toast('Usulan masuk ke Kotak Masuk Memori.')}catch(e){toast(e.message)}}
'''
    if "let relationshipData=null;" not in page:
        page = once(page, "</script>", relationship_js + "</script>", "relationship behavior")

    gradle.write_text(build, encoding="utf-8")
    main.write_text(main_text, encoding="utf-8")
    runtime.write_text(runtime_text, encoding="utf-8")
    html.write_text(page, encoding="utf-8")

    combined = "\n".join((build, main_text, runtime_text, page))
    required = (
        "versionCode 10054", "versionName '1.0.0-rc54'", NEW_BUNDLE,
        'EXPECTED_CORE_VERSION = "1.0.0-rc66"', 'id="relationship"',
        'data-view="relationship"', "async function loadRelationship()",
        "/api/relationship/preferences", "/api/relationship/moments",
        "Simpan sebagai Momen kita", "relationshipData",
    )
    missing = [marker for marker in required if marker not in combined]
    if missing:
        raise SystemExit("Android RC54 integration incomplete: " + ", ".join(missing))
    if 'data-view="focus"' in page or "Jadikan Fokus" in page:
        raise SystemExit("Android RC54 still exposes Focus as a primary relationship action")
    print("FURINAHUB_ANDROID_RC54_RELATIONSHIP_FIRST_OK")


if __name__ == "__main__":
    main()
