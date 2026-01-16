import os
import shutil
import subprocess
import sys

import requests


def _get_ffmpeg_path():
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg

    local_bin = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bin")
    local_ffmpeg = os.path.join(local_bin, "ffmpeg.exe")
    if os.path.exists(local_ffmpeg):
        return local_ffmpeg

    return None


def _download_ffmpeg():
    print("📦 FFmpeg tidak ditemukan, downloading...")

    local_bin = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bin")
    os.makedirs(local_bin, exist_ok=True)

    url = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
    zip_path = os.path.join(local_bin, "ffmpeg.zip")

    try:
        print(f"⬇️  Downloading FFmpeg dari {url[:50]}...")
        response = requests.get(url, stream=True, timeout=60)
        response.raise_for_status()

        total_size = int(response.headers.get("content-length", 0))
        downloaded = 0

        with open(zip_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                downloaded += len(chunk)
                if total_size > 0:
                    pct = (downloaded / total_size) * 100
                    print(f"\r⬇️  Downloading... {pct:.1f}%", end="", flush=True)

        print("\n📂 Extracting FFmpeg...")

        import zipfile

        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            for name in zip_ref.namelist():
                if name.endswith("ffmpeg.exe"):
                    with zip_ref.open(name) as src:
                        ffmpeg_dest = os.path.join(local_bin, "ffmpeg.exe")
                        with open(ffmpeg_dest, "wb") as dst:
                            dst.write(src.read())
                    print(f"✅ FFmpeg extracted ke {ffmpeg_dest}")
                    break
                if name.endswith("ffprobe.exe"):
                    with zip_ref.open(name) as src:
                        ffprobe_dest = os.path.join(local_bin, "ffprobe.exe")
                        with open(ffprobe_dest, "wb") as dst:
                            dst.write(src.read())

        try:
            os.remove(zip_path)
        except Exception:
            pass

        return os.path.join(local_bin, "ffmpeg.exe")

    except Exception as e:
        raise RuntimeError(
            f"Gagal download FFmpeg: {e}\n\nSolusi manual: install FFmpeg via 'winget install ffmpeg' atau download dari https://ffmpeg.org"
        )


def cek_dependensi(install_whisper=False):
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-U", "yt-dlp"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    if install_whisper:
        try:
            import faster_whisper  # noqa: F401
        except ImportError:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "faster-whisper"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

    ffmpeg_path = _get_ffmpeg_path()
    if not ffmpeg_path:
        ffmpeg_path = _download_ffmpeg()

    local_bin = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bin")
    if local_bin not in os.environ.get("PATH", ""):
        os.environ["PATH"] = local_bin + os.pathsep + os.environ.get("PATH", "")

