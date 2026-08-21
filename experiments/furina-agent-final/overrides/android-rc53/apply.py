#!/usr/bin/env python3
"""RC53: FurinaHub Full surfaces the few decisions that benefit from touch UI."""
from pathlib import Path
import sys

OLD_BUNDLE = 'furina-2026.08.21-rc64-rc52'
NEW_BUNDLE = 'furina-2026.08.22-rc65-rc53'


def once(text, old, new, label):
    if old not in text:
        if new in text:
            return text
        raise SystemExit(f'RC53 marker missing: {label}')
    return text.replace(old, new, 1)


def main():
    if len(sys.argv) != 2:
        raise SystemExit('usage: apply.py <furina-root>')
    root = Path(sys.argv[1]).resolve(); app = root/'bridge/app'; java = app/'src/main/java/com/wynndev/furinaagentbridge'; html = app/'src/main/assets/furinahub/index.html'
    gradle = app/'build.gradle'; main = java/'MainActivity.java'; runtime = java/'BridgeRuntime.java'
    for path in (gradle, main, runtime, html):
        if not path.is_file():
            raise SystemExit(f'RC53 source missing: {path}')
    g = once(gradle.read_text(), 'versionCode 10052', 'versionCode 10053', 'version code')
    g = once(g, "versionName '1.0.0-rc52'", "versionName '1.0.0-rc53'", 'version name')
    m = main.read_text().replace(OLD_BUNDLE, NEW_BUNDLE)
    m = once(m, 'EXPECTED_CORE_VERSION = "1.0.0-rc64"', 'EXPECTED_CORE_VERSION = "1.0.0-rc65"', 'core target')
    r = runtime.read_text().replace(OLD_BUNDLE, NEW_BUNDLE)
    page = html.read_text(encoding='utf-8')

    today = '''<section id="today" class="view"><div class="sectionhead"><h1>Hari ini</h1><div class="sub">Yang perlu kamu lihat sekarang—bukan dashboard yang penuh angka.</div></div><div id="todayOffline" class="card"></div><div id="todayOnline" class="hidden"><div class="card"><h3>Berikutnya</h3><div id="todayFocus"></div></div><div class="card"><h3>Ruang kerja Furina</h3><div id="todaySignals"></div></div><div class="actions"><button class="btn primary" onclick="go('chat')">Lanjut chat</button><button class="btn" onclick="go('focus')">Kelola fokus</button></div></div></section>'''
    page = once(page, '<section id="focus" class="view">', today + '<section id="focus" class="view">', 'Today section')
    nav = '<button class="nav" data-view="today" onclick="go(\'today\')"><svg viewBox="0 0 24 24"><path d="M4 12h16M12 4v16"/><path d="M5 5l14 14M19 5L5 19"/></svg>Hari ini</button>'
    page = once(page, '<button class="nav" data-view="focus"', nav + '<button class="nav" data-view="focus"', 'Today navigation')
    page = once(page, "if(id==='memory')loadMemory();if(id==='focus')loadFocus();", "if(id==='memory')loadMemory();if(id==='today')loadToday();if(id==='focus')loadFocus();", 'Today loader')

    menu_old = "<button onclick=\"copySelected()\">Salin teks</button>${selectedMessage.role==='user'&&canBranch?'<button onclick=\"editSelected()\">Edit & kirim ulang dari sini</button>':''}${selectedMessage.role==='assistant'&&canBranch?'<button onclick=\"regenerateSelected()\">Buat ulang jawaban</button>':''}${canBranch?'<button style=\"color:var(--danger)\" onclick=\"deleteSelectedBranch()\">Hapus dari pesan ini</button>':''}<button onclick=\"closeSheets()\">Batal</button>"
    menu_new = "<button onclick=\"copySelected()\">Salin teks</button>${selectedMessage.text?.trim()?'<button onclick=\"captureSelected(\\'memory\\')\">Usulkan sebagai memori</button><button onclick=\"captureSelected(\\'focus\\')\">Jadikan Fokus</button>':''}${selectedMessage.role==='user'&&canBranch?'<button onclick=\"editSelected()\">Edit & kirim ulang dari sini</button>':''}${selectedMessage.role==='assistant'&&canBranch?'<button onclick=\"regenerateSelected()\">Buat ulang jawaban</button>':''}${canBranch?'<button style=\"color:var(--danger)\" onclick=\"deleteSelectedBranch()\">Hapus dari pesan ini</button>':''}<button onclick=\"closeSheets()\">Batal</button>"
    page = once(page, menu_old, menu_new, 'conversation capture menu')

    extra = r'''
async function loadToday(){try{const d=await core('GET','/api/workspace/brief');renderToday(d)}catch(e){toast(e.message)}}
function renderToday(data){const online=document.getElementById('todayOnline'),offline=document.getElementById('todayOffline');if(!connection.connected){online.classList.add('hidden');offline.innerHTML=iconOffline('Hari ini membutuhkan Core','Hubungkan Furina Lite di Termux untuk melihat ruang kerja yang sama.');return}offline.innerHTML='';online.classList.remove('hidden');const item=data?.next_focus;document.getElementById('todayFocus').innerHTML=item?`<div class="row"><div class="rowmain"><div class="rowtitle">${esc(item.text)}</div><div class="rowdesc">${Number(item.due_at||0)?esc(new Date(Number(item.due_at)*1000).toLocaleString('id-ID',{dateStyle:'medium',timeStyle:'short'})):'Tanpa waktu'}</div></div><button class="btn" onclick="go('focus')">Buka</button></div>`:'<div class="empty">Tidak ada Fokus aktif. Jangan membuat daftar baru bila belum ada hal yang perlu ditindaklanjuti.</div>';const profile=(data?.profile?.profiles||[]).find(x=>x.id===data?.profile?.current);document.getElementById('todaySignals').innerHTML=`<div class="row"><div class="rowmain"><div class="rowtitle">${Number(data?.memory_inbox_count||0)} memori menunggu tinjauan</div><div class="rowdesc">Tidak ada memori baru yang dipakai sebelum kamu menerimanya.</div></div><button class="btn" onclick="go('memory')">Tinjau</button></div><div class="row"><div class="rowmain"><div class="rowtitle">Profil respons: ${esc(profile?.label||'Natural')}</div><div class="rowdesc">Sama untuk FurinaHub dan Furina Lite.</div></div><button class="btn" onclick="go('personalization')">Ubah</button></div>`}
async function captureSelected(action){const message=selectedMessage;closeSheets();if(!message?.text?.trim())return;const isMemory=action==='memory';const text=await askText(isMemory?'Usulkan sebagai memori':'Jadikan Fokus',isMemory?'Edit bila perlu. Usulan harus kamu terima di Kotak Masuk Memori.':'Edit bila perlu, lalu tentukan waktu opsional.',{value:message.text,multiline:true});if(!text?.trim())return;let when='';if(!isMemory){when=await askText('Waktu (opsional)','Contoh: besok sore');if(when===null)return}try{await core('POST','/api/capture',{action,text:text.trim(),when:(when||'').trim(),source_ref:`pesan:${message.id||'baru'}`});if(isMemory){await loadMemory();await loadWorkspaceExtras();toast('Usulan masuk ke Kotak Masuk Memori.')}else{toast('Fokus disimpan.');if(document.getElementById('focus').classList.contains('active'))await loadFocus()}if(document.getElementById('today').classList.contains('active'))await loadToday()}catch(e){toast(e.message)}}
'''
    if 'async function loadToday()' not in page:
        pos = page.rfind('</script>')
        if pos < 0:
            raise SystemExit('RC53 marker missing: script close')
        page = page[:pos] + extra + page[pos:]
    gradle.write_text(g); main.write_text(m); runtime.write_text(r); html.write_text(page, encoding='utf-8')
    combined = '\n'.join((g, m, r, page))
    for marker in ('versionCode 10053', "versionName '1.0.0-rc53'", NEW_BUNDLE, 'EXPECTED_CORE_VERSION = "1.0.0-rc65"', 'id="today"', 'async function loadToday()', 'captureSelected', 'Usulkan sebagai memori'):
        if marker not in combined:
            raise SystemExit(f'RC53 integration incomplete: {marker}')
    print('FURINAHUB_ANDROID_RC53_TODAY_CAPTURE_OK')


if __name__ == '__main__':
    main()
