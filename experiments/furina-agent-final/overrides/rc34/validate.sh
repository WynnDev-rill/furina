#!/usr/bin/env bash
set -euo pipefail

REPO="$(git rev-parse --show-toplevel)"
META="$REPO/experiments/furina-agent-final"
RC33="$META/overrides/rc33"
RC34="$META/overrides/rc34"
ARCHIVE=/tmp/furina-agent-rc34-source.tar.gz
WORK=/tmp/furina-agent-rc34-validate
ROOT="$WORK/termux"

rm -rf "$WORK" "$ARCHIVE"
mkdir -p "$WORK"
: > "$ARCHIVE"
for chunk in "$META"/source-*.b64; do
  base64 --decode "$chunk" >> "$ARCHIVE"
done

EXPECTED_SOURCE_SHA="$(python3 - "$META/manifest.json" <<'PY'
import json,sys
print(json.load(open(sys.argv[1],encoding='utf-8'))['source_sha256'])
PY
)"
echo "$EXPECTED_SOURCE_SHA  $ARCHIVE" | sha256sum -c -
test "$(python3 -c 'import json;print(json.load(open("'"$META"'/manifest.json"))["version"])')" = "1.0.0-rc34"
test "$(python3 -c 'import json;print(json.load(open("'"$META"'/manifest.json"))["bridge_version"])')" = "1.0.0-rc18"

tar -xzf "$ARCHIVE" -C "$WORK"
patch -p0 -d "$WORK" < "$META/patches/api30-inputstream.patch"
patch -p0 -d "$WORK" < "$META/patches/runtime-online-agent.patch"
python3 "$META/overrides/apply-bridge-primitives-rc5.py" "$ROOT"

python3 - "$META/overrides" "$ROOT" <<'PY'
import hashlib,json,pathlib,sys
src=pathlib.Path(sys.argv[1]).resolve(); dst=pathlib.Path(sys.argv[2]).resolve()
manifest=json.loads((src/'manifest.json').read_text(encoding='utf-8'))
def blob(data: bytes) -> str:
    return hashlib.sha1(f'blob {len(data)}\0'.encode()+data).hexdigest()
for item in manifest['files']:
    data=(src/item['path']).read_bytes()
    assert blob(data)==item['git_blob_sha'], item['path']
    target=(dst/item['target']).resolve()
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_bytes(data)
PY

TRANSFORMS=(
  apply-bridge-rc4.py
  apply-universal-agent-rc5.py
  apply-core-rc6.py
  apply-core-rc6-postfix.py
  apply-bridge-rc6.py
  apply-core-rc7.py
  apply-bridge-rc7.py
  apply-core-rc8.py
  apply-core-rc8-postfix.py
  apply-core-rc9.py
  apply-ui-rc10.py
  apply-ui-rc10-hotfix.py
  apply-core-rc11.py
  apply-ui-rc12.py
  apply-ui-rc12-postfix.py
  apply-core-rc13.py
  apply-bridge-rc8.py
  apply-core-rc14.py
  apply-core-rc15.py
  apply-core-rc16.py
  apply-core-rc17-hotfix.py
  apply-bridge-rc9.py
  apply-core-rc18.py
  apply-ui-performance-bridge-rc10.py
  apply-ui-performance-rc19.py
  apply-reactive-bridge-rc11.py
  apply-reactive-core-rc20.py
  apply-reactive-bridge-rc12.py
  apply-reactive-core-rc21.py
  apply-bridge-rc13.py
  apply-system-rc22.py
  apply-safety-rc22.py
  apply-semantic-core-rc23.py
  apply-semantic-guard-rc23.py
  apply-lifecycle-core-rc24.py
  apply-bridge-rc14.py
  apply-stateful-core-rc25.py
  apply-stateful-core-rc25-postfix.py
  apply-stateful-bridge-rc15.py
  apply-stateful-bridge-rc15-postfix.py
  apply-semantic-resilience-rc26.py
  apply-runtime-recovery-rc27.py
  apply-runtime-core-rc28.py
  apply-universal-ui-core-rc29.py
  apply-universal-ui-bridge-rc16.py
  apply-privileged-core-rc30.py
  apply-privileged-bridge-rc17.py
)
for transform in "${TRANSFORMS[@]}"; do
  python3 "$META/overrides/$transform" "$ROOT"
