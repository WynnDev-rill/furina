#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-/tmp/furina-agent-rc54-validate/termux}"
HERE="$(cd "$(dirname "$0")" && pwd)"
PROJECT="$(cd "$HERE/../.." && pwd)"

# Reconstruct the exact previously released private 1.0.0 baseline first.
bash "$PROJECT/overrides/final-1.0/validate.sh"
python3 "$HERE/preflight.py" "$ROOT"
python3 "$HERE/apply.py" "$ROOT"
python3 "$PROJECT/overrides/android-private-1.0.1/apply.py" "$ROOT"

python3 -m py_compile \
  "$ROOT/core/furina_agent/local_models.py" \
  "$ROOT/core/furina_agent/config.py" \
  "$ROOT/core/furina_agent/routing.py" \
  "$ROOT/core/furina_agent/tui.py" \
  "$ROOT/core/furina_agent/hub.py"

grep -Fq 'VERSION = "1.0.1"' "$ROOT/core/furina_agent/version.py"
grep -Fq 'versionCode 10059' "$ROOT/bridge/app/build.gradle"
grep -Fq "versionName '1.0.1'" "$ROOT/bridge/app/build.gradle"
grep -Fq 'furina-2026.08.23-private-1.0.1' "$ROOT/bridge/app/src/main/java/com/wynndev/furinaagentbridge/MainActivity.java"

env STAGE_ROOT="$ROOT" python3 - <<'PY'
import ast, os
from pathlib import Path
root=Path(os.environ['STAGE_ROOT']); core=root/'core/furina_agent'
tui=(core/'tui.py').read_text(encoding='utf-8')
routing=(core/'routing.py').read_text(encoding='utf-8')
hub=(core/'hub.py').read_text(encoding='utf-8')
config=(core/'config.py').read_text(encoding='utf-8')
models=(core/'local_models.py').read_text(encoding='utf-8')
page=(root/'bridge/app/src/main/assets/furinahub/index.html').read_text(encoding='utf-8')
for p in core.glob('*.py'): ast.parse(p.read_text(encoding='utf-8'),filename=str(p))
assert tui.count('def run_tui():') == 1
assert '["Chat", "Provider & Model", "Pengaturan", "Exit"]' in tui
run=tui[tui.index('def run_tui():'):]
run=run[:run.index('\ndef ',20)] if '\ndef ' in run[20:] else run
assert '_auto_start_local(console)' not in run
assert 'Toggle local auto-start' not in tui[tui.index('def _settings'):tui.index('def _auto_start_local')]
assert 'AUTO · online' not in tui[tui.index('def _providers'):tui.index('def _settings')]
assert 'Memory' not in tui[tui.index('def _main_menu'):tui.index('def _providers')]
assert 'routing_mode: str = "online"' in config
assert '{"local", "online"}' in config
chat=routing[routing.index('    def chat('):]
assert 'routing_mode in {"auto", "online"}' not in chat
assert 'Provider online belum dikonfigurasi' in chat
assert 'wifugpt-1.7b-q4km' in models and 'qwen3-1.7b-heretic-q5km' in models
assert 'd256ccbab62bbd80064ecb73be0512b0b8d16bc930d5ae9ac8079216b88b2b54' in models
assert 'f2b0b5f7fead5fdcfb79f783b96465fe97f56361b11e8de972afd71b9ba994a2' in models
assert 'Qwen_Qwen3.5-4B-Q4_K_M.gguf' not in hub
assert 'MODEL_CATALOG = tuple(dict(item) for item in LOCAL_MODEL_CATALOG)' in hub
assert 'data-view="memory"' not in page
assert '<section id="memory" class="view hidden" aria-hidden="true">' in page
assert 'id="localModelRows"' in page and 'id="modelProgress"' in page
assert "['local','auto','online']" not in page
assert 'downloadLocalModel' in page and 'selectLocalModel' in page and 'selectOnlineModel' in page
assert 'Unduh' in page and 'Pilih' in page and 'Aktif' in page
print('FURINA_PRIVATE_1_0_1_SURFACE_OK')
PY

# Import Config with an isolated FURINA_HOME and prove AUTO migrates to ONLINE
# and legacy catalog files are removed without touching arbitrary GGUF files.
TMP_HOME="$(mktemp -d)"
trap 'rm -rf "$TMP_HOME"' EXIT
mkdir -p "$TMP_HOME/models" "$TMP_HOME/data"
printf 'legacy' > "$TMP_HOME/models/Qwen_Qwen3.5-4B-Q4_K_M.gguf"
printf 'user' > "$TMP_HOME/models/my-private-model.gguf"
FURINA_HOME="$TMP_HOME" PYTHONPATH="$ROOT/core" python3 - <<'PY'
from furina_agent.config import load_config,save_config
from furina_agent.local_models import retire_legacy_catalog
cfg=load_config(); cfg.routing_mode='auto'; cfg.model_path=str(__import__('pathlib').Path(__import__('os').environ['FURINA_HOME'])/'models/Qwen_Qwen3.5-4B-Q4_K_M.gguf'); save_config(cfg)
cfg=load_config(); changed=retire_legacy_catalog(cfg)
if changed: save_config(cfg)
assert cfg.routing_mode=='online' and cfg.model_path=='' and cfg.auto_start is False
from pathlib import Path
home=Path(__import__('os').environ['FURINA_HOME'])
assert not (home/'models/Qwen_Qwen3.5-4B-Q4_K_M.gguf').exists()
assert (home/'models/my-private-model.gguf').exists()
print('FURINA_PRIVATE_1_0_1_MODEL_MIGRATION_OK')
PY

# Build the exact updater that will be released and verify `hapus furina` in an
# isolated prefix. The uninstall must remove Furina-owned data/launchers only.
CLIENT="$TMP_HOME/furina-update.py"
python3 "$PROJECT/overrides/runtime-private-1.0.1/build_client.py" "$PROJECT/overrides/runtime-r39/update_client.py" "$CLIENT"
grep -Fq 'CLIENT_VERSION = "1.2.0"' "$CLIENT"
grep -Fq '"hapus"' "$CLIENT"
grep -Fq 'def uninstall_termux' "$CLIENT"
! grep -Fq 'wifuGPT-1.7B-Q4_K_M.gguf' "$CLIENT"

TESTROOT="$TMP_HOME/uninstall-root"
TESTPREFIX="$TMP_HOME/prefix"
mkdir -p "$TESTROOT/updater" "$TESTROOT/data" "$TESTPREFIX/bin"
cp "$CLIENT" "$TESTROOT/updater/update_client.py"
printf 'keep-test' > "$TESTROOT/data/user-memory"
FURINA_HOME="$TESTROOT" PREFIX="$TESTPREFIX" python3 - <<PY
import importlib.util
from pathlib import Path
spec=importlib.util.spec_from_file_location('fu',Path('$CLIENT'))
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
m.install_launchers(Path('$TESTROOT'))
assert (Path('$TESTPREFIX')/'bin/hapus').exists()
PY
FURINA_HOME="$TESTROOT" PREFIX="$TESTPREFIX" bash "$TESTPREFIX/bin/hapus" furina --yes
test ! -e "$TESTROOT"
test ! -e "$TESTPREFIX/bin/furina"
test ! -e "$TESTPREFIX/bin/hapus"

echo FURINA_PRIVATE_1_0_1_VALIDATION_OK
