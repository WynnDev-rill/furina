#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
VERSION="1.0.0-rc20"
ROOT="$HOME/.furina-agent"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

if [[ ! -f "$ROOT/core/furina_agent/version.py" ]]; then
  echo "RC20 updater membutuhkan instalasi Furina Agent yang sudah ada." >&2
  exit 1
fi

DISPLAY_NAME="Furina"
if [[ -f "$ROOT/config.json" ]]; then
  DISPLAY_NAME="$(python - "$ROOT/config.json" <<'PY' 2>/dev/null || true
import json,sys
try:
    data=json.load(open(sys.argv[1],encoding='utf-8'))
    print(str(data.get('persona_name') or 'Furina').strip()[:48] or 'Furina')
except Exception:
    print('Furina')
PY
)"
fi

ui_title() {
  printf '\033[2J\033[H'
  printf '\033[1;36m%s\033[0m \033[1mBy Wynn\033[0m\n' "$DISPLAY_NAME"
  printf '\033[2mUpdate Core RC20 · memory dan model dipertahankan\033[0m\n\n'
}
ui_progress() {
  local pct="$1" label="$2" width=22 filled empty bar="" i
  filled=$(( pct * width / 100 )); empty=$(( width - filled ))
  for ((i=0;i<filled;i++)); do bar+="█"; done
  for ((i=0;i<empty;i++)); do bar+="░"; done
  printf '\r\033[K\033[35m›\033[0m \033[2m[%s]\033[0m \033[1m%3d%%\033[0m %s' "$bar" "$pct" "$label"
}
mark() { ui_progress "$1" "$2"; printf '\n'; }

ui_title
mark 8 "Memeriksa instalasi Furina"
CURRENT="$(python - "$ROOT/core/furina_agent/version.py" <<'PY'
import re,sys
text=open(sys.argv[1],encoding='utf-8').read()
m=re.search(r'VERSION\s*=\s*[\"\x27]([^\"\x27]+)',text)
print(m.group(1) if m else 'unknown')
PY
)"
mark 18 "Membaca versi saat ini: $CURRENT"

cp -R "$ROOT/core" "$STAGE/core"
mark 30 "Membuat salinan aman Core"

