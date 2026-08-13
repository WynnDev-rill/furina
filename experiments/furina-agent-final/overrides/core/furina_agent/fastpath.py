from __future__ import annotations

import json
import math
import re
import time
from dataclasses import dataclass


_EXTERNAL = re.compile(r"\b(?:send|kirim|post|publish|bagikan|share|call|panggil|telepon|submit|unggah|upload|reply|balas|bayar|transfer|beli|purchase)\b", re.I)
_SEARCH = re.compile(r"\b(?:cari|carikan|search|telusur|telusuri)\b", re.I)
_WRITE = re.compile(r"\b(?:tulis|tuliskan|ketik|ketikkan|isi|isikan|catat|catatkan)\b", re.I)
_SCROLL = re.compile(r"\b(?:scroll|geser|swipe)\b", re.I)
_OPEN = re.compile(r"\b(?:buka|open|jalankan)\b", re.I)
_COMPLEX = re.compile(r"\b(?:kalau|jika|sampai|setelah itu kalau|pilih yang|yang paling|bandingkan)\b", re.I)


@dataclass
class FastSkill:
    id: int
    score: float
    package: str
    steps: list[dict]
    success_count: int
    failure_count: int


def goal_tags(goal: str) -> set[str]:
    text = str(goal or "")
    tags: set[str] = set()
    if _OPEN.search(text): tags.add("buka")
    if _SEARCH.search(text): tags.add("cari")
    if _WRITE.search(text): tags.add("tulis")
    if _SCROLL.search(text): tags.add("scroll")
    if _EXTERNAL.search(text): tags.add("external")
    return tags


def _requested_scrolls(goal: str) -> int:
    low = str(goal or "").casefold()
    values: list[int] = []
    for m in re.finditer(r"(?:scroll|geser|swipe)[^0-9]{0,14}(\d{1,2})\s*(?:x|kali)?|(\d{1,2})\s*(?:x|kali)\s*(?:scroll|geser|swipe)", low):
        raw = m.group(1) or m.group(2)
        if raw:
            values.append(max(1, min(int(raw), 20)))
    if values:
        return max(values)
    return 1 if _SCROLL.search(low) else 0


def _quoted_or_tail(goal: str, verb_pattern: str) -> str:
    text = " ".join(str(goal or "").split())
    quoted = re.search(verb_pattern + r"[^\"'“”]{0,22}[\"“']([^\"'“”]{1,320})[\"”']", text, re.I)
    if quoted:
        return quoted.group(1).strip()[:320]
    m = re.search(verb_pattern + r"(?:kan)?(?:\s+(?:teks|pesan|catatan|tentang))?\s*[:=-]?\s*(.{1,320}?)(?:\s+(?:lalu|terus|kemudian|di aplikasi|ke aplikasi)\b|$)", text, re.I)
    if not m:
        return ""
    value = m.group(1).strip(" \t\r\n\"'“”")
    return value[:320]


def dynamic_text(goal: str) -> str:
    if _SEARCH.search(goal):
        value = _quoted_or_tail(goal, r"\b(?:cari|carikan|search|telusur|telusuri)\b")
        if value:
            return value
    if _WRITE.search(goal):
        return _quoted_or_tail(goal, r"\b(?:tulis|tuliskan|ketik|ketikkan|isi|isikan|catat|catatkan)\b")
    return ""


def _match_package(goal: str, apps: list[dict]) -> str:
    low = str(goal or "").casefold()
    candidates: list[tuple[int, str]] = []
    for app in apps:
        if not isinstance(app, dict):
            continue
        label = str(app.get("label") or "").strip()
        package = str(app.get("package") or "").strip()
        if not package:
            continue
        if label and label.casefold() in low:
            candidates.append((len(label), package))
        package_tail = package.rsplit(".", 1)[-1].replace("_", " ").replace("-", " ")
        if len(package_tail) >= 4 and package_tail.casefold() in low:
            candidates.append((len(package_tail), package))
    return max(candidates, default=(0, ""))[1]


def compile_fast_contract(goal: str, apps: list[dict]) -> dict | None:
    """Compile common explicit device tasks without an LLM call.

    Complex/conditional/external tasks deliberately fall back to the normal
    contract compiler. The fast compiler only handles things that can be
    described from explicit verbs and installed-app labels.
    """
    text = " ".join(str(goal or "").split())
    tags = goal_tags(text)
    if not tags or "external" in tags or _COMPLEX.search(text):
        return None
    if not (tags & {"buka", "cari", "tulis", "scroll"}):
        return None
    package = _match_package(text, apps)
    write_text = dynamic_text(text) if tags & {"cari", "tulis"} else ""
    scrolls = _requested_scrolls(text)
    # Search/write without an extractable value is ambiguous; let the LLM parse it.
    if ("cari" in tags or "tulis" in tags) and not write_text:
        return None
    # Opening a named app should resolve to an installed package. Scrolling the
    # current app is allowed without a package.
    if "buka" in tags and not package:
        return None

    criteria: list[str] = []
    if package:
        criteria.append(f"aplikasi target {package} aktif")
    if "cari" in tags:
        criteria.append(f"hasil pencarian untuk {write_text[:120]} tampil")
    elif "tulis" in tags:
        criteria.append("teks yang diminta benar-benar masuk ke field")
    if scrolls:
        criteria.append(f"scroll yang diminta benar-benar terjadi {scrolls} kali")
    if not criteria:
        return None
    return {
        "summary": text[:300],
        "criteria": criteria[:5],
        "external_expected": False,
        "required_scrolls": scrolls,
        "required_write_text": write_text,
        "target_package": package,
        "fast_tags": sorted(tags),
    }


