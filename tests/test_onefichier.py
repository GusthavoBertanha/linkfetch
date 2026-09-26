from __future__ import annotations

import unittest

from linkfetch.resolvers.onefichier import (
    OneFichierResolutionError,
    OneFichierResolver,
    extract_onefichier_result,
    is_onefichier_link,
)


class OneFichierResolverTests(unittest.TestCase):
    def test_recognizes_public_share_link(self) -> None:
        url = "https://1fichier.com/?abc123&af=123"
        self.assertTrue(is_onefichier_link(url))
        self.assertTrue(OneFichierResolver().supports(url))

    def test_extracts_final_download_button(self) -> None:
        html = '<a class="ok btn-general btn-orange" href="https://cdn12.1fichier.com/a/file">Click here to download</a>'
        self.assertEqual(
            extract_onefichier_result(html, "https://1fichier.com/?abc123"),
            "https://cdn12.1fichier.com/a/file",
        )

    def test_rejects_login_link(self) -> None:
        html = '<a href="/login.pl">Sign in and download now</a>'
        with self.assertRaises(OneFichierResolutionError):
            extract_onefichier_result(html, "https://1fichier.com/?abc123")

    def test_reports_no_free_slots(self) -> None:
        html = "<p>High demand: all free guest slots are currently in use.</p>"
        with self.assertRaisesRegex(OneFichierResolutionError, "free download slots"):
            extract_onefichier_result(html, "https://1fichier.com/?abc123")


if __name__ == "__main__":
    unittest.main()
