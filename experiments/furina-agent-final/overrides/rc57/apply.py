#!/usr/bin/env python3
from __future__ import annotations
import ast, os, re, sys
from pathlib import Path

TARGET_VERSION="1.0.0-rc57"
SUPPORTED={"1.0.0-rc56",TARGET_VERSION}

def read_version(p):
    m=re.search(r'VERSION\s*=\s*["\']([^"\']+)',p.read_text(encoding='utf-8')); return m.group(1) if m else ''

def node_for(text, cls, method):
    tree=ast.parse(text)
    for top in tree.body:
        if isinstance(top,ast.ClassDef) and top.name==cls:
            for item in top.body:
                if isinstance(item,(ast.FunctionDef,ast.AsyncFunctionDef)) and item.name==method:return item
    return None

def insert_before(text,line,block):
    lines=text.splitlines(keepends=True); lines.insert(line-1,block.rstrip()+"\n"); return ''.join(lines)

def insert_after(text,line,block):
    lines=text.splitlines(keepends=True); lines.insert(line,block.rstrip()+"\n"); return ''.join(lines)

def ensure_import(text,stmt):
    if stmt in text:return text
    lines=text.splitlines(keepends=True); at=0
    for i,line in enumerate(lines):
        s=line.strip()
        if s.startswith('from __future__ import') or s.startswith('import ') or s.startswith('from '): at=i+1; continue
        if not s: continue
        if at: break
    lines.insert(at,stmt+'\n'); return ''.join(lines)

def ensure_init(text):
    if 'self.upstream_bridge = UpstreamCompanionBridge(' in text:return text
    n=node_for(text,'FurinaChat','__init__')
    if not n: raise RuntimeError('FurinaChat.__init__ missing')
    lines=text.splitlines(keepends=True); target=None
    for i in range(n.lineno,n.end_lineno+1):
        if 'self.llm = llm' in lines[i-1]: target=i; break
    if not target: target=n.end_lineno
    return insert_after(text,target,'        self.upstream_bridge = UpstreamCompanionBridge(store, llm, getattr(cfg, "user_nickname", ""))')

def ensure_context(text):
    if 'UPSTREAM COMPANION LAYERS:' in text:return text
    n=node_for(text,'FurinaChat','_messages')
    if not n: raise RuntimeError('FurinaChat._messages missing')
    lines=text.splitlines(keepends=True); target=None
    for i in range(n.lineno,n.end_lineno+1):
        if 'messages = ' in lines[i-1] and 'system' in lines[i-1]: target=i; break
    if not target:
        for i in range(n.lineno,n.end_lineno+1):
            if lines[i-1].lstrip().startswith('return '): target=i; break
    if not target: raise RuntimeError('_messages output boundary missing')
    return insert_before(text,target,'        system += "\\n\\nUPSTREAM COMPANION LAYERS:\\n" + self.upstream_bridge.context()')

def ensure_after_turn(text):
    if 'self.upstream_bridge.after_turn(user_text, answer)' in text:return text
    n=node_for(text,'FurinaChat','respond')
    if not n: raise RuntimeError('FurinaChat.respond missing')
    lines=text.splitlines(keepends=True); target=None
    for i in range(n.lineno,n.end_lineno+1):
        if 'self.companion_state.after_turn(user_text, answer)' in lines[i-1]: target=i; break
    if not target:
        for i in range(n.lineno,n.end_lineno+1):
            if 'self.store.add_message("assistant", answer)' in lines[i-1] or "self.store.add_message('assistant', answer)" in lines[i-1]: target=i; break
    if not target: raise RuntimeError('respond after-turn boundary missing')
    return insert_after(text,target,'        self.upstream_bridge.after_turn(user_text, answer)')

def atomic(path,content):
    tmp=path.with_name(path.name+'.rc57.new')
    if isinstance(content,bytes):tmp.write_bytes(content)
    else:tmp.write_text(content,encoding='utf-8')
    os.chmod(tmp,0o600);os.replace(tmp,path)

def main():
    if len(sys.argv)!=2:raise SystemExit('usage: apply.py <termux-root>')
    root=Path(sys.argv[1]).resolve(); core=root/'core/furina_agent'; here=Path(__file__).resolve().parent
    chatp=core/'chat.py'; vp=core/'version.py'; personap=core/'persona.py'; bridgep=core/'upstream_bridge.py'; runtimep=core/'upstream_runtime'
    for p in (chatp,vp,here/'persona.py',here/'upstream_bridge.py',here/'soul_worker.py',here/'utsuwa_worker.mjs'):
        if not p.is_file():raise SystemExit(f'RC57 required source missing: {p}')
    current=read_version(vp)
    if current not in SUPPORTED:raise SystemExit(f'RC57 requires RC56 foundation, found {current or "unknown"}')
    chat=chatp.read_text(encoding='utf-8');ast.parse(chat)
    chat=ensure_import(chat,'from .upstream_bridge import UpstreamCompanionBridge')
    chat=ensure_init(chat);chat=ensure_context(chat);chat=ensure_after_turn(chat)
    persona=(here/'persona.py').read_text(encoding='utf-8');bridge=(here/'upstream_bridge.py').read_text(encoding='utf-8')
    version=vp.read_text(encoding='utf-8')
    version=re.sub(r'VERSION\s*=\s*(["\'])([^"\']+)\1',f'VERSION = "{TARGET_VERSION}"',version,count=1)
    for label,text in ((str(chatp),chat),(str(personap),persona),(str(bridgep),bridge),(str(vp),version)):compile(text,label,'exec')
    required=('UpstreamCompanionBridge','UPSTREAM COMPANION LAYERS:','self.upstream_bridge.after_turn(user_text, answer)','answer = naturalize(')
    missing=[x for x in required if x not in chat]
    if missing:raise SystemExit('RC57 chat integration incomplete: '+', '.join(missing))
    runtimep.mkdir(parents=True,exist_ok=True)
    atomic(personap,persona);atomic(bridgep,bridge)
    atomic(runtimep/'soul_worker.py',(here/'soul_worker.py').read_bytes())
    atomic(runtimep/'utsuwa_worker.mjs',(here/'utsuwa_worker.mjs').read_bytes())
    atomic(chatp,chat);atomic(vp,version)
    for p in (chatp,personap,bridgep,vp):compile(p.read_text(encoding='utf-8'),str(p),'exec')
    if read_version(vp)!=TARGET_VERSION:raise SystemExit('RC57 version commit failed')
    print('FURINA_RC57_UPSTREAM_COMPANION_PACK_OK')
if __name__=='__main__':main()
