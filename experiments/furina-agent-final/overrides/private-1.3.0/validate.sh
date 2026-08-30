#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-/tmp/furina-agent-rc54-validate/termux}"
CANONICAL="/tmp/furina-agent-rc54-validate/termux"
HERE="$(cd "$(dirname "$0")" && pwd)"
PROJECT="$(cd "$HERE/../.." && pwd)"

if [[ "$ROOT" != "$CANONICAL" ]]; then
  bash "$PROJECT/overrides/private-1.2.9/validate.sh" "$CANONICAL"
  mkdir -p "$(dirname "$ROOT")"
  rm -rf "$ROOT"
  cp -a "$CANONICAL" "$ROOT"
else
  bash "$PROJECT/overrides/private-1.2.9/validate.sh" "$ROOT"
fi

python3 "$HERE/apply.py" "$ROOT"
python3 -m py_compile "$ROOT"/core/furina_agent/*.py "$HERE"/*.py

grep -Fq 'VERSION = "1.1.31"' "$ROOT/core/furina_agent/version.py"
grep -Fq 'EXPECTED_DEPENDENCY_REVISION = "2026.08.30-r81"' "$ROOT/core/furina_agent/hub.py"
grep -Fq 'FURINA_TERMUX_129_INTERLEAVED_PRIVATE_ASIDES' "$ROOT/core/furina_agent/chat.py"
grep -Fq 'FURINA_TERMUX_129_BLUE_ASIDE_RENDERER' "$ROOT/core/furina_agent/chat_surface.py"

TEST_HOME="$(mktemp -d)"
HOME="$TEST_HOME" FURINA_HOME="$TEST_HOME" PYTHONPATH="$ROOT/core" python3 "$HERE/test_v129.py"
HOME="$TEST_HOME" FURINA_HOME="$TEST_HOME" PYTHONPATH="$ROOT/core" python3 "$HERE/test_v130.py"
HOME="$TEST_HOME" FURINA_HOME="$TEST_HOME" PYTHONPATH="$ROOT/core" python3 "$HERE/test_v131.py"

echo FURINA_TERMUX_131_VALIDATION_OK
