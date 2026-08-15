#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text and old not in text:
        return text
    if text.count(old) != 1:
        raise SystemExit(f"RC29 marker mismatch: {label} ({text.count(old)})")
    return text.replace(old, new, 1)


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("usage: apply.py <termux-root>")
    root = Path(sys.argv[1]).resolve()
    app = root / "bridge/app"
    main_activity = app / "src/main/java/com/wynndev/furinaagentbridge/MainActivity.java"
    html_path = app / "src/main/assets/furinahub/index.html"
    gradle = app / "build.gradle"
    res_drawable = app / "src/main/res/drawable"
    for path in (main_activity, html_path, gradle):
        if not path.is_file():
            raise SystemExit(f"RC29 source missing: {path}")

    body = main_activity.read_text(encoding="utf-8")
    body = replace_once(
        body,
        'nativeMenu.setImageResource(android.R.drawable.ic_menu_sort_by_size);',
        'nativeMenu.setImageResource(com.wynndev.furinaagentbridge.R.drawable.ic_furinahub_menu);',
        "native menu icon",
    )
    body = replace_once(
        body,
        '''        nativeMenu.setColorFilter(Color.rgb(243, 240, 248));
        nativeMenu.setBackgroundColor(Color.TRANSPARENT);
''',
        '''        nativeMenu.setColorFilter(Color.rgb(243, 240, 248));
        nativeMenu.setPadding(dp(12), dp(12), dp(12), dp(12));
        nativeMenu.setBackgroundColor(Color.TRANSPARENT);
''',
        "native menu padding",
    )
    body = replace_once(body, 'nativeTitle.setTextSize(19);', 'nativeTitle.setTextSize(18);', "native title size")
    body = replace_once(
        body,
        'nativeTitle.setTypeface(android.graphics.Typeface.DEFAULT, android.graphics.Typeface.BOLD);',
        'nativeTitle.setTypeface(android.graphics.Typeface.create("sans-serif", android.graphics.Typeface.BOLD));',
        "native title font",
    )
    body = replace_once(
        body,
        'for (int i = Math.max(0, lines.length - 8); i < lines.length; i++) {',
        'for (int i = Math.max(0, lines.length - 14); i < lines.length; i++) {',
        "update error tail lines",
    )
    body = replace_once(
        body,
        'return value.length() > 560 ? value.substring(value.length() - 560) : value;',
        'return value.length() > 900 ? value.substring(value.length() - 900) : value;',
        "update error tail size",
    )
    main_activity.write_text(body, encoding="utf-8")

    res_drawable.mkdir(parents=True, exist_ok=True)
    (res_drawable / "ic_furinahub_menu.xml").write_text(
        '''<?xml version="1.0" encoding="utf-8"?>
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="24dp" android:height="24dp"
    android:viewportWidth="24" android:viewportHeight="24">
    <path android:fillColor="@android:color/transparent"
        android:strokeColor="#FFFFFFFF" android:strokeWidth="2"
        android:strokeLineCap="round" android:strokeLineJoin="round"
        android:pathData="M4,7 L20,7 M4,12 L20,12 M4,17 L20,17" />
</vector>
''',
        encoding="utf-8",
    )

    html = html_path.read_text(encoding="utf-8")
    polish = r'''
/* RC29: mobile-native visual polish */
html,body,button,input,select,textarea{font-family:Roboto,"Noto Sans",Arial,sans-serif!important}
[data-theme="dark"]{--bg:#101014;--surface:#18181f;--surface2:#202029;--surface3:#292933;--ink:#f6f4f8;--muted:#aaa7b4;--line:#30303a;--accent:#998cff;--accent-soft:#302b52;--shadow:0 10px 30px rgba(0,0,0,.22)}
.view{padding-top:18px}.sectionhead{margin-bottom:16px}.sectionhead h1{font-size:22px;letter-spacing:-.01em}.card{border-radius:18px;padding:14px;box-shadow:none}.row{min-height:56px}
.messages{padding:18px 18px 12px}.msg{margin:7px 0}.bubble{font-size:15px;line-height:1.55}.msg.assistant .bubble{background:transparent;border:0;padding:9px 2px;border-radius:0;max-width:min(91%,720px)}.msg.user .bubble{background:var(--accent-soft);border-radius:19px 19px 6px 19px;padding:10px 13px;max-width:min(82%,650px)}
.composer{padding:9px 12px calc(10px + env(safe-area-inset-bottom));background:color-mix(in srgb,var(--bg) 94%,transparent);border-top:1px solid color-mix(in srgb,var(--line) 65%,transparent);backdrop-filter:blur(16px)}.composebox{border-radius:22px;box-shadow:0 3px 14px rgba(0,0,0,.10);padding-left:11px}.send,.plus{width:42px;height:42px;min-width:42px;min-height:42px}.plus{background:var(--surface2);border-color:transparent}
.drawerback{background:#0008}.drawer{width:min(82vw,304px);padding:calc(14px + env(safe-area-inset-top)) 10px calc(14px + env(safe-area-inset-bottom));border-right:1px solid var(--line);border-radius:0 24px 24px 0;box-shadow:24px 0 56px #0005}.drawerbrand{font-size:18px;padding:8px 12px 14px}.nav{min-height:50px;padding:0 12px;border-radius:13px}.historyTitle{padding-left:12px}.historyRow .historyDelete{opacity:.72}.drawer .sep{margin:9px 8px}
.pluginSearch{padding-top:0}.pluginSearch input{border-radius:16px;background:var(--surface2);border-color:transparent}.pluginLogo,.pluginFallback{width:44px;height:44px;border-radius:13px}.statusError{padding:12px;border-radius:14px;background:color-mix(in srgb,var(--danger) 8%,var(--surface));border:1px solid color-mix(in srgb,var(--danger) 30%,var(--line))}.statusError .rowdesc{margin-top:5px}.statusActions{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:12px}.updateError{color:var(--danger)!important}.percentHero strong{font-size:27px}.determinate{height:7px}.themeChoice{min-height:48px}.btn{border-radius:13px}
@media(max-width:380px){.drawer{width:86vw}.statusActions{grid-template-columns:1fr}.messages{padding-left:14px;padding-right:14px}}
'''
    html = replace_once(html, "</style>", polish + "\n</style>", "visual polish CSS")

    old_conversations = '''function renderConversations(items,active){const target=document.getElementById('conversationRows');target.innerHTML=items.length?items.map(x=>`<div class="historyRow"><button class="nav historyOpen ${Number(x.id)===Number(active)?'on':''}" onclick="switchConversation(${Number(x.id)})">${esc(x.title||'Percakapan baru')}</button><button class="nav historyDelete" aria-label="Hapus percakapan" onclick="deleteConversation(${Number(x.id)})">×</button></div>`).join(''):'<div class="empty" style="padding:8px 12px">Belum ada riwayat.</div>'}'''
    new_conversations = '''function prettyConversationTitle(value){let t=String(value||'').trim();if(!t)return'Percakapan baru';if(/^\[(?:Gambar|Image):/i.test(t))return'Percakapan bergambar';t=t.replace(/^\[(?:Gambar|Image|File):[^\]]+\]\s*/i,'').trim();if(/^(?:hi|hai|hu|halo|hello|hey|test|tes)$/i.test(t)||t.length<3)return'Percakapan baru';return t.length>54?t.slice(0,51)+'…':t}
function renderConversations(items,active){const target=document.getElementById('conversationRows');target.innerHTML=items.length?items.map(x=>`<div class="historyRow"><button class="nav historyOpen ${Number(x.id)===Number(active)?'on':''}" onclick="switchConversation(${Number(x.id)})">${esc(prettyConversationTitle(x.title))}</button><button class="nav historyDelete" aria-label="Hapus percakapan" onclick="deleteConversation(${Number(x.id)})">×</button></div>`).join(''):'<div class="empty" style="padding:8px 12px">Belum ada riwayat.</div>'}'''
    html = replace_once(html, old_conversations, new_conversations, "conversation title cleanup")

    old_plugins = '''async function loadPlugins(){const status=document.getElementById('pluginStatus');status.innerHTML='<div class="loadingline"></div>';try{const result=await core('GET','/api/connectors/plugins');pluginData=result.plugins||[];if(!result.online){status.innerHTML=`<div class="rowtitle">${result.state==='missing'?'Komponen Plugin belum terpasang':'Menyiapkan Plugin'}</div><div class="rowdesc">${esc(result.message||'Layanan Plugin belum siap.')}</div><button class="btn full" style="margin-top:12px" onclick="loadPlugins()">Coba lagi</button>`;document.getElementById('pluginRows').innerHTML='';if(result.state==='starting')setTimeout(()=>{if(document.getElementById('plugins').classList.contains('active'))loadPlugins()},2500);return}status.innerHTML=`<div class="rowtitle">Plugin siap</div><div class="rowdesc">${pluginData.length} plugin tersedia. Data login tetap disimpan di layanan lokal.</div>`;renderPlugins(document.getElementById('pluginSearch').value)}catch(e){pluginData=[];status.innerHTML='<div class="rowtitle inlineError">Plugin belum dapat dimuat</div><div class="rowdesc">Periksa Core & dependency, lalu coba lagi.</div><button class="btn full" style="margin-top:12px" onclick="loadPlugins()">Coba lagi</button>';document.getElementById('pluginRows').innerHTML=''}}'''
    new_plugins = '''async function repairPlugin(){toast('Menjalankan perbaikan Plugin…');go('settings');await updateCore()}
async function loadPlugins(){const status=document.getElementById('pluginStatus');status.classList.remove('statusError');status.innerHTML='<div class="loadingline"></div>';try{const result=await core('GET','/api/connectors/plugins');pluginData=result.plugins||[];if(!result.online){const failed=result.state==='error'||result.state==='missing'||result.repairable;status.classList.toggle('statusError',!!failed);const title=result.state==='missing'?'Komponen Plugin belum terpasang':result.state==='error'?'Plugin gagal dimulai':'Menyiapkan Plugin';status.innerHTML=`<div class="rowtitle ${failed?'inlineError':''}">${title}</div><div class="rowdesc">${esc(result.message||'Layanan Plugin belum siap.')}</div><div class="statusActions"><button class="btn" onclick="loadPlugins()">Coba lagi</button>${failed?'<button class="btn primary" onclick="repairPlugin()">Perbaiki Plugin</button>':''}</div>`;document.getElementById('pluginRows').innerHTML='';if(result.state==='starting')setTimeout(()=>{if(document.getElementById('plugins').classList.contains('active'))loadPlugins()},2500);return}status.classList.remove('statusError');status.innerHTML=`<div class="rowtitle">Plugin siap</div><div class="rowdesc">${pluginData.length} plugin tersedia. Credential tetap berada di runtime lokal.</div>`;renderPlugins(document.getElementById('pluginSearch').value)}catch(e){pluginData=[];status.classList.add('statusError');status.innerHTML=`<div class="rowtitle inlineError">Plugin belum dapat dimuat</div><div class="rowdesc">${esc(e.message||'Periksa Core & dependency, lalu coba lagi.')}</div><div class="statusActions"><button class="btn" onclick="loadPlugins()">Coba lagi</button><button class="btn primary" onclick="repairPlugin()">Perbaiki Plugin</button></div>`;document.getElementById('pluginRows').innerHTML=''}}'''
    html = replace_once(html, old_plugins, new_plugins, "Plugin recovery UI")

    old_native = '''function refreshNativeCoreUpdate(){if(!NATIVE?.coreUpdateStatus)return;const el=document.getElementById('coreUpdateStatus'),btn=document.getElementById('coreUpdateBtn');const msg=NATIVE.coreUpdateStatus();if(msg)el.textContent=msg;const busy=!!NATIVE.coreUpdateBusy();btn.disabled=busy||!connection.termux_installed;btn.textContent=busy?'Memperbarui Core…':'Perbaiki / update Core & dependency';if(busy)setTimeout(refreshNativeCoreUpdate,650);else if(msg&&msg!=='Belum diperiksa.')toast(msg)}'''
    new_native = '''function refreshNativeCoreUpdate(){if(!NATIVE?.coreUpdateStatus)return;const el=document.getElementById('coreUpdateStatus'),btn=document.getElementById('coreUpdateBtn');const msg=NATIVE.coreUpdateStatus();if(msg)el.textContent=msg;el.classList.toggle('updateError',/gagal|error|berhenti|kode [1-9]/i.test(msg||''));const busy=!!NATIVE.coreUpdateBusy();btn.disabled=busy||!connection.termux_installed;btn.textContent=busy?'Memperbarui Core…':'Perbaiki / update Core & dependency';if(busy)setTimeout(refreshNativeCoreUpdate,650);else if(msg&&msg!=='Belum diperiksa.')toast(msg)}'''
    html = replace_once(html, old_native, new_native, "native update error styling")
    html_path.write_text(html, encoding="utf-8")

    gradle_text = gradle.read_text(encoding="utf-8")
    gradle_text = replace_once(gradle_text, "versionCode 10028", "versionCode 10029", "versionCode")
    gradle_text = replace_once(gradle_text, "versionName '1.0.0-rc28'", "versionName '1.0.0-rc29'", "versionName")
    gradle.write_text(gradle_text, encoding="utf-8")

    checks = {
        main_activity: (
            "R.drawable.ic_furinahub_menu",
            'Typeface.create("sans-serif"',
            "lines.length - 14",
            "value.length() > 900",
        ),
        html_path: (
            "RC29: mobile-native visual polish",
            "prettyConversationTitle",
            "async function repairPlugin()",
            "Plugin gagal dimulai",
            "updateError",
            'font-family:Roboto,"Noto Sans",Arial,sans-serif',
        ),
        gradle: ("versionCode 10029", "versionName '1.0.0-rc29'"),
    }
    for path, markers in checks.items():
        text = path.read_text(encoding="utf-8")
        missing = [m for m in markers if m not in text]
        if missing:
            raise SystemExit(f"RC29 marker hilang di {path.name}: {missing}")
    print("FURINAHUB_ANDROID_RC29_OK")


if __name__ == "__main__":
    main()