done
python3 "$META/overrides/apply-device-control-core-rc31.py" "$ROOT"
python3 "$META/overrides/apply-device-control-bridge-rc18.py" "$ROOT"
python3 "$META/overrides/apply-policy-boundary-core-rc32.py" "$ROOT"
python3 "$RC33/apply.py" "$ROOT" "$RC33"
python3 "$RC34/apply.py" "$ROOT"
python3 -m compileall -q "$ROOT/core/furina_agent"

PYTHONPATH="$ROOT/core" python3 - <<'PY'
import json,tempfile
from pathlib import Path

from furina_agent.intent_guard import conversation_frame,strong_device_request,committed_device_intent
from furina_agent.policy import build_goal_lock,classify_action
from furina_agent.providers import ProviderState
from furina_agent.psyche import PsycheEngine,STATE_KEY
from furina_agent.routing import RoutingLLM
from furina_agent.tool_runtime import AgentToolRuntime
from furina_agent.version import VERSION

assert VERSION == '1.0.0-rc34'
assert STATE_KEY == 'furina_psyche_v1'

# RC33 continuity must survive RC34.
class Store:
    def __init__(self): self.state={}
    def get_state(self,k,d=None): return self.state.get(k,d)
    def set_state(self,k,v): self.state[k]=v
    def relationship_state(self): return {'trust':0.4,'closeness':0.3,'friction':0.05,'playfulness':0.3}
p=PsycheEngine(Store())
before=dict(p.state['long']['traits'])
p.observe_user('jawabanmu salah lagi')
assert p.state['short']['valence'] < 0
assert p.state['long']['traits'] == before

# Clear chat frames must never route to Agent merely because an app is named.
chat_cases=(
    'WhatsApp sekarang sering lambat menurutmu kenapa?',
    'Tadi aku buka WhatsApp lalu chat Ariel',
    'Kalau aku bilang buka WhatsApp, kamu bakal apa?',
    'Jangan buka WhatsApp',
    'ketik itu artinya apa?',
    'Kenapa kalau buka YouTube kadang lama?',
)
for text in chat_cases:
    assert conversation_frame(text), text
    assert not strong_device_request(text), text

# Actual requests remain device-shaped.
for text in ('Bisa buka WhatsApp?','Tolong bukain WhatsApp','Buka WhatsApp lalu cari Ariel'):
    assert not conversation_frame(text), text
    assert strong_device_request(text), text

assert committed_device_intent(
    'Bisa buka WhatsApp?',
    {'speech_act':'request','explicit_device_action':True,'action_span':'buka WhatsApp'},
    [{'type':'open_app','package':'com.whatsapp'}],0.91,
)
assert not committed_device_intent(
    'WhatsApp lagi lambat',
    {'speech_act':'request','explicit_device_action':True,'action_span':'WhatsApp'},
    [{'type':'open_app','package':'com.whatsapp'}],0.99,
)
assert not committed_device_intent(
    'Kalau aku bilang buka WhatsApp, kamu bakal apa?',
    {'speech_act':'request','explicit_device_action':True,'action_span':'buka WhatsApp'},
    [{'type':'open_app','package':'com.whatsapp'}],0.99,
)

# Exercise CompanionSession.classify with fake parser output and fake app inventory.
import furina_agent.companion as companion
class FakeStore:
    def __init__(self): self.events=[]
    def log_event(self,*args): self.events.append(args)
class FakeBridge:
    def apps(self): return {'apps':[{'label':'WhatsApp','package':'com.whatsapp'},{'label':'YouTube','package':'com.google.android.youtube'}]}
    def ensure_paired(self): return False
class FakeLLM:
    def __init__(self,obj=None,fail=False): self.obj=obj; self.fail=fail
    def chat(self,*args,**kwargs):
        if self.fail: raise RuntimeError('offline')
        return json.dumps(self.obj)

