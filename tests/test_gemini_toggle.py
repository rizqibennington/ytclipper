import tempfile
import unittest
from unittest import mock


from app.services import clip_service


class TestGeminiToggle(unittest.TestCase):
    def test_start_job_disables_gemini_even_if_config_has_key(self):
        captured = {}

        def _fake_start_job(job_id, payload):
            captured["job_id"] = job_id
            captured["payload"] = payload

        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(clip_service, "load_config", return_value={"gemini_api_key": "CFGKEY"}):
                with mock.patch.object(clip_service, "save_config"):
                    with mock.patch.object(clip_service, "create_job"):
                        with mock.patch.object(clip_service, "start_job", side_effect=_fake_start_job):
                            res = clip_service.start_clip_job(
                                {
                                    "url": "https://youtu.be/dQw4w9WgXcQ",
                                    "segments": [{"enabled": True, "start": 0, "end": 10}],
                                    "output_dir": d,
                                    "use_gemini_suggestions": False,
                                    "gemini_api_key": "",
                                }
                            )
        self.assertTrue(res.get("ok"))
        self.assertIn("payload", captured)
        self.assertIsNone(captured["payload"].get("gemini_api_key"))

    def test_start_job_enables_gemini_uses_config_key_when_missing(self):
        captured = {}

        def _fake_start_job(job_id, payload):
            captured["payload"] = payload

        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(clip_service, "load_config", return_value={"gemini_api_key": "CFGKEY"}):
                with mock.patch.object(clip_service, "save_config"):
                    with mock.patch.object(clip_service, "create_job"):
                        with mock.patch.object(clip_service, "start_job", side_effect=_fake_start_job):
                            clip_service.start_clip_job(
                                {
                                    "url": "https://youtu.be/dQw4w9WgXcQ",
                                    "segments": [{"enabled": True, "start": 0, "end": 10}],
                                    "output_dir": d,
                                    "use_gemini_suggestions": True,
                                    "gemini_api_key": "",
                                }
                            )
        self.assertEqual(captured["payload"].get("gemini_api_key"), "CFGKEY")


if __name__ == "__main__":
    unittest.main()

