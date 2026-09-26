from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from linkfetch.downloader import Downloader
from linkfetch.resolvers.mega import MegaResolver, is_mega_public_link


class MegaResolverTests(unittest.TestCase):
    def test_recognizes_public_file_and_folder_links(self) -> None:
        self.assertTrue(is_mega_public_link("https://mega.nz/file/abc123#secret_key"))
        self.assertTrue(is_mega_public_link("https://mega.nz/folder/abc123#secret_key"))

    def test_rejects_missing_key_and_unrelated_host(self) -> None:
        self.assertFalse(is_mega_public_link("https://mega.nz/file/abc123"))
        self.assertFalse(is_mega_public_link("https://example.com/file/abc123#secret"))

    def test_selects_official_transport(self) -> None:
        result = MegaResolver().resolve("https://mega.nz/file/abc123#secret_key")
        self.assertEqual(result.transport, "mega")

    def test_uses_native_transport(self) -> None:
        item = MegaResolver().resolve("https://mega.nz/file/abc123#secret_key")
        with tempfile.TemporaryDirectory() as directory:
            with patch("linkfetch.mega_transport.download_public_link") as native:
                native.return_value = Path(directory) / "file.bin"
                result = Downloader(Path(directory), quiet=True).download(item)
            self.assertEqual(result, native.return_value)
            native.assert_called_once()


if __name__ == "__main__":
    unittest.main()
