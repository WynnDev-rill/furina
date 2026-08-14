#!/usr/bin/env python3
from __future__ import annotations
import pathlib,sys

def rep(text,old,new,label):
    if new in text and old not in text: return text
    n=text.count(old)
    if n!=1: raise SystemExit(f'RC24 marker mismatch {label}: {n}')
    return text.replace(old,new,1)

def main():
    if len(sys.argv)!=2: raise SystemExit('usage: apply-lifecycle-core-rc24.py <termux-root>')
    root=pathlib.Path(sys.argv[1]).resolve(); core=root/'core/furina_agent'
    agent=core/'agent.py'; version=core/'version.py'
    for p in (agent,version):
        if not p.is_file(): raise SystemExit(f'missing RC24 source: {p}')
    a=agent.read_text(encoding='utf-8')

    a=rep(a,
'''        left_termux = False
        termux_return_candidate_at = 0.0
        cancel_event = threading.Event()
''',
'''        left_termux = False
        termux_return_candidate_at = 0.0
        last_external_screen: dict | None = None
        cancel_event = threading.Event()
''','lifecycle state')

    a=rep(a,'                    elif now - returned_at >= 0.75:\n','                    elif now - returned_at >= 0.12:\n','return debounce watcher')

    a=rep(a,
'''        def completed(result: str, final_screen: dict) -> str:
            if getattr(self.cfg, "skill_learning_enabled", True):
''',
'''        def completed(result: str, final_screen: dict) -> str:
            cancel_event.set()
            if getattr(self.cfg, "skill_learning_enabled", True):
''','completion stops watcher')

    a=rep(a,
'''            return result

        def user_returned_to_termux(screen: dict) -> bool:
            nonlocal left_termux, termux_return_candidate_at
''',
'''            clean = str(result or "").strip()
            return "Berhasil." if clean in {"", "Selesai", "Selesai."} else clean

        def return_to_termux_result(screen: dict | None = None) -> str:
            cancel_event.set()
            reference = last_external_screen if isinstance(last_external_screen, dict) else (screen if isinstance(screen, dict) else {})
            try:
                hard_ok, _reason = self._deterministic_gate(contract, reference, history)
            except Exception:
                hard_ok = False
            if hard_ok:
                self.store.log_event("agent_completed_on_user_return", {"goal": goal, "history": len(history)})
                return completed("Berhasil.", reference)
            self.store.penalize_skills(suggested_ids)
            self.store.log_event("agent_cancelled_user_return", {"goal": goal, "history": len(history)})
            return "Tugas dihentikan karena kamu kembali ke Termux."

        def user_returned_to_termux(screen: dict) -> bool:
            nonlocal left_termux, termux_return_candidate_at, last_external_screen
''','terminal return helper')

    a=rep(a,
'''            if package and package not in TERMUX_PACKAGES:
                left_termux = True
                termux_return_candidate_at = 0.0
                return False
''',
'''            if package and package not in TERMUX_PACKAGES:
                left_termux = True
                last_external_screen = screen
                termux_return_candidate_at = 0.0
                return False
''','remember external screen')

    a=rep(a,'                return now - termux_return_candidate_at >= 0.75\n','                return now - termux_return_candidate_at >= 0.12\n','snapshot return debounce')

    a=rep(a,
'''        sequence_result, sequence_screen, sequence_attempted = self._try_ui_sequence(
            goal, contract, apps, approve, task_authorized, history, semantic_steps
        )
        if sequence_result is not None:
            if sequence_screen is not None:
                return completed(sequence_result, sequence_screen)
            return sequence_result
''',
'''        sequence_result, sequence_screen, sequence_attempted = self._try_ui_sequence(
            goal, contract, apps, approve, task_authorized, history, semantic_steps
        )
        if sequence_result == "__FURINA_USER_RETURN__":
            return return_to_termux_result(sequence_screen)
        if sequence_result is not None:
            if sequence_screen is not None:
                return completed(sequence_result, sequence_screen)
            cancel_event.set()
            return sequence_result
''','sequence return lifecycle')

    a=a.replace('                self.store.penalize_skills(suggested_ids)\n                self.store.log_event("agent_cancelled_user_return", {"goal": goal, "step": step_index + 1})\n                return "Tugas dihentikan karena kamu kembali ke Termux."\n','                return return_to_termux_result(screen)\n',1)
    a=a.replace('                    return "Tugas dihentikan karena kamu kembali ke Termux."\n','                    return return_to_termux_result(last_external_screen)\n',1)
    a=a.replace('                return "Tugas dihentikan karena kamu kembali ke Termux."\n','                return return_to_termux_result(last_external_screen)\n',1)
    a=a.replace('                self.store.penalize_skills(suggested_ids)\n                self.store.log_event("agent_cancelled_user_return", {"goal": goal, "step": step_index + 1})\n                return "Tugas dihentikan karena kamu kembali ke Termux."\n','                return return_to_termux_result(after_screen)\n',1)

    a=rep(a,
'''            screen = self.bridge.screen()
            if user_returned_to_termux(screen):
''',
'''            screen = self.bridge.screen()
            if cancel_event.is_set():
                return return_to_termux_result(screen)
            if user_returned_to_termux(screen):
''','loop preflight cancel')

    a=rep(a,
'''        try:
            result = self.tools.execute({"type": "run_ui_sequence", "steps": steps})
''',
'''        try:
            result = self.tools.execute({"type": "run_ui_sequence", "steps": steps})
''','sequence execute anchor')
    a=rep(a,
'''        completed = max(0, min(int(result.get("completed_steps", 0) or 0), len(steps))) if isinstance(result, dict) else 0
''',
'''        if isinstance(result, dict) and result.get("cancelled_user_return"):
            try:
                screen = self.bridge.screen()
            except Exception:
                screen = None
            return "__FURINA_USER_RETURN__", screen, True
        completed = max(0, min(int(result.get("completed_steps", 0) or 0), len(steps))) if isinstance(result, dict) else 0
''','sequence cancellation result')

    agent.write_text(a,encoding='utf-8')
    v=version.read_text(encoding='utf-8')
    v=rep(v,'VERSION = "1.0.0-rc23"','VERSION = "1.0.0-rc24"','core version')
    version.write_text(v,encoding='utf-8')
    for p in (agent,version): compile(p.read_text(encoding='utf-8'),str(p),'exec')
    checks=[(agent,'agent_completed_on_user_return'),(agent,'return_to_termux_result'),(agent,'>= 0.12'),(agent,'__FURINA_USER_RETURN__'),(version,'VERSION = "1.0.0-rc24"')]
    missing=[n for p,n in checks if n not in p.read_text(encoding='utf-8')]
    if missing: raise SystemExit('RC24 Core incomplete: '+', '.join(missing))
    print('Furina Core RC24 terminal lifecycle: OK')

if __name__=='__main__': main()
