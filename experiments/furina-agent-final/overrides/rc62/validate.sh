#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
BASE=/tmp/furina-agent-rc61-validate/termux
STAGE=/tmp/furina-agent-rc62-validate/termux
VENV=/tmp/furina-dateparser-1.4.2

bash "$ROOT/overrides/rc61/validate.sh"
rm -rf "$STAGE"
mkdir -p "$(dirname "$STAGE")"
cp -a "$BASE" "$STAGE"
# Core RC62 and Android RC50 are one bundle; establish the released RC49 bridge
# before Core changes its bridge target to RC50.
python3 "$ROOT/overrides/android-rc49/apply.py" "$STAGE"
python3 "$HERE/apply.py" "$STAGE"
python3 -m py_compile "$HERE/apply.py"
python3 -m compileall -q "$STAGE/core/furina_agent"

if [[ ! -x "$VENV/bin/python" ]]; then
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install --disable-pip-version-check -q 'dateparser==1.4.2'
fi
PYTHONPATH="$STAGE/core" "$VENV/bin/python" - "$STAGE" <<'PY'
from pathlib import Path
import datetime as dt
import importlib.metadata as metadata
import sys

assert metadata.version('dateparser') == '1.4.2'
from furina_agent.prospective import extract_prospectives

base=dt.datetime(2026,8,21,10,0,0)
cases={
    'ingatkan aku besok sore membeli obat': dt.datetime(2026,8,22,16,0,0),
    'ingatkan aku dua minggu lagi memperpanjang paket': dt.datetime(2026,9,4,10,0,0),
    'ingatkan aku dalam 90 menit minum air': dt.datetime(2026,8,21,11,30,0),
    'ingatkan aku tanggal 25/8 pukul 09:30 rapat': dt.datetime(2026,8,25,9,30,0),
}
for text, expected in cases.items():
    result=extract_prospectives(text,base.timestamp())
    assert result and dt.datetime.fromtimestamp(result[0][1]) == expected, (text,result)

root=Path(sys.argv[1]); core=root/'core/furina_agent'
assert 'VERSION = "1.0.0-rc62"' in (core/'version.py').read_text()
hub=(core/'hub.py').read_text()
assert 'furina-2026.08.21-rc62-rc50' in hub and '"bundle_synced":' in hub
print('FURINA_RC62_DATEPARSER_BUNDLE_VALIDATION_OK')
PY

# A released RC61 device may already target a newer bridge than the original
# fixture. This was the exact field variation that blocked RC61 -> RC63.
VARIANT=/tmp/furina-agent-rc62-variant/termux
rm -rf "$VARIANT"; mkdir -p "$(dirname "$VARIANT")"; cp -a "$BASE" "$VARIANT"
python3 - "$VARIANT/core/furina_agent/hub.py" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]); text=p.read_text(encoding='utf-8')
old='            "core_version": VERSION,\n            "bridge_target": "1.0.0-rc48",'
assert old in text
p.write_text(text.replace(old, '            "core_version": VERSION,\n            "bridge_target": "1.0.0-rc50",', 1), encoding='utf-8')
PY
python3 "$HERE/apply.py" "$VARIANT"
grep -Fq 'VERSION = "1.0.0-rc62"' "$VARIANT/core/furina_agent/version.py"
test "$(grep -Fc '"bundle_id": "furina-2026.08.21-rc62-rc50"' "$VARIANT/core/furina_agent/hub.py")" -eq 1
printf '%s\n' FURINA_RC62_RELEASED_RC61_VARIANT_OK
