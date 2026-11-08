import json
import os
import re
import time

import requests

from app.core_constants import MAX_DURATION, MIN_SCORE
from app.yt_utils import load_cookies_into_session


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
        m = re.search(rf'(?:window\[\s*"{re.escape(var_name)}"\s*\])\s*=\s*', text)
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


def _extract_ytcfg(text):
    m = re.search(r"ytcfg\.set\(\s*\{", text)
    if not m:
        return None
    start = text.find("{", m.end() - 1)
    if start < 0:
        return None
    raw = _extract_balanced(text, start, "{", "}")
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


def _walk_json(obj, max_nodes=None):
    stack = [obj]
    seen = 0
    limit = int(max_nodes) if max_nodes is not None else None
    while stack:
        cur = stack.pop()
        seen += 1
        if limit is not None and seen > limit:
            return
        if isinstance(cur, dict):
            yield cur
            for v in cur.values():
                stack.append(v)
        elif isinstance(cur, list):
            for v in cur:
                stack.append(v)


def _collect_heat_markers(root, max_nodes=None):
    found = []
    for d in _walk_json(root, max_nodes=max_nodes):
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


def _collect_chapter_starts(root, max_nodes=None):
    starts = []
    for d in _walk_json(root, max_nodes=max_nodes):
        cr = d.get("chapterRenderer")
        if not isinstance(cr, dict):
            continue
        start_ms = cr.get("timeRangeStartMillis")
        if start_ms is None:
            start_ms = cr.get("startMillis")
        if start_ms is None:
            continue
        try:
            starts.append(float(start_ms) / 1000.0)
        except Exception:
            continue
    starts = sorted(set(starts))
    return starts


def _build_chapter_segments(chapter_starts, duration_seconds):
    if not chapter_starts:
        return []
    if duration_seconds is None:
        return []
    try:
        dur_total = float(duration_seconds)
    except Exception:
        return []
    if dur_total <= 0:
        return []

    starts = [s for s in chapter_starts if 0 <= s < dur_total]
    if 0.0 not in starts:
        starts = [0.0] + starts
    starts = sorted(set(starts))

    items = []
    for i, s in enumerate(starts):
        next_s = dur_total if i + 1 >= len(starts) else starts[i + 1]
        end = min(next_s, s + float(MAX_DURATION), dur_total)
        if end - s <= 0:
            continue
        items.append({"start": float(s), "duration": float(end - s), "score": 0.0})
    return items


def _fetch_innertube_player(video_id, ytcfg, referer_url, headers_base, session=None):
    if not isinstance(ytcfg, dict):
        return None
    api_key = ytcfg.get("INNERTUBE_API_KEY")
    if not api_key:
        return None

    ctx = ytcfg.get("INNERTUBE_CONTEXT")
    if not isinstance(ctx, dict):
        client_version = (
            ytcfg.get("INNERTUBE_CONTEXT_CLIENT_VERSION")
            or ytcfg.get("INNERTUBE_CLIENT_VERSION")
            or ytcfg.get("INNERTUBE_CLIENT_VERSION_ALT")
        )
        client_name = ytcfg.get("INNERTUBE_CONTEXT_CLIENT_NAME") or ytcfg.get("INNERTUBE_CLIENT_NAME") or 1
        if not client_version:
            return None
        ctx = {"client": {"clientName": str(client_name), "clientVersion": str(client_version), "hl": "en", "gl": "US"}}

    client_name_hdr = ytcfg.get("INNERTUBE_CONTEXT_CLIENT_NAME") or ytcfg.get("INNERTUBE_CLIENT_NAME") or 1
    client_ver_hdr = ytcfg.get("INNERTUBE_CONTEXT_CLIENT_VERSION") or ytcfg.get("INNERTUBE_CLIENT_VERSION")
    if not client_ver_hdr:
        return None

    url = f"https://www.youtube.com/youtubei/v1/player?key={api_key}"
    headers = dict(headers_base or {})
    headers.update(
        {
            "Content-Type": "application/json",
            "Origin": "https://www.youtube.com",
            "Referer": referer_url,
            "X-Youtube-Client-Name": str(client_name_hdr),
            "X-Youtube-Client-Version": str(client_ver_hdr),
        }
    )
    payload = {"context": ctx, "videoId": str(video_id), "racyCheckOk": True, "contentCheckOk": True}
    timeout = (6, 20)
    try:
        sess = session or requests
        res = sess.post(url, headers=headers, json=payload, timeout=timeout)
        if not res.ok:
            return None
        data = res.json()
        if isinstance(data, dict):
            return data
    except Exception:
        return None
    return None


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


