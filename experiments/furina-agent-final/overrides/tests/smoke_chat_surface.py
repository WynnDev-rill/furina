#!/usr/bin/env python3
from __future__ import annotations

import asyncio

from textual.app import App


def smoke_run(self, *args, **kwargs):
    async def go():
        async with self.run_test(size=(72, 28)) as pilot:
            await pilot.pause()
            ids = {w.id for w in self.query("*") if getattr(w, "id", None)}
            required = {"header", "messages", "status", "composer"}
            missing = required - ids
            if missing:
                raise SystemExit(f"RC11 chat surface missing widgets: {sorted(missing)}")
            composer = self.query_one("#composer")
            if self.focused is not composer:
                raise SystemExit("RC11 composer did not receive focus")
            print("RC11_CHAT_SURFACE_MOUNT_OK")

    asyncio.run(go())


App.run = smoke_run

from furina_agent.chat_surface import run_chat_surface

run_chat_surface()
