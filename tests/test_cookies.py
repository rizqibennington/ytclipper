import os
import tempfile
import unittest
from fastapi.testclient import TestClient

from app import create_app
from app.yt_utils import (
    delete_cookies,
    get_cookies_path,
    get_cookies_status,
    get_yt_dlp_cookies_args,
    get_yt_dlp_proxy_args,
    save_cookies,
)


class TestCookies(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.test_cookie_path = os.path.join(self.tmpdir.name, "test_cookies.txt")
        self.orig_env = os.environ.get("YTCLIPPER_COOKIES_PATH")
        os.environ["YTCLIPPER_COOKIES_PATH"] = self.test_cookie_path

    def tearDown(self):
        if self.orig_env is not None:
            os.environ["YTCLIPPER_COOKIES_PATH"] = self.orig_env
        else:
            os.environ.pop("YTCLIPPER_COOKIES_PATH", None)
        self.tmpdir.cleanup()

    def test_cookies_status_empty(self):
        status = get_cookies_status()
        self.assertFalse(status["installed"])
        self.assertIsNone(status["path"])

    def test_save_and_get_cookies(self):
        sample_cookie = (
            "# Netscape HTTP Cookie File\n"
            ".youtube.com\tTRUE\t/\tTRUE\t1799999999\tSID\tsample_session_id\n"
            ".google.com\tTRUE\t/\tTRUE\t1799999999\tHSID\tsample_hsid\n"
        )
        saved_path = save_cookies(sample_cookie)
        self.assertEqual(saved_path, self.test_cookie_path)
        self.assertTrue(os.path.isfile(self.test_cookie_path))

        status = get_cookies_status()
        self.assertTrue(status["installed"])
        self.assertEqual(status["line_count"], 2)
        self.assertTrue(status["has_youtube_cookies"])

        args = get_yt_dlp_cookies_args()
        self.assertTrue(len(args) == 2)
        self.assertEqual(args[0], "--cookies")

        deleted = delete_cookies()
        self.assertTrue(deleted)
        self.assertFalse(os.path.isfile(self.test_cookie_path))

    def test_proxy_args(self):
        orig_proxy = os.environ.get("YTCLIPPER_PROXY")
        try:
            os.environ["YTCLIPPER_PROXY"] = "http://127.0.0.1:7890"
            args = get_yt_dlp_proxy_args()
            self.assertEqual(args, ["--proxy", "http://127.0.0.1:7890"])
        finally:
            if orig_proxy is not None:
                os.environ["YTCLIPPER_PROXY"] = orig_proxy
            else:
                os.environ.pop("YTCLIPPER_PROXY", None)

    def test_cookies_api_endpoints(self):
        app = create_app()
        client = TestClient(app)

        # 1. GET status initially
        res = client.get("/api/cookies")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["ok"])
        self.assertFalse(data["status"]["installed"])

        # 2. POST upload cookies
        sample_content = (
            "# Netscape HTTP Cookie File\n"
            ".youtube.com\tTRUE\t/\tTRUE\t1799999999\tLOGIN_INFO\taaa:bbb\n"
        )
        res = client.post("/api/cookies", json={"cookies": sample_content})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["ok"])
        self.assertTrue(data["status"]["installed"])

        # 3. GET status again
        res = client.get("/api/cookies")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["status"]["installed"])

        # 4. DELETE cookies
        res = client.delete("/api/cookies")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()["ok"])

        # 5. GET status after deletion
        res = client.get("/api/cookies")
        self.assertFalse(res.json()["status"]["installed"])


if __name__ == "__main__":
    unittest.main()
