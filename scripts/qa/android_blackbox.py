#!/usr/bin/env python3
"""Exercise the installed release APK through ADB/UIAutomator, without app internals."""
import argparse
import json
import re
import subprocess
import time
import xml.etree.ElementTree as ET
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--apk', required=True)
parser.add_argument('--output', required=True)
parser.add_argument('--candidate', action='store_true')
args = parser.parse_args()
out = Path(args.output)
out.mkdir(parents=True, exist_ok=True)
package = 'com.wynndev.furina'
checks = []

def adb(*items, check=True, binary=False, timeout=40):
    result = subprocess.run(['adb', *map(str, items)], capture_output=True, timeout=timeout)
    if check and result.returncode:
        raise RuntimeError(result.stderr.decode(errors='replace') + result.stdout.decode(errors='replace'))
    return result.stdout if binary else result.stdout.decode(errors='replace')

def shell(*items, **kwargs):
    return adb('shell', *items, **kwargs)

def hierarchy():
    # Dumping to an external path works for a non-debuggable release APK.
    shell('uiautomator', 'dump', '/sdcard/furina-qa.xml', check=False)
    raw = shell('cat', '/sdcard/furina-qa.xml')
    return raw, ET.fromstring(raw[raw.index('<?xml'):])

def capture(name):
    time.sleep(.7)
    (out / f'{name}.png').write_bytes(adb('exec-out', 'screencap', '-p', binary=True))
    raw, tree = hierarchy()
    (out / f'{name}.xml').write_text(raw)
    return tree

