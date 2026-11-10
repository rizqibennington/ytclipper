import os

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    cv2 = None
    HAS_CV2 = False

try:
    import numpy as np
except ImportError:
    np = None

YUNET_MODEL_FILENAME = "face_detection_yunet.onnx"
YUNET_URL = "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"


def get_model_path():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    models_dir = os.path.join(base_dir, "models")
    os.makedirs(models_dir, exist_ok=True)
    return os.path.join(models_dir, YUNET_MODEL_FILENAME)


def ensure_yunet_model():
    model_path = get_model_path()
    if os.path.exists(model_path) and os.path.getsize(model_path) > 100000:
        return model_path

    try:
        import requests
        r = requests.get(YUNET_URL, timeout=15)
        if r.status_code == 200 and len(r.content) > 100000:
            with open(model_path, "wb") as f:
                f.write(r.content)
            return model_path
    except Exception as e:
        print(f"⚠️ [SpeakerTracker] Gagal mengunduh model YuNet: {e}")
    return model_path if os.path.exists(model_path) else None


def create_detector(model_path, input_size=(640, 360), conf_threshold=0.5):
    if not HAS_CV2 or cv2 is None or not model_path or not os.path.exists(model_path):
        return None
    try:
        return cv2.FaceDetectorYN.create(model_path, "", input_size, conf_threshold, 0.3, 100)
    except Exception as e:
        print(f"⚠️ [SpeakerTracker] Gagal inisialisasi FaceDetectorYN: {e}")
        return None


def detect_faces_in_bgr(detector, frame_bgr):
    if detector is None or frame_bgr is None:
        return []
    h, w = frame_bgr.shape[:2]
    detector.setInputSize((w, h))
    try:
        _, faces = detector.detect(frame_bgr)
        if faces is None or len(faces) == 0:
            return []
        results = []
        for f in faces:
            fx, fy, fw, fh = float(f[0]), float(f[1]), float(f[2]), float(f[3])
            conf = float(f[14])
            results.append({
                "x": fx,
                "y": fy,
                "w": fw,
                "h": fh,
                "cx": fx + fw / 2.0,
                "cy": fy + fh / 2.0,
                "conf": conf,
            })
        return results
    except Exception:
        return []


def analyze_video_speakers(video_path, max_duration=180.0):
    """
    Menganalisis video untuk menemukan posisi wajah pembicara (Kiri dan Kanan),
    serta mendeteksi siapa yang sedang berbicara pada setiap rentang waktu.
    
    Returns:
        {
            "left_cx": float (0.0 to 1.0),
            "right_cx": float (0.0 to 1.0),
            "intervals": [ {"start": float, "end": float, "speaker": "left"|"right"} ],
            "has_faces": bool
        }
    """
    fallback = {
        "left_cx": 0.25,
        "right_cx": 0.75,
        "intervals": [],
        "has_faces": False,
    }
    if not HAS_CV2 or cv2 is None or np is None:
        print("⚠️ [SpeakerTracker] OpenCV (cv2) tidak tersedia. Menggunakan crop cadangan.")
        return fallback

    model_path = ensure_yunet_model()
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        cap.release()
        return fallback

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    duration = total_frames / fps if total_frames > 0 else max_duration
    duration = min(duration, max_duration)

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 1280)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 720)

    # Sample video at 2 fps for efficiency and accuracy
    sample_interval_s = 0.5
    step_frames = max(1, int(fps * sample_interval_s))

    detector = create_detector(model_path, input_size=(width, height))
    if detector is None:
        cap.release()
        return fallback

    left_faces_x = []
    right_faces_x = []
    timeline_activity = [] # list of (time_s, left_act, right_act)

    prev_left_crop = None
    prev_right_crop = None

    frame_idx = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        t_sec = frame_idx / fps
        if t_sec > duration:
            break

        if frame_idx % step_frames == 0:
            faces = detect_faces_in_bgr(detector, frame)
            
            # Find closest left face and right face
            l_face = None
            r_face = None
            for f in faces:
                norm_cx = f["cx"] / width
                if norm_cx < 0.5:
                    if l_face is None or f["conf"] > l_face["conf"]:
                        l_face = f
                else:
                    if r_face is None or f["conf"] > r_face["conf"]:
                        r_face = f

            l_motion = 0.0
            r_motion = 0.0

            # Compute mouth area motion difference
            if l_face:
                left_faces_x.append(l_face["cx"] / width)
                # Mouth is roughly lower 40% of face box
                mx = max(0, int(l_face["x"]))
                my = max(0, int(l_face["y"] + l_face["h"] * 0.55))
                mw = max(1, min(width - mx, int(l_face["w"])))
                mh = max(1, min(height - my, int(l_face["h"] * 0.45)))
                cur_crop = cv2.cvtColor(frame[my:my+mh, mx:mx+mw], cv2.COLOR_BGR2GRAY)
                cur_crop = cv2.resize(cur_crop, (48, 32))
                if prev_left_crop is not None:
                    l_motion = float(np.mean(cv2.absdiff(cur_crop, prev_left_crop)))
                prev_left_crop = cur_crop

            if r_face:
                right_faces_x.append(r_face["cx"] / width)
                mx = max(0, int(r_face["x"]))
                my = max(0, int(r_face["y"] + r_face["h"] * 0.55))
                mw = max(1, min(width - mx, int(r_face["w"])))
                mh = max(1, min(height - my, int(r_face["h"] * 0.45)))
                cur_crop = cv2.cvtColor(frame[my:my+mh, mx:mx+mw], cv2.COLOR_BGR2GRAY)
                cur_crop = cv2.resize(cur_crop, (48, 32))
                if prev_right_crop is not None:
                    r_motion = float(np.mean(cv2.absdiff(cur_crop, prev_right_crop)))
                prev_right_crop = cur_crop

            timeline_activity.append((t_sec, l_motion, r_motion))

        frame_idx += 1

    cap.release()

    has_faces = len(left_faces_x) > 0 or len(right_faces_x) > 0
    final_left_cx = float(np.median(left_faces_x)) if left_faces_x else 0.25
    final_right_cx = float(np.median(right_faces_x)) if right_faces_x else 0.75

    # Determine speaker switching timeline with smoothing
    # Threshold for mouth movement: normal speech mouth motion is typically > 1.5
    raw_decisions = [] # (t_sec, 'left' | 'right')
    initial_speaker = "right" if right_faces_x and not left_faces_x else "left"
    current_speaker = initial_speaker

    for t_sec, l_act, r_act in timeline_activity:
        diff = l_act - r_act
        if diff > 1.2:
            current_speaker = "left"
        elif diff < -1.2:
            current_speaker = "right"
        raw_decisions.append((t_sec, current_speaker))

    if not raw_decisions:
        raw_decisions = [(0.0, initial_speaker)]

    # Apply Minimum Shot Duration (debounce: e.g. 2.2 seconds per shot)
    min_shot_duration = 2.2
    intervals = []
    
    seg_start = 0.0
    seg_speaker = raw_decisions[0][1]

    for t_sec, spk in raw_decisions:
        if spk != seg_speaker:
            if (t_sec - seg_start) >= min_shot_duration:
                intervals.append({
                    "start": round(seg_start, 2),
                    "end": round(t_sec, 2),
                    "speaker": seg_speaker
                })
                seg_start = t_sec
                seg_speaker = spk

    intervals.append({
        "start": round(seg_start, 2),
        "end": round(duration, 2),
        "speaker": seg_speaker
    })

    return {
        "left_cx": final_left_cx,
        "right_cx": final_right_cx,
        "intervals": intervals,
        "has_faces": has_faces
    }


