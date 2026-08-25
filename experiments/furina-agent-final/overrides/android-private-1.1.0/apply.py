#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/furina-agent-rc54-validate/termux")
APP = ROOT / "bridge/app"
BUILD = APP / "build.gradle"
MAIN = APP / "src/main/java/com/wynndev/furinaagentbridge/MainActivity.java"
HTML = APP / "src/main/assets/furinahub/index.html"


def replace_between(text: str, start: str, end: str, replacement: str, label: str) -> str:
    a = text.find(start)
    if a < 0:
        raise SystemExit(f"{label}: start marker missing")
    b = text.find(end, a + len(start))
    if b < 0:
        raise SystemExit(f"{label}: end marker missing")
    return text[:a] + replacement + text[b:]


# Android version boundary.
build = BUILD.read_text(encoding="utf-8")
if build.count("versionCode 10067") != 1 or build.count("versionName '1.0.9'") != 1:
    raise SystemExit("expected FurinaHub 1.0.9/10067")
build = build.replace("versionCode 10067", "versionCode 10077", 1)
build = build.replace("versionName '1.0.9'", "versionName '1.1.9'", 1)
BUILD.write_text(build, encoding="utf-8")

# FurinaHub no longer owns update orchestration. Keep old bridge methods inert so
# cached HTML cannot start an updater, while `furina update` remains the single
# owner of Core + APK installation and version confirmation.
main = MAIN.read_text(encoding="utf-8")
main = main.replace('EXPECTED_CORE_VERSION = "1.0.9"', 'EXPECTED_CORE_VERSION = "1.1.9"', 1)
main = main.replace("furina-2026.08.24-private-1.0.9", "furina-2026.08.25-private-1.1.9")
main, count = re.subn(r'EXPECTED_DEPENDENCY_REVISION = "[^"]+"', 'EXPECTED_DEPENDENCY_REVISION = "2026.08.25-r59"', main, count=1)
if count != 1:
    raise SystemExit("Android dependency revision missing")
main = main.replace(
    "        bridgeUpdater = new BridgeUpdater(this, hiddenUpdateStatus, hiddenUpdateButton);\n",
    "        // 1.1.9: update orchestration is Termux-only (`furina update`).\n",
)
main = main.replace("        if (bridgeUpdater != null) bridgeUpdater.onResume();\n", "")
main = main.replace(
    "                    bundleSyncChecked = false;\n                    handler.post(this::startCoreRecoveryUpdate);",
    "                    bundleSyncChecked = false;\n                    coreUpdateState = \"Versi Core berbeda. Jalankan `furina update` di Termux.\";\n                    handler.post(() -> setConnection(\"mismatch\", \"Versi Core berbeda. Update melalui Termux.\", false));",
)
main = main.replace(
    "@JavascriptInterface public void startCoreUpdate() { handler.post(MainActivity.this::startCoreRecoveryUpdate); }",
    "@JavascriptInterface public void startCoreUpdate() { coreUpdateState = \"Pembaruan dikelola melalui Termux: furina update\"; }",
)
main = re.sub(
    r'@JavascriptInterface public void checkAppUpdate\(\) \{.*?\n        \}',
    '@JavascriptInterface public void checkAppUpdate() { appUpdateBusy = false; appUpdateState = "Pembaruan dikelola melalui Termux: furina update";\n        }',
    main,
    count=1,
    flags=re.S,
)
MAIN.write_text(main, encoding="utf-8")

page = HTML.read_text(encoding="utf-8")