def _step_types(steps: list[dict]) -> set[str]:
    return {str(s.get("type") or "") for s in steps if isinstance(s, dict)}


def _skill_compatible(tags: set[str], steps: list[dict]) -> bool:
    types = _step_types(steps)
    if "external" in tags:
        return False
    if "cari" in tags and not ({"set_text", "ime_action"} <= types):
        return False
    if "tulis" in tags and "set_text" not in types:
        return False
    if "scroll" in tags and not (types & {"scroll_node", "scroll_global", "swipe"}):
        return False
    if tags == {"buka"} and types - {"open_app"}:
        return False
    return bool(types)


def choose_fast_skill(store, goal: str, package: str, min_successes: int = 2) -> FastSkill | None:
    tags = goal_tags(goal)
    if "external" in tags:
        return None
    rows = store._conn().execute(
        "SELECT * FROM learned_skills WHERE success_count>=? ORDER BY last_success_at DESC LIMIT 160",
        (max(2, int(min_successes)),),
    ).fetchall()
    now = time.time()
    best: FastSkill | None = None
    for row in rows:
        row_package = str(row["app_package"] or "")
        if package and row_package and row_package != package:
            continue
        try:
            steps = json.loads(row["steps_json"] or "[]")
        except Exception:
            continue
        if not isinstance(steps, list) or not _skill_compatible(tags, steps):
            continue
        wins = max(0, int(row["success_count"] or 0))
        fails = max(0, int(row["failure_count"] or 0))
        reliability = (wins + 1.0) / (wins + fails + 2.0)
        if reliability < 0.72 or fails > max(2, wins // 2):
            continue
        age_days = max(0.0, (now - float(row["last_success_at"] or now)) / 86400.0)
        recency = math.exp(-age_days / 30.0)
        goal_meta = str(row["goal_text"] or "").casefold()
        intent_hits = sum(1 for tag in tags if tag in goal_meta)
        intent_score = intent_hits / max(1, len(tags))
        package_score = 1.0 if package and row_package == package else 0.45 if not package else 0.0
        score = 0.43 * reliability + 0.27 * intent_score + 0.18 * package_score + 0.12 * recency
        candidate = FastSkill(int(row["id"]), score, row_package, steps[:14], wins, fails)
        if score >= 0.72 and (best is None or score > best.score):
            best = candidate
    return best


def _node_matches(node: dict, target: dict) -> bool:
    if not isinstance(node, dict) or not isinstance(target, dict):
        return False
    view = str(target.get("view_id") or "")
    if view and str(node.get("view_id") or "") != view:
        return False
    cls = str(target.get("class") or "")
    if cls and str(node.get("class") or "") != cls:
        return False
    for flag in ("editable", "scrollable"):
        if bool(target.get(flag)) and not bool(node.get(flag)):
            return False
    return bool(view or cls or target.get("editable") or target.get("scrollable"))


def materialize_step(step: dict, screen: dict, current_text: str) -> dict | None:
    if not isinstance(step, dict):
        return None
    typ = str(step.get("type") or "")
    if typ == "open_app":
        package = str(step.get("package") or "")
        return {"type": "open_app", "package": package} if package else None
    if typ == "scroll_global":
        return {"type": "scroll_global", "direction": str(step.get("direction") or "forward"), "distance": 0.62}
    if typ not in {"tap_node", "long_press", "scroll_node", "set_text", "ime_action"}:
        return None
    target = step.get("target") if isinstance(step.get("target"), dict) else {}
    matches = [n for n in (screen.get("nodes") or []) if isinstance(n, dict) and _node_matches(n, target)]
    # Ambiguous selectors are not replayed blindly. The normal planner can resolve them.
    if len(matches) != 1:
        return None
    node = matches[0]
    action: dict = {"type": typ, "node": node.get("id")}
    if typ == "set_text":
        if step.get("input") != "from_current_goal" or not current_text:
            return None
        action["text"] = current_text
    if typ == "scroll_node":
        action["direction"] = str(step.get("direction") or "forward")
    if typ == "long_press":
        action["duration_ms"] = 650
    return action


def event_sequence(store, screen: dict | None = None) -> int:
    values: list[int] = []
    if isinstance(screen, dict):
        try:
            values.append(int(screen.get("event_seq", 0) or 0))
        except Exception:
            pass
    try:
        event = store.get_state("device_last_event", {})
        if isinstance(event, dict):
            values.append(int(event.get("seq", 0) or 0))
    except Exception:
        pass
    return max(values, default=0)


def wait_for_event(store, before_seq: int, timeout_ms: int = 650, poll_ms: int = 35, cancel_event=None) -> bool:
    deadline = time.monotonic() + max(0.08, min(float(timeout_ms) / 1000.0, 1.8))
    interval = max(0.015, min(float(poll_ms) / 1000.0, 0.12))
    while time.monotonic() < deadline:
        if cancel_event is not None and cancel_event.is_set():
            return False
        try:
            event = store.get_state("device_last_event", {})
            if isinstance(event, dict) and int(event.get("seq", 0) or 0) > int(before_seq):
                return True
        except Exception:
            pass
        time.sleep(interval)
    return False
