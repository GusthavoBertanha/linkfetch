from __future__ import annotations

import unittest

from linkfetch.resolvers.vikingfile import VikingFileResolver, is_vikingfile_link


class VikingFileResolverTests(unittest.TestCase):
    def test_recognizes_original_and_redirect_hosts(self) -> None:
        original = "https://vikingfile.com/f/AbC123"
        redirected = "https://vik1ngfile.site/f/AbC123"
        self.assertTrue(is_vikingfile_link(original))
        self.assertTrue(is_vikingfile_link(redirected))
        self.assertTrue(VikingFileResolver().supports(original))

    def test_rejects_unrelated_paths_and_hosts(self) -> None:
        self.assertFalse(is_vikingfile_link("https://vikingfile.com/premium"))
        self.assertFalse(is_vikingfile_link("https://example.com/f/AbC123"))


if __name__ == "__main__":
    unittest.main()
