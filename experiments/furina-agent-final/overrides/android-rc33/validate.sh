#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
STAGE=/tmp/furina-agent-rc34-validate/termux

bash "$ROOT/overrides/android-rc32/validate.sh"
python3 "$HERE/apply.py" "$STAGE"
python3 -m py_compile "$HERE/apply.py"

python3 - "$STAGE" <<'PY'
from pathlib import Path
import re,subprocess,sys,tempfile

root=Path(sys.argv[1])
app=root/'bridge/app'
html=(app/'src/main/assets/furinahub/index.html').read_text(encoding='utf-8')
gradle=(app/'build.gradle').read_text(encoding='utf-8')

drawer=html[html.index('<aside id="drawer"'):html.index('</aside>')+len('</aside>')]
models=html[html.index('<section id="models"'):html.index('<section id="personalization"')]
settings=html[html.index('<section id="settings"'):html.index('</main>')]

assert 'data-view="plugins"' not in drawer
assert 'data-view="agent"' not in drawer
assert drawer.index('data-view="settings"') < drawer.index('newConversation()')
assert '<h3>Routing</h3>' in models
assert '<h3>Provider online</h3>' in models
assert 'id="localModels"' not in models
assert 'id="modelCatalog"' not in models
assert 'id="supportModels"' not in models
assert 'Model offline dikelola otomatis di Core' in models
assert '<section id="agent" class="view hidden">' in html
assert '<section id="plugins" class="view hidden">' in html
assert '<div class="card hidden"><h3>Kontrol perangkat</h3>' in settings
assert 'onclick="openPluginPicker()"' not in html
assert 'handleMention(this.value)' not in html
assert "document.getElementById('advancedCard').classList.add('hidden');" in html
assert "versionCode 10033" in gradle
assert "versionName '1.0.0-rc33'" in gradle

scripts=re.findall(r'<script>(.*?)</script>',html,re.S)
assert len(scripts)==1
path=Path(tempfile.mkdtemp())/'hub.js'
path.write_text(scripts[0],encoding='utf-8')
subprocess.run(['node','--check',str(path)],check=True)
print('FURINAHUB_ANDROID_RC33_SIMPLIFIED_UI_REGRESSION_OK')
PY
