#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text and old not in text:
        return text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"RC32 marker mismatch: {label} ({count})")
    return text.replace(old, new, 1)


def replace_js_function(text: str, name: str, next_name: str, replacement: str) -> str:
    start = text.find(f"function {name}(")
    end = text.find(f"function {next_name}(", start + 1)
    if start < 0 or end < 0 or end <= start:
        raise SystemExit(f"RC32 JS boundary mismatch: {name} -> {next_name}")
    return text[:start] + replacement.rstrip() + "\n" + text[end:]


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("usage: apply.py <termux-root>")
    root = Path(sys.argv[1]).resolve()
    app = root / "bridge/app"
    html_path = app / "src/main/assets/furinahub/index.html"
    gradle = app / "build.gradle"
    for path in (html_path, gradle):
        if not path.is_file():
            raise SystemExit(f"RC32 source missing: {path}")

    html = html_path.read_text(encoding="utf-8")
    css = r'''
/* RC32: simple, contract-driven Plugin UI */
.pluginGroup{margin:20px 2px 8px;color:var(--muted);font-size:11px;font-weight:720;text-transform:uppercase;letter-spacing:.055em}.pluginMeta{display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin-top:4px}.pluginMeta span{font-size:11px;color:var(--muted)}.pluginMeta span+span:before{content:'·';margin-right:6px}.pluginButton{min-width:112px}.pluginButton.ready{color:var(--ok);background:color-mix(in srgb,var(--ok) 10%,var(--surface2))}.pluginButton.unsupported{font-size:11px}.pluginCatalogNote{padding:9px 2px 0;color:var(--muted);font-size:11px;line-height:1.45}.pluginConnectHint{display:none;margin:0 0 12px;padding:10px 12px;border-radius:12px;background:var(--surface2);color:var(--muted);font-size:11px;line-height:1.5;overflow-wrap:anywhere}.pluginConnectHint.show{display:block}.pluginConnectFields{display:grid;gap:11px}.pluginConnectFields label{display:grid;gap:6px;color:var(--muted);font-size:12px}.pluginConnectFields input{width:100%;min-height:48px;padding:10px 12px;border:1px solid var(--line);border-radius:13px;background:var(--bg);color:var(--ink);outline:none}.pluginConnectFields input:focus{border-color:var(--accent);box-shadow:0 0 0 3px color-mix(in srgb,var(--accent) 12%,transparent)}.pluginConnectFields small{line-height:1.4;color:var(--muted)}
'''
    html = replace_once(html, "</style>", css + "\n</style>", "Plugin CSS")

    modal = '''<div id="pluginConnectLayer" class="dialogLayer" role="dialog" aria-modal="true" aria-labelledby="pluginConnectTitle"><div class="dialogCard"><h2 id="pluginConnectTitle">Hubungkan Plugin</h2><p id="pluginConnectMessage"></p><div id="pluginConnectHint" class="pluginConnectHint"></div><div id="pluginConnectFields" class="pluginConnectFields"></div><div class="dialogActions"><button class="btn" onclick="closePluginSetup()">Batal</button><button id="pluginConnectSubmit" class="btn primary" onclick="submitPluginSetup()">Lanjutkan</button></div></div></div>\n'''
    html = replace_once(html, '<div id="pluginPicker" class="dialogLayer"', modal + '<div id="pluginPicker" class="dialogLayer"', "Plugin setup dialog")
    html = replace_once(html, "function showAttachment(){", "let pluginSetup=null;\nfunction showAttachment(){", "Plugin setup state")
    html = replace_once(
        html,
        "onResume(){if(connection.connected)refreshSharedSettings()}};",
        "onResume(){if(connection.connected){refreshSharedSettings();if(document.getElementById('plugins')?.classList.contains('active'))loadPlugins()}}};",
        "refresh OAuth on resume",
    )

    load_plugins = r'''async function loadPlugins(){
 const status=document.getElementById('pluginStatus');status.innerHTML='<div class="loadingline"></div>';
 try{
  const result=await core('GET','/api/connectors/plugins');pluginData=Array.isArray(result.plugins)?result.plugins:[];
  if(!result.online){status.innerHTML=`<div class="rowtitle">${result.state==='missing'?'Komponen Plugin belum terpasang':result.state==='error'?'Plugin perlu diperbaiki':'Menyiapkan Plugin'}</div><div class="rowdesc">${esc(result.message||'Layanan Plugin belum siap.')}</div><button class="btn full" style="margin-top:12px" onclick="loadPlugins()">Coba lagi</button>`;document.getElementById('pluginRows').innerHTML='';if(result.state==='starting')setTimeout(()=>{if(document.getElementById('plugins').classList.contains('active'))loadPlugins()},2500);return}
  const total=Number(result.total_count||result.count||pluginData.length);status.innerHTML=`<div class="rowtitle">Plugin siap</div><div class="rowdesc">${total} layanan tersedia. Tanpa-login langsung siap; credential akun tetap berada di runtime lokal.</div>`;
  renderPlugins(document.getElementById('pluginSearch').value)
 }catch(e){pluginData=[];status.innerHTML=`<div class="rowtitle inlineError">Plugin belum dapat dimuat</div><div class="rowdesc">${esc(e.message||'Periksa Furina Core, lalu coba lagi.')}</div><button class="btn full" style="margin-top:12px" onclick="loadPlugins()">Coba lagi</button>`;document.getElementById('pluginRows').innerHTML=''}
}'''
    html = replace_js_function(html, "loadPlugins", "pluginIcon", load_plugins)

    render_plugins = r'''function pluginAuthText(p){const a=Array.isArray(p.auth_types)?p.auth_types:[];if(p.no_auth)return'Tanpa login';const names=[];if(a.includes('oauth2'))names.push('OAuth');if(a.includes('api_key'))names.push('API key');if(a.includes('custom_credential'))names.push('Credential');return names.join(' / ')||'Autentikasi khusus'}
function pluginButton(p){if(p.connected)return`<button class="btn pluginButton ready" disabled>Terhubung</button>`;if(p.no_auth)return`<button class="btn pluginButton ready" disabled>Siap</button>`;if(!p.supported)return`<button class="btn pluginButton unsupported" disabled>Tidak didukung</button>`;return`<button class="btn primary pluginButton" onclick="connectPlugin('${p.id}')">Hubungkan</button>`}
function renderPlugins(query=''){
 const q=String(query).trim().toLowerCase();let items=pluginData.filter(p=>!q||JSON.stringify(p).toLowerCase().includes(q));
 if(!q)items=items.filter(p=>p.connected||Number(p.priority)<18).slice(0,28);else items=items.slice(0,80);
 const groups={};items.forEach(p=>(groups[p.category||'Lainnya']??=[]).push(p));
 const rows=Object.entries(groups).map(([group,list])=>`<div class="pluginGroup">${esc(group)}</div><div class="card">${list.map(p=>`<div class="row"><div style="display:flex;gap:12px;align-items:center;min-width:0;flex:1">${pluginIcon(p)}<div class="rowmain"><div class="rowtitle">${esc(p.name)}</div><div class="rowdesc">${esc(p.description||'')}</div><div class="pluginMeta"><span>${Number(p.action_count||0)} action</span><span>${esc(pluginAuthText(p))}</span>${p.connection_label?`<span>${esc(p.connection_label)}</span>`:''}</div></div></div>${pluginButton(p)}</div>`).join('')}</div>`).join('');
 const note=!q&&pluginData.length>items.length?`<div class="pluginCatalogNote">Menampilkan layanan utama. Gunakan pencarian untuk mengakses seluruh ${pluginData.length} plugin.</div>`:q&&pluginData.filter(p=>JSON.stringify(p).toLowerCase().includes(q)).length>items.length?`<div class="pluginCatalogNote">Terlalu banyak hasil. Persempit kata pencarian.</div>`:'';
 document.getElementById('pluginRows').innerHTML=rows+note||'<div class="empty">Plugin tidak ditemukan.</div>'
}'''
    html = replace_js_function(html, "renderPlugins", "filterPlugins", render_plugins)

    connect_block = r'''async function handlePluginConnectResult(p,result){
 if(!result)return;
 if(result.flow==='connected'){toast(result.message||'Plugin terhubung.');closePluginSetup();await loadPlugins();return}
 if(result.flow==='no_auth'){toast(result.message||'Plugin siap tanpa login.');await loadPlugins();return}
 if(result.flow==='oauth_browser'){
  closePluginSetup();
  if(result.authorization_url&&NATIVE?.openExternalUrl){NATIVE.openExternalUrl(result.authorization_url);toast('Selesaikan izin di browser, lalu kembali ke FurinaHub.')}else toast('Browser tidak dapat dibuka.');return
 }
 if(result.flow==='credential'||result.flow==='oauth_setup'){openPluginSetup(p,result);return}
 toast(result.message||'Metode koneksi plugin ini belum didukung.')
}
async function connectPlugin(id){
 const p=pluginData.find(x=>x.id===id);if(!p||p.connected||p.no_auth||!p.supported)return;
 try{const result=await core('POST','/api/connectors/connect',{service:id,mode:'auto'});await handlePluginConnectResult(p,result)}catch(e){toast(e.message)}
}
function openPluginSetup(p,result){
 pluginSetup={provider:p,mode:result.mode||'api_key',fields:Array.isArray(result.fields)?result.fields:[]};
 document.getElementById('pluginConnectTitle').textContent=(result.flow==='oauth_setup'?'Siapkan login ':'Hubungkan ')+p.name;
 document.getElementById('pluginConnectMessage').textContent=result.message||'Masukkan credential yang diminta layanan ini.';
 const hint=document.getElementById('pluginConnectHint'),redirect=String(result.expected_redirect_uri||'');hint.textContent=redirect?'Redirect URI untuk aplikasi OAuth: '+redirect:'';hint.classList.toggle('show',!!redirect);
 const fields=document.getElementById('pluginConnectFields');fields.innerHTML=pluginSetup.fields.map((f,i)=>`<label>${esc(f.label||f.key)}<input class="pluginCredentialInput" data-key="${esc(f.key)}" type="${f.secret?'password':'text'}" autocomplete="off" ${f.required?'required':''} placeholder="${esc(f.hint||'')}">${f.hint?`<small>${esc(f.hint)}</small>`:''}</label>`).join('');
 document.getElementById('pluginConnectLayer').classList.add('show');setTimeout(()=>fields.querySelector('input')?.focus(),60)
}
function closePluginSetup(){const layer=document.getElementById('pluginConnectLayer');layer.querySelectorAll('input').forEach(x=>x.value='');layer.classList.remove('show');pluginSetup=null}
async function submitPluginSetup(){
 if(!pluginSetup)return;const values={};for(const input of document.querySelectorAll('#pluginConnectFields .pluginCredentialInput')){const value=input.value.trim();if(input.required&&!value){input.focus();toast('Lengkapi field yang wajib.');return}if(value)values[input.dataset.key]=value}
 const btn=document.getElementById('pluginConnectSubmit');btn.disabled=true;
 try{const result=await core('POST','/api/connectors/connect',{service:pluginSetup.provider.id,mode:pluginSetup.mode,values});const p=pluginSetup.provider;await handlePluginConnectResult(p,result)}catch(e){toast(e.message)}finally{btn.disabled=false}
}'''
    html = replace_js_function(html, "connectPlugin", "openPluginPicker", connect_block)

    picker = r'''function renderPluginPicker(query=''){const q=String(query).toLowerCase(),items=pluginData.filter(p=>p.ready&&(!q||JSON.stringify(p).toLowerCase().includes(q)));document.getElementById('pluginPickerRows').innerHTML=items.length?items.slice(0,80).map(p=>`<button class="row" style="width:100%;border:0;background:transparent;text-align:left" onclick="togglePlugin('${p.id}')">${pluginIcon(p)}<span class="rowmain"><span class="rowtitle">${esc(p.name)}</span><span class="rowdesc">${p.connected?(p.connection_label||'Akun terhubung'):'Tanpa login'} · ${selectedPlugins.includes(p.id)?'dipakai di chat':'siap digunakan'}</span></span><span class="badge ${selectedPlugins.includes(p.id)?'ok':''}">${selectedPlugins.includes(p.id)?'Dipilih':'Pilih'}</span></button>`).join(''):'<div class="empty">Belum ada plugin yang siap. Buka Kelola plugin.</div>'}'''
    html = replace_js_function(html, "renderPluginPicker", "togglePlugin", picker)

    html_path.write_text(html, encoding="utf-8")

    gradle_text = gradle.read_text(encoding="utf-8")
    gradle_text = replace_once(gradle_text, "versionCode 10031", "versionCode 10032", "versionCode")
    gradle_text = replace_once(gradle_text, "versionName '1.0.0-rc31'", "versionName '1.0.0-rc32'", "versionName")
    gradle.write_text(gradle_text, encoding="utf-8")

    checks = {
        html_path: (
            "RC32: simple, contract-driven Plugin UI",
            'id="pluginConnectLayer"',
            "function pluginAuthText(",
            "p.no_auth)return'Tanpa login'",
            "p.ready&&",
            "mode:'auto'",
            "result.flow==='oauth_browser'",
            "pluginCredentialInput",
            "Menampilkan layanan utama",
        ),
        gradle: ("versionCode 10032", "versionName '1.0.0-rc32'"),
    }
    for path, markers in checks.items():
        text = path.read_text(encoding="utf-8")
        missing = [marker for marker in markers if marker not in text]
        if missing:
            raise SystemExit(f"RC32 marker hilang di {path.name}: {missing}")
    if "p.connected?'Terhubung':'Hubungkan'" in html:
        raise SystemExit("RC32 legacy Plugin status masih tersisa")
    print("FURINAHUB_ANDROID_RC32_PLUGIN_UX_OK")


if __name__ == "__main__":
    main()
