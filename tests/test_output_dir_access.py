import os
import tempfile
import unittest
from unittest import mock


from app.services.clip_service import inspect_output_dir


class TestOutputDirAccess(unittest.TestCase):
    def test_existing_dir_ok(self):
        with tempfile.TemporaryDirectory() as d:
            res = inspect_output_dir(d)
            self.assertTrue(res["ok"])
            self.assertIsNone(res["error"])
            self.assertTrue(os.path.isabs(res["path"]))

    def test_missing_dir_not_ok(self):
        with tempfile.TemporaryDirectory() as d:
            missing = os.path.join(d, "does-not-exist")
            res = inspect_output_dir(missing)
            self.assertFalse(res["ok"])
            self.assertIsNotNone(res["error"])

    def test_permission_error_not_ok(self):
        with tempfile.TemporaryDirectory() as d:
            with mock.patch("app.services.clip_service.os.listdir", side_effect=PermissionError()):
                res = inspect_output_dir(d)
                self.assertFalse(res["ok"])
                self.assertIsNotNone(res["error"])
                self.assertIn("Tidak punya akses", res["error"])


if __name__ == "__main__":
    unittest.main()

