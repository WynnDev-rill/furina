#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
STAGE=/tmp/furina-agent-rc35-validate/termux

# RC50 validates into its historical stage path. Reuse it, then copy the
# resulting staged tree so RC51/RC35 have an isolated validation target.
bash "$ROOT/overrides/rc50/validate.sh"
rm -rf "$STAGE"
cp -a /tmp/furina-agent-rc34-validate/termux "$STAGE"
python3 "$HERE/apply.py" "$STAGE"
python3 -m py_compile "$HERE/apply.py"
python3 -m compileall -q "$STAGE/core/furina_agent"

python3 - "$STAGE" <<'PY'
from pathlib import Path
import sys
root=Path(sys.argv[1])
hub=(root/'core/furina_agent/hub.py').read_text(encoding='utf-8')
version=(root/'core/furina_agent/version.py').read_text(encoding='utf-8')
assert 'VERSION = "1.0.0-rc51"' in version
assert '"bridge_target": "1.0.0-rc35"' in hub
for marker in (
    'CATATAN VISUAL INTERNAL',
    'Maksimal 6 butir singkat',
    'Berikan SATU jawaban final sebagai companion',
    'jangan pernah tampilkan, kutip, rangkum, atau jelaskan',
    'umumnya 1-3 kalimat',
    'self.session.chat.respond(companion_input)',
):
    assert marker in hub, marker
chat=hub[hub.index('def chat('):hub.index('def public_job(')]
assert 'self.store.add_message("assistant", answer)' not in chat
print('FURINAHUB_CORE_RC51_REGRESSION_OK')
PY
