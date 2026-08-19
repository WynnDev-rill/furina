#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("rc60_apply", HERE / "apply.py")
assert SPEC and SPEC.loader
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)

SOURCE = '''class Runtime:\n    def get_update_status(self) -> dict:\n        return {"old": True}\n\n    def get_model_status(self) -> dict:\n        return {}\n\n    def _set_update_status(self, **values) -> None:\n        self.x = values\n\n    @staticmethod\n    def helper_between_status_methods():\n        return "keep"\n\n    def _run_core_update(self) -> None:\n        self.old = True\n\n    def helper_inserted_by_previous_patch(self):\n        return "must survive"\n\n    def chat(self, text: str, image=None, plugins=None, extra=False) -> dict:\n        return {"text": text, "extra": extra}\n'''

out = MOD.replace_class_method(
    SOURCE,
    "Runtime",
    "_run_core_update",
    '''    def _run_core_update(self) -> None:\n        self.new = True\n''',
)
assert "self.new = True" in out
assert "self.old = True" not in out
assert "helper_inserted_by_previous_patch" in out
assert "extra=False" in out

out = MOD.replace_class_method(
    out,
    "Runtime",
    "_set_update_status",
    '''    def _set_update_status(self, **values) -> None:\n        self.new_status = values\n''',
)
assert "self.new_status = values" in out
assert "helper_between_status_methods" in out
compile(out, "rc60-boundary-regression", "exec")
print("FURINA_RC60_AST_BOUNDARY_REGRESSION_OK")
