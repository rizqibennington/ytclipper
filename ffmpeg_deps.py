import json
import os
import shutil
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone

import requests

from config_store import load_config, save_config


def _env_bool(name, default=False):
    v = os.environ.get(name)
    if v is None:
        return bool(default)
    return str(v).strip().lower() not in ("0", "false", "no", "off", "")


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _get_mem_mb():
    try:
        if sys.platform.startswith("win"):
            import ctypes

            class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
                _fields_ = [
                    ("cb", ctypes.c_ulong),
                    ("PageFaultCount", ctypes.c_ulong),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                ]

            counters = PROCESS_MEMORY_COUNTERS()
            counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
            hproc = ctypes.windll.kernel32.GetCurrentProcess()
            ok = ctypes.windll.psapi.GetProcessMemoryInfo(hproc, ctypes.byref(counters), counters.cb)
            if ok:
                return float(counters.WorkingSetSize) / (1024.0 * 1024.0)

        import resource

        ru = resource.getrusage(resource.RUSAGE_SELF)
        rss = getattr(ru, "ru_maxrss", 0) or 0
        if sys.platform == "darwin":
            return float(rss) / (1024.0 * 1024.0)
        return float(rss) / 1024.0
    except Exception:
        return None


class _DepsLogger:
    def __init__(self, path, verbose=False):
        self.path = str(path) if path else None
        self.verbose = bool(verbose)
        self._fh = None
        if self.path:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            self._fh = open(self.path, "a", encoding="utf-8", buffering=1)

    def close(self):
        try:
            if self._fh:
                self._fh.close()
        except Exception:
            pass

    def emit(self, event, dep=None, status=None, duration_ms=None, **extra):
        rec = {
            "ts": _now_iso(),
            "event": str(event),
            "dep": dep,
            "status": status,
            "duration_ms": duration_ms,
            "mem_mb": _get_mem_mb(),
        }
        for k, v in (extra or {}).items():
            if v is not None:
                rec[str(k)] = v

        if self._fh:
            try:
                self._fh.write(json.dumps(rec, ensure_ascii=False, separators=(",", ":")) + "\n")
            except Exception:
                pass

        if self.verbose:
            try:
                parts = [f"{rec['ts']}", f"{rec['event']}"]
                if dep:
                    parts.append(f"dep={dep}")
                if status:
                    parts.append(f"status={status}")
                if duration_ms is not None:
                    parts.append(f"t={duration_ms}ms")
                if rec.get("mem_mb") is not None:
                    parts.append(f"mem={rec['mem_mb']:.1f}MB")
                msg = " | ".join(parts)
                print(msg, flush=True)
            except Exception:
                return


def _pause_if_needed(logger, pause_file, dep=None):
    pf = str(pause_file or "")
    if not pf:
        return

    paused = False
    while True:
        try:
            exists = os.path.exists(pf)
        except Exception:
            exists = False

        if not exists:
            if paused:
                logger.emit("pause.resume", dep=dep, status="success", pause_file=pf)
            return

        if not paused:
            paused = True
            logger.emit("pause.wait", dep=dep, status="pending", pause_file=pf)
        time.sleep(0.35)


def _get_ffmpeg_path():
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg

    local_bin = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bin")
    local_ffmpeg = os.path.join(local_bin, "ffmpeg.exe")
    if os.path.exists(local_ffmpeg):
        return local_ffmpeg

    return None


