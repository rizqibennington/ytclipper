import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import create_app
from app.jobs import create_job, get_job, run_job


FFMPEG = shutil.which("ffmpeg") or Path(__file__).resolve().parents[1] / "bin" / "ffmpeg.exe"
DRAFT = "1\n00:00:00,000 --> 00:00:01,000\nCaption awal\n"


class TestRenderProgress(unittest.TestCase):
    def test_burn_progress_and_eta_use_render_clock(self):
        job_id = "test_render_progress"
        create_job(job_id, output_dir=tempfile.gettempdir())
        snapshots = []

        def process(event_cb, **kwargs):
            for stage in ("download", "clip", "subtitle", "subtitle_burn"):
                event_cb({"stage": stage, "clip_index": 1})
                snapshots.append(get_job(job_id))
            event_cb({"stage": "subtitle_burn", "clip_index": 1, "render_fraction": 0.5})
            snapshots.append(get_job(job_id))
            return {}

        with patch("app.jobs.proses_dengan_segmen", side_effect=process), patch(
            "app.jobs.time.perf_counter", side_effect=[300.0, 304.0],
        ):
            run_job(job_id, {"segments": [], "url": "fixture", "crop_mode": "default", "use_subtitle": True})

        percents = [snapshot["percent"] for snapshot in snapshots]
        self.assertEqual(percents, sorted(percents))
        self.assertGreater(percents[-1], percents[-2])
        self.assertEqual(snapshots[-2]["eta"], "")
        self.assertEqual(snapshots[-1]["eta"], "00:04")