# Shared 20-trait personalization. Every click toggles the one Core-owned list;
# no presets, sliders, or a second APK-only personality state remain.
new_personal = '''<section id="personalization" class="view"><div class="sectionhead"><h1>Personalisasi</h1><div class="sub">Pilih kombinasi sifat Furina. Seluruh 20 sifat ditampilkan langsung, tanpa halaman atau daftar tersembunyi.</div></div><div id="personalOffline" class="card"></div><div id="personalOnline" class="hidden"><div class="card"><div class="field"><label for="assistantName">Nama companion</label><input id="assistantName" maxlength="48"></div><div class="field"><label for="nickname">Nama panggilan kamu</label><input id="nickname" maxlength="48"></div><button class="btn full" onclick="saveIdentity110()">Simpan identitas</button></div><div class="card"><div class="row"><div class="rowmain"><div class="rowtitle">20 sifat kepribadian</div><div class="rowdesc">Ketuk sifat untuk mengaktifkan atau menonaktifkan. Tidak ada sifat yang dipotong dari daftar.</div></div><span id="traitCount110" class="badge">0/20</span></div><div id="personalityTraitGrid110" class="traitGrid110" aria-label="Daftar 20 sifat kepribadian"></div><div id="traitPreview110" class="traitPreview110" aria-live="polite"></div></div></div></section>'''
page = replace_between(page, '<section id="personalization"', '<section id="agent"', new_personal, "personalization section")

# Settings keep a passive update note only. There is no update button/checker in
# the APK surface.
settings_start = page.find('<section id="settings"')
settings_end = page.find('</main>', settings_start)
if settings_start < 0 or settings_end < 0:
    raise SystemExit("settings section missing")
new_settings = '''<section id="settings" class="view"><div class="sectionhead"><h1>Pengaturan</h1><div class="sub">FurinaHub menggunakan Core dan state yang sama dengan Furina di Termux.</div></div><div class="card settingsConnectionCard"><div class="connectionHero"><div class="connectionIcon"><svg viewBox="0 0 24 24"><path d="M8 12h8M12 8v8"/><path d="M5 5a10 10 0 0 0 0 14M19 5a10 10 0 0 1 0 14"/></svg></div><div class="rowmain"><div class="rowtitle">Furina Core</div><div id="connectionMessage" class="rowdesc">Belum terhubung.</div></div><span id="connectionBadge" class="badge">Offline</span></div><div class="actions settingsActions"><button id="connectBtn" class="btn primary" onclick="nativeConnect()">Hubungkan ke Termux</button><button class="btn" onclick="nativeTermux()">Buka Termux</button></div><div class="connectionHint">Tombol Hubungkan akan mengganti sesi Core lama secara aman agar token dan port lokal tidak saling mengunci.</div></div><div class="card"><h3>Tampilan</h3><div class="field"><label>Tema</label><div id="themeChoices" class="themeChoices"><button class="themeChoice" data-theme-choice="system" onclick="setTheme('system')">Sistem</button><button class="themeChoice" data-theme-choice="light" onclick="setTheme('light')">Terang</button><button class="themeChoice" data-theme-choice="dark" onclick="setTheme('dark')">Gelap</button></div></div></div><div class="card"><h3>Pembaruan</h3><div class="rowdesc">Gunakan <strong>furina update</strong> di Termux untuk memperbarui Core dan FurinaHub sebagai satu paket.</div></div><div id="advancedCard" class="card hidden"><h3>Lanjutan</h3><div class="field"><label for="threads">Threads model lokal</label><input id="threads" type="number" min="1" max="12"></div><div class="field"><label for="contextSize">Context size</label><input id="contextSize" type="number" min="2048" max="16384" step="512"></div><div class="field"><label for="maxTokens">Max output tokens</label><input id="maxTokens" type="number" min="128" max="8192" step="128"></div><button class="btn full" onclick="saveAdvanced()">Simpan pengaturan lanjutan</button></div></section>'''
page = page[:settings_start] + new_settings + page[settings_end:]