if [[ "$CURRENT" != "1.0.0-rc20" ]]; then
python - "$STAGE/core/furina_agent" <<'PY'
from pathlib import Path
import sys
core=Path(sys.argv[1]); agent=core/'agent.py'; chat=core/'chat_surface.py'; version=core/'version.py'
a=agent.read_text(encoding='utf-8')
a=a.replace('''        left_termux = False\n        cancel_event = threading.Event()\n        task_started = time.monotonic()\n        def watch_user_return():\n            seen_outside = False\n            while not cancel_event.is_set() and time.monotonic() - task_started < 300:\n                package = str(self.store.get_state("device_foreground_package", "") or "")\n                if package and package not in TERMUX_PACKAGES:\n                    seen_outside = True\n                elif seen_outside and package in TERMUX_PACKAGES:\n                    cancel_event.set()\n                    return\n                time.sleep(0.05)\n''','''        left_termux = False\n        termux_return_candidate_at = 0.0\n        cancel_event = threading.Event()\n        task_started = time.monotonic()\n        def watch_user_return():\n            seen_outside = False\n            returned_at = 0.0\n            while not cancel_event.is_set() and time.monotonic() - task_started < 300:\n                package = str(self.store.get_state("device_foreground_package", "") or "")\n                now = time.monotonic()\n                if package and package not in TERMUX_PACKAGES:\n                    seen_outside = True\n                    returned_at = 0.0\n                elif seen_outside and package in TERMUX_PACKAGES:\n                    if returned_at <= 0.0: returned_at = now\n                    elif now - returned_at >= 0.75:\n                        cancel_event.set(); return\n                else: returned_at = 0.0\n                time.sleep(0.05)\n''',1)
a=a.replace('''        def user_returned_to_termux(screen: dict) -> bool:\n            nonlocal left_termux\n            package = str(screen.get("package") or "")\n            if package and package not in TERMUX_PACKAGES:\n                left_termux = True\n                return False\n            return bool(left_termux and package in TERMUX_PACKAGES)\n''','''        def user_returned_to_termux(screen: dict) -> bool:\n            nonlocal left_termux, termux_return_candidate_at\n            package = str(screen.get("package") or "")\n            now = time.monotonic()\n            if package and package not in TERMUX_PACKAGES:\n                left_termux = True; termux_return_candidate_at = 0.0; return False\n            if left_termux and package in TERMUX_PACKAGES:\n                if termux_return_candidate_at <= 0.0:\n                    termux_return_candidate_at = now; return False\n                return now - termux_return_candidate_at >= 0.75\n            termux_return_candidate_at = 0.0\n            return False\n''',1)
agent.write_text(a,encoding='utf-8')
c=chat.read_text(encoding='utf-8')
start=c.find('    class ConfirmScreen(ModalScreen[bool]):\n'); end=c.find('    class ChatApp(App[None]):\n',start)
if start >= 0 and end >= 0:
    confirm='''    class ConfirmScreen(ModalScreen[bool]):\n        BINDINGS = [\n            Binding("left", "choose_allow", "", show=False, priority=True),\n            Binding("right", "choose_cancel", "", show=False, priority=True),\n            Binding("enter", "confirm", "", show=False, priority=True),\n            Binding("escape", "cancel", "", show=False, priority=True),\n        ]\n        def __init__(self) -> None:\n            super().__init__(); self._allow_selected=True\n        def _body(self) -> str:\n            a="[bold bright_cyan]› Izinkan[/]" if self._allow_selected else "  Izinkan"\n            b="[bold bright_cyan]› Batal[/]" if not self._allow_selected else "  Batal"\n            return "[bold]Furina perlu menggunakan layar untuk menjalankan perintah ini.[/]\\n\\n"+a+"        "+b+"\\n\\n[dim]← → pilih · Enter konfirmasi · Esc batal[/]"\n        def compose(self) -> ComposeResult: yield Static(self._body(), id="confirm-box", markup=True)\n        def _refresh_choice(self) -> None: self.query_one("#confirm-box", Static).update(self._body())\n        def action_choose_allow(self) -> None: self._allow_selected=True; self._refresh_choice()\n        def action_choose_cancel(self) -> None: self._allow_selected=False; self._refresh_choice()\n        def action_confirm(self) -> None: self.dismiss(bool(self._allow_selected))\n        def action_cancel(self) -> None: self.dismiss(False)\n\n'''
    c=c[:start]+confirm+c[end:]
c=c.replace('Binding("escape", "back", "", show=False, priority=True)','Binding("escape", "back", "", show=False)',1)
chat.write_text(c,encoding='utf-8')
version.write_text(version.read_text(encoding='utf-8').replace('1.0.0-rc19','1.0.0-rc20',1),encoding='utf-8')
PY
fi
mark 68 "Menerapkan Core RC20"

PYTHONPATH="$STAGE/core" python -m compileall -q "$STAGE/core/furina_agent"
PYTHONPATH="$STAGE/core" python - <<'PY'
from furina_agent.version import VERSION
from furina_agent.agent import AndroidAgent
assert VERSION == '1.0.0-rc20', VERSION
assert hasattr(AndroidAgent, '_compile_ui_sequence')
assert hasattr(AndroidAgent, '_try_ui_sequence')
PY
mark 84 "Memvalidasi Core dan executor"

if [[ "$CURRENT" != "1.0.0-rc20" ]]; then
  rm -rf "$ROOT/core.prev"
  mv "$ROOT/core" "$ROOT/core.prev"
  mv "$STAGE/core" "$ROOT/core"
fi
mark 94 "Mempertahankan memory dan model"
mark 100 "Update selesai"
printf '\n\033[32m✓\033[0m Furina Core RC20 siap.\n'
printf '\033[2mJalankan:\033[0m \033[1;36mfurina\033[0m\n\n'