def make_session(obj=None,fail=False):
    s=companion.CompanionSession.__new__(companion.CompanionSession)
    s.store=FakeStore(); s.bridge=FakeBridge(); s.llm=FakeLLM(obj,fail)
    return s

# Even malicious/incorrect parser device output is rejected for discussion text before LLM is consulted.
s=make_session({'mode':'device','speech_act':'request','explicit_device_action':True,'action_span':'buka WhatsApp','confidence':0.99,'steps':[{'type':'open_app','app':'WhatsApp','package':'com.whatsapp'}]})
assert s.classify('Kalau aku bilang buka WhatsApp, kamu bakal apa?').mode == 'chat'

# App mention + parser failure is chat, not the old RC26/27 fail-open.
s=make_session(fail=True)
assert s.classify('WhatsApp lagi error dari tadi').mode == 'chat'

# Explicit request remains device.
s=make_session({'mode':'device','speech_act':'request','explicit_device_action':True,'action_span':'buka WhatsApp','confidence':0.95,'steps':[{'type':'open_app','app':'WhatsApp','package':'com.whatsapp'}]})
intent=s.classify('Bisa buka WhatsApp?')
assert intent.mode == 'device' and intent.steps and intent.steps[0].get('package') == 'com.whatsapp'

companion_src=open(companion.__file__,encoding='utf-8').read()
assert 'semantic_intent_device_fallback' not in companion_src
assert 'semantic_device_rejected' in companion_src
assert 'semantic_intent_error_chat_fallback' in companion_src
assert 'role="intent"' in companion_src

import furina_agent.direct_control as direct
assert 'direct_control_chat_guard' in open(direct.__file__,encoding='utf-8').read()

# Role history remains isolated.
assert RoutingLLM._infer_role([{'role':'system','content':'Kamu Experience Integrator internal'}],True) == 'memory'
with tempfile.TemporaryDirectory() as td:
    state=ProviderState(Path(td)/'provider.json')
    state.mark_success('groq','chat-model','conversation')
    state.mark_success('groq','json-model','memory')
    assert state.last_good('groq','conversation') == 'chat-model'
    assert state.last_good('groq','memory') == 'json-model'

# RC32 still gates actual actions after routing.
apps=[{'label':'WhatsApp','package':'com.whatsapp'},{'label':'Notes','package':'com.notes'}]
lock=build_goal_lock('buka WhatsApp cari Ariel',apps,[{'type':'open_app','package':'com.whatsapp'}])
assert classify_action({'package':'com.whatsapp','nodes':[{'id':7,'text':'Send'}]},{'type':'tap_node','node':7},lock)[0] == 'blocked'
runtime=AgentToolRuntime.__new__(AgentToolRuntime); runtime._handlers={}
try: runtime._handler_for('arbitrary_shell')
except ValueError: pass
else: raise AssertionError('unknown capability failed open')

print('RC34_CHAT_INTENT_GUARD_AND_RC32_POLICY_OK')
PY

grep -q 'versionCode 10018' "$ROOT/bridge/app/build.gradle"
grep -q "versionName '1.0.0-rc18'" "$ROOT/bridge/app/build.gradle"

python3 -m py_compile "$RC34/apply.py"
bash -n "$META/install.sh"
ACTUAL_APPLY="$(git -C "$REPO" hash-object "$RC34/apply.py")"
EXPECTED_APPLY="$(sed -n 's/^RC34_APPLY_BLOB="\([0-9a-f]*\)"$/\1/p' "$META/install.sh")"
[[ "$ACTUAL_APPLY" == "$EXPECTED_APPLY" ]]
grep -q 'VERSION="1.0.0-rc34"' "$META/install.sh"
grep -q 'PREV_COMMIT="5b6b3685e8b0e82eb6d92af7b187340420d041b7"' "$META/install.sh"
grep -q 'Menguji chat vs perintah Agent + RC32 policy' "$META/install.sh"
grep -q 'Nama aplikasi sekarang hanya konteks, bukan izin menjalankan Agent' "$META/install.sh"

echo 'RC34_FULL_VALIDATION_OK'
