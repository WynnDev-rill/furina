#!/usr/bin/env python3
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT=Path(sys.argv[1] if len(sys.argv)>1 else "/tmp/furina-agent-rc54-validate/termux")
PATH=ROOT/"core/furina_agent/chat.py"
text=PATH.read_text(encoding="utf-8")

# Historical final-stage chat no longer guarantees the old
# _relationship_context helper. Local Fast Path owns a compact relationship
# serializer so prompt generation does not depend on an obsolete method name.
if "def _local_relationship_context" not in text:
    tree=ast.parse(text)
    cls=next((n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=="FurinaChat"),None)
    if cls is None: raise SystemExit("FurinaChat missing")
    target=next((n for n in cls.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name=="_messages"),None)
    if target is None: raise SystemExit("FurinaChat._messages missing")
    lines=text.splitlines(keepends=True)
    pos=sum(len(x) for x in lines[:target.lineno-1])
    method='''    def _local_relationship_context(self) -> str:\n        try:\n            s = self.store.relationship_state()\n        except Exception:\n            return "Relasi: pasangan; gunakan continuity percakapan secara natural."\n        if not isinstance(s, dict):\n            return "Relasi: pasangan; gunakan continuity percakapan secara natural."\n        parts = ["Relasi: pasangan"]\n        for key in ("closeness", "trust", "friction", "playfulness"):\n            try:\n                if key in s: parts.append(f"{key}={float(s[key]):.2f}")\n            except Exception:\n                pass\n        return "; ".join(parts) + "."\n\n'''
    text=text[:pos]+method+text[pos:]

text=text.replace("self._relationship_context()[:500]", "self._local_relationship_context()[:500]")
PATH.write_text(text,encoding="utf-8")
compile(text,str(PATH),"exec")
print("FURINA_PRIVATE_1_0_3_CHAT_FIXUP_OK")
