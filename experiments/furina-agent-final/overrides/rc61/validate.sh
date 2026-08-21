#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
BASE=/tmp/furina-agent-rc48-validate/termux
STAGE=/tmp/furina-agent-rc61-validate/termux

bash "$ROOT/overrides/android-rc48/validate.sh"
rm -rf "$STAGE"
mkdir -p "$(dirname "$STAGE")"
cp -a "$BASE" "$STAGE"
for version in 55 56 57 58 59 60 61; do
  python3 "$ROOT/overrides/rc${version}/apply.py" "$STAGE"
done
python3 -m compileall -q "$STAGE/core/furina_agent"

python3 - "$STAGE" <<'PY'
from pathlib import Path
import ast,sys
root=Path(sys.argv[1]); core=root/'core/furina_agent'
hub=(core/'hub.py').read_text(encoding='utf-8')
chat=(core/'chat.py').read_text(encoding='utf-8')
bridge=(core/'upstream_bridge.py').read_text(encoding='utf-8')
zero=(core/'upstream_runtime/zerochat_worker.py').read_text(encoding='utf-8')
version=(core/'version.py').read_text(encoding='utf-8')
for name,text in [('hub',hub),('chat',chat),('bridge',bridge),('zero',zero),('version',version)]: ast.parse(text,filename=name)
assert 'VERSION = "1.0.0-rc61"' in version
assert 'EXPECTED_DEPENDENCY_REVISION = "2026.08.21-r31"' in hub
assert 'updater melewati batas waktu 25 menit' in hub
assert 'proc.terminate()' in hub and 'proc.kill()' in hub
assert 'COUNT(*) FROM messages' in hub and 'self._title_pending' in hub
assert 'headers["Range"]' in hub and 'part.open("ab" if offset else "wb")' in hub
assert chat.count('def _background_worker_loop(self)') == 1
assert bridge.count('def _turn_worker_loop(self)') == 1
assert 'if not relevant and not priority and not episodes' in bridge
assert 'get_nowait()' in chat and 'get_nowait()' in bridge
assert 'self._schedule_background(user_text, answer, turn)' in chat
assert 'turns=turns' in bridge and 'for turn in turns[:8]' in zero
print('FURINA_RC61_STATIC_REGRESSION_OK')
PY

(
  cd "$STAGE"
  PYTHONPATH=core python3 -m unittest -v \
    tests.test_chat tests.test_memory tests.test_providers tests.test_llm
)

printf '%s\n' FURINA_RC61_VALIDATION_OK