def _download_ffmpeg(logger, verbose=False, pause_file=None):
    _pause_if_needed(logger, pause_file, dep="ffmpeg")
    logger.emit("dep.start", dep="ffmpeg", status="pending")

    local_bin = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bin")
    os.makedirs(local_bin, exist_ok=True)

    url = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
    zip_path = os.path.join(local_bin, "ffmpeg.zip")

    t0 = time.perf_counter()

    try:
        logger.emit("network.request", dep="ffmpeg", status="pending", method="GET", url=url)
        response = requests.get(url, stream=True, timeout=(10, 60))
        response.raise_for_status()

        logger.emit(
            "network.response",
            dep="ffmpeg",
            status="success",
            url=url,
            http_status=int(getattr(response, "status_code", 0) or 0),
        )

        total_size = int(response.headers.get("content-length", 0))
        downloaded = 0
        last_pct = -1
        last_mark = 0

        with open(zip_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                _pause_if_needed(logger, pause_file, dep="ffmpeg")
                if not chunk:
                    continue
                f.write(chunk)
                downloaded += len(chunk)
                if total_size > 0:
                    pct_i = int((downloaded * 100) / max(1, total_size))
                    if pct_i != last_pct and (pct_i % 5 == 0 or pct_i == 100):
                        last_pct = pct_i
                        logger.emit(
                            "network.progress",
                            dep="ffmpeg",
                            status="pending",
                            url=url,
                            downloaded_bytes=downloaded,
                            total_bytes=total_size,
                            percent=pct_i,
                        )
                        if verbose:
                            print(f"⬇️  Downloading FFmpeg... {pct_i}%", flush=True)
                else:
                    if (downloaded - last_mark) >= 25 * 1024 * 1024:
                        last_mark = downloaded
                        logger.emit("network.progress", dep="ffmpeg", status="pending", url=url, downloaded_bytes=downloaded)

        logger.emit(
            "network.done",
            dep="ffmpeg",
            status="success",
            url=url,
            downloaded_bytes=downloaded,
            total_bytes=total_size if total_size > 0 else None,
        )

        logger.emit("ffmpeg.extract.start", dep="ffmpeg", status="pending", zip_path=zip_path)

        import zipfile
        import shutil as _shutil

        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            ffmpeg_member = None
            ffprobe_member = None
            for info in zip_ref.infolist():
                name = str(getattr(info, "filename", "") or "")
                if not ffmpeg_member and name.endswith("ffmpeg.exe"):
                    ffmpeg_member = name
                elif not ffprobe_member and name.endswith("ffprobe.exe"):
                    ffprobe_member = name
                if ffmpeg_member and ffprobe_member:
                    break

            if not ffmpeg_member:
                raise RuntimeError("File ffmpeg.exe tidak ditemukan di zip.")

            _pause_if_needed(logger, pause_file, dep="ffmpeg")
            ffmpeg_dest = os.path.join(local_bin, "ffmpeg.exe")
            with zip_ref.open(ffmpeg_member) as src, open(ffmpeg_dest, "wb") as dst:
                _shutil.copyfileobj(src, dst, length=1024 * 1024)

            if ffprobe_member:
                ffprobe_dest = os.path.join(local_bin, "ffprobe.exe")
                with zip_ref.open(ffprobe_member) as src, open(ffprobe_dest, "wb") as dst:
                    _shutil.copyfileobj(src, dst, length=1024 * 1024)

        logger.emit("ffmpeg.extract.done", dep="ffmpeg", status="success", ffmpeg_path=os.path.join(local_bin, "ffmpeg.exe"))

        try:
            os.remove(zip_path)
        except Exception:
            pass

        logger.emit("dep.done", dep="ffmpeg", status="success", duration_ms=int((time.perf_counter() - t0) * 1000))
        return os.path.join(local_bin, "ffmpeg.exe")

    except Exception as e:
        logger.emit(
            "dep.done",
            dep="ffmpeg",
            status="failed",
            duration_ms=int((time.perf_counter() - t0) * 1000),
            error=str(e),
            traceback=traceback.format_exc(limit=20),
        )
        raise RuntimeError(
            f"Gagal download FFmpeg: {e}\n\nSolusi manual: install FFmpeg via 'winget install ffmpeg' atau download dari https://ffmpeg.org"
        )


def _run_pip(logger, dep, args, timeout_s=None, verbose=False):
    t0 = time.perf_counter()
    timeout_s = int(timeout_s) if timeout_s else None
    cmd = [sys.executable, "-m", "pip"] + list(args)
    env = dict(os.environ)
    env.setdefault("PIP_DISABLE_PIP_VERSION_CHECK", "1")
    env.setdefault("PIP_NO_INPUT", "1")
    logger.emit("dep.start", dep=dep, status="pending", cmd=cmd, timeout_s=timeout_s)
    try:
        if verbose:
            p = subprocess.run(cmd, text=True, timeout=timeout_s)
            rc = int(getattr(p, "returncode", 0) or 0)
            if rc != 0:
                raise subprocess.CalledProcessError(rc, cmd)
        else:
            p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env, timeout=timeout_s)
            rc = int(getattr(p, "returncode", 0) or 0)
            if rc != 0:
                raise subprocess.CalledProcessError(rc, cmd, output=p.stdout, stderr=p.stderr)

        logger.emit("dep.done", dep=dep, status="success", duration_ms=int((time.perf_counter() - t0) * 1000))
        return True
    except subprocess.TimeoutExpired as e:
        logger.emit(
            "dep.done",
            dep=dep,
            status="failed",
            duration_ms=int((time.perf_counter() - t0) * 1000),
            error=f"Timeout after {timeout_s}s",
        )
        raise RuntimeError(f"Pengecekan {dep} timeout setelah {timeout_s}s") from e
    except Exception as e:
        out = None
        err = None
        if isinstance(e, subprocess.CalledProcessError):
            try:
                out = str(getattr(e, "output", None) or "")[-8000:] or None
                err = str(getattr(e, "stderr", None) or "")[-8000:] or None
            except Exception:
                out = None
                err = None
        logger.emit(
            "dep.done",
            dep=dep,
            status="failed",
            duration_ms=int((time.perf_counter() - t0) * 1000),
            error=str(e),
            stdout_tail=out,
            stderr_tail=err,
            traceback=traceback.format_exc(limit=12),
        )
        raise


