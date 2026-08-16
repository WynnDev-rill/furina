#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
STAGE=/tmp/furina-agent-rc34-validate/termux

bash "$ROOT/overrides/rc47/validate.sh"
python3 "$HERE/apply.py" "$STAGE"
python3 -m py_compile "$HERE/apply.py"
bash -n "$HERE/install-body.sh"

PYTHONPATH="$STAGE/core" FURINA_HOME=/tmp/furinahub-rc48-test python3 - <<'PY'
from furina_agent.version import VERSION
from furina_agent.hub import CONNECTOR_LOG_PATH, Runtime
assert VERSION == "1.0.0-rc48"
assert CONNECTOR_LOG_PATH.name == "openconnector.log"
obj = object.__new__(Runtime)
assert callable(obj._connector_log_detail)
print("FURINAHUB_RC48_CORE_IMPORT_OK")
PY

python3 - "$STAGE" "$HERE/install-body.sh" <<'PY'
from pathlib import Path
import re,subprocess,sys,tempfile
stage=Path(sys.argv[1])
body=Path(sys.argv[2]).read_text(encoding='utf-8')
hub=(stage/'core/furina_agent/hub.py').read_text(encoding='utf-8')
version=(stage/'core/furina_agent/version.py').read_text(encoding='utf-8')
assert 'VERSION = "1.0.0-rc48"' in version
assert 'self._connector_request("GET", "/v1/health")' in hub
assert 'provider.get("authTypes")' in hub
assert '"connected": service in connected or "no_auth" in auth_types' in hub
assert 'Plugin gagal start:' in hub
assert 'DEPENDENCY_REVISION="2026.08.16-r12"' in body
assert 'URL="http://127.0.0.1:3000/v1/health"' in body
assert 'node "$APP/src/server/index.ts"' in body
assert 'npm install --omit=dev --workspaces=false --no-audit --no-fund' in body
assert 'if start_plugin; then' in body
assert 'Do not stamp the revision on failure' in body
start=body.index("  cat > \"$PREFIX/bin/furina-openconnector\" <<'SH'\n")
start=body.index("\n",start)+1
end=body.index("\nSH\n",start)
launcher=body[start:end]+"\n"
path=Path(tempfile.mkdtemp())/'furina-openconnector'
path.write_text(launcher,encoding='utf-8')
subprocess.run(['bash','-n',str(path)],check=True)
assert '/v1/health' in launcher
assert 'start_with_repair' in launcher
assert 'repair_deps' in launcher
print('FURINAHUB_RC48_PLUGIN_REGRESSION_OK')
PY

echo FURINAHUB_CORE_RC48_VALIDATE_OK
