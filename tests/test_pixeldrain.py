from __future__ import annotations

import unittest

from linkfetch.resolvers.pixeldrain import PixelDrainResolver, pixeldrain_file_id


class PixelDrainResolverTests(unittest.TestCase):
    def test_extracts_id_from_public_page(self) -> None:
        self.assertEqual(pixeldrain_file_id("https://pixeldrain.com/u/Abc_123-x"), "Abc_123-x")

    def test_accepts_existing_api_link(self) -> None:
        self.assertEqual(pixeldrain_file_id("https://pixeldrain.com/api/file/abc123?download"), "abc123")

    def test_rejects_lists_and_unrelated_pages(self) -> None:
        self.assertIsNone(pixeldrain_file_id("https://pixeldrain.com/l/abc123"))
        self.assertIsNone(pixeldrain_file_id("https://example.com/u/abc123"))

    def test_resolves_to_documented_download_endpoint(self) -> None:
        result = PixelDrainResolver().resolve("https://pixeldrain.com/u/abc123")
        self.assertEqual(result.url, "https://pixeldrain.com/api/file/abc123?download")
        self.assertEqual(result.headers["Referer"], "https://pixeldrain.com/u/abc123")


if __name__ == "__main__":
    unittest.main()
