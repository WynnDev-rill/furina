#!/usr/bin/env python3
from __future__ import annotations
import pathlib,sys

def rep(text,old,new,label):
    if new in text and old not in text: return text
    n=text.count(old)
    if n!=1: raise SystemExit(f'Bridge RC15 postfix marker mismatch {label}: {n}')
    return text.replace(old,new,1)

def main():
    if len(sys.argv)!=2: raise SystemExit('usage: apply-stateful-bridge-rc15-postfix.py <termux-root>')
    root=pathlib.Path(sys.argv[1]).resolve(); service=root/'bridge/app/src/main/java/com/wynndev/furinaagentbridge/FurinaAccessibilityService.java'
    if not service.is_file(): raise SystemExit('missing Bridge RC15 service')
    s=service.read_text(encoding='utf-8')
    s=rep(s,
'''        if ("message".equals(normalizedRole) && bestScore < 0) return null;
        if ("search".equals(normalizedRole) && bestScore < 40) return null;
''',
'''        if ("message".equals(normalizedRole) && bestScore < 0 && count != 1) return null;
        if ("search".equals(normalizedRole) && bestScore < 40 && count != 1) return null;
''','single editable fallback')
    service.write_text(s,encoding='utf-8')
    if 'bestScore < 40 && count != 1' not in s: raise SystemExit('Bridge RC15 postfix incomplete')
    print('Furina Bridge RC15 single-editable fallback: OK')

if __name__=='__main__': main()
