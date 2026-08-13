#!/usr/bin/env python3
from __future__ import annotations
import pathlib, sys


def rep(text: str, old: str, new: str, label: str) -> str:
    if new in text and old not in text:
        return text
    n=text.count(old)
    if n!=1:
        raise SystemExit(f'RC22 marker mismatch {label}: {n}')
    return text.replace(old,new,1)


def main():
    if len(sys.argv)!=2: raise SystemExit('usage: apply-system-rc22.py <termux-root>')
    root=pathlib.Path(sys.argv[1]).resolve(); core=root/'core/furina_agent'
    config=core/'config.py'; providers=core/'providers.py'; routing=core/'routing.py'; companion=core/'companion.py'; chat_surface=core/'chat_surface.py'; tui=core/'tui.py'; version=core/'version.py'
    for p in (config,providers,routing,companion,chat_surface,tui,version):
        if not p.is_file(): raise SystemExit(f'missing RC22 source: {p}')

    c=config.read_text()
    c=rep(c,'    config_revision: int = 11','    config_revision: int = 12','config revision')
    c=rep(c,'    routing_mode: str = "local"','    routing_mode: str = "auto"','default auto routing')
    c=rep(c,'    provider_max_models: int = 5\n','''    provider_max_models: int = 3
    provider_request_timeout_seconds: int = 12
    provider_discovery_timeout_seconds: int = 6
    provider_total_budget_seconds: int = 24
    local_start_timeout_seconds: int = 30
''','provider latency config')
    c=rep(c,'    if defaults.get("routing_mode") not in {"local", "auto", "online"}:\n        defaults["routing_mode"] = "local"\n','    if defaults.get("routing_mode") not in {"local", "auto", "online"}:\n        defaults["routing_mode"] = "auto"\n','routing fallback')
    c=rep(c,'    defaults["memory_limit"] = max(3, min(int(defaults["memory_limit"]), 16))\n','''    defaults["memory_limit"] = max(3, min(int(defaults["memory_limit"]), 16))
    defaults["provider_max_models"] = max(1, min(int(defaults["provider_max_models"]), 5))
    defaults["provider_request_timeout_seconds"] = max(5, min(int(defaults["provider_request_timeout_seconds"]), 30))
    defaults["provider_discovery_timeout_seconds"] = max(3, min(int(defaults["provider_discovery_timeout_seconds"]), 15))
    defaults["provider_total_budget_seconds"] = max(10, min(int(defaults["provider_total_budget_seconds"]), 60))
    defaults["local_start_timeout_seconds"] = max(10, min(int(defaults["local_start_timeout_seconds"]), 60))
''','latency clamps')
    config.write_text(c)

    p=providers.read_text()
    p=rep(p,'    def list_models(self, *, force: bool = False) -> list[ModelInfo]:\n','    def list_models(self, *, force: bool = False, timeout_seconds: int | None = None) -> list[ModelInfo]:\n','model timeout signature')
    p=rep(p,'        raw = self._json("GET", self.base_url + "/models", timeout=20)\n','        raw = self._json("GET", self.base_url + "/models", timeout=timeout_seconds or int(getattr(self.cfg, "provider_discovery_timeout_seconds", 6)))\n','model timeout')
    p=rep(p,'    def candidate_models(self) -> list[ModelInfo]:\n        models = self.list_models()\n','    def candidate_models(self, *, timeout_seconds: int | None = None) -> list[ModelInfo]:\n        models = self.list_models(timeout_seconds=timeout_seconds)\n','candidate timeout')
    p=rep(p,'''        json_mode: bool,
    ) -> tuple[str, str]:''','''        json_mode: bool,
        timeout_seconds: int | None = None,
    ) -> tuple[str, str]:''','chat once signature')
    old_timeout='timeout=120'
    if p.count(old_timeout)!=2: raise SystemExit(f'RC22 marker mismatch provider timeouts: {p.count(old_timeout)}')
    p=p.replace(old_timeout,'timeout=timeout_seconds or int(getattr(self.cfg, "provider_request_timeout_seconds", 12))')
    p=rep(p,'''        json_mode: bool = False,
    ) -> str:
        normalized = normalize_messages(messages)
        answer, finish = self._chat_once(''','''        json_mode: bool = False,
        timeout_seconds: int | None = None,
    ) -> str:
        normalized = normalize_messages(messages)
        total_timeout = max(3, int(timeout_seconds or getattr(self.cfg, "provider_request_timeout_seconds", 12)))
        deadline = time.monotonic() + total_timeout
        answer, finish = self._chat_once(''','chat model deadline')
    p=rep(p,'''            temperature=temperature,
            json_mode=json_mode,
        )

        if not json_mode:''','''            temperature=temperature,
            json_mode=json_mode,
            timeout_seconds=max(2, int(deadline - time.monotonic())),
        )

        if not json_mode:''','first call deadline')
    p=rep(p,'''            for _ in range(self.cfg.response_continuations):
                if finish not in {"length", "max_tokens"}:
                    break
''','''            for _ in range(self.cfg.response_continuations):
                if finish not in {"length", "max_tokens"} or deadline - time.monotonic() < 2:
                    break
''','continuation budget')
    p=rep(p,'''                    temperature=temperature,
                    json_mode=False,
                )
''','''                    temperature=temperature,
                    json_mode=False,
                    timeout_seconds=max(2, int(deadline - time.monotonic())),
                )
''','continuation timeout')
    providers.write_text(p)

    r=routing.read_text()
    start=r.index('    def _online_chat('); end=r.index('    def vision(', start)
    new_online='''    def _online_chat(self, messages, *, max_tokens: int, temperature: float, json_mode: bool = False) -> str:
        self.last_failures = []
        configured = self.configured_online()
        if not configured:
            raise LLMError("Belum ada API key online yang dikonfigurasi.")

        deadline = time.monotonic() + max(10, int(getattr(self.cfg, "provider_total_budget_seconds", 24)))
        request_limit = max(5, int(getattr(self.cfg, "provider_request_timeout_seconds", 12)))
        discovery_limit = max(3, int(getattr(self.cfg, "provider_discovery_timeout_seconds", 6)))
        for name in configured:
            if deadline - time.monotonic() < 2:
                break
            key = self.secrets.get(name)
            if not key:
                continue
            provider = OpenAICompatibleProvider(name, key, self.cfg)
            tried: set[str] = set()

            last_good = provider.state.last_good(name)
            if last_good and not (name == "openrouter" and self.cfg.provider_prefer_free and not last_good.lower().endswith(":free")):
                tried.add(last_good)
                remaining = deadline - time.monotonic()
                if remaining >= 2:
                    try:
                        answer = provider.chat_model(
                            last_good, messages, max_tokens=max_tokens, temperature=temperature, json_mode=json_mode,
                            timeout_seconds=max(2, min(request_limit, int(remaining))),
                        )
                        self.last = RouteResult(name, last_good)
                        return answer
                    except ProviderError as e:
                        self.last_failures.append(f"{name}/{last_good}: {provider_error_summary(e)}")
                        if e.invalid_key or e.status is None:
                            continue

            remaining = deadline - time.monotonic()
            if remaining < 2:
                break
            try:
                candidates = provider.candidate_models(timeout_seconds=max(2, min(discovery_limit, int(remaining))))
            except ProviderError as e:
                self.last_failures.append(f"{name}: {provider_error_summary(e)}")
                continue

            for candidate in candidates:
                if candidate.id in tried:
                    continue
                remaining = deadline - time.monotonic()
                if remaining < 2:
                    break
                try:
                    answer = provider.chat_model(
                        candidate.id, messages, max_tokens=max_tokens, temperature=temperature, json_mode=json_mode,
                        timeout_seconds=max(2, min(request_limit, int(remaining))),
                    )
                    self.last = RouteResult(name, candidate.id)
                    return answer
                except ProviderError as e:
                    self.last_failures.append(f"{name}/{candidate.id}: {provider_error_summary(e)}")
                    if e.invalid_key or e.status is None:
                        break
                    continue
        if time.monotonic() >= deadline:
            self.last_failures.append("online: batas waktu failover tercapai")
        detail = "; ".join(self.last_failures[-5:])
        raise LLMError("Semua provider online gagal" + (f": {detail}" if detail else ""))

'''
    r=r[:start]+new_online+r[end:]
    r=rep(r,'from dataclasses import dataclass\nimport subprocess\n','from dataclasses import dataclass\nimport subprocess\nimport time\n','routing time import')
    r=rep(r,'            subprocess.run([str(launcher), "start"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=135, check=False)\n','            subprocess.run([str(launcher), "start"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=int(getattr(self.cfg, "local_start_timeout_seconds", 30)), check=False)\n','local startup timeout')
    routing.write_text(r)

    co=companion.read_text()
    co=rep(co,'        if _obvious_device_intent(text):\n            return Intent("device", text, 0.99)\n        routed_text = router_view(text)\n','''        if _obvious_device_intent(text):
            return Intent("device", text, 0.99)
        if not _DEVICE_VERBS.search(text):
            return Intent("chat", text, 0.99)
        routed_text = router_view(text)
''','fast chat routing')
    companion.write_text(co)

    cs=chat_surface.read_text()
    cs=rep(cs,'            pending.event.wait()\n            return pending.value\n','''            if not pending.event.wait(300):
                return False
            return pending.value
''','confirmation timeout')
    cs=rep(cs,'            except Exception:\n                self.call_from_thread(self._fail, assistant_id)\n','''            except Exception as exc:
                try:
                    self.session.store.log_event("chat_surface_error", {"error": str(exc)[:400]})
                except Exception:
                    pass
                self.call_from_thread(self._fail, assistant_id)
''','chat error logging')
    chat_surface.write_text(cs)

    t=tui.read_text()
    t=rep(t,'        console.print(f"\\n[dim]Routing[/]  [bold]{cfg.routing_mode.upper()}[/]")\n','        route_label = {"auto": "AUTO · ONLINE → LOCAL", "local": "LOCAL", "online": "ONLINE"}.get(cfg.routing_mode, cfg.routing_mode.upper())\n        console.print(f"\\n[dim]Routing[/]  [bold]{route_label}[/]")\n','routing label')
    t=rep(t,'''                    console.print("[green]Tersimpan lokal.[/]")
                    if cfg.routing_mode == "local" and _confirm("Aktifkan AUTO?", default=True):
                        cfg.routing_mode = "auto"
                        save_config(cfg)
''','''                    console.print("[green]Tersimpan lokal.[/]")
                    if cfg.routing_mode == "local":
                        cfg.routing_mode = "auto"
                        save_config(cfg)
                        console.print("[dim]Routing otomatis diubah ke AUTO · online dahulu, local jika provider tidak tersedia.[/]")
''','key auto routing')
    t=rep(t,'            picked = _choose("Routing", ["LOCAL", "AUTO", "ONLINE", "Back"], height=6)\n            if picked in {"LOCAL", "AUTO", "ONLINE"}:\n                cfg.routing_mode = {"LOCAL": "local", "AUTO": "auto", "ONLINE": "online"}[picked]\n','''            picked = _choose("Routing", ["AUTO · online → local", "LOCAL", "ONLINE", "Back"], height=6)
            if picked in {"AUTO · online → local", "LOCAL", "ONLINE"}:
                cfg.routing_mode = {"AUTO · online → local": "auto", "LOCAL": "local", "ONLINE": "online"}[picked]
''','routing chooser')
    t=rep(t,'    mode = _choose("Model", ["LOCAL", "AUTO", "ONLINE"], height=5)\n    if mode:\n        cfg.routing_mode = {"LOCAL": "local", "AUTO": "auto", "ONLINE": "online"}[mode]\n','''    mode = _choose("Model", ["AUTO · online → local", "LOCAL", "ONLINE"], height=5)
    if mode:
        cfg.routing_mode = {"AUTO · online → local": "auto", "LOCAL": "local", "ONLINE": "online"}[mode]
''','setup routing chooser')
    t=rep(t,'        choice = _choose("", ["Update Core", "Repair Bridge", "Setup ulang", "Back"], height=6)\n','        choice = _choose("", ["Update Furina", "Repair Bridge", "Setup ulang", "Back"], height=6)\n','update label')
    t=rep(t,'        if choice == "Update Core":\n            if _confirm("Pasang update Core? Memory dan model tetap disimpan.", default=True):\n','        if choice == "Update Furina":\n            if _confirm("Periksa update Furina? Core/Bridge hanya diperbarui jika memang perlu; memory dan model tetap disimpan.", default=True):\n','update prompt')
    t=rep(t,'def _show_due(console):\n    try:\n        due = MemoryStore().due_prospectives(time.time(), 3)\n','def _show_due(console):\n    store = MemoryStore()\n    try:\n        due = store.due_prospectives(time.time(), 3)\n','reminder store')
    t=rep(t,'    if not cfg.auto_start or cfg.routing_mode != "local" or not cfg.model_path or LocalLLM(cfg).health():\n        return\n','''    online_ready = bool(ProviderSecrets().configured())
    should_warm_local = cfg.routing_mode == "local" or (cfg.routing_mode == "auto" and not online_ready)
    if not cfg.auto_start or not should_warm_local or not cfg.model_path or LocalLLM(cfg).health():
        return
''','auto local warm')
    tui.write_text(t)

    v=version.read_text(); v=rep(v,'VERSION = "1.0.0-rc21"','VERSION = "1.0.0-rc22"','version'); version.write_text(v)
    for pth in (config,providers,routing,companion,chat_surface,tui,version): compile(pth.read_text(),str(pth),'exec')
    checks=[(config,'provider_total_budget_seconds: int = 24'),(routing,'batas waktu failover tercapai'),(companion,'if not _DEVICE_VERBS.search(text)'),(tui,'AUTO · ONLINE → LOCAL'),(tui,'store = MemoryStore()'),(version,'1.0.0-rc22')]
    missing=[n for pth,n in checks if n not in pth.read_text()]
    if missing: raise SystemExit('RC22 incomplete: '+', '.join(missing))
    print('Furina Core RC22 system screening fixes: OK')

if __name__=='__main__': main()