def cek_dependensi(
    install_whisper=False,
    verbose=None,
    log_path=None,
    pause_file=None,
):
    if verbose is None:
        if os.environ.get("YTCLIPPER_DEPS_VERBOSE") is not None:
            verbose = _env_bool("YTCLIPPER_DEPS_VERBOSE", False)
        else:
            try:
                verbose = bool((load_config() or {}).get("deps_verbose", False))
            except Exception:
                verbose = False
    else:
        verbose = bool(verbose)
    pause_file = pause_file or os.environ.get("YTCLIPPER_DEPS_PAUSE_FILE") or os.path.join(os.path.expanduser("~"), ".ytclipper_deps.pause")
    log_path = log_path or os.environ.get("YTCLIPPER_DEPS_LOG") or os.path.join(os.path.expanduser("~"), ".ytclipper_deps.jsonl")

    logger = _DepsLogger(log_path, verbose=verbose)
    try:
        logger.emit(
            "deps.check.start",
            status="pending",
            install_whisper=bool(install_whisper),
            pid=os.getpid(),
            pause_file=pause_file,
            log_path=log_path,
        )

        _pause_if_needed(logger, pause_file, dep="yt_dlp")

        cfg = load_config() or {}
        last_upgrade = float(cfg.get("deps_last_upgrade_ytdlp_ts", 0) or 0)
        upgrade_every_s = int(os.environ.get("YTCLIPPER_DEPS_UPGRADE_YTDLP_EVERY_S", "86400") or "86400")
        force_upgrade = _env_bool("YTCLIPPER_DEPS_FORCE_UPGRADE", False)
        auto_upgrade = _env_bool("YTCLIPPER_DEPS_AUTO_UPGRADE", False)

        ytdlp_ok = True
        try:
            import yt_dlp  # noqa: F401
        except Exception:
            ytdlp_ok = False

        need_upgrade = bool(force_upgrade) or (bool(auto_upgrade) and (time.time() - last_upgrade) >= max(0, upgrade_every_s))
        if not ytdlp_ok:
            _run_pip(
                logger,
                dep="yt_dlp",
                args=["install", "yt-dlp", "--disable-pip-version-check", "--no-input", "--progress-bar", "off"],
                timeout_s=os.environ.get("YTCLIPPER_DEPS_PIP_TIMEOUT_S") or 600,
                verbose=verbose,
            )
        elif need_upgrade:
            _run_pip(
                logger,
                dep="yt_dlp",
                args=["install", "-U", "yt-dlp", "--disable-pip-version-check", "--no-input", "--progress-bar", "off"],
                timeout_s=os.environ.get("YTCLIPPER_DEPS_PIP_TIMEOUT_S") or 600,
                verbose=verbose,
            )
            cfg["deps_last_upgrade_ytdlp_ts"] = float(time.time())
            save_config(cfg)
        else:
            reason = "recently_upgraded" if auto_upgrade else "auto_upgrade_off"
            logger.emit("dep.skip", dep="yt_dlp", status="success", reason=reason)

        if install_whisper:
            _pause_if_needed(logger, pause_file, dep="faster_whisper")
            fw_ok = True
            try:
                import faster_whisper  # noqa: F401
            except Exception:
                fw_ok = False

            if not fw_ok:
                _run_pip(
                    logger,
                    dep="faster_whisper",
                    args=["install", "faster-whisper", "--disable-pip-version-check", "--no-input", "--progress-bar", "off"],
                    timeout_s=os.environ.get("YTCLIPPER_DEPS_PIP_TIMEOUT_S") or 900,
                    verbose=verbose,
                )
            else:
                logger.emit("dep.skip", dep="faster_whisper", status="success", reason="already_installed")

        _pause_if_needed(logger, pause_file, dep="ffmpeg")
        ffmpeg_path = _get_ffmpeg_path()
        if not ffmpeg_path:
            ffmpeg_path = _download_ffmpeg(logger, verbose=verbose, pause_file=pause_file)
        else:
            logger.emit("dep.skip", dep="ffmpeg", status="success", reason="already_present", ffmpeg_path=ffmpeg_path)

        local_bin = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bin")
        if local_bin and local_bin not in os.environ.get("PATH", ""):
            os.environ["PATH"] = local_bin + os.pathsep + os.environ.get("PATH", "")
            logger.emit("path.update", dep="ffmpeg", status="success", added=local_bin)

        logger.emit("deps.check.done", status="success")
        return {
            "ok": True,
            "log_path": log_path,
            "pause_file": pause_file,
            "ffmpeg_path": ffmpeg_path,
        }
    except Exception as e:
        logger.emit("deps.check.done", status="failed", error=str(e), traceback=traceback.format_exc(limit=20))
        raise
    finally:
        logger.close()