# Local selection is one atomic action keyed by catalog id and writes the same
# Core routing/model state used by Termux.
page = replace_between(
    page,
    'function modelRow',
    'function renderModels',
    '''function modelRow(x,c){const active=c.routing_mode==='local'&&x.active,installed=!!x.installed,label=active?'Aktif':(installed?'Pilih':'Unduh'),action=active?'':(installed?`selectLocalModel(${JSON.stringify(x.id)})`:`downloadLocalModel(${JSON.stringify(x.id)})`);return `<div class="row"><div class="rowmain"><div class="rowtitle">${esc(x.name)}</div><div class="rowdesc">${esc(x.purpose||x.description||'Model lokal')} · ${esc(x.size_label||((Number(x.size_bytes||0)/1073741824).toFixed(1)+' GB'))}</div></div><div class="modelActions"><button class="btn ${active?'primary':''}" ${active?'disabled':''} onclick="${action}">${label}</button>${installed&&!active?`<button class="btn" onclick="deleteModel(${JSON.stringify(x.path)})">Hapus</button>`:''}</div></div>`}\n''',
    "modelRow",
)
page = replace_between(
    page,
    'async function selectOnlineModel',
    'async function downloadLocalModel',
    '''async function selectOnlineModel(){try{const r=await core('POST','/api/models',{action:'online'});settingsData=r.settings||await core('GET','/api/settings');renderModels();renderSettings();toast(r.message||'Model Online aktif.')}catch(e){toast(e.message)}}\nasync function selectLocalModel(catalogId){try{const r=await core('POST','/api/models',{action:'select',catalog_id:catalogId});settingsData=r.settings||await core('GET','/api/settings');renderModels();renderSettings();toast(r.message||'Model lokal aktif.')}catch(e){toast(e.message)}}\n''',
    "model selection",
)

