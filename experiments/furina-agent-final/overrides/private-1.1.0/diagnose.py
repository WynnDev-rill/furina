#!/usr/bin/env python3
from __future__ import annotations
import ast, sys
from pathlib import Path

root=Path(sys.argv[1] if len(sys.argv)>1 else '/tmp/furina-agent-rc54-validate/termux')
core=root/'core/furina_agent'; app=root/'bridge/app'; html=app/'src/main/assets/furinahub/index.html'; main=app/'src/main/java/com/wynndev/furinaagentbridge/MainActivity.java'

def source(path: Path, class_name: str|None, method: str) -> str:
    text=path.read_text(encoding='utf-8',errors='replace'); tree=ast.parse(text)
    body=tree.body
    if class_name:
        cls=next(n for n in body if isinstance(n,ast.ClassDef) and n.name==class_name); body=cls.body
    node=next(n for n in body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name==method)
    return ast.get_source_segment(text,node) or ''

print('=== HUB SETTINGS FULL ===')
p=core/'hub_settings.py'
print(p.read_text(encoding='utf-8',errors='replace') if p.exists() else 'MISSING')

for method in ('public_settings','save_settings','_queue_auto_title','change_model','chat','start_chat','public_job','bootstrap','start_core_update','get_update_status'):
    print(f'\n=== HUB Runtime.{method} ===')
    try: print(source(core/'hub.py','Runtime',method))
    except Exception as e: print('ERR',e)

for method in ('_messages','respond','_background_worker_loop'):
    print(f'\n=== CHAT FurinaChat.{method} ===')
    try: print(source(core/'chat.py','FurinaChat',method))
    except Exception as e: print('ERR',e)

for method in ('_settings','run_tui','_private_identity'):
    print(f'\n=== TUI {method} ===')
    try: print(source(core/'tui.py',None,method))
    except Exception as e: print('ERR',e)

if html.exists():
    text=html.read_text(encoding='utf-8',errors='replace')
    def segment(a,b):
        i=text.find(a); j=text.find(b,i+len(a)) if i>=0 else -1
        print(text[i:j if j>=0 else i+12000] if i>=0 else 'MISSING')
    print('\n=== HUB PERSONALIZATION HTML ==='); segment('<section id="personalization"','<section id="settings"')
    print('\n=== HUB SETTINGS HTML ==='); segment('<section id="settings"','</main>')
    print('\n=== HUB JS MODELS/PERSONALIZATION ==='); segment('function modelRow','function renderAgent')
    print('\n=== HUB JS UPDATE/INIT ==='); segment('let unifiedCoreUpdate','function renderFocus')

if main.exists():
    text=main.read_text(encoding='utf-8',errors='replace')
    for token in ('private BridgeUpdater','private void startCoreRecoveryUpdate','private void monitorAppUpdate','@JavascriptInterface public void checkAppUpdate'):
        print(f'\n=== MAIN {token} ===')
        i=text.find(token); print(text[i:i+7000] if i>=0 else 'MISSING')
