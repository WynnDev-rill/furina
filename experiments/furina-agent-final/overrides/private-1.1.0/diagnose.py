#!/usr/bin/env python3
from __future__ import annotations
import ast, re, sys
from pathlib import Path

root=Path(sys.argv[1] if len(sys.argv)>1 else '/tmp/furina-agent-rc54-validate/termux')
core=root/'core/furina_agent'; app=root/'bridge/app'; html=app/'src/main/assets/furinahub/index.html'; main=app/'src/main/java/com/wynndev/furinaagentbridge/MainActivity.java'

print('=== FILES ===')
for p in sorted(core.glob('*.py')):
    print(p.name)

for name in ('config.py','persona.py','chat.py','tui.py','hub.py','hub_web.py','local_models.py','routing.py','memory.py','companion.py'):
    p=core/name
    if not p.exists(): continue
    text=p.read_text(encoding='utf-8',errors='replace')
    print(f'\n=== {name} METHODS/FUNCTIONS ===')
    try:
        tree=ast.parse(text)
        for node in tree.body:
            if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):
                print('fn',node.name)
            elif isinstance(node,ast.ClassDef):
                print('class',node.name,':',','.join(n.name for n in node.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))))
    except Exception as e: print('PARSE',e)
    pats=('persona','personal','trait','sifat','nickname','model','routing','task','worker','update','conversation','async','job','profile')
    lines=text.splitlines()
    hits=[]
    for i,line in enumerate(lines,1):
        if any(x in line.casefold() for x in pats): hits.append((i,line[:260]))
    print(f'=== {name} HITS ({len(hits)}) ===')
    for i,line in hits[:180]: print(f'{i}: {line}')

if html.exists():
    text=html.read_text(encoding='utf-8',errors='replace')
    print('\n=== HUB HTML HITS ===')
    pats=('personal','sifat','persona','model','local','update','pembaruan','task','job','conversation','sendmessage','poll','stream')
    lines=text.splitlines()
    for i,line in enumerate(lines,1):
        if any(x in line.casefold() for x in pats): print(f'{i}: {line[:600]}')
if main.exists():
    text=main.read_text(encoding='utf-8',errors='replace')
    print('\n=== MAIN ACTIVITY HITS ===')
    for i,line in enumerate(text.splitlines(),1):
        if any(x in line.casefold() for x in ('update','task','notification','hub','local','model')): print(f'{i}: {line[:500]}')