def click(label=None, klass=None, required=True):
    for attempt in range(3):
        _, tree = hierarchy()
        nodes = [n for n in tree.iter('node') if
                 (label is None or label in [n.get('text'), n.get('content-desc')]) and
                 (klass is None or n.get('class') == klass)]
        for node in reversed(nodes):
            if node.get('enabled') == 'false':
                continue
            bounds = list(map(int, re.findall(r'-?\d+', node.get('bounds', ''))))
            if len(bounds) == 4 and bounds[0] >= 0 and bounds[1] >= 0 and bounds[2] > bounds[0] and bounds[3] > bounds[1]:
                shell('input', 'tap', (bounds[0] + bounds[2]) // 2, (bounds[1] + bounds[3]) // 2)
                time.sleep(.6)
                return True
        time.sleep(.5)
    if required:
        raise AssertionError(f'Visible control missing: {label or klass}')
    return False

def scenario(name, action):
    try:
        action()
        checks.append({'name': name, 'passed': True})
    except Exception as error:
        checks.append({'name': name, 'passed': False, 'error': str(error)})
        capture(f'{name}-failure')

def launch():
    value = shell('am', 'start', '-W', '-n', f'{package}/.NativeHubActivity')
    time.sleep(4)
    return value

def restart():
    shell('am', 'force-stop', package)
    launch()

def draft_flow():
    if not args.candidate:
        click('Chat')
    click(klass='android.widget.EditText')
    shell('input', 'text', 'Draft%suji%sFurinaHub')
    capture('02-keyboard-draft')
    shell('input', 'keyevent', 4)
    time.sleep(1)
    restart()
    tree = capture('03-restart-draft')
    assert any('Draft uji FurinaHub' in n.get('text', '') for n in tree.iter('node')), 'Draft lost after process restart'

def navigation_flow():
    for index, label in enumerate(['Persona', 'Memori', 'Setelan']):
        if args.candidate and label != 'Setelan':
            click('Setelan')
        click(label)
        capture(f'10-{index}-{label}-top')
        for count in range(3):
            shell('input', 'swipe', 360, 1220, 360, 420, 350)
            capture(f'11-{index}-{label}-scroll-{count}')
        shell('input', 'keyevent', 4)
        if args.candidate and label != 'Setelan':
            shell('input', 'keyevent', 4)
    if not args.candidate:
        click('Chat')
    click('Riwayat percakapan')
    capture('15-history')
    shell('input', 'keyevent', 4)

def accessibility_flow():
    shell('cmd', 'uimode', 'night', 'yes')
    capture('20-dark-chat')
    shell('settings', 'put', 'system', 'font_scale', '2.0')
    capture('21-large-text-chat')
    click('Setelan')
    capture('22-large-text-settings')
    shell('settings', 'put', 'system', 'font_scale', '1.0')
    shell('settings', 'put', 'system', 'accelerometer_rotation', '0')
    shell('settings', 'put', 'system', 'user_rotation', '1')
    capture('23-landscape-settings')
    shell('settings', 'put', 'system', 'user_rotation', '0')
    shell('cmd', 'uimode', 'night', 'no')


def wait_text(text, present=True, attempts=12):
    for _ in range(attempts):
        _, tree = hierarchy()
        found = any(text in (n.get('text', '') + n.get('content-desc', '')) for n in tree.iter('node'))
        if found == present:
            return
        time.sleep(.5)
    raise AssertionError(f'UI text {text!r}, expected present={present}')

def fill_field(value, index=0):
    _, tree = hierarchy()
    nodes = [n for n in tree.iter('node') if n.get('class') == 'android.widget.EditText']
    nodes = [n for n in nodes if not n.get('bounds', '').startswith('[-')]
    node = nodes[index]
    x1, y1, x2, y2 = map(int, re.findall(r'\d+', node.get('bounds')))
    shell('input', 'tap', (x1+x2)//2, (y1+y2)//2)
    shell('input', 'keycombination', 113, 29)
    shell('input', 'keyevent', 67)
    shell('input', 'text', value.replace(' ', '%s'))

def chat_transport_flow():
    from fixture_provider import ProviderFixture
    fixture = ProviderFixture()
    fixture.start()
    adb('reverse', 'tcp:8765', 'tcp:8765')
    try:
        restart()
        click('Setelan')
        click('Model')
        click('Online')
        click('Atur Endpoint sendiri')
        fill_field('http://127.0.0.1:8765/v1', 0)
        fill_field('qa-model', 1)
        shell('input', 'keyevent', 4)
        capture('40-endpoint-form')
        click('Simpan & tes')
        wait_text('Siap')
        shell('input', 'keyevent', 4)
        shell('input', 'keyevent', 4)

        # Add a memory through the same controls used by a person.
        click('Setelan')
        click('Memori')
        click('Tambah memori')
        fill_field('Kode proyek adalah zefir')
        shell('input', 'keyevent', 4)
        click('Simpan')
        wait_text('Kode proyek adalah zefir')
        capture('41-memory-saved')
        shell('input', 'keyevent', 4)
        shell('input', 'keyevent', 4)
        click('Percakapan baru')

        def send_message(value):
            fill_field(value)
            click('Kirim')

        send_message('QA_CHAT zefir')
        wait_text('Jawaban uji')
        wait_text('Hentikan', present=False)
        capture('42-chat-reply')
        request = next(r for r in fixture.requests if 'QA_CHAT' in r['messages'][-1]['content'])
        system = ' '.join(m['content'] for m in request['messages'] if m['role'] == 'system')
        assert 'zefir' in system.lower(), 'Saved memory missing from provider context'
        assert 'Furina' in system, 'Persona missing from provider context'

        send_message('QA_STOP')
        time.sleep(2)
        click('Hentikan')
        wait_text('Hentikan', present=False)
        restart()
        wait_text('Potongan')
        capture('43-stopped-reply-after-restart')

        send_message('QA_RECOVER')
        time.sleep(3)
        restart()
        wait_text('Pulih')
        wait_text('Hentikan', present=False)
        capture('44-process-recovery')

        send_message('QA_RATE')
        wait_text('QA_RATE')
        wait_text('Hentikan', present=False)
        capture('45-rate-limit-draft')
        _, tree = hierarchy()
        assert any(n.get('class') == 'android.widget.EditText' and 'QA_RATE' in n.get('text', '') for n in tree.iter('node')), 'Failed request did not restore draft'
        assert sum('QA_RATE' in r['messages'][-1]['content'] for r in fixture.requests) == 1, 'Custom endpoint retried without permission'
        (out / 'provider-assertions.json').write_text(json.dumps({'memory_retrieved': True, 'persona_applied': True, 'no_silent_retry': True}, indent=2))
    finally:
        (out / 'provider-requests.json').write_text(json.dumps(fixture.requests, indent=2, ensure_ascii=False))
        fixture.close()
        adb('reverse', '--remove', 'tcp:8765', check=False)


try:
    (out / 'device.txt').write_text(shell('getprop'))
    adb('install', '-r', args.apk, timeout=120)
    shell('wm', 'size', '720x1600')
    shell('wm', 'density', '320')
    shell('settings', 'put', 'global', 'window_animation_scale', '1')
    shell('settings', 'put', 'global', 'transition_animation_scale', '1')
    shell('settings', 'put', 'global', 'animator_duration_scale', '1')
    shell('input', 'keyevent', 82)
    adb('logcat', '-c')
    (out / 'cold-start.txt').write_text(launch())
    click('Izinkan', required=False)
    click('Allow', required=False)
    tree = capture('01-launch')
    if args.candidate:
        assert any('Draft uji FurinaHub' in n.get('text', '') for n in tree.iter('node')), 'Upgrade lost baseline draft'
    scenario('draft-restart', draft_flow)
    scenario('navigation', navigation_flow)
    if args.candidate:
        def pages():
            for label in ['Model', 'Tampilan chat', 'Termux', 'Data & aplikasi']:
                click('Setelan')
                click(label)
                capture('30-' + label.replace(' ', '-'))
                shell('input', 'swipe', 360, 1220, 360, 420, 350)
                capture('31-' + label.replace(' ', '-'))
                shell('input', 'keyevent', 4)
                shell('input', 'keyevent', 4)
        scenario('settings-pages', pages)
    if args.candidate:
        scenario('chat-http-memory-stop-recovery', chat_transport_flow)
        restart()
    scenario('accessibility', accessibility_flow)
finally:
    (out / 'logcat.txt').write_text(adb('logcat', '-d', '-v', 'threadtime', check=False))
    (out / 'memory.txt').write_text(shell('dumpsys', 'meminfo', package, check=False))
    (out / 'frames.txt').write_text(shell('dumpsys', 'gfxinfo', package, 'framestats', check=False))
    (out / 'checks.json').write_text(json.dumps(checks, indent=2))
    print(json.dumps(checks, indent=2))
    shell('settings', 'put', 'system', 'font_scale', '1.0', check=False)
    shell('settings', 'put', 'system', 'user_rotation', '0', check=False)

if not checks or any(not c['passed'] for c in checks):
    raise SystemExit(1)