@unittest.skipUnless(Path(FFMPEG).is_file(), "FFmpeg tidak tersedia")
class TestSubtitleReview(unittest.TestCase):
    def setUp(self):
        self.tmp = self.enterContext(tempfile.TemporaryDirectory())
        self.folder = Path(self.tmp)
        self.source = self.folder / "source.mp4"
        self.output = self.folder / "output [clip], editor's test"
        self.client = self.enterContext(TestClient(create_app()))
        self.run = subprocess.run
        self.enterContext(patch.dict(os.environ, {"PATH": str(Path(FFMPEG).parent) + os.pathsep + os.environ["PATH"]}))
        self.run([
            FFMPEG, "-v", "error", "-f", "lavfi", "-i", "color=black:s=320x180:r=4",
            "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000",
            "-t", "2", self.source,
        ], check=True)
        self.enterContext(patch("app.clipper.subprocess.run", side_effect=self.run_clip_command))
        self.enterContext(patch("app.clipper.get_duration", return_value=2))
        self.enterContext(patch("app.clipper.cek_dependensi"))
        self.enterContext(patch("app.clipper.generate_subtitle", side_effect=self.transcribe))
        self.enterContext(patch("app.services.clip_service.load_config", return_value={}))
        self.enterContext(patch("app.services.clip_service.save_config"))

    def run_clip_command(self, cmd, **kwargs):
        if cmd[1:3] == ["-m", "yt_dlp"]:
            path = cmd[cmd.index("-o") + 1].replace("%(ext)s", "mp4")
            shutil.copyfile(self.source, path)
            return subprocess.CompletedProcess(cmd, 0, "", "")
        return self.run([FFMPEG, *cmd[1:]], **kwargs)

    def transcribe(self, video, subtitle, **kwargs):
        Path(subtitle).write_text(DRAFT, encoding="utf-8")
        return True

    def start(self, *, review=True, segments=None):
        response = self.client.post("/api/start", json={
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "segments": segments or [{"start": 0, "end": 2}],
            "use_subtitle": True,
            "review_subtitles": review,
            "output_dir": str(self.output),
        })
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["job_id"]

    def wait(self, job_id, predicate):
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            status = self.client.get(f"/api/status/{job_id}").json()
            if predicate(status):
                return status
            if status["done"]:
                self.fail(status)
            time.sleep(0.05)
        self.fail(f"Job tidak mencapai kondisi yang ditunggu: {status}")

    def test_review_preview_and_burn_edited_timing(self):
        job = self.start()
        review = self.wait(job, lambda status: status["subtitle_review"])["subtitle_review"]
        self.assertEqual(review["srt"], DRAFT)
        base = f"/api/subtitle-review/{job}"
        review_id = review["review_id"]
        preview = self.client.get(f"{base}/{review_id}/video", headers={"Range": "bytes=0-99"})
        self.assertEqual(preview.status_code, 206)
        self.assertEqual(len(preview.content), 100)
        response = self.client.post(base, json={"review_id": review_id, "srt": "waktu salah"})
        self.assertEqual(response.status_code, 400)
        edited = DRAFT.replace("00:00:00,000 --> 00:00:01,000", "00:00:01,000 --> 00:00:02,000")
        edited = edited.replace("Caption awal", "Koreksi")
        self.assertEqual(self.client.post(base, json={"review_id": "0" * 32, "srt": edited}).status_code, 409)
        self.assertEqual(self.client.post(base, json={"review_id": review_id, "srt": edited}).status_code, 200)
        self.assertEqual(self.client.post(base, json={"review_id": review_id, "srt": edited}).status_code, 409)
        status = self.wait(job, lambda status: status["done"])
        self.assertEqual(status["success_count"], 1, status)
        self.assertEqual(self.client.get(f"{base}/{review_id}/video").status_code, 404)
        final = self.output / status["files"][0]
        result = self.run([FFMPEG, "-hide_banner", "-i", final, "-vf", "bbox", "-f", "null", "-"],
                          check=True, capture_output=True, text=True)
        bounds = [line for line in result.stderr.splitlines() if "x1:" in line]
        self.assertEqual(len(bounds), 4)
        self.assertIn("pts_time:1 ", bounds[0])
        self.assertIn("720x1280", result.stderr)
        self.assertIn("Audio: aac", result.stderr)
        self.assertEqual(list(self.output.iterdir()), [final])

    def test_cancel_review_cleans_temp_files(self):
        job = self.start()
        review = self.wait(job, lambda status: status["subtitle_review"])["subtitle_review"]
        self.assertEqual(self.client.post(f"/api/cancel/{job}").status_code, 200)
        status = self.wait(job, lambda status: status["done"])
        self.assertEqual(status["stage"], "cancelled")
        self.assertIsNone(status["subtitle_review"])
        self.assertEqual(self.client.post(f"/api/subtitle-review/{job}", json={
            "review_id": review["review_id"], "srt": DRAFT,
        }).status_code, 409)
        deadline = time.monotonic() + 5
        while list(self.output.iterdir()) and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertEqual(list(self.output.iterdir()), [])

    def test_direct_render_without_review(self):
        job = self.start(review=False)
        status = self.wait(job, lambda status: status["done"])
        self.assertEqual(status["success_count"], 1, status)
        self.assertIsNone(status["subtitle_review"])

    def test_blank_caption_and_review_next_clip(self):
        job = self.start(segments=[{"start": 0, "end": 2}, {"start": 1, "end": 2}])
        base = f"/api/subtitle-review/{job}"
        first = self.wait(job, lambda status: status["subtitle_review"])["subtitle_review"]
        self.assertEqual(self.client.post(base, json={"review_id": first["review_id"], "srt": ""}).status_code, 200)
        second = self.wait(job, lambda status: (status["subtitle_review"] or {}).get("clip_index") == 2)["subtitle_review"]
        self.assertEqual(self.client.post(base, json={"review_id": first["review_id"], "srt": DRAFT}).status_code, 409)
        self.assertEqual(self.client.post(base, json={"review_id": second["review_id"], "srt": DRAFT}).status_code, 200)
        status = self.wait(job, lambda status: status["done"])
        self.assertEqual(status["success_count"], 2, status)
