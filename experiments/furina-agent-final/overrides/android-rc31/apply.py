#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text and old not in text:
        return text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"RC31 marker mismatch: {label} ({count})")
    return text.replace(old, new, 1)


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("usage: apply.py <termux-root>")
    root = Path(sys.argv[1]).resolve()
    app = root / "bridge/app"
    html_path = app / "src/main/assets/furinahub/index.html"
    gradle = app / "build.gradle"
    for path in (html_path, gradle):
        if not path.is_file():
            raise SystemExit(f"RC31 source missing: {path}")

    html = html_path.read_text(encoding="utf-8")
    polish = r'''
/* RC31: full-width mobile layout + simpler ownership */
html,body,.app,.content{width:100%;max-width:100%;overflow-x:hidden}.content{align-items:stretch}.view,.chatview{width:100%!important;min-width:0;max-width:860px;margin-left:auto;margin-right:auto}.messages,.composer,.composebox{min-width:0}.messages,.composer{width:100%;max-width:100%}.composer{margin:0}.composebox{width:auto}.pluginSafety{display:flex;align-items:center;gap:12px;min-height:54px;margin:8px 0 14px;padding:7px 12px;border:1px solid var(--line);border-radius:15px;background:var(--surface)}.pluginSafety .rowmain{flex:1}.skillDetails{border-top:1px solid var(--line);margin-top:3px;padding-top:3px}.skillDetails summary{min-height:50px;display:flex;align-items:center;cursor:pointer;color:var(--muted);font-size:13px;font-weight:650;list-style:none}.skillDetails summary::-webkit-details-marker{display:none}.skillDetails summary:after{content:'+';margin-left:auto;font-size:19px;font-weight:400}.skillDetails[open] summary:after{content:'−'}
@media(max-width:900px){.view,.chatview{max-width:none;margin-left:0;margin-right:0}.view{padding-left:14px;padding-right:14px}.messages{padding-left:14px;padding-right:14px}.composer{padding-left:10px;padding-right:10px}}
'''
    html = replace_once(html, "</style>", polish + "\n</style>", "full-width CSS")

    old_plugins = '''<section id="plugins" class="view"><div class="sectionhead"><h1>Plugin</h1><div class="sub">Hubungkan aplikasi melalui OpenConnector, lalu panggil dari chat dengan @.</div></div><div class="pluginSearch"><input id="pluginSearch" placeholder="Cari GitHub, Gmail, Drive…" oninput="filterPlugins(this.value)"></div><div id="pluginStatus" class="card"></div><div id="pluginRows"></div></section>'''
    new_plugins = '''<section id="plugins" class="view"><div class="sectionhead"><h1>Plugin</h1><div class="sub">Hubungkan hanya layanan yang kamu perlukan. Plugin dikelola oleh Furina Core.</div></div><div class="pluginSearch"><input id="pluginSearch" placeholder="Cari GitHub, Gmail, Drive…" oninput="filterPlugins(this.value)"></div><div id="pluginStatus" class="card"></div><label class="pluginSafety"><div class="rowmain"><div class="rowtitle">Izinkan aksi tulis</div><div class="rowdesc">Aksi yang mengubah data tetap meminta konfirmasi.</div></div><span class="switch"><input id="connectorWrite" type="checkbox" onchange="saveConnector()"><span></span></span></label><div id="pluginRows"></div></section>'''
    html = replace_once(html, old_plugins, new_plugins, "move Plugin safety")

    old_plugin_settings = '''<div class="card"><h3>Layanan Plugin</h3><div id="connectorStatus" class="rowdesc">Belum diperiksa.</div><label class="row"><div class="rowmain"><div class="rowtitle">Izinkan aksi tulis</div><div class="rowdesc">Aksi yang mengubah data tetap meminta konfirmasi.</div></div><span class="switch"><input id="connectorWrite" type="checkbox"><span></span></span></label><button class="btn full" onclick="checkConnector()">Periksa layanan Plugin</button></div>'''
    html = replace_once(html, old_plugin_settings, "", "remove duplicate Plugin settings")

    old_core_card = '''<div class="card"><h3>Core & dependency</h3><div id="coreUpdateStatus" class="sub">Recovery updater berjalan langsung melalui Termux dan tetap tersedia saat Core bermasalah.</div><div class="percentHero"><div id="coreUpdateStage" class="small">Siap diperiksa</div><strong id="coreUpdatePercent">0%</strong></div><div id="coreUpdateProgress" class="determinate hidden"><span></span></div><button id="coreUpdateBtn" class="btn full" style="margin-top:12px" onclick="updateCore()">Perbaiki / update Core & dependency</button></div>'''
    new_core_card = '''<div class="card"><h3>Furina Core</h3><div id="coreUpdateStatus" class="sub">Menggunakan jalur yang sama dengan <code>furina update</code>. Dependency dikelola otomatis oleh Core.</div><div class="percentHero"><div id="coreUpdateStage" class="small">Siap diperiksa</div><strong id="coreUpdatePercent">0%</strong></div><div id="coreUpdateProgress" class="determinate hidden"><span></span></div><button id="coreUpdateBtn" class="btn full" style="margin-top:12px" onclick="updateCore()">Update Core</button></div>'''
    html = replace_once(html, old_core_card, new_core_card, "simplify Core card")

    old_skill_render = '''document.getElementById('skills').innerHTML=Object.entries(settingsData.skill_meta||{}).map(([k,v])=>`<div class="row"><div class="rowmain"><div class="rowtitle">${esc(v.label)}</div><div class="rowdesc">${esc(v.description)}</div></div><label class="switch"><input type="checkbox" ${skills[k]?'checked':''} onchange="toggleSkill('${k}',this.checked)"><span></span></label></div>`).join('');const connector=h.connectors||{};document.getElementById('connectorWrite').checked=!!connector.allow_write_actions;const status=systemData?.connector||{};document.getElementById('connectorStatus').textContent=status.online?`Siap digunakan${status.action_count!=null?' · '+status.action_count+' action':''}`:(status.message||'Belum diperiksa')'''
    new_skill_render = '''const skillMeta=Object.entries(settingsData.skill_meta||{}),extraKeys=new Set(['app_launcher','quick_navigation','semantic_tap','smart_scroll','focused_typing','local_reminders','screen_reader','app_finder','form_fill','workflow_macros']);const skillRow=([k,v])=>`<div class="row"><div class="rowmain"><div class="rowtitle">${esc(v.label)}</div><div class="rowdesc">${esc(v.description)}</div></div><label class="switch"><input type="checkbox" ${skills[k]?'checked':''} onchange="toggleSkill('${k}',this.checked)"><span></span></label></div>`;const baseSkills=skillMeta.filter(([k])=>!extraKeys.has(k)),extraSkills=skillMeta.filter(([k])=>extraKeys.has(k));document.getElementById('skills').innerHTML=baseSkills.map(skillRow).join('')+(extraSkills.length?`<details class="skillDetails"><summary>Skill tambahan (${extraSkills.length})</summary>${extraSkills.map(skillRow).join('')}</details>`:'');const connector=h.connectors||{},writeToggle=document.getElementById('connectorWrite');if(writeToggle)writeToggle.checked=!!connector.allow_write_actions'''
    html = replace_once(html, old_skill_render, new_skill_render, "group extra skills")

    old_check = '''async function checkConnector(){try{await saveConnector();const status=systemData?.connector||{};toast(status.online?'Plugin siap digunakan.':status.message||'Layanan Plugin sedang disiapkan.');if(!status.online)setTimeout(loadSystem,2500)}catch(e){toast('Layanan Plugin belum dapat diperiksa.')}}\n'''
    html = replace_once(html, old_check, "", "remove duplicate Plugin checker")

    html = replace_once(
        html,
        '''document.getElementById('coreUpdateBtn').disabled=!connection.termux_installed||!!connection.busy;''',
        '''const coreBtn=document.getElementById('coreUpdateBtn');coreBtn.disabled=!connection.termux_installed||!!connection.busy;coreBtn.textContent=connection.connected?'Update Core':'Recovery lewat Termux';''',
        "Core button mode",
    )
    html = replace_once(
        html,
        '''function renderSystem(){if(!systemData)return;document.getElementById('coreUpdateStatus').textContent=`Core ${systemData.core_version||'?'} · dependency ${systemData.dependency_revision||'?'}`;renderAgent()}''',
        '''function renderSystem(){if(!systemData)return;document.getElementById('coreUpdateStatus').textContent=`Core ${systemData.core_version||'?'} · runtime ${systemData.dependency_revision||'?'}`;renderAgent()}''',
        "runtime wording",
    )
    old_native = '''function refreshNativeCoreUpdate(){if(!NATIVE?.coreUpdateStatus)return;const el=document.getElementById('coreUpdateStatus'),btn=document.getElementById('coreUpdateBtn');const msg=NATIVE.coreUpdateStatus();if(msg)el.textContent=msg;el.classList.toggle('updateError',/gagal|error|berhenti|kode [1-9]/i.test(msg||''));const busy=!!NATIVE.coreUpdateBusy();btn.disabled=busy||!connection.termux_installed;btn.textContent=busy?'Memperbarui Core…':'Perbaiki / update Core & dependency';if(busy)setTimeout(refreshNativeCoreUpdate,650);else if(msg&&msg!=='Belum diperiksa.')toast(msg)}'''
    new_native = '''function refreshNativeCoreUpdate(){if(!NATIVE?.coreUpdateStatus)return;const el=document.getElementById('coreUpdateStatus'),btn=document.getElementById('coreUpdateBtn');const msg=NATIVE.coreUpdateStatus();if(msg&&msg!=='Belum diperiksa.')el.textContent=msg;el.classList.toggle('updateError',/gagal|error|berhenti|kode [1-9]/i.test(msg||''));const busy=!!NATIVE.coreUpdateBusy();btn.disabled=busy||!connection.termux_installed;btn.textContent=busy?'Recovery Core…':connection.connected?'Update Core':'Recovery lewat Termux';if(busy)setTimeout(refreshNativeCoreUpdate,650);else if(msg&&msg!=='Belum diperiksa.')toast(msg)}'''
    html = replace_once(html, old_native, new_native, "native recovery wording")

    html_path.write_text(html, encoding="utf-8")

    gradle_text = gradle.read_text(encoding="utf-8")
    gradle_text = replace_once(gradle_text, "versionCode 10030", "versionCode 10031", "versionCode")
    gradle_text = replace_once(gradle_text, "versionName '1.0.0-rc30'", "versionName '1.0.0-rc31'", "versionName")
    gradle.write_text(gradle_text, encoding="utf-8")

    checks = {
        html_path: (
            "RC31: full-width mobile layout",
            ".view,.chatview{width:100%!important",
            "class=\"pluginSafety\"",
            "Skill tambahan (",
            "Recovery lewat Termux",
            "Menggunakan jalur yang sama dengan <code>furina update</code>",
        ),
        gradle: ("versionCode 10031", "versionName '1.0.0-rc31'"),
    }
    for path, markers in checks.items():
        text = path.read_text(encoding="utf-8")
        missing = [marker for marker in markers if marker not in text]
        if missing:
            raise SystemExit(f"RC31 marker hilang di {path.name}: {missing}")
    if 'id="connectorStatus"' in html or 'checkConnector()' in html:
        raise SystemExit("RC31 duplicate Plugin settings masih tersisa")
    print("FURINAHUB_ANDROID_RC31_OK")


if __name__ == "__main__":
    main()
