import json
import re

import requests

from core_constants import MAX_DURATION, MIN_SCORE


def _extract_balanced(text, start_index, open_ch, close_ch):
    if start_index < 0 or start_index >= len(text):
        return None
    if text[start_index] != open_ch:
        return None

    depth = 0
    in_str = False
    esc = False
    for i in range(start_index, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue

        if ch == '"':
            in_str = True
            continue

        if ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                return text[start_index : i + 1]
    return None


def _extract_assigned_json(text, var_name):
    m = re.search(rf"(?:var\s+)?{re.escape(var_name)}\s*=\s*", text)
    if not m:
        return None
    start = text.find("{", m.end())
    if start < 0:
        return None
    raw = _extract_balanced(text, start, "{", "}")
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


def _walk_json(obj):
    stack = [obj]
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            yield cur
            for v in cur.values():
                stack.append(v)
        elif isinstance(cur, list):
            for v in cur:
                stack.append(v)


def _collect_heat_markers(root):
    found = []
    for d in _walk_json(root):
        if "heatMarkerRenderer" in d and isinstance(d.get("heatMarkerRenderer"), dict):
            found.append(d["heatMarkerRenderer"])
        markers = d.get("markers")
        if isinstance(markers, list):
            for it in markers:
                if isinstance(it, dict) and "heatMarkerRenderer" in it and isinstance(it.get("heatMarkerRenderer"), dict):
                    found.append(it["heatMarkerRenderer"])
                elif isinstance(it, dict):
                    found.append(it)
        heat_markers = d.get("heatMarkers")
        if isinstance(heat_markers, list):
            for it in heat_markers:
                if isinstance(it, dict) and "heatMarkerRenderer" in it and isinstance(it.get("heatMarkerRenderer"), dict):
                    found.append(it["heatMarkerRenderer"])
    return found


def _norm_score(marker):
    for k in ("intensityScoreNormalized", "heatMarkerIntensityScoreNormalized", "heatMarkerIntensityScore", "intensityScore"):
        try:
            v = marker.get(k)
            if v is None:
                continue
            return float(v)
        except Exception:
            continue
    return 0.0


def _norm_start_duration(marker):
    start_keys = ("startMillis", "timeRangeStartMillis")
    dur_keys = ("durationMillis", "timeRangeDurationMillis")
    start_ms = None
    dur_ms = None
    for k in start_keys:
        if k in marker:
            start_ms = marker.get(k)
            break
    for k in dur_keys:
        if k in marker:
            dur_ms = marker.get(k)
            break
    if start_ms is None or dur_ms is None:
        return None
    try:
        start_s = float(start_ms) / 1000.0
        dur_s = float(dur_ms) / 1000.0
        return start_s, dur_s
    except Exception:
        return None


def ambil_most_replayed(video_id, min_score=None, fallback_limit=10):
    url = f"https://www.youtube.com/watch?v={video_id}"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept-Language": "en-US,en;q=0.9,id;q=0.8",
    }

    html = ""
    try:
        html = requests.get(url, headers=headers, timeout=20).text
        if "consent.youtube.com" in html or "Before you continue to YouTube" in html:
            html = requests.get(url, headers=headers, cookies={"CONSENT": "YES+1"}, timeout=20).text
    except Exception:
        return []

    all_markers = []

    pos = html.find('"markers"')
    if pos >= 0:
        arr_start = html.find("[", pos)
        raw_arr = _extract_balanced(html, arr_start, "[", "]")
        if raw_arr:
            try:
                markers = json.loads(raw_arr)
                if isinstance(markers, list):
                    all_markers.extend(markers)
            except Exception:
                pass

    for var_name in ("ytInitialPlayerResponse", "ytInitialData"):
        root = _extract_assigned_json(html, var_name)
        if root:
            all_markers.extend(_collect_heat_markers(root))

    normalized = {}
    for marker in all_markers:
        if not isinstance(marker, dict):
            continue
        if "heatMarkerRenderer" in marker and isinstance(marker.get("heatMarkerRenderer"), dict):
            marker = marker["heatMarkerRenderer"]

        sd = _norm_start_duration(marker)
        if not sd:
            continue
        start_s, dur_s = sd
        if dur_s <= 0:
            continue
        score = _norm_score(marker)
        key = (int(start_s * 1000), int(dur_s * 1000))
        prev = normalized.get(key)
        if prev is None or score > prev["score"]:
            normalized[key] = {
                "start": start_s,
                "duration": min(dur_s, float(MAX_DURATION)),
                "score": float(score),
            }

    items = list(normalized.values())
    items.sort(key=lambda x: x["score"], reverse=True)

    threshold = MIN_SCORE if min_score is None else float(min_score)
    filtered = [it for it in items if it["score"] >= threshold]
    if filtered:
        return filtered
    return items[: max(1, int(fallback_limit))]

