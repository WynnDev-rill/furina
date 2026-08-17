#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
STAGE=/tmp/furina-agent-rc34-validate/termux

bash "$ROOT/overrides/rc49/validate.sh"
python3 "$HERE/apply.py" "$STAGE"
python3 -m py_compile "$HERE/apply.py"
python3 -m compileall -q "$STAGE/core/furina_agent"
grep -Fq 'VERSION = "1.0.0-rc50"' "$STAGE/core/furina_agent/version.py"

python3 - "$STAGE" <<'PY'
from pathlib import Path
import sys
root=Path(sys.argv[1])
hub=(root/'core/furina_agent/hub.py').read_text(encoding='utf-8')
version=(root/'core/furina_agent/version.py').read_text(encoding='utf-8')
assert 'VERSION = "1.0.0-rc50"' in version
for marker in (
    'def conversation_list(',
    'title_locked',
    'def _queue_auto_title(',
    'role="conversation_title"',
    'def get_chat_progress(',
    '/api/chat/progress/',
    'Menganalisis gambar',
    'Menyusun jawaban sesuai personalisasi',
    'self.session.chat.respond(companion_input)',
    'UPDATE messages SET content=?, attachment_json=?',
    '"bridge_target": "1.0.0-rc34"',
):
    assert marker in hub, marker
assert 'self.store.add_message("assistant", answer)' not in hub[hub.index('def chat('):hub.index('def public_job(')]
print('FURINAHUB_CORE_RC50_REGRESSION_OK')
PY
