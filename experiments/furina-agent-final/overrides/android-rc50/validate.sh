#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
BASE=/tmp/furina-agent-rc62-validate/termux
STAGE=/tmp/furina-agent-rc50-validate/termux

bash "$ROOT/overrides/rc62/validate.sh"
rm -rf "$STAGE"
mkdir -p "$(dirname "$STAGE")"
cp -a "$BASE" "$STAGE"
python3 "$HERE/apply.py" "$STAGE"
python3 -m py_compile "$HERE/apply.py"

python3 - "$STAGE" <<'PY'
from pathlib import Path
import re,sys
root=Path(sys.argv[1]); app=root/'bridge/app'
java=app/'src/main/java/com/wynndev/furinaagentbridge'
html=(app/'src/main/assets/furinahub/index.html').read_text()
main=(java/'MainActivity.java').read_text()
native=(java/'NativeImageEditorActivity.java').read_text()
updater=(java/'BridgeUpdater.java').read_text()
manifest=(app/'src/main/AndroidManifest.xml').read_text()
gradle=(app/'build.gradle').read_text()
fuse=(app/'src/main/assets/furinahub/fuse.min.cjs').read_text()
license=(app/'src/main/assets/licenses/Fuse.js-Apache-2.0.txt').read_text()
assert 'versionCode 10050' in gradle and "versionName '1.0.0-rc50'" in gradle
assert 'NativeImageEditorActivity' in manifest and 'ImageDecoder.decodeBitmap' in native
assert 'Canvas canvas = new Canvas(result)' in native and 'canvas.drawBitmap(bitmap' in native
assert '@JavascriptInterface public void editImage' in main and 'startActivityForResult(intent, REQ_NATIVE_EDITOR)' in main
assert 'NATIVE.editImage' in html and 'function openImageEditor' in html
assert 'window.Fuse=module.exports' in main and 'useTokenSearch:true' in html
assert 'Fuse.js v7.5.0' in fuse and 'Apache License' in license
assert updater.count('furina-update-stable/bundle.json') == 1 and 'Cache-Control' in updater
assert 'furina-2026.08.21-rc62-rc50' in main and 'ensureBundleSync' in main
scripts=re.findall(r'<script(?:\s[^>]*)?>(.*?)</script>',html,re.I|re.S)
Path('/tmp/furinahub-rc50-inline.js').write_text('\n'.join(scripts))
print('FURINAHUB_RC50_NATIVE_EDITOR_FUSE_STATIC_OK')
PY
node --check /tmp/furinahub-rc50-inline.js
node - "$HERE/vendor/fuse.min.cjs" <<'JS'
const Fuse=require(process.argv[2]);
const search=new Fuse([{text:'membeli obat besok sore'}],{
  keys:['text'],threshold:.45,ignoreLocation:true,useTokenSearch:true
});
if(Fuse.version!=='7.5.0'||search.search('membli obbat').length!==1)process.exit(1);
console.log('FURINAHUB_FUSE_7_5_TOKEN_TYPO_OK');
JS
printf '%s\n' FURINAHUB_RC50_VALIDATION_OK