def _cluster_heatmap_peaks(markers, duration_seconds=None, target_duration=45.0, min_duration=25.0, max_duration=60.0, limit=10):
    """
    Mengelompokkan titik-titik heatmap puncak (Most Replayed) menjadi segmen Shorts
    berdurasi optimal (30-60 detik) dengan hook sebelum puncak dan resolusi setelahnya,
    serta Non-Maximum Suppression (NMS) untuk menghindari duplikasi tumpang-tindih.
    """
    if not markers:
        return []

    sorted_markers = sorted(markers, key=lambda x: x["start"])
    dur_total = float(duration_seconds) if duration_seconds is not None else None
    if dur_total is None or dur_total <= 0:
        dur_total = max((m["start"] + m["duration"] for m in sorted_markers), default=0.0)

    candidates = []
    n = len(sorted_markers)
    for i, m in enumerate(sorted_markers):
        sc = m["score"]
        if sc < 0.2:
            continue
        prev_sc = sorted_markers[i - 1]["score"] if i > 0 else 0.0
        next_sc = sorted_markers[i + 1]["score"] if i < n - 1 else 0.0

        is_peak = (sc >= prev_sc and sc >= next_sc) or (sc >= 0.7)
        if not is_peak:
            continue

        p_start = m["start"]
        pre_roll = min(12.0, target_duration * 0.3)
        win_start = max(0.0, p_start - pre_roll)
        win_end = min(dur_total, win_start + target_duration)

        if (win_end - win_start) < min_duration and dur_total >= min_duration:
            win_start = max(0.0, win_end - min_duration)

        win_dur = win_end - win_start
        if win_dur < 10.0:
            continue
        if win_dur > max_duration:
            win_end = win_start + max_duration

        window_scores = [
            it["score"] for it in sorted_markers
            if it["start"] >= win_start and it["start"] <= win_end
        ]
        avg_score = sum(window_scores) / max(1, len(window_scores))
        composite_score = (0.7 * sc) + (0.3 * avg_score)

        candidates.append({
            "start": round(win_start, 1),
            "duration": round(win_end - win_start, 1),
            "score": round(composite_score, 2),
            "peak_time": p_start,
        })

    if not candidates:
        for m in sorted(sorted_markers, key=lambda x: -x["score"])[:5]:
            win_start = max(0.0, m["start"] - 8.0)
            win_end = min(dur_total, win_start + target_duration)
            candidates.append({
                "start": round(win_start, 1),
                "duration": round(win_end - win_start, 1),
                "score": round(m["score"], 2),
                "peak_time": m["start"],
            })

    # Non-Maximum Suppression (Anti-Tumpang Tindih)
    candidates.sort(key=lambda x: -x["score"])
    selected = []
    for cand in candidates:
        c_st = cand["start"]
        c_en = c_st + cand["duration"]
        overlap = False
        for s in selected:
            s_st = s["start"]
            s_en = s_st + s["duration"]
            inter_st = max(c_st, s_st)
            inter_en = min(c_en, s_en)
            inter_dur = max(0.0, inter_en - inter_st)
            if inter_dur > 0.35 * cand["duration"]:
                overlap = True
                break
        if not overlap:
            selected.append(cand)
            if len(selected) >= int(limit or 10):
                break

    selected.sort(key=lambda x: x["start"])
    return selected


