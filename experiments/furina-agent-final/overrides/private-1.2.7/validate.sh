#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-/tmp/furina-agent-rc54-validate/termux}"
CANONICAL="/tmp/furina-agent-rc54-validate/termux"
HERE="$(cd "$(dirname "$0")" && pwd)"
PROJECT="$(cd "$HERE/../.." && pwd)"

# Older validators reconstruct at the historical canonical staging path. Build
# there once, then copy the verified predecessor tree when a custom stage was
# requested. This makes custom-stage validation real rather than nominal.
if [[ "$ROOT" != "$CANONICAL" ]]; then
  bash "$PROJECT/overrides/private-1.2.6/validate.sh" "$CANONICAL"
  mkdir -p "$(dirname "$ROOT")"
  cp -a "$CANONICAL" "$ROOT"
else
  bash "$PROJECT/overrides/private-1.2.6/validate.sh" "$ROOT"
fi

python3 "$HERE/apply.py" "$ROOT"
python3 -m py_compile "$ROOT"/core/furina_agent/*.py "$HERE"/*.py

grep -Fq 'VERSION = "1.1.26"' "$ROOT/core/furina_agent/version.py"
grep -Fq 'FURINA_TERMUX_126_DYNAMIC_SETTINGS' "$ROOT/core/furina_agent/hub_settings.py"
grep -Fq 'FURINA_TERMUX_126_PRIVATE_REASONING' "$ROOT/core/furina_agent/providers.py"
grep -Fq 'FURINA_TERMUX_126_FINAL_BEHAVIOR_KERNEL' "$ROOT/core/furina_agent/chat.py"

TEST_HOME="$(mktemp -d)"
HOME="$TEST_HOME" FURINA_HOME="$TEST_HOME" PYTHONPATH="$ROOT/core" python3 "$HERE/test_v126.py"

echo FURINA_TERMUX_126_VALIDATION_OK
