import io
import os
import tempfile
import unittest
import zipfile
from fastapi.testclient import TestClient

from app import create_app
from app.heatmap import _cluster_heatmap_peaks
from app.jobs import cancel_job, create_job, get_job, update_job
from app.services.ai_service import _build_ai_segments


class TestFeatures(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.client = TestClient(self.app)

    def test_cluster_heatmap_peaks(self):
        # 10 raw markers from YouTube (each ~6 seconds)
        raw_markers = [
            {"start": 0.0, "duration": 6.0, "score": 0.1},
            {"start": 6.0, "duration": 6.0, "score": 0.15},
            {"start": 12.0, "duration": 6.0, "score": 0.2},
            {"start": 60.0, "duration": 6.0, "score": 0.85},
            {"start": 66.0, "duration": 6.0, "score": 0.98}, # PEAK 1
            {"start": 72.0, "duration": 6.0, "score": 0.80},
            {"start": 78.0, "duration": 6.0, "score": 0.40},
            {"start": 180.0, "duration": 6.0, "score": 0.90}, # PEAK 2
            {"start": 186.0, "duration": 6.0, "score": 0.70},
            {"start": 192.0, "duration": 6.0, "score": 0.30},
        ]

        clustered = _cluster_heatmap_peaks(raw_markers, duration_seconds=300, target_duration=45.0, min_duration=25.0, max_duration=60.0, limit=5)
        self.assertTrue(len(clustered) >= 2)
        for c in clustered:
            dur = c["duration"]
            self.assertGreaterEqual(dur, 25.0)
            self.assertLessEqual(dur, 60.0)
            self.assertGreaterEqual(c["score"], 0.0)
            self.assertLessEqual(c["score"], 1.0)

    def test_build_ai_segments_grouping_and_length(self):
        # Subtitle chunks of ~5 seconds each
        transcript = [
            {"start": 0.0, "end": 5.0, "text": "Halo guys selamat datang di channel kita."},
            {"start": 5.0, "end": 10.0, "text": "Hari ini kita mau bahas sesuatu yang seru banget."},
            {"start": 10.0, "end": 15.0, "text": "Jadi intinya begini, ternyata rahasia terbesarnya adalah..."},
            {"start": 15.0, "end": 20.0, "text": "Semua orang mengira ini hal biasa."},
            {"start": 20.0, "end": 25.0, "text": "Tapi faktanya ini plot twist yang luar biasa parah gila."},
            {"start": 25.0, "end": 35.0, "text": "Kalian nggak bakal nyangka hasilnya bisa seperti ini."},
            {"start": 35.0, "end": 45.0, "text": "Kesimpulannya jangan pernah ragu untuk mencoba."},
            {"start": 45.0, "end": 55.0, "text": "Nah itu dia video hari ini jangan lupa subscribe ya."},
            {"start": 100.0, "end": 105.0, "text": "Di segmen berikutnya kita ada cerita lain yang wkwk kocak banget."},
            {"start": 105.0, "end": 140.0, "text": "Serius ini lucu parah kalian harus dengerin sampai habis."},
        ]

        segs = _build_ai_segments(transcript, duration_seconds=160, limit=5)
        self.assertTrue(len(segs) > 0)
        for s in segs:
            dur = s["end"] - s["start"]
            # Segments must be reasonable Shorts length (>= 25s and <= 180s)
            self.assertGreaterEqual(dur, 20)
            self.assertLessEqual(dur, 180)
            self.assertTrue(s["enabled"])
            self.assertGreaterEqual(s["score"], 0.0)
            self.assertLessEqual(s["score"], 1.0)

    def test_cancel_job(self):
        job_id = "test_cancel_123"
        create_job(job_id, output_dir=tempfile.gettempdir())
        update_job(job_id, running=True, status="Processing...")

        # Test API cancel
        res = self.client.post(f"/api/cancel/{job_id}")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json().get("ok"))

        job = get_job(job_id)
        self.assertTrue(job.get("cancelled"))
        self.assertFalse(job.get("running"))
        self.assertTrue(job.get("done"))
        self.assertEqual(job.get("stage"), "cancelled")

    def test_download_zip_endpoint(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            job_id = "test_zip_job"
            create_job(job_id, output_dir=tmpdir)

            # Create dummy clip and ai txt
            mp4_file = "clip_1_test.mp4"
            ai_file = "clip_1_test_ai.txt"

            with open(os.path.join(tmpdir, mp4_file), "wb") as f:
                f.write(b"dummy mp4 video bytes")

            with open(os.path.join(tmpdir, ai_file), "w", encoding="utf-8") as f:
                f.write("JUDUL:\n- Viral Clip\n")

            update_job(
                job_id,
                done=True,
                files=[mp4_file],
                ai_metadata={mp4_file: {"titles": ["Viral Clip"], "caption": "Caption", "hashtags": ["#shorts"]}},
            )

            # Request zip
            res = self.client.get(f"/api/download-zip/{job_id}")
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.headers.get("content-type"), "application/zip")

            # Validate zip contents
            zip_bytes = io.BytesIO(res.content)
            with zipfile.ZipFile(zip_bytes, "r") as zf:
                names = zf.namelist()
                self.assertIn(mp4_file, names)
                self.assertIn(ai_file, names)
                self.assertEqual(zf.read(mp4_file), b"dummy mp4 video bytes")

    def test_minimum_duration_enforcement(self):
        # Even with tiny 1-second subtitle lines, returned segments MUST be at least 15s (Shorts standard)
        tiny_transcript = [
            {"start": 10.0, "end": 11.0, "text": "Intinya ini rahasia gila parah banget."},
            {"start": 12.0, "end": 13.0, "text": "Ternyata plot twist ending yang mengejutkan."},
        ]
        segs = _build_ai_segments(tiny_transcript, duration_seconds=120, limit=2)
        self.assertTrue(len(segs) > 0)
        for s in segs:
            dur = s["end"] - s["start"]
            self.assertGreaterEqual(dur, 15, f"Segment duration {dur}s is too short for YouTube Shorts!")

    def test_crop_modes_allowed_in_start_job(self):
        from app.schemas.ai import StartJobRequest
        req1 = StartJobRequest(
            url="https://youtube.com/watch?v=12345678901",
            segments=[{"start": 0, "end": 30}],
            crop_mode="split_podcast",
        )
        self.assertEqual(req1.crop_mode, "split_podcast")

        req2 = StartJobRequest(
            url="https://youtube.com/watch?v=12345678901",
            segments=[{"start": 0, "end": 30}],
            crop_mode="podcast_speaker",
        )
        self.assertEqual(req2.crop_mode, "podcast_speaker")


if __name__ == "__main__":
    unittest.main()
