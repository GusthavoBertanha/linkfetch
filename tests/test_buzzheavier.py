from __future__ import annotations

import unittest
from unittest.mock import patch

from linkfetch.resolvers.buzzheavier import BuzzHeavierResolver, buzzheavier_file_id


class BuzzHeavierResolverTests(unittest.TestCase):
    def test_recognizes_share_and_direct_paths(self) -> None:
        self.assertEqual(buzzheavier_file_id("https://buzzheavier.com/abc123"), "abc123")
        self.assertEqual(buzzheavier_file_id("https://buzzheavier.com/abc123/download"), "abc123")
        self.assertEqual(buzzheavier_file_id("https://bzzhr.co/d/abc123"), "abc123")
        self.assertEqual(buzzheavier_file_id("https://buzzheavier.com/f/GW70e8OpAAA"), "GW70e8OpAAA")

    def test_rejects_reserved_and_unrelated_paths(self) -> None:
        self.assertIsNone(buzzheavier_file_id("https://buzzheavier.com/developers"))
        self.assertIsNone(buzzheavier_file_id("https://example.com/abc123"))

    @patch("linkfetch.resolvers.buzzheavier.capture_download_click")
    def test_uses_webview_capture(self, capture: object) -> None:
        from linkfetch.models import ResolvedDownload

        capture.return_value = ResolvedDownload("https://cdn.example/file.bin")
        result = BuzzHeavierResolver().resolve("https://buzzheavier.com/abc123")
        self.assertEqual(result.url, "https://cdn.example/file.bin")
        capture.assert_called_once_with(
            "https://buzzheavier.com/abc123",
            button_selector='a[href*="/download"], button[type="submit"]',
        )


if __name__ == "__main__":
    unittest.main()
