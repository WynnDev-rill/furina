#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text and old not in text:
        return text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"Android RC45 marker mismatch: {label} ({count})")
    return text.replace(old, new, 1)


def function_start(text: str, name: str, after: int = 0) -> int:
    hits = []
    for prefix in ("async function ", "function "):
        pos = text.find(prefix + name + "(", after)
        if pos >= 0:
            hits.append(pos)
    return min(hits) if hits else -1


def replace_function(text: str, name: str, next_name: str, replacement: str) -> str:
    start = function_start(text, name)
    end = function_start(text, next_name, max(start, 0) + 1)
    if start < 0 or end < 0 or end <= start:
        raise SystemExit(f"Android RC45 JS boundary mismatch: {name} -> {next_name}")
    return text[:start] + replacement.rstrip() + "\n" + text[end:]


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("usage: apply.py <termux-root>")
    root = Path(sys.argv[1]).resolve()
    app = root / "bridge/app"
    html_path = app / "src/main/assets/furinahub/index.html"
    gradle_path = app / "build.gradle"
    hub_path = root / "core/furina_agent/hub.py"
    updater_path = app / "src/main/java/com/wynndev/furinaagentbridge/BridgeUpdater.java"
    for path in (html_path, gradle_path, hub_path, updater_path):
        if not path.is_file():
            raise SystemExit(f"Android RC45 source missing: {path}")

    gradle = gradle_path.read_text(encoding="utf-8")
    gradle = replace_once(gradle, "versionCode 10044", "versionCode 10045", "versionCode")
    gradle = replace_once(gradle, "versionName '1.0.0-rc44'", "versionName '1.0.0-rc45'", "versionName")

    hub = hub_path.read_text(encoding="utf-8")
    old_target = '"bridge_target": "1.0.0-rc44"'
    new_target = '"bridge_target": "1.0.0-rc45"'
    if old_target in hub:
        hub = hub.replace(old_target, new_target)
    if old_target in hub or new_target not in hub:
        raise SystemExit("Android RC45 bridge target migration incomplete")

    updater = updater_path.read_text(encoding="utf-8")
    updater = replace_once(updater, "FurinaHub-Updater/10", "FurinaHub-Updater/11", "updater agent")

    html = html_path.read_text(encoding="utf-8")
    render_system = r'''let unifiedCoreUpdate=null,unifiedUpdateSyncBusy=false;
function updateStateLabel(s){if(!s)return'Belum diperiksa.';if(s.state==='error')return s.message||'Pembaruan gagal.';if(s.state==='done'){if(s.result==='updated')return s.message||'Pembaruan berhasil.';return s.message||'Tidak ada pembaruan terbaru.'}return s.message||'Sedang memeriksa pembaruan…'}
function renderSystem(){if(!systemData)return;const status=document.getElementById('coreUpdateStatus');if(!unifiedCoreUpdate)status.textContent=`Core ${systemData.core_version||'?'} · dependency ${systemData.dependency_revision||'?'}`;renderAgent();if(connection.connected)syncUnifiedUpdateStatus(true)}
async function syncUnifiedUpdateStatus(silent=false){if(!connection.connected||unifiedUpdateSyncBusy)return unifiedCoreUpdate;unifiedUpdateSyncBusy=true;try{const s=await core('GET','/api/update/status');unifiedCoreUpdate=s;paintCoreUpdate(s);return s}catch(e){if(!silent)toast('Status update: '+e.message);return unifiedCoreUpdate}finally{unifiedUpdateSyncBusy=false}}'''
    html = replace_function(html, "renderSystem", "updateCore", render_system)

    update_core = r'''async function updateCore(){if(connection.connected){try{const r=await core('POST','/api/update/core',{});unifiedCoreUpdate=r;paintCoreUpdate(r);pollCoreUpdate();return}catch(e){toast(e.message)}}if(NATIVE?.startCoreUpdate){NATIVE.startCoreUpdate();refreshNativeCoreUpdate();return}toast('Termux belum dapat menjalankan updater.')}'''
    html = replace_function(html, "updateCore", "refreshNativeCoreUpdate", update_core)

    refresh_native = r'''function refreshNativeCoreUpdate(){if(connection.connected){syncUnifiedUpdateStatus(true);return}if(!NATIVE?.coreUpdateStatus)return;const el=document.getElementById('coreUpdateStatus'),btn=document.getElementById('coreUpdateBtn');const msg=NATIVE.coreUpdateStatus();if(msg)el.textContent=msg;const busy=!!NATIVE.coreUpdateBusy();btn.disabled=busy||!connection.termux_installed;btn.textContent=busy?'Memperbarui Core…':'Perbaiki / update Core & dependency';if(busy)setTimeout(refreshNativeCoreUpdate,650)}'''
    html = replace_function(html, "refreshNativeCoreUpdate", "paintCoreUpdate", refresh_native)

    paint = r'''function paintCoreUpdate(s){if(!s)return;unifiedCoreUpdate=s;const p=Math.max(0,Math.min(100,Number(s.percent||0))),bar=document.getElementById('coreUpdateProgress'),label=document.getElementById('coreUpdatePercent'),stage=document.getElementById('coreUpdateStage'),status=document.getElementById('coreUpdateStatus'),btn=document.getElementById('coreUpdateBtn'),running=['starting','running'].includes(s.state);status.textContent=updateStateLabel(s);status.style.color=s.state==='error'?'#ff718d':'';bar.classList.toggle('hidden',!['starting','running','done','error'].includes(s.state));bar.querySelector('span').style.width=p+'%';label.textContent=p+'%';const stageMap={checking:'Memeriksa',waiting:'Menunggu',foundation:'Menyiapkan fondasi',download:'Mengambil pembaruan',apply:'Menerapkan',validation:'Memvalidasi',commit:'Menyimpan',done:s.result==='updated'?'Berhasil diperbarui':'Sudah terbaru'};stage.textContent=s.state==='error'?'Gagal · '+(s.stage||'update'):(stageMap[s.stage]||({starting:'Menyiapkan',running:'Sedang berjalan',done:'Selesai'}[s.state]||'Siap diperiksa'));btn.disabled=running}'''
    html = replace_function(html, "paintCoreUpdate", "pollCoreUpdate", paint)

    poll = r'''async function pollCoreUpdate(){for(let i=0;i<1500;i++){await new Promise(r=>setTimeout(r,800));try{const s=await core('GET','/api/update/status');paintCoreUpdate(s);if(['done','error'].includes(s.state)){document.getElementById('coreUpdateBtn').disabled=false;return s}}catch(e){return null}}return null}'''
    html = replace_function(html, "pollCoreUpdate", "checkAllUpdates", poll)

    check_all = r'''async function checkAllUpdates(){const btn=document.getElementById('allUpdateBtn');if(btn.disabled)return;btn.disabled=true;btn.textContent='Memeriksa pembaruan…';let coreState=null;try{if(connection.termux_installed){if(connection.connected){try{coreState=await core('POST','/api/update/core',{});paintCoreUpdate(coreState);if(!['done','error'].includes(coreState.state))coreState=await pollCoreUpdate()}catch(e){coreState={state:'error',stage:'core',percent:0,message:'Pembaruan gagal pada tahap Core: '+e.message};paintCoreUpdate(coreState)}}else if(NATIVE?.startCoreUpdate){NATIVE.startCoreUpdate();for(let i=0;i<1500&&NATIVE.coreUpdateBusy();i++){refreshNativeCoreUpdate();await new Promise(r=>setTimeout(r,800))}refreshNativeCoreUpdate()}}if(NATIVE){NATIVE.checkAppUpdate();refreshAppUpdate();for(let i=0;i<240&&NATIVE.appUpdateBusy();i++)await new Promise(r=>setTimeout(r,500));refreshAppUpdate()}if(connection.connected)await syncUnifiedUpdateStatus(true)}finally{btn.disabled=false;btn.textContent='Periksa pembaruan'}}'''
    html = replace_function(html, "checkAllUpdates", "nativeAppUpdate", check_all)

    init = r'''function init(){initTheme();if(NATIVE){try{connection=JSON.parse(NATIVE.connectionStatus())}catch(e){}}applyConnection();refreshAppUpdate();if(connection.connected)syncUnifiedUpdateStatus(true);else refreshNativeCoreUpdate();document.addEventListener('visibilitychange',()=>{if(!document.hidden){if(connection.connected){syncUnifiedUpdateStatus(true);refreshSharedSettings()}else refreshNativeCoreUpdate();refreshAppUpdate()}});window.setInterval(()=>{if(!document.hidden&&connection.connected)syncUnifiedUpdateStatus(true)},4000)}
init();'''
    # init is the final function before its invocation.
    init_start = function_start(html, "init")
    init_call = html.find("init();", max(0, init_start) + 1)
    if init_start < 0 or init_call < 0:
        raise SystemExit("Android RC45 init boundary missing")
    end = init_call + len("init();")
    html = html[:init_start] + init + html[end:]

    checks = (
        "versionCode 10045",
        "versionName '1.0.0-rc45'",
        '"bridge_target": "1.0.0-rc45"',
        "FurinaHub-Updater/11",
        "syncUnifiedUpdateStatus",
        "unifiedCoreUpdate",
        "Tidak ada pembaruan terbaru.",
        "Pembaruan berhasil.",
        "Pembaruan gagal pada tahap Core",
        "window.setInterval",
    )
    combined = gradle + "\n" + hub + "\n" + updater + "\n" + html
    missing = [item for item in checks if item not in combined]
    if missing:
        raise SystemExit("Android RC45 unified update markers missing: " + ", ".join(missing))

    gradle_path.write_text(gradle, encoding="utf-8")
    hub_path.write_text(hub, encoding="utf-8")
    updater_path.write_text(updater, encoding="utf-8")
    html_path.write_text(html, encoding="utf-8")
    print("FURINAHUB_ANDROID_RC45_UNIFIED_UPDATE_OK")


if __name__ == "__main__":
    main()
