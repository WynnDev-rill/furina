#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: build-root.sh <work-dir>" >&2
  exit 2
fi

REPO="$(git rev-parse --show-toplevel)"
META="$REPO/experiments/furina-agent-final"
RC33="$META/overrides/rc33"
RC34="$META/overrides/rc34"
RC35="$META/overrides/rc35"
WORK="$1"
ARCHIVE="$WORK/source.tar.gz"
ROOT="$WORK/termux"

rm -rf "$WORK"
mkdir -p "$WORK"
: > "$ARCHIVE"
for chunk in "$META"/source-*.b64; do
  base64 --decode "$chunk" >> "$ARCHIVE"
done

EXPECTED_SOURCE_SHA="$(python3 - "$META/manifest.json" <<'PY'
import json,sys
print(json.load(open(sys.argv[1],encoding='utf-8'))['source_sha256'])
PY
)"
echo "$EXPECTED_SOURCE_SHA  $ARCHIVE" | sha256sum -c -
tar -xzf "$ARCHIVE" -C "$WORK"

patch -p0 -d "$WORK" < "$META/patches/api30-inputstream.patch"
patch -p0 -d "$WORK" < "$META/patches/runtime-online-agent.patch"
python3 "$META/overrides/apply-bridge-primitives-rc5.py" "$ROOT"

python3 - "$META/overrides" "$ROOT" <<'PY'
import hashlib,json,pathlib,sys
src=pathlib.Path(sys.argv[1]).resolve(); dst=pathlib.Path(sys.argv[2]).resolve()
manifest=json.loads((src/'manifest.json').read_text(encoding='utf-8'))
def blob(data: bytes) -> str:
    return hashlib.sha1(f'blob {len(data)}\0'.encode()+data).hexdigest()
for item in manifest['files']:
    data=(src/item['path']).read_bytes()
    assert blob(data)==item['git_blob_sha'], item['path']
    target=(dst/item['target']).resolve()
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_bytes(data)
PY

TRANSFORMS=(
  apply-bridge-rc4.py
  apply-universal-agent-rc5.py
  apply-core-rc6.py
  apply-core-rc6-postfix.py
  apply-bridge-rc6.py
  apply-core-rc7.py
  apply-bridge-rc7.py
  apply-core-rc8.py
  apply-core-rc8-postfix.py
  apply-core-rc9.py
  apply-ui-rc10.py
  apply-ui-rc10-hotfix.py
  apply-core-rc11.py
  apply-ui-rc12.py
  apply-ui-rc12-postfix.py
  apply-core-rc13.py
  apply-bridge-rc8.py
  apply-core-rc14.py
  apply-core-rc15.py
  apply-core-rc16.py
  apply-core-rc17-hotfix.py
  apply-bridge-rc9.py
  apply-core-rc18.py
  apply-ui-performance-bridge-rc10.py
  apply-ui-performance-rc19.py
  apply-reactive-bridge-rc11.py
  apply-reactive-core-rc20.py
  apply-reactive-bridge-rc12.py
  apply-reactive-core-rc21.py
  apply-bridge-rc13.py
  apply-system-rc22.py
  apply-safety-rc22.py
  apply-semantic-core-rc23.py
  apply-semantic-guard-rc23.py
  apply-lifecycle-core-rc24.py
  apply-bridge-rc14.py
  apply-stateful-core-rc25.py
  apply-stateful-core-rc25-postfix.py
  apply-stateful-bridge-rc15.py
  apply-stateful-bridge-rc15-postfix.py
  apply-semantic-resilience-rc26.py
  apply-runtime-recovery-rc27.py
  apply-runtime-core-rc28.py
  apply-universal-ui-core-rc29.py
  apply-universal-ui-bridge-rc16.py
  apply-privileged-core-rc30.py
  apply-privileged-bridge-rc17.py
)
for transform in "${TRANSFORMS[@]}"; do
  python3 "$META/overrides/$transform" "$ROOT"
done
python3 "$META/overrides/apply-device-control-core-rc31.py" "$ROOT"
python3 "$META/overrides/apply-device-control-bridge-rc18.py" "$ROOT"
python3 "$META/overrides/apply-policy-boundary-core-rc32.py" "$ROOT"
python3 "$RC33/apply.py" "$ROOT" "$RC33"
python3 "$RC34/apply.py" "$ROOT"
python3 "$RC35/apply.py" "$ROOT" "$RC35"
python3 "$META/overrides/apply-furinahub-bridge-rc19.py" "$ROOT"
python3 -m compileall -q "$ROOT/core/furina_agent"

echo "$ROOT"
