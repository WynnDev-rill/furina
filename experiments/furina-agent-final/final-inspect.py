#!/usr/bin/env python3
from __future__ import annotations
import ast,re,sys
from pathlib import Path

root=Path(sys.argv[1] if len(sys.argv)>1 else '/tmp/furina-agent-rc54-validate/termux')
core=root/'core/furina_agent'; html=root/'bridge/app/src/main/assets/furinahub/index.html'

def show_context(text:str, needle:str, radius:int=260):
    print(f'--- CONTEXT {needle!r} ---')
    start=0; found=False
    while True:
        i=text.find(needle,start)
        if i<0: break
        found=True
        print(text[max(0,i-radius):min(len(text),i+len(needle)+radius)].replace('\n','\\n'))
        start=i+len(needle)
    if not found: print('(none)')

def show_function(path:Path,name:str):
    text=path.read_text(encoding='utf-8',errors='replace'); tree=ast.parse(text)
    for node in ast.walk(tree):
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name==name:
            lines=text.splitlines(); print(f'--- {path.name}:{name} ---'); print('\n'.join(lines[node.lineno-1:node.end_lineno])); return
    print(f'--- {path.name}:{name} missing ---')

page=html.read_text(encoding='utf-8',errors='replace')
for needle in ('Core aktif','data-view="relationship"','id="relationship"'):
    show_context(page,needle)
for name in ('_header','run_tui','_lite_update_recovery'):
    show_function(core/'tui.py',name)
for name in ('__init__','_schedule_background','_background_worker_loop','_background'):
    show_function(core/'chat.py',name)
