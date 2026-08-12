from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request
from pathlib import Path

from .config import Config, save_config


class BridgeError(RuntimeError):
    pass


class AndroidBridge:
    def __init__(self, cfg: Config):
        self.cfg = cfg

    @property
    def base_url(self) -> str:
        return f"http://{self.cfg.bridge_host}:{self.cfg.bridge_port}"

    def _request(self, method: str, path: str, payload: dict | None = None, timeout: int = 10, *, authenticated: bool = True):
        headers = {}
        if authenticated and self.cfg.bridge_token:
            headers["X-Furina-Token"] = self.cfg.bridge_token
        data = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(payload).encode()
        req = urllib.request.Request(self.base_url + path, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                body = r.read()
                if r.headers.get_content_type() == "application/json":
                    return json.loads(body.decode("utf-8"))
                return body
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            raise BridgeError(f"Bridge HTTP {e.code}: {body[:500]}") from e
        except Exception as e:
            raise BridgeError(f"Bridge tidak dapat dihubungi: {e}") from e

    def health(self):
        return self._request("GET", "/health", authenticated=False)

    def auto_pair(self) -> bool:
        result = self._request("GET", "/bootstrap", authenticated=False, timeout=4)
        token = str(result.get("token") or "").strip() if isinstance(result, dict) else ""
        if not token:
            return False
        self.cfg.bridge_token = token
        save_config(self.cfg)
        return True

    def ensure_paired(self) -> bool:
        try:
            self.apps()
            return True
        except Exception:
            pass
        try:
            return self.auto_pair()
        except Exception:
            return False

    def screen(self):
        return self._request("GET", "/screen")

    def apps(self):
        return self._request("GET", "/apps")

    def action(self, action: dict):
        return self._request("POST", "/action", action)

    def screenshot_base64(self) -> str:
        result = self._request("GET", "/screenshot", timeout=20)
        if isinstance(result, dict):
            return str(result.get("png_base64") or "")
        if isinstance(result, (bytes, bytearray)):
            return base64.b64encode(bytes(result)).decode("ascii")
        return ""

    def screenshot(self, output: Path) -> Path:
        data = base64.b64decode(self.screenshot_base64())
        output.write_bytes(data)
        return output
