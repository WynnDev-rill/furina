#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-/tmp/furina-agent-rc54-validate/termux}"
CANONICAL="/tmp/furina-agent-rc54-validate/termux"
HERE="$(cd "$(dirname "$0")" && pwd)"
PROJECT="$(cd "$HERE/../.." && pwd)"

if [[ "$ROOT" != "$CANONICAL" ]]; then
  bash "$PROJECT/overrides/private-1.2.8/validate.sh" "$CANONICAL"
  mkdir -p "$(dirname "$ROOT")"
  rm -rf "$ROOT"
  cp -a "$CANONICAL" "$ROOT"
else
  bash "$PROJECT/overrides/private-1.2.8/validate.sh" "$ROOT"
fi

python3 "$HERE/apply.py" "$ROOT"
python3 -m py_compile "$ROOT"/core/furina_agent/*.py "$HERE"/*.py

grep -Fq 'VERSION = "1.1.28"' "$ROOT/core/furina_agent/version.py"
grep -Fq 'EXPECTED_DEPENDENCY_REVISION = "2026.08.29-r78"' "$ROOT/core/furina_agent/hub.py"
grep -Fq 'FURINA_TERMUX_128_INNER_THOUGHT_SETTING' "$ROOT/core/furina_agent/hub_settings.py"
grep -Fq 'FURINA_TERMUX_128_NEUTRAL_HUMAN_IDENTITY' "$ROOT/core/furina_agent/persona.py"
grep -Fq 'FURINA_TERMUX_128_HUMAN_ROLEPLAY_GATE' "$ROOT/core/furina_agent/providers.py"
grep -Fq 'FURINA_TERMUX_128_ADAPTIVE_STYLE_POLICY' "$ROOT/core/furina_agent/chat.py"
grep -Fq 'FURINA_TERMUX_128_INNER_THOUGHT_UI' "$ROOT/core/furina_agent/tui.py"

TEST_HOME="$(mktemp -d)"
HOME="$TEST_HOME" FURINA_HOME="$TEST_HOME" PYTHONPATH="$ROOT/core" python3 "$HERE/test_v128.py"

echo FURINA_TERMUX_128_VALIDATION_OK