page = replace_between(
    page,
    'function renderSettings',
    'async function refreshSharedSettings',
    r'''function renderSettings(){if(!settingsData)return;const h=settingsData.hub||{},c=settingsData.core||{},defs=settingsData.personality_traits||[],active=new Set(h.personality_traits||[]);const an=document.getElementById('assistantName'),nn=document.getElementById('nickname');if(an)an.value=h.assistant_name||c.persona_name||'Furina';if(nn)nn.value=h.user_nickname||c.user_nickname||'';const count=document.getElementById('traitCount110');if(count)count.textContent=active.size+'/20';const grid=document.getElementById('personalityTraitGrid110'),preview=document.getElementById('traitPreview110');if(grid){grid.innerHTML=defs.map(t=>`<button type="button" class="traitChoice110 ${active.has(t.id)?'on':''}" aria-pressed="${active.has(t.id)}" onclick="togglePersonality110(${JSON.stringify(t.id)})"><span class="traitMark110">${active.has(t.id)?'✓':''}</span><span>${esc(t.label)}</span></button>`).join('');const shown=defs.find(t=>t.id===window._traitPreview110)||defs.find(t=>active.has(t.id))||defs[0];if(preview)preview.textContent=shown?`${shown.label}: ${shown.description}`:''}const th=document.getElementById('threads'),cs=document.getElementById('contextSize'),mt=document.getElementById('maxTokens');if(th)th.value=c.threads||4;if(cs)cs.value=c.context_size||4096;if(mt)mt.value=c.max_tokens||1024}
async function togglePersonality110(id){if(!settingsData)return;const current=[...(settingsData.hub?.personality_traits||[])],i=current.indexOf(id);if(i>=0)current.splice(i,1);else current.push(id);window._traitPreview110=id;try{settingsData=await core('POST','/api/settings',{hub:{personality_traits:current}});renderSettings();const item=(settingsData.personality_traits||[]).find(x=>x.id===id);toast((i>=0?'Dinonaktifkan: ':'Diaktifkan: ')+(item?.label||id))}catch(e){toast(e.message)}}
async function saveIdentity110(){try{settingsData=await core('POST','/api/settings',{hub:{assistant_name:document.getElementById('assistantName').value,user_nickname:document.getElementById('nickname').value}});renderSettings();document.getElementById('brand').textContent=settingsData.hub?.assistant_name||'FurinaHub';toast('Identitas disimpan.')}catch(e){toast(e.message)}}
'''
''',
    "personalization JS",
)

# Remove the old Hub updater engine. Keep the original loadFocus function marker
# untouched after this replacement so JS remains syntactically valid.
page = replace_between(
    page,
    'let unifiedCoreUpdate',
    'async function loadFocus',
    '''function renderSystem(){if(!systemData)return;renderAgent()}\nfunction init(){initTheme();if(NATIVE){try{connection=JSON.parse(NATIVE.connectionStatus())}catch(e){}}applyConnection();if(connection.connected)refreshSharedSettings();document.addEventListener('visibilitychange',()=>{if(!document.hidden&&connection.connected)refreshSharedSettings()})}\ninit();\n\n''',
    "Hub updater JS",
)

# Some historical UI revisions left one-shot update refresh calls outside the
# updater block. Remove those calls only (not arbitrary functions), then require
# the final surface to contain no active Hub updater API or poller.
for fn in ("checkAllUpdates", "refreshAppUpdate", "syncUnifiedUpdateStatus"):
    page = re.sub(rf'(?<!function )\b{fn}\([^)]*\)\s*;?', '', page)

for forbidden in (
    'checkAllUpdates(', 'refreshAppUpdate(', 'syncUnifiedUpdateStatus(',
    "'/api/update/core'", "'/api/update/status'",
    'window.setInterval(()=>{if(!document.hidden&&connection.connected)syncUnifiedUpdateStatus',
):
    if forbidden in page:
        raise SystemExit(f"Hub updater residue: {forbidden}")
if "action:'select',catalog_id:catalogId" not in page:
    raise SystemExit("atomic model select missing")
if "personalityTraitGrid110" not in page or "togglePersonality110" not in page:
    raise SystemExit("trait UI missing")

# Compact two-column trait grid: all twenty options are always present.
page = replace_between(
    page,
    "function setTheme",
    "function initTheme",
    r'''function setTheme(mode){localStorage.setItem('furinahub-theme',mode);const dark=mode==='dark'||(mode==='system'&&matchMedia('(prefers-color-scheme:dark)').matches);document.documentElement.dataset.theme=dark?'dark':'light';document.querySelectorAll('[data-theme-choice]').forEach(button=>button.classList.toggle('on',button.dataset.themeChoice===mode))}
''',
    "theme controls",
)
extra_css = r'''#settings .settingsConnectionCard{padding:16px}.settingsConnectionCard .connectionHero{align-items:flex-start}.settingsConnectionCard .connectionIcon{margin-top:1px}.connectionHint{margin-top:11px;font-size:12px;line-height:1.45;color:var(--muted)}.themeChoices{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}.themeChoice{min-height:44px;padding:0 8px;border:1px solid var(--line);border-radius:14px;background:var(--surface);color:var(--ink);font-weight:650}.themeChoice.on{background:var(--accent-soft);border-color:var(--accent);color:var(--accent)}.traitGrid110{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin-top:12px}.traitChoice110{display:flex;align-items:center;gap:8px;min-height:44px;padding:9px 10px;border:1px solid var(--line);border-radius:13px;background:var(--surface2);color:var(--ink);text-align:left;font-size:13px;font-weight:650}.traitChoice110.on{background:var(--accent-soft);border-color:color-mix(in srgb,var(--accent) 60%,var(--line));color:var(--accent)}.traitMark110{display:grid;place-items:center;width:17px;height:17px;border:1px solid currentColor;border-radius:5px;font-size:12px;line-height:1;flex:none}.traitPreview110{margin-top:12px;padding:10px 11px;border-left:2px solid var(--accent);border-radius:0 10px 10px 0;background:color-mix(in srgb,var(--accent-soft) 55%,transparent);font-size:12px;line-height:1.5;color:var(--muted)}@media(max-width:360px){.settingsActions{flex-direction:column}.traitGrid110{grid-template-columns:1fr}.themeChoices{gap:6px}.themeChoice{font-size:12px}}'''
if "</style>" not in page:
    raise SystemExit("style close marker missing")
page = page.replace("</style>", extra_css + "</style>", 1)
HTML.write_text(page, encoding="utf-8")
print("FURINAHUB_PRIVATE_1_1_0_UI_UPDATE_OWNERSHIP_OK")
