import os
import subprocess
import unittest
from app.speaker_tracker import (
    build_dynamic_speaker_crop_filter,
    build_split_podcast_filter,
    ensure_yunet_model,
)


class TestSpeakerTracker(unittest.TestCase):
    def test_ensure_yunet_model(self):
        path = ensure_yunet_model()
        self.assertIsNotNone(path)

    def test_build_split_podcast_filter(self):
        res = {"left_cx": 0.22, "right_cx": 0.78}
        vf = build_split_podcast_filter(res)
        self.assertIn("crop=720:640", vf)
        self.assertIn("0.220*iw", vf)
        self.assertIn("0.780*iw", vf)
        self.assertIn("vstack=inputs=2[out]", vf)

    def test_build_dynamic_speaker_crop_filter_single_interval(self):
        res = {
            "left_cx": 0.25,
            "right_cx": 0.75,
            "intervals": [{"start": 0.0, "end": 10.0, "speaker": "left"}],
        }
        vf = build_dynamic_speaker_crop_filter(res)
        self.assertIn("scale=", vf)
        self.assertIn("crop=720:1280", vf)
        self.assertIn("0.250*iw", vf)

    def test_build_dynamic_speaker_crop_filter_multiple_intervals(self):
        res = {
            "left_cx": 0.28,
            "right_cx": 0.72,
            "intervals": [
                {"start": 0.0, "end": 5.0, "speaker": "left"},
                {"start": 5.0, "end": 12.0, "speaker": "right"},
                {"start": 12.0, "end": 20.0, "speaker": "left"},
            ],
        }
        vf = build_dynamic_speaker_crop_filter(res)
        self.assertIn("between(t\\,0.00\\,5.00)", vf)
        self.assertIn("between(t\\,5.00\\,12.00)", vf)
        self.assertIn("0.280*iw", vf)
        self.assertIn("0.720*iw", vf)

    def test_ffmpeg_execution_with_filters(self):
        ffmpeg_bin = os.path.join(os.path.dirname(__file__), "..", "bin", "ffmpeg.exe")
        if not os.path.exists(ffmpeg_bin):
            self.skipTest("ffmpeg.exe tidak ditemukan di folder bin")

        # Test split_podcast filter in ffmpeg
        vf_split = build_split_podcast_filter({"left_cx": 0.25, "right_cx": 0.75})
        cmd1 = [
            ffmpeg_bin, "-y", "-f", "lavfi", "-i", "testsrc=duration=0.5:size=1280x720:rate=25",
            "-filter_complex", vf_split, "-map", "[out]", "-c:v", "libx264", "-preset", "ultrafast",
            "-f", "null", "-"
        ]
        res1 = subprocess.run(cmd1, capture_output=True, text=True)
        self.assertEqual(res1.returncode, 0, f"FFmpeg split_podcast failed: {res1.stderr}")

        # Test dynamic speaker filter in ffmpeg
        res_data = {
            "left_cx": 0.25,
            "right_cx": 0.75,
            "intervals": [
                {"start": 0.0, "end": 0.25, "speaker": "left"},
                {"start": 0.25, "end": 0.5, "speaker": "right"}
            ]
        }
        vf_dyn = build_dynamic_speaker_crop_filter(res_data)
        cmd2 = [
            ffmpeg_bin, "-y", "-f", "lavfi", "-i", "testsrc=duration=0.5:size=1280x720:rate=25",
            "-filter_complex", vf_dyn, "-map", "[out]", "-c:v", "libx264", "-preset", "ultrafast",
            "-f", "null", "-"
        ]
        res2 = subprocess.run(cmd2, capture_output=True, text=True)
        self.assertEqual(res2.returncode, 0, f"FFmpeg podcast_speaker failed: {res2.stderr}")

        single_speaker = build_dynamic_speaker_crop_filter({
            "intervals": [{"speaker": "left"}],
        })
        cases = (
            ("1280x720", single_speaker),
            ("1280x720", build_dynamic_speaker_crop_filter({"has_faces": False})),
            ("720x1280", vf_split),
        )
        for size, vf in cases:
            with self.subTest(size=size, filter=vf):
                result = subprocess.run([
                    ffmpeg_bin, "-f", "lavfi", "-i", f"color=s={size}",
                    "-filter_complex", f"{vf};[out]showinfo[probe]",
                    "-map", "[probe]", "-frames:v", "1", "-f", "null", "-",
                ], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("sar:1/1 s:720x1280", result.stderr)


if __name__ == "__main__":
    unittest.main()

