from __future__ import annotations

import tempfile
import threading
import unittest
import ssl
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from linkfetch.downloader import DownloadError, Downloader, compatible_tls_context, safe_filename
from linkfetch.models import ResolvedDownload

PAYLOAD = bytes(range(256)) * 4096


class RangeHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/page":
            body = b"<html><body>download page</body></html>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        start = 0
        range_header = self.headers.get("Range")
        if range_header:
            start = int(range_header.removeprefix("bytes=").split("-", 1)[0])
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {start}-{len(PAYLOAD) - 1}/{len(PAYLOAD)}")
        else:
            self.send_response(200)
        body = PAYLOAD[start:]
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Content-Disposition", 'attachment; filename="fixture.bin"')
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        pass


class DownloaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), RangeHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}/file"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()

    def test_downloads_file_and_removes_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            result = Downloader(output, quiet=True).download(ResolvedDownload(self.url))
            self.assertEqual(result.name, "fixture.bin")
            self.assertEqual(result.read_bytes(), PAYLOAD)
            self.assertEqual(list(output.glob("*.linkfetch.json")), [])

    def test_resumes_existing_partial_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            halfway = len(PAYLOAD) // 2
            (output / "fixture.bin.part").write_bytes(PAYLOAD[:halfway])
            result = Downloader(output, quiet=True).download(ResolvedDownload(self.url, filename="fixture.bin"))
            self.assertEqual(result.read_bytes(), PAYLOAD)

    def test_resumes_when_server_supplies_a_different_filename(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            halfway = len(PAYLOAD) // 2
            (output / "file.part").write_bytes(PAYLOAD[:halfway])
            result = Downloader(output, quiet=True).download(ResolvedDownload(self.url))
            self.assertEqual(result.name, "fixture.bin")
            self.assertEqual(result.read_bytes(), PAYLOAD)
            self.assertFalse((output / "file.part").exists())

    def test_sanitizes_filename(self) -> None:
        self.assertEqual(safe_filename('../bad<>:"name?.zip'), "_bad____name_.zip")

    def test_compatible_tls_still_verifies_certificates(self) -> None:
        context = compatible_tls_context()
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(context.check_hostname)
        strict = getattr(ssl, "VERIFY_X509_STRICT", 0)
        if strict:
            self.assertFalse(context.verify_flags & strict)

    def test_refuses_to_save_an_html_page_as_a_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            page_url = f"http://127.0.0.1:{self.server.server_port}/page"
            with self.assertRaisesRegex(DownloadError, "HTML page"):
                Downloader(output, retries=5, quiet=True).download(ResolvedDownload(page_url))
            self.assertEqual(list(output.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
