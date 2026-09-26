from __future__ import annotations

import unittest
from unittest.mock import patch

from linkfetch.models import ResolvedDownload
from linkfetch.resolvers.filecrypt import FileCryptResolutionError, FileCryptResolver, is_filecrypt_container
from linkfetch.webview_capture import extract_filecrypt_link_ids


class FileCryptResolverTests(unittest.TestCase):
    def test_recognizes_container_urls(self) -> None:
        self.assertTrue(is_filecrypt_container("https://filecrypt.cc/Container/92899AE7D6.html"))
        self.assertFalse(is_filecrypt_container("https://filecrypt.cc/Link/ABC.html"))
        self.assertFalse(is_filecrypt_container("https://example.com/Container/ABC.html"))

    def test_extracts_unique_ids_from_onclick_handlers(self) -> None:
        scripts = ["openLink('ABC123', this)", 'return openLink("XYZ_9", this)', "openLink('ABC123')"]
        self.assertEqual(extract_filecrypt_link_ids(scripts), ["ABC123", "XYZ_9"])

    @patch("linkfetch.resolvers.mediafire.MediaFireResolver.resolve")
    @patch("linkfetch.resolvers.mediafire.MediaFireResolver.supports", return_value=True)
    @patch("linkfetch.resolvers.filecrypt.capture_filecrypt_links")
    def test_hands_mediafire_destination_to_its_adapter(self, capture, supports, resolve) -> None:
        capture.return_value = (["https://www.mediafire.com/file/example/file.zip/file"], {})
        resolve.return_value = ResolvedDownload("https://download.example/file.zip")
        result = FileCryptResolver().resolve("https://filecrypt.cc/Container/92899AE7D6.html")
        self.assertEqual(result.url, "https://download.example/file.zip")
        supports.assert_called_once()
        resolve.assert_called_once()

    @patch("linkfetch.resolvers.filecrypt.capture_filecrypt_links")
    def test_rejects_batch_containers_for_now(self, capture) -> None:
        capture.return_value = (["A", "B"], {})
        with self.assertRaisesRegex(FileCryptResolutionError, "Batch containers"):
            FileCryptResolver().resolve("https://filecrypt.cc/Container/92899AE7D6.html")


if __name__ == "__main__":
    unittest.main()
