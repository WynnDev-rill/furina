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
        raise SystemExit(f"RC33 marker mismatch: {label} ({count})")
    return text.replace(old, new, 1)


def remove_nav(text: str, view: str, label: str) -> str:
    pattern = re.compile(
        rf'<button class="nav" data-view="{re.escape(view)}"[^>]*>.*?</button>\n?',
        re.S,
    )
    text, count = pattern.subn("", text, count=1)
    if count != 1:
        raise SystemExit(f"RC33 nav marker mismatch: {label} ({count})")
    return text


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("usage: apply.py <termux-root>")
    root = Path(sys.argv[1]).resolve()
    app = root / "bridge/app"
    html_path = app / "src/main/assets/furinahub/index.html"
    gradle = app / "build.gradle"
    for path in (html_path, gradle):
        if not path.is_file():
            raise SystemExit(f"RC33 source missing: {path}")

    html = html_path.read_text(encoding="utf-8")

    # Keep the internal Agent/OpenConnector implementation available to Core,
    # but remove their FurinaHub entry points.
    html = replace_once(
        html,
        '<section id="agent" class="view">',
        '<section id="agent" class="view hidden">',
        "hide Agent view",
    )
    html = replace_once(
        html,
        '<section id="plugins" class="view">',
        '<section id="plugins" class="view hidden">',
        "hide Plugin view",
    )
    html = replace_once(
        html,
        '<div class="card"><h3>Kontrol perangkat</h3><div id="modeSeg" class="seg"></div>',
        '<div class="card hidden"><h3>Kontrol perangkat</h3><div id="modeSeg" class="seg"></div>',
        "hide device control modes",
    )

    old_models = '''<section id="models" class="view"><div class="sectionhead"><h1>Model & Provider</h1><div class="sub">Model dapat diganti tanpa mengganti identitas, Psyche, atau memori companion.</div></div><div id="modelsOffline" class="card"></div><div id="modelsOnline" class="hidden"><div class="card"><h3>Routing</h3><div id="routingSeg" class="seg"></div></div><div class="card"><h3>Model Qwen</h3><div class="sub">Unduh, aktifkan, atau hapus model langsung. File tetap berada di Termux.</div><div id="localModels"></div><div id="modelCatalog"></div><div id="modelProgress"></div></div><div class="card"><button class="supportToggle" onclick="toggleSupport()">+ Dukungan vision & memori</button><div id="supportModels" class="hidden"></div></div><div class="card"><h3>Provider online</h3><div id="providerRows"></div><div id="providerTestResult" class="resultCard"></div></div></div></section>'''
    new_models = '''<section id="models" class="view"><div class="sectionhead"><h1>Model & Provider</h1><div class="sub">Atur routing dan provider online. Model offline dikelola otomatis di Core dan tidak ditampilkan di FurinaHub.</div></div><div id="modelsOffline" class="card"></div><div id="modelsOnline" class="hidden"><div class="card"><h3>Routing</h3><div id="routingSeg" class="seg"></div></div><div class="card"><h3>Provider online</h3><div id="providerRows"></div><div id="providerTestResult" class="resultCard"></div></div></div></section>'''
    html = replace_once(html, old_models, new_models, "simplify Model & Provider")

    settings_pattern = re.compile(
        r'<button class="nav" data-view="settings" onclick="go\(\'settings\'\)">.*?Pengaturan</button>',
        re.S,
    )
    settings_match = settings_pattern.search(html)
    if not settings_match:
        raise SystemExit("RC33 settings nav marker missing")
    settings_nav = settings_match.group(0)
    html = html[:settings_match.start()] + html[settings_match.end():]
    html = remove_nav(html, "plugins", "Plugin")
    html = remove_nav(html, "agent", "Agent & Skill")
    drawer_marker = '<div class="sep"></div><button class="nav" onclick="newConversation()"'
    html = replace_once(
        html,
        drawer_marker,
        '<div class="sep"></div>' + settings_nav + '<div class="sep"></div><button class="nav" onclick="newConversation()"',
        "promote Settings",
    )
    html, trailing_sep_count = re.subn(
        r'<div id="conversationRows"></div><div class="sep"></div>\s*</aside>',
        '<div id="conversationRows"></div></aside>',
        html,
        count=1,
    )
    if trailing_sep_count != 1:
        raise SystemExit(f"RC33 trailing drawer separator marker mismatch ({trailing_sep_count})")

    plugin_button_pattern = re.compile(
        r'<button onclick="openPluginPicker\(\)">.*?</button>',
        re.S,
    )
    html, plugin_button_count = plugin_button_pattern.subn("", html, count=1)
    if plugin_button_count != 1:
        raise SystemExit(f"RC33 Plugin plus-menu marker mismatch ({plugin_button_count})")
    html = replace_once(
        html,
        'oninput="autoGrow(this);handleMention(this.value)"',
        'oninput="autoGrow(this)"',
        "disable Plugin mention picker",
    )

    html = replace_once(
        html,
        "document.getElementById('advancedCard').classList.toggle('hidden',!connection.connected);",
        "document.getElementById('advancedCard').classList.add('hidden');",
        "keep local model advanced settings hidden",
    )
    html = replace_once(
        html,
        "Hubungkan Core untuk memilih model lokal atau provider online.",
        "Hubungkan Core untuk mengatur routing dan provider online.",
        "offline Model helper",
    )
    html = replace_once(
        html,
        "Hubungkan Furina Core di Termux sekali dari Pengaturan untuk mulai menggunakan chat, memori, model, dan Agent.",
        "Hubungkan Furina Core di Termux sekali dari Pengaturan untuk mulai menggunakan chat, memori, dan provider.",
        "disconnected chat helper",
    )

    old_render_models = '''function renderModels(){if(!settingsData)return;const c=settingsData.core||{};document.getElementById('routingSeg').innerHTML=['local','auto','online'].map(x=>`<button class="${c.routing_mode===x?'on':''}" onclick="saveCore({routing_mode:'${x}'})">${{local:'Lokal',auto:'Auto',online:'Online'}[x]}</button>`).join('');const all=settingsData.models||[],qwen=all.filter(x=>x.primary),support=all.filter(x=>!x.primary);document.getElementById('localModels').innerHTML=qwen.length?'<div class="pluginGroup">Terpasang</div>'+qwen.map(x=>modelRow(x,true)).join(''):'<div class="empty">Belum ada model Qwen terpasang.</div>';document.getElementById('modelCatalog').innerHTML='<div class="pluginGroup">Pilihan unduhan</div>'+(settingsData.model_catalog||[]).map(x=>`<div class="row modelCatalogRow"><div class="rowmain"><div class="rowtitle">${esc(x.name)}</div><div class="rowdesc">${esc(x.description)} · ${esc(x.size_label)}</div></div>${x.installed?`<span class="modelState">${x.active?'Aktif':'Terpasang'}</span>`:`<button class="btn primary" onclick="downloadQwen('${x.id}')">Unduh</button>`}</div>`).join('');document.getElementById('supportModels').innerHTML=support.length?support.map(x=>modelRow(x,false)).join(''):'<div class="empty">Belum ada komponen vision atau memori.</div>';document.getElementById('providerRows').innerHTML=(settingsData.providers||[]).map(p=>`<div class="row"><div class="rowmain"><div class="rowtitle">${esc(p.label)}</div><div class="rowdesc">${p.configured?'API key tersimpan: '+esc(p.masked||'••••'):'Belum dikonfigurasi'}</div></div><div class="stack"><button class="btn" onclick="configureProvider('${p.id}',${p.configured})">${p.configured?'Ubah':'Atur'}</button>${p.configured?`<button class="btn" onclick="testProvider('${p.id}')">Tes koneksi</button>`:''}</div></div>`).join('');paintModelProgress(settingsData.model_status||{})}'''
    new_render_models = '''function renderModels(){if(!settingsData)return;const c=settingsData.core||{};document.getElementById('routingSeg').innerHTML=['local','auto','online'].map(x=>`<button class="${c.routing_mode===x?'on':''}" onclick="saveCore({routing_mode:'${x}'})">${{local:'Lokal',auto:'Auto',online:'Online'}[x]}</button>`).join('');document.getElementById('providerRows').innerHTML=(settingsData.providers||[]).map(p=>`<div class="row"><div class="rowmain"><div class="rowtitle">${esc(p.label)}</div><div class="rowdesc">${p.configured?'API key tersimpan: '+esc(p.masked||'••••'):'Belum dikonfigurasi'}</div></div><div class="stack"><button class="btn" onclick="configureProvider('${p.id}',${p.configured})">${p.configured?'Ubah':'Atur'}</button>${p.configured?`<button class="btn" onclick="testProvider('${p.id}')">Tes koneksi</button>`:''}</div></div>`).join('')}'''
    html = replace_once(html, old_render_models, new_render_models, "provider-only Model renderer")

    html_path.write_text(html, encoding="utf-8")

    gradle_text = gradle.read_text(encoding="utf-8")
    gradle_text = replace_once(gradle_text, "versionCode 10032", "versionCode 10033", "versionCode")
    gradle_text = replace_once(gradle_text, "versionName '1.0.0-rc32'", "versionName '1.0.0-rc33'", "versionName")
    gradle.write_text(gradle_text, encoding="utf-8")

    model_section = html[html.index('<section id="models"'):html.index('<section id="personalization"')]
    drawer = html[html.index('<aside id="drawer"'):html.index('</aside>') + len('</aside>')]
    settings = html[html.index('<section id="settings"'):html.index('</main>')]

    assert 'data-view="plugins"' not in drawer
    assert 'data-view="agent"' not in drawer
    assert drawer.index('data-view="settings"') < drawer.index("newConversation()")
    assert 'id="localModels"' not in model_section
    assert 'id="modelCatalog"' not in model_section
    assert 'id="supportModels"' not in model_section
    assert "<h3>Provider online</h3>" in model_section
    assert "<h3>Routing</h3>" in model_section
    assert '<section id="agent" class="view hidden">' in html
    assert '<section id="plugins" class="view hidden">' in html
    assert '<div class="card hidden"><h3>Kontrol perangkat</h3>' in settings
    assert 'onclick="openPluginPicker()"' not in html
    assert 'handleMention(this.value)' not in html
    assert "document.getElementById('advancedCard').classList.add('hidden');" in html
    assert "versionCode 10033" in gradle_text
    assert "versionName '1.0.0-rc33'" in gradle_text
    print("FURINAHUB_ANDROID_RC33_SIMPLIFIED_UI_OK")


if __name__ == "__main__":
    main()
