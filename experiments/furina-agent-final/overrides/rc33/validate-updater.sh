#!/usr/bin/env bash
set -euo pipefail

REPO="$(git rev-parse --show-toplevel)"
INSTALL="$REPO/experiments/furina-agent-final/install.sh"

bash -n "$INSTALL"

python3 - "$INSTALL" <<'PY'
import pathlib,sys
text=pathlib.Path(sys.argv[1]).read_text(encoding='utf-8')

required=(
    'run_quiet "Memeriksa lingkungan Termux"',
    'Memeriksa manifest dan versi target',
    'Memverifikasi integritas paket RC33',
    'Merekonstruksi fondasi Core RC32',
    'Membuat salinan aman Core',
    'Menerapkan Psyche continuity RC33',
    'Memeriksa syntax dan import seluruh Core',
    'Menjalankan regression lokal Psyche, routing, dan policy',
    'Memasang Core secara atomik',
    'Core RC33 terverifikasi sehat; tidak ada file yang diubah',
    'Log lengkap:',
)
for marker in required:
    assert marker in text, marker

# RC33 yang sudah aktif tidak boleh lagi keluar sebelum health-check.
old_early_exit='''if [[ "$CURRENT" == "1.0.0-rc33" ]]; then
  echo "✓ Core RC33 sudah aktif."
  exit 0
fi'''
assert old_early_exit not in text

body=text[text.rfind('\nui_title\n')+1:]
order=(
    'run_quiet "Memeriksa lingkungan Termux"',
    'run_quiet "Memeriksa manifest dan versi target"',
    'run_quiet "Memverifikasi integritas paket RC33"',
    'run_quiet "Membuat salinan aman Core"',
    'run_quiet "Memeriksa syntax dan import seluruh Core"',
    'run_quiet "Menjalankan regression lokal Psyche, routing, dan policy"',
)
pos=-1
for marker in order:
    new=body.find(marker)
    assert new > pos, (marker,pos,new)
    pos=new

# Health-check perangkat harus benar-benar menguji Psyche, role routing,
# persona migration dan RC32 Action Firewall, bukan hanya menampilkan progress.
for marker in (
    "p.state['long']['traits'] == before",
    "state.last_good('groq','conversation') == 'chat-model'",
    "'companion_state' not in response_src",
    "'RC32_POLICY_BOUNDARY' in agent_src",
    "runtime._handler_for('arbitrary_shell')",
):
    assert marker in text, marker

print('RC33_UPDATER_PROGRESS_AND_HEALTHCHECK_OK')
PY
