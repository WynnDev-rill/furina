#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

VERSION="1.0.0-rc44"
HUB_VERSION="1.0.0-rc28"
DEPENDENCY_REVISION="2026.08.15-r8"
ROOT="$HOME/.furina-agent"
BASE="https://raw.githubusercontent.com/WynnDev-rill/furina/experiment/furina-agent-termux/experiments/furina-agent-final"
PINNED_RC43="44d215a38b336c903d06f04be01f30e60143ba35"
PINNED_BASE="https://raw.githubusercontent.com/WynnDev-rill/furina/$PINNED_RC43/experiments/furina-agent-final"
RC43_BODY_URL="$PINNED_BASE/overrides/rc43/install-body.sh"
RC43_BODY_BLOB="dcaeee6a1ad8588f76c37138b180b472b8720178"
RC44_APPLY_URL="$BASE/overrides/rc44/apply.py"
RC44_APPLY_BLOB="1c81b788e0581f363cc166b576feee68ec8b5798"
RELEASE_BASE="https://github.com/WynnDev-rill/furina/releases/download/furinahub-v1.0.0-rc28"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

if [[ ! -d /data/data/com.termux/files/usr ]]; then
  echo "Installer FurinaHub harus dijalankan dari Termux." >&2
  exit 1
fi

mkdir -p "$ROOT"/{cache,logs,run,data,models}

fetch() {
  local url="$1" out="$2"
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL --retry 4 "$url" -o "$out"
  elif command -v python >/dev/null 2>&1; then
    python - "$url" "$out" <<'PY'
import sys,urllib.request
urllib.request.urlretrieve(sys.argv[1],sys.argv[2])
PY
  else
    pkg install -y python >/dev/null
    python - "$url" "$out" <<'PY'
import sys,urllib.request
urllib.request.urlretrieve(sys.argv[1],sys.argv[2])
PY
  fi
}

verify_blob() {
  python - "$1" "$2" <<'PY'
import hashlib,pathlib,sys
path,expected=sys.argv[1:]
data=pathlib.Path(path).read_bytes()
actual=hashlib.sha1(f"blob {len(data)}\0".encode()+data).hexdigest()
if actual != expected:
    raise SystemExit(f"Integritas file berubah: {actual} != {expected}")
PY
}

core_version() {
  python - "$ROOT/core/furina_agent/version.py" <<'PY'
import re,sys
try: text=open(sys.argv[1],encoding='utf-8').read()
except Exception: print('missing'); raise SystemExit
m=re.search(r'VERSION\s*=\s*["\x27]([^"\x27]+)',text)
print(m.group(1) if m else 'unknown')
PY
}

CURRENT="$(core_version 2>/dev/null || true)"
if [[ "$CURRENT" != "$VERSION" ]]; then
  echo "FurinaHub: menyiapkan fondasi Core RC43…"
  fetch "$RC43_BODY_URL" "$TMP/rc43-install-body.sh"
  verify_blob "$TMP/rc43-install-body.sh" "$RC43_BODY_BLOB"
  python - "$TMP/rc43-install-body.sh" "$PINNED_BASE" <<'PY'
from pathlib import Path
import sys
path=Path(sys.argv[1]); pinned=sys.argv[2]
text=path.read_text(encoding='utf-8')
old='BASE="https://raw.githubusercontent.com/WynnDev-rill/furina/experiment/furina-agent-termux/experiments/furina-agent-final"'
new=f'BASE="{pinned}"'
if text.count(old) != 1:
    raise SystemExit('RC43 BASE marker berubah')
path.write_text(text.replace(old,new,1),encoding='utf-8')
PY
  mkdir -p "$TMP/fake-bin"
  cat > "$TMP/fake-bin/termux-open" <<'SH'
#!/data/data/com.termux/files/usr/bin/bash
exit 0
SH
  chmod 755 "$TMP/fake-bin/termux-open"
  PATH="$TMP/fake-bin:$PATH" bash "$TMP/rc43-install-body.sh" "$@"

  fetch "$RC44_APPLY_URL" "$TMP/apply-rc44.py"
  verify_blob "$TMP/apply-rc44.py" "$RC44_APPLY_BLOB"
  rm -rf "$TMP/stage"
  mkdir -p "$TMP/stage"
  cp -R "$ROOT/core" "$TMP/stage/core"
  python "$TMP/apply-rc44.py" "$TMP/stage"
  FURINA_HOME="$TMP/test-home" PYTHONPATH="$TMP/stage/core" python -m compileall -q "$TMP/stage/core/furina_agent"
  FURINA_HOME="$TMP/test-home" PYTHONPATH="$TMP/stage/core" python - <<'PY'
from furina_agent.version import VERSION
from furina_agent.hub import Runtime
assert VERSION == '1.0.0-rc44'
assert Runtime._connector_is_read_action('github.get_issue')
assert not Runtime._connector_is_read_action('gmail.sendEmail')
assert not Runtime._connector_is_read_action('github.search_and_delete')
print('FURINAHUB_RC44_INSTALL_VALIDATED')
PY
  furina stop >/dev/null 2>&1 || true
  rm -rf "$ROOT/core.prev"
  mv "$ROOT/core" "$ROOT/core.prev"
  mv "$TMP/stage/core" "$ROOT/core"
else
  echo "FurinaHub Core RC44 sudah aktif."
fi

APK_OUT="$HOME/FurinaHub.apk"
APK_MARKER="$ROOT/data/furinahub_apk_revision"
APK_BEFORE="$(cat "$APK_MARKER" 2>/dev/null || true)"
if [[ "$APK_BEFORE" != "$HUB_VERSION" || ! -s "$APK_OUT" ]]; then
  echo "FurinaHub: menyiapkan APK RC28…"
  fetch "$RELEASE_BASE/bridge.json" "$TMP/bridge.json"
  read -r APK_URL APK_SHA < <(python - "$TMP/bridge.json" <<'PY'
import json,sys
m=json.load(open(sys.argv[1],encoding='utf-8'))
assert m['package_name']=='com.wynndev.furinaagentbridge'
assert int(m['version_code'])==10028
assert m['version']=='1.0.0-rc28'
assert str(m['apk_url']).startswith('https://github.com/WynnDev-rill/furina/releases/download/furinahub-v1.0.0-rc28/')
assert len(str(m['sha256']))==64
print(m['apk_url'],m['sha256'])
PY
)
  fetch "$APK_URL" "$TMP/FurinaHub.apk"
  python - "$TMP/FurinaHub.apk" "$APK_SHA" <<'PY'
import hashlib,pathlib,sys
path,expected=sys.argv[1:]
actual=hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()
if actual.lower()!=expected.lower():
    raise SystemExit(f'Hash APK tidak cocok: {actual} != {expected}')
PY
  cp "$TMP/FurinaHub.apk" "$APK_OUT"
  chmod 600 "$APK_OUT"
  printf '%s\n' "$HUB_VERSION" > "$APK_MARKER"
fi

if [[ "$APK_BEFORE" != "$HUB_VERSION" ]] && command -v termux-open >/dev/null 2>&1; then
  termux-open --content-type application/vnd.android.package-archive "$APK_OUT" >/dev/null 2>&1 || true
fi

printf '\n\033[32m✓\033[0m FurinaHub Core RC44 aktif.\n'
printf '  APK RC28: %s\n' "$APK_OUT"
printf '  Perbaikan: Agent approval, gambar besar, Plugin safety, validasi GGUF, dan lifecycle WebView.\n'
