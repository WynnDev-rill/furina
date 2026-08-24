#!/usr/bin/env python3
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/furina-agent-rc54-validate/termux")
PATH = ROOT / "core/furina_agent/memory.py"

text = PATH.read_text(encoding="utf-8")
tree = ast.parse(text)
cls = next((n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "MemoryStore"), None)
if cls is None:
    raise SystemExit("MemoryStore missing")
nodes = [n for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == "_query_dimensions"]
if len(nodes) != 1:
    raise SystemExit(f"_query_dimensions expected once, got {len(nodes)}")
node = nodes[0]
lines = text.splitlines(keepends=True)
start_line = min([node.lineno] + [d.lineno for d in node.decorator_list])
start = sum(len(x) for x in lines[:start_line - 1])
end = sum(len(x) for x in lines[:node.end_lineno])
replacement = r'''    @staticmethod
    def _query_dimensions(query: str) -> set[str]:
        q = " ".join(str(query or "").casefold().split())
        dims: set[str] = set()
        # Indonesian possessive forms are common in natural recall questions:
        # tujuanku, targetku, rencanaku, kesukaanku, kebiasaanku, profilku.
        if re.search(r"\b(suka|sukai|kusukai|kesukaan(?:ku)?|favorit(?:ku)?|favorite|preferensi(?:ku)?|benci|tidak suka|nggak suka)\b", q):
            dims.add("preference")
        if re.search(r"\b(tujuan(?:ku)?|target(?:ku)?|goal|rencana(?:ku)?|berencana|cita-cita(?:ku)?|ingin|mau)\b", q) or "tahun ini" in q:
            dims.add("goal")
        if re.search(r"\b(biasanya|sering|kebiasaan(?:ku)?|rutin|rutinitas(?:ku)?|kulakukan|lakukan)\b", q):
            dims.add("pattern")
        if re.search(r"\b(nama(?:ku)?|siapa aku|identitas(?:ku)?)\b", q):
            dims.add("identity")
        if re.search(r"\b(umur(?:ku)?|usia(?:ku)?|tinggal|lokasi(?:ku)?|kerja|pekerjaan(?:ku)?|profil(?:ku)?|tentang aku)\b", q):
            dims.add("profile")
        if re.search(r"\b(hubungan(?:ku)?|pasangan|relationship)\b", q):
            dims.add("relationship")
        if re.search(r"\b(kamu ingat apa|ingat apa saja|apa yang kamu ingat|apa saja yang kamu ingat|tentang diriku|tentang aku)\b", q):
            dims.update({"identity", "profile", "preference", "goal", "pattern", "relationship"})
        return dims'''
PATH.write_text(text[:start] + replacement.rstrip() + "\n" + text[end:], encoding="utf-8")
compile(PATH.read_text(encoding="utf-8"), str(PATH), "exec")
print("FURINA_PRIVATE_1_0_5_QUERY_DIMENSIONS_OK")
