#!/usr/bin/env python3
from __future__ import annotations
import pathlib,sys

def rep(text,old,new,label):
    if new in text and old not in text: return text
    n=text.count(old)
    if n!=1: raise SystemExit(f'RC25 postfix marker mismatch {label}: {n}')
    return text.replace(old,new,1)

def main():
    if len(sys.argv)!=2: raise SystemExit('usage: apply-stateful-core-rc25-postfix.py <termux-root>')
    root=pathlib.Path(sys.argv[1]).resolve(); companion=root/'core/furina_agent/companion.py'
    if not companion.is_file(): raise SystemExit('missing RC25 companion source')
    c=companion.read_text(encoding='utf-8')
    c=rep(c,
'''            out.append(step)
        return out

    @staticmethod
    def _requires_screen(steps: list[dict]) -> bool:
''',
'''            out.append(step)

        # Repair common model omissions without app-specific hardcoding.  If an
        # external send exists, a payload must be typed before it, and a search
        # result normally needs to be selected before typing into the next UI.
        send_index = next((i for i in range(len(out) - 1, -1, -1) if str(out[i].get("type") or "") == "send"), -1)
        if send_index >= 0:
            has_type = any(str(x.get("type") or "") == "type" and str(x.get("text") or "") for x in out[:send_index])
            send_text = str(out[send_index].get("text") or "")
            if not has_type and send_text:
                out.insert(send_index, {"type": "type", "text": send_text[:4000], "field_role": "message"})
                send_index += 1
            type_index = next((i for i in range(send_index - 1, -1, -1) if str(out[i].get("type") or "") == "type"), -1)
            if type_index >= 0:
                search_index = next((i for i in range(type_index - 1, -1, -1) if str(out[i].get("type") or "") == "search"), -1)
                if search_index >= 0 and not any(str(out[i].get("type") or "") in {"select", "tap"} for i in range(search_index + 1, type_index)):
                    query = str(out[search_index].get("query") or "").strip()
                    if query:
                        out.insert(search_index + 1, {"type": "select", "target": query[:180]})
        return out[:18]

    @staticmethod
    def _requires_screen(steps: list[dict]) -> bool:
''','semantic repair')
    companion.write_text(c,encoding='utf-8')
    compile(c,str(companion),'exec')
    if 'Repair common model omissions' not in c: raise SystemExit('RC25 postfix incomplete')
    print('Furina Core RC25 semantic repair postfix: OK')

if __name__=='__main__': main()
