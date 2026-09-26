from __future__ import annotations

import unittest

from linkfetch.resolvers.known_hosts import (
    KnownHostResolver,
    KnownHostUnavailableError,
    normalized_known_host,
)


class KnownHostResolverTests(unittest.TestCase):
    def test_recognizes_known_unresolved_hosts(self) -> None:
        samples = {
            "https://qiwi.gg/file/abc": "qiwi.gg",
            "https://ranoz.gg/file/abc": "ranoz.gg",
            "https://www.rootz.so/d/abc": "rootz.so",
            "https://transfer.it/t/abc": "transfer.it",
            "https://letsupload.io/abc/file.bin": "letsupload.io",
            "https://uptobox.com/abc": "uptobox.com",
        }
        for url, expected in samples.items():
            with self.subTest(url=url):
                self.assertEqual(normalized_known_host(url), expected)

    def test_does_not_claim_other_hosts(self) -> None:
        self.assertIsNone(normalized_known_host("https://example.com/file"))

    def test_returns_a_specific_diagnostic(self) -> None:
        resolver = KnownHostResolver()
        with self.assertRaisesRegex(KnownHostUnavailableError, "Cloudflare"):
            resolver.resolve("https://qiwi.gg/file/abc")

    def test_reports_parked_letsupload_domain(self) -> None:
        with self.assertRaisesRegex(KnownHostUnavailableError, "listed for sale"):
            KnownHostResolver().resolve("https://letsupload.io/abc/file.bin")


if __name__ == "__main__":
    unittest.main()