def _podcast_cover_scale(width, height):
    # Scale to cover the crop while preserving the display aspect ratio.
    return (
        f"scale='max({width},ceil({height}*dar/2)*2)':"
        f"'max({height},ceil({width}/dar/2)*2)',setsar=1[scaled];"
    )


def build_split_podcast_filter(analysis_result=None, target_width=720, target_height=1280):
    """
    Menghasilkan filter_complex FFmpeg untuk split podcast 50:50 (Duo Stack):
    - Setengah atas (height = 640): Wajah pembicara kiri / host
    - Setengah bawah (height = 640): Wajah pembicara kanan / guest
    """
    analysis = analysis_result or {}
    left_cx = float(analysis.get("left_cx", 0.25))
    right_cx = float(analysis.get("right_cx", 0.75))
    half_h = target_height // 2

    scaled = _podcast_cover_scale(target_width, half_h)
    split = "[scaled]split=2[s1][s2];"
    x_left = f"'clip({left_cx:.3f}*iw-{target_width}/2,0,iw-{target_width})'"
    x_right = f"'clip({right_cx:.3f}*iw-{target_width}/2,0,iw-{target_width})'"
    top_crop = f"[s1]crop={target_width}:{half_h}:{x_left}:(ih-oh)/2[top];"
    bottom_crop = f"[s2]crop={target_width}:{half_h}:{x_right}:(ih-oh)/2[bottom];"
    stack = "[top][bottom]vstack=inputs=2[out]"

    return scaled + split + top_crop + bottom_crop + stack


def build_dynamic_speaker_crop_filter(analysis_result, target_width=720, target_height=1280):
    """
    Menghasilkan filter_complex FFmpeg untuk memotong video 9:16 secara dinamis
    mengikuti wajah pembicara aktif berdasarkan timeline intervals.
    """
    left_cx = analysis_result.get("left_cx", 0.25)
    right_cx = analysis_result.get("right_cx", 0.75)
    intervals = analysis_result.get("intervals", [])

    scaled_vf = _podcast_cover_scale(target_width, target_height)
    crop_prefix = f"[scaled]crop={target_width}:{target_height}"
    crop_y = "(ih-oh)/2"

    # Compute clampable X coordinates
    # Center speaker 1: x_pos = left_cx * iw - target_width / 2
    # Center speaker 2: x_pos = right_cx * iw - target_width / 2
    # Clamped between 0 and iw - target_width
    x_left_expr = f"clip({left_cx:.3f}*iw-{target_width}/2,0,iw-{target_width})"
    x_right_expr = f"clip({right_cx:.3f}*iw-{target_width}/2,0,iw-{target_width})"

    if analysis_result.get("has_faces") is False or not intervals:
        return f"{scaled_vf}{crop_prefix}:(iw-ow)/2:{crop_y}[out]"
    if len(intervals) == 1:
        default_x = x_left_expr if intervals[0]["speaker"] == "left" else x_right_expr
        return f"{scaled_vf}{crop_prefix}:'{default_x}':{crop_y}[out]"

    # Build nested if(between(t, start, end), x_val, ...) expression
    def build_expr(idx):
        if idx >= len(intervals) - 1:
            return x_left_expr if intervals[idx]["speaker"] == "left" else x_right_expr
        item = intervals[idx]
        cur_x = x_left_expr if item["speaker"] == "left" else x_right_expr
        next_branch = build_expr(idx + 1)
        return f"if(between(t\\,{item['start']:.2f}\\,{item['end']:.2f})\\,{cur_x}\\,{next_branch})"

    dyn_x = build_expr(0)
    crop_vf = f"{crop_prefix}:'{dyn_x}':{crop_y}[out]"
    return scaled_vf + crop_vf

