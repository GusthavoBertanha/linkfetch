from __future__ import annotations

import unittest

from linkfetch.resolvers.mediafire import (
    MediaFireResolutionError,
    MediaFireResolver,
    extract_mediafire_download,
    is_mediafire_download,
    is_mediafire_page,
)


class MediaFireResolverTests(unittest.TestCase):
    def test_recognizes_public_file_page(self) -> None:
        url = "https://www.mediafire.com/file/abc123/example.zip/file"
        self.assertTrue(is_mediafire_page(url))
        self.assertTrue(MediaFireResolver().supports(url))

    def test_does_not_claim_unrelated_mediafire_page(self) -> None:
        self.assertFalse(is_mediafire_page("https://www.mediafire.com/about/"))

    def test_extracts_official_download_button(self) -> None:
        html = """
        <html><body>
          <a href="https://advertising.example/download">DOWNLOAD</a>
          <a id="downloadButton" class="input popsok"
             href="https://download123.mediafire.com/token/folder/example%20file.zip"
             aria-label="Download file">Download (10 MB)</a>
        </body></html>
        """
        url, filename = extract_mediafire_download(
            html, "https://www.mediafire.com/file/abc/example/file"
        )
        self.assertEqual(
            url,
            "https://download123.mediafire.com/token/folder/example%20file.zip",
        )
        self.assertEqual(filename, "example file.zip")

    def test_rejects_advertising_link_even_when_marked_as_download(self) -> None:
        html = '<a id="downloadButton" href="https://advertising.example/file">Download</a>'
        with self.assertRaises(MediaFireResolutionError):
            extract_mediafire_download(html, "https://www.mediafire.com/file/abc/example/file")

    def test_accepts_known_download_hosts_only(self) -> None:
        self.assertTrue(is_mediafire_download("https://download12.mediafire.com/a/b/file.zip"))
        self.assertTrue(is_mediafire_download("https://cdn.mediafireusercontent.com/a/file.zip"))
        self.assertFalse(is_mediafire_download("https://mediafire.com/file/abc/name/file"))
        self.assertFalse(is_mediafire_download("https://evil.example/file.zip"))


if __name__ == "__main__":
    unittest.main()
