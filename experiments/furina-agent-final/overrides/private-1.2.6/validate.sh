#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-/tmp/furina-agent-rc54-validate/termux}"
HERE="$(cd "$(dirname "$0")" && pwd)"
PROJECT="$(cd "$HERE/../.." && pwd)"

bash "$PROJECT/overrides/private-1.2.5/validate.sh" "$ROOT"
python3 "$HERE/apply.py" "$ROOT"
python3 -m py_compile "$ROOT"/core/furina_agent/*.py "$HERE"/*.py

grep -Fq 'VERSION = "1.1.25"' "$ROOT/core/furina_agent/version.py"
grep -Fq 'FURINA_TERMUX_125_NEUTRAL_CORPUS' "$ROOT/core/furina_agent/training_room.py"
grep -Fq 'FURINA_TERMUX_125_LIVE_TRAINING_COMMIT' "$ROOT/core/furina_agent/chat.py"
grep -Fq 'FURINA_TERMUX_125_NEUTRAL_TRAINING_TUI' "$ROOT/core/furina_agent/tui.py"
grep -Fq 'CorpusItem("c090"' "$ROOT/core/furina_agent/training_corpus.py"
test -f "$ROOT/core/furina_agent/training_corpus.NOTICE.md"

TEST_HOME="$(mktemp -d)"
HOME="$TEST_HOME" FURINA_HOME="$TEST_HOME" PYTHONPATH="$ROOT/core" python3 "$HERE/test_v125.py"

python3 - "$PROJECT" <<'PY'
import sys
from pathlib import Path
project=Path(sys.argv[1])
source=(project/'overrides/private-1.2.6/validate.sh').read_text(encoding='utf-8')
assert 'private-1.2.5/validate.sh" "$ROOT"' in source
print('FURINA_TERMUX_125_CUSTOM_STAGE_FORWARDING_OK')
PY

echo FURINA_TERMUX_125_VALIDATION_OK
