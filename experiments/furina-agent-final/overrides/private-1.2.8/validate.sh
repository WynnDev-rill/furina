#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-/tmp/furina-agent-rc54-validate/termux}"
CANONICAL="/tmp/furina-agent-rc54-validate/termux"
HERE="$(cd "$(dirname "$0")" && pwd)"
PROJECT="$(cd "$HERE/../.." && pwd)"

if [[ "$ROOT" != "$CANONICAL" ]]; then
  bash "$PROJECT/overrides/private-1.2.7/validate.sh" "$CANONICAL"
  mkdir -p "$(dirname "$ROOT")"
  rm -rf "$ROOT"
  cp -a "$CANONICAL" "$ROOT"
else
  bash "$PROJECT/overrides/private-1.2.7/validate.sh" "$ROOT"
fi

python3 "$HERE/apply.py" "$ROOT"
python3 -m py_compile "$ROOT"/core/furina_agent/*.py "$HERE"/*.py

grep -Fq 'VERSION = "1.1.27"' "$ROOT/core/furina_agent/version.py"
grep -Fq 'FURINA_TERMUX_127_BUILTIN_TRAITS_ONLY' "$ROOT/core/furina_agent/hub_settings.py"
grep -Fq 'FURINA_TERMUX_127_VISIBLE_OUTPUT_GATE' "$ROOT/core/furina_agent/providers.py"
grep -Fq 'FURINA_TERMUX_127_RESTORED_PERSONALITY_UI' "$ROOT/core/furina_agent/tui.py"

TEST_HOME="$(mktemp -d)"
HOME="$TEST_HOME" FURINA_HOME="$TEST_HOME" PYTHONPATH="$ROOT/core" python3 "$HERE/test_v127.py"

echo FURINA_TERMUX_127_VALIDATION_OK
