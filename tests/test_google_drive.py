from __future__ import annotations

import unittest

from linkfetch.resolvers.google_drive import GoogleDriveResolver, google_drive_file_id


class GoogleDriveResolverTests(unittest.TestCase):
    def test_extracts_id_from_file_page(self) -> None:
        url = "https://drive.google.com/file/d/1q0WDZrNccx0VZnSbbkjDd22emqrw1ayj/view"
        self.assertEqual(google_drive_file_id(url), "1q0WDZrNccx0VZnSbbkjDd22emqrw1ayj")

    def test_extracts_id_from_query_variants(self) -> None:
        file_id = "1q0WDZrNccx0VZnSbbkjDd22emqrw1ayj"
        self.assertEqual(google_drive_file_id(f"https://drive.google.com/open?id={file_id}"), file_id)
        self.assertEqual(google_drive_file_id(f"https://drive.google.com/uc?export=download&id={file_id}"), file_id)

    def test_rejects_folders_and_other_hosts(self) -> None:
        self.assertIsNone(google_drive_file_id("https://drive.google.com/drive/folders/abc123"))
        self.assertIsNone(google_drive_file_id("https://example.com/file/d/1234567890/view"))

    def test_resolves_to_content_endpoint(self) -> None:
        source = "https://drive.google.com/file/d/1q0WDZrNccx0VZnSbbkjDd22emqrw1ayj/view"
        result = GoogleDriveResolver().resolve(source)
        self.assertEqual(
            result.url,
            "https://drive.usercontent.google.com/download?id=1q0WDZrNccx0VZnSbbkjDd22emqrw1ayj&export=download&confirm=t",
        )
        self.assertEqual(result.headers["Referer"], source)


if __name__ == "__main__":
    unittest.main()