def ambil_most_replayed(video_id, min_score=None, fallback_limit=10, duration_seconds=None, diag=None, session=None):
    url = f"https://www.youtube.com/watch?v={video_id}"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept-Language": "en-US,en;q=0.9,id;q=0.8",
    }

    diag_out = diag if isinstance(diag, dict) else None
    t_all = time.perf_counter()
    sess = session or requests.Session()
    # Load cookies from file if available
    load_cookies_into_session(sess)
    proxy = os.environ.get('YTCLIPPER_PROXY')
    if proxy and str(proxy).strip():
        p = str(proxy).strip()
        sess.proxies.update({'http': p, 'https': p})
    
    timeout = (6, 20)
    if os.environ.get("YTCLIPPER_HEATMAP_SCAN_INITIAL_DATA") is not None:
        scan_initial_data = str(os.environ.get("YTCLIPPER_HEATMAP_SCAN_INITIAL_DATA") or "").strip().lower() not in (
            "0",
            "false",
            "no",
            "off",
            "",
        )
    else:
        scan_initial_data = False

    html = ""
    try:
        t0 = time.perf_counter()
        html = sess.get(url, headers=headers, timeout=timeout).text
        if diag_out is not None:
            diag_out["fetch_watch_ms"] = int((time.perf_counter() - t0) * 1000)
            diag_out["watch_html_len"] = int(len(html or ""))
        if "consent.youtube.com" in html or "Before you continue to YouTube" in html:
            t1 = time.perf_counter()
            html = sess.get(url, headers=headers, cookies={"CONSENT": "YES+1"}, timeout=timeout).text
            if diag_out is not None:
                diag_out["fetch_consent_ms"] = int((time.perf_counter() - t1) * 1000)
                diag_out["watch_html_len"] = int(len(html or ""))
    except Exception:
        if diag_out is not None:
            diag_out["error"] = "fetch_watch_failed"
        return []

    lower = html.lower()
    if "/sorry/" in lower or "unusual traffic" in lower or "detected unusual traffic" in lower:
        raise ValueError(
            "YouTube menolak request (robot check). Coba buka videonya sekali di browser, lalu coba lagi. "
            "Kalau masih sama: matikan VPN/proxy, ganti jaringan, atau tunggu beberapa menit."
        )

    all_markers = []
    chapter_starts = []

    threshold = MIN_SCORE if min_score is None else float(min_score)

    t_parse = time.perf_counter()
    root = _extract_assigned_json(html, "ytInitialPlayerResponse")
    if root:
        all_markers.extend(_collect_heat_markers(root))
        chapter_starts.extend(_collect_chapter_starts(root))
    if diag_out is not None:
        diag_out["parse_player_response_ms"] = int((time.perf_counter() - t_parse) * 1000)

    if all_markers:
        pass
    else:
        t_cfg = time.perf_counter()
        ytcfg = _extract_ytcfg(html)
        if diag_out is not None:
            diag_out["extract_ytcfg_ms"] = int((time.perf_counter() - t_cfg) * 1000)
        if ytcfg:
            t_it = time.perf_counter()
            player = _fetch_innertube_player(video_id, ytcfg, url, headers, session=sess)
            if diag_out is not None:
                diag_out["innertube_player_ms"] = int((time.perf_counter() - t_it) * 1000)
            if player:
                all_markers.extend(_collect_heat_markers(player))
                chapter_starts.extend(_collect_chapter_starts(player))

    if not all_markers:
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

    if not all_markers and scan_initial_data:
        walk_limit = int(os.environ.get("YTCLIPPER_HEATMAP_WALK_MAX_NODES", "60000") or "60000")
        t_id = time.perf_counter()
        root2 = _extract_assigned_json(html, "ytInitialData")
        if root2:
            all_markers.extend(_collect_heat_markers(root2, max_nodes=walk_limit))
            chapter_starts.extend(_collect_chapter_starts(root2, max_nodes=walk_limit))
        if diag_out is not None:
            diag_out["parse_initial_data_ms"] = int((time.perf_counter() - t_id) * 1000)
            diag_out["initial_data_walk_max_nodes"] = walk_limit

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
            normalized[key] = {"start": start_s, "duration": min(dur_s, float(MAX_DURATION)), "score": float(score)}

    items = list(normalized.values())
    items.sort(key=lambda x: x["score"], reverse=True)

    if diag_out is not None:
        diag_out["markers_in"] = int(len(all_markers))
        diag_out["markers_norm"] = int(len(items))

    # Kelompokkan puncak heatmap menjadi klip Shorts utuh berkualitas tinggi (20-60s)
    if items:
        clustered = _cluster_heatmap_peaks(items, duration_seconds=duration_seconds, limit=fallback_limit)
        if clustered:
            if diag_out is not None:
                diag_out["total_ms"] = int((time.perf_counter() - t_all) * 1000)
                diag_out["clustered"] = len(clustered)
            return clustered

    # Fallback: jika clustering kosong, jangan pernah mengembalikan micro-marker mentah 1-6 detik!
    # Lakukan ekspansi titik puncak ke rentang Shorts (20-45 detik).
    expanded = []
    dur_total = float(duration_seconds) if duration_seconds is not None else None
    for it in items[: max(1, int(fallback_limit))]:
        st = float(it.get("start", 0.0))
        win_start = max(0.0, st - 8.0)
        win_dur = 45.0
        if dur_total:
            win_end = min(dur_total, win_start + win_dur)
            if (win_end - win_start) < 20.0 and dur_total >= 20.0:
                win_start = max(0.0, win_end - 20.0)
            win_dur = win_end - win_start
        expanded.append({
            "start": round(win_start, 1),
            "duration": round(win_dur, 1),
            "score": float(it.get("score", 0.0)),
        })

    if expanded:
        if diag_out is not None:
            diag_out["total_ms"] = int((time.perf_counter() - t_all) * 1000)
        return expanded

    chapter_items = _build_chapter_segments(chapter_starts, duration_seconds)
    if chapter_items:
        if diag_out is not None:
            diag_out["total_ms"] = int((time.perf_counter() - t_all) * 1000)
        return chapter_items[: max(1, int(fallback_limit))]
    if diag_out is not None:
        diag_out["total_ms"] = int((time.perf_counter() - t_all) * 1000)
    return []

