from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from pathlib import Path

from linkfetch.browser import (
    BrowserTarget,
    _executable_from_command,
    browser_candidates,
    classify_browser,
    profile_directory,
    valid_resolved_url,
)
from linkfetch.resolvers.akirabox import AkiraBoxResolver, is_akirabox_file


class BrowserHelpersTests(unittest.TestCase):
    def test_accepts_a_real_destination(self) -> None:
        page = "https://akirabox.to/abc123/file"
        self.assertEqual(
            valid_resolved_url(page, "https://cdn.example/file.bin"),
            "https://cdn.example/file.bin",
        )

    def test_rejects_empty_same_page_and_unsafe_schemes(self) -> None:
        page = "https://akirabox.to/abc123/file"
        self.assertIsNone(valid_resolved_url(page, "#"))
        self.assertIsNone(valid_resolved_url(page, page))
        self.assertIsNone(valid_resolved_url(page, "javascript:alert(1)"))

    def test_profile_uses_local_app_data(self) -> None:
        with patch.dict(os.environ, {"LOCALAPPDATA": "C:/Users/test/AppData/Local"}):
            self.assertEqual(
                profile_directory().as_posix(),
                "C:/Users/test/AppData/Local/LinkFetch/browser-profile",
            )

    def test_akirabox_recognizes_only_file_pages(self) -> None:
        url = "https://akirabox.com/AbC123/file"
        self.assertTrue(is_akirabox_file(url))
        self.assertTrue(AkiraBoxResolver().supports(url))
        self.assertFalse(is_akirabox_file("https://akirabox.com/premium"))
        self.assertFalse(is_akirabox_file("https://example.com/AbC123/file"))

    def test_reads_executable_from_windows_command(self) -> None:
        command = '"C:\\Program Files\\Browser\\browser.exe" --single-argument %1'
        self.assertEqual(
            _executable_from_command(command),
            Path("C:/Program Files/Browser/browser.exe"),
        )

    def test_classifies_common_chromium_browsers(self) -> None:
        self.assertEqual(
            classify_browser(Path("C:/Program Files/Google/Chrome/Application/chrome.exe")),
            BrowserTarget("Google Chrome", "chromium", channel="chrome"),
        )
        brave = Path("C:/Program Files/BraveSoftware/Brave-Browser/Application/brave.exe")
        self.assertEqual(classify_browser(brave), BrowserTarget("brave", "chromium", executable=brave))

    def test_explicit_browser_preference(self) -> None:
        self.assertEqual(
            browser_candidates("edge"),
            [BrowserTarget("Microsoft Edge", "chromium", channel="msedge")],
        )


if __name__ == "__main__":
    unittest.main()
