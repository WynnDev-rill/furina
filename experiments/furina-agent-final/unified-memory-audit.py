#!/usr/bin/env python3
from __future__ import annotations
import ast, json, os, sys
from pathlib import Path

repo=Path(os.environ.get('GITHUB_WORKSPACE') or Path.cwd())
stage=Path(sys.argv[1] if len(sys.argv)>1 else '/tmp/furina-agent-rc54-validate/termux')
core=stage/'core/furina_agent'; app=stage/'bridge/app'; blockers=[]; warnings=[]
def fail(code,msg): blockers.append(f'{code}: {msg}')

for path in core.glob('*.py'):
    try: ast.parse(path.read_text(encoding='utf-8'),filename=str(path))
    except Exception as exc: fail('PY_PARSE',f'{path.name}: {exc}')

manifest=json.load(open(repo/'experiments/furina-agent-final/manifest.json',encoding='utf-8'))
expected={'version':'1.0.4','dependency_revision':'2026.08.24-r44','bundle_id':'furina-2026.08.24-private-1.0.4','bridge_version':'1.0.4','bridge_version_code':10062,'runtime_contract':'furina-runtime/v10-unified-memory-stream'}
for key,value in expected.items():
    if manifest.get(key)!=value: fail('MANIFEST',f'{key}={manifest.get(key)!r}, expected {value!r}')

chat=(core/'chat.py').read_text(); memory=(core/'memory.py').read_text(); hub=(core/'hub.py').read_text(); html=(app/'src/main/assets/furinahub/index.html').read_text(); web=(core/'hub_web.py').read_text(); build=(app/'build.gradle').read_text(); main=(app/'src/main/java/com/wynndev/furinaagentbridge/MainActivity.java').read_text()
for token in ('SHARED PERSONAL CONTEXT','def _relationship_context','def _consolidate','def _reflect','memory_worker_error'):
    if token not in chat: fail('CHAT',f'missing {token}')
for token in ('def relevant_beliefs','no unrelated importance fallback','Old inferred memories remain stored'):
    if token not in memory: fail('MEMORY',f'missing {token}')
for token in ('def start_chat(','/api/chat/start','partial','on_token=on_token'):
    if token not in hub: fail('HUB_STREAM',f'missing {token}')
start=html.find('async function sendMessage(forcedText)'); end=html.find('\nfunction thinkingArchiveKey()',start)
send=html[start:end] if start>=0 and end>start else ''
if not send: fail('HUB_UI','sendMessage missing')
for bad in ('refreshConversation()','renderBoot()'):
    if bad in send: fail('HUB_UI',f'live send still calls {bad}')
for token in ('/api/chat/start','state.partial','bubble.textContent=partial','FURINAHUB_STREAM_V3_NO_RERENDER'):
    if token not in html: fail('HUB_UI',f'missing {token}')
if web != 'HTML = '+repr(html)+'\n': fail('HUB_PARITY','loopback HTML differs from APK asset')
if 'versionCode 10062' not in build or "versionName '1.0.4'" not in build: fail('ANDROID','version boundary mismatch')
for token in ('EXPECTED_CORE_VERSION = "1.0.4"','EXPECTED_DEPENDENCY_REVISION = "2026.08.24-r44"','furina-2026.08.24-private-1.0.4'):
    if token not in main: fail('ANDROID',f'missing {token}')

models=manifest.get('local_model_catalog') or []
if [m.get('id') for m in models] != ['wifugpt-1.7b-q4km','qwen3-1.7b-heretic-q5km']: fail('MODEL','local catalog changed')
if manifest.get('routing_modes') != ['online','local']: fail('ROUTING','routing modes changed')

print(f'Python modules checked: {len(list(core.glob("*.py")))}')
print(f'Blockers: {len(blockers)}')
print(f'Warnings: {len(warnings)}')
for item in blockers: print('BLOCKER',item)
for item in warnings: print('WARNING',item)
if blockers: raise SystemExit(1)
print('FURINA_PRIVATE_1_0_4_AUDIT_OK')
