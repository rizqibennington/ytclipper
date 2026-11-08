import unittest
from fastapi.testclient import TestClient

from app import create_app
from app.clipper import _hex_to_ass_color


class TestSubtitleStyle(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.client = TestClient(self.app)

    def test_hex_to_ass_color(self):
        # Standard white #FFFFFF -> &H00FFFFFF
        self.assertEqual(_hex_to_ass_color("#FFFFFF"), "&H00FFFFFF")
        # Standard yellow #FFFF00 -> Blue=00, Green=FF, Red=FF -> &H0000FFFF
        self.assertEqual(_hex_to_ass_color("#FFFF00"), "&H0000FFFF")
        # Standard cyan #00FFFF -> Blue=FF, Green=FF, Red=00 -> &H00FFFF00
        self.assertEqual(_hex_to_ass_color("#00FFFF"), "&H00FFFF00")
        # Red #FF0000 -> Blue=00, Green=00, Red=FF -> &H000000FF
        self.assertEqual(_hex_to_ass_color("#FF0000"), "&H000000FF")
        # Blue #0000FF -> Blue=FF, Green=00, Red=00 -> &H00FF0000
        self.assertEqual(_hex_to_ass_color("#0000FF"), "&H00FF0000")
        # Fallback on invalid
        self.assertEqual(_hex_to_ass_color("invalid"), "&H00FFFFFF")
        self.assertEqual(_hex_to_ass_color(None), "&H00FFFFFF")

    def test_config_endpoint_persists_subtitle_typography(self):
        res = self.client.post("/api/config", json={
            "subtitle_font_name": "Montserrat",
            "subtitle_font_size": 28,
            "subtitle_font_color": "#FFFF00",
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data.get("ok"))

        # Verify get config
        get_res = self.client.get("/api/config")
        self.assertEqual(get_res.status_code, 200)
        cfg = get_res.json()
        self.assertEqual(cfg.get("subtitle_font_name"), "Montserrat")
        self.assertEqual(cfg.get("subtitle_font_size"), 28)
        self.assertEqual(cfg.get("subtitle_font_color"), "#FFFF00")


if __name__ == "__main__":
    unittest.main()

