from __future__ import annotations

import json
import os
import re
import ssl
import time
from email.message import Message
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlsplit
from urllib.request import Request, urlopen

from linkfetch.models import ResolvedDownload

CHUNK_SIZE = 1024 * 256
USER_AGENT = "LinkFetch/0.1 (+https://github.com/)"
INVALID_FILENAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


class DownloadError(RuntimeError):
    pass


class PageResponseError(DownloadError):
    pass


def compatible_tls_context() -> ssl.SSLContext:
    context = ssl.create_default_context()
    strict = getattr(ssl, "VERIFY_X509_STRICT", 0)
    if strict:
        # Python 3.13 enables OpenSSL strict mode by default. Some otherwise
        # valid legacy CA chains used by Archive.org mirrors omit a critical
        # marker. Keep chain and hostname verification, relaxing only strict.
        context.verify_flags &= ~strict
    return context


def safe_filename(value: str) -> str:
    value = INVALID_FILENAME.sub("_", unquote(value)).strip(" .")
    return value[:240] or "download.bin"


def filename_from_headers(headers: Message, url: str) -> str:
    disposition = headers.get("Content-Disposition", "")
    filename = headers.get_filename() if disposition else None
    if filename:
        return safe_filename(filename)
    path_name = Path(urlsplit(url).path).name
    return safe_filename(path_name or "download.bin")


class Downloader:
    def __init__(
        self,
        output: Path,
        *,
        retries: int = 5,
        timeout: float = 30,
        resume: bool = True,
        quiet: bool = False,
    ) -> None:
        self.output = output.resolve()
        self.retries = max(0, retries)
        self.timeout = timeout
        self.resume = resume
        self.quiet = quiet

    def download(self, item: ResolvedDownload, name: str | None = None) -> Path:
        self.output.mkdir(parents=True, exist_ok=True)
        if item.transport == "mega":
            from linkfetch.mega_transport import download_public_link
            last_error: Exception | None = None
            for attempt in range(self.retries + 1):
                try:
                    return download_public_link(self, item.url, name=name)
                except (HTTPError, URLError, OSError, DownloadError) as exc:
                    last_error = exc
                    if attempt >= self.retries:
                        break
                    delay = min(30, 2**attempt)
                    self._print(f"Temporary MEGA failure: {exc}. Retrying in {delay}s…")
                    time.sleep(delay)
            raise DownloadError(
                f"MEGA download failed after {self.retries + 1} attempt(s): {last_error}"
            )
        if item.transport != "http":
            raise DownloadError(f"Unknown transport: {item.transport}")
        last_error: Exception | None = None
        selected_name = safe_filename(name or item.filename) if (name or item.filename) else None

        for attempt in range(self.retries + 1):
            try:
                return self._attempt(item, selected_name)
            except (HTTPError, URLError, OSError, DownloadError) as exc:
                last_error = exc
                if isinstance(exc, HTTPError) and exc.code == 403 and "pixeldrain.com" in exc.url:
                    raise DownloadError(
                        "PixelDrain rejected the automated download. Open the page in a browser; "
                        "the service may require a CAPTCHA due to traffic limits or file verification."
                    ) from exc
                if (
                    attempt >= self.retries
                    or isinstance(exc, PageResponseError)
                    or (isinstance(exc, HTTPError) and 400 <= exc.code < 500 and exc.code not in {408, 429})
                ):
                    break
                delay = min(30, 2**attempt)
                self._print(f"Temporary failure: {exc}. Retrying in {delay}s…")
                time.sleep(delay)

        raise DownloadError(f"Download failed after {self.retries + 1} attempt(s): {last_error}")

    def _attempt(self, item: ResolvedDownload, selected_name: str | None) -> Path:
        provisional = selected_name or safe_filename(Path(urlsplit(item.url).path).name or "download.bin")
        part = self.output / f"{provisional}.part"
        state = self.output / f"{provisional}.linkfetch.json"
        offset = part.stat().st_size if self.resume and part.exists() else 0

        headers = {"User-Agent": USER_AGENT, "Accept-Encoding": "identity", **item.headers}
        if offset:
            headers["Range"] = f"bytes={offset}-"
        request = Request(item.url, headers=headers)

        with urlopen(request, timeout=self.timeout, context=compatible_tls_context()) as response:
            status = getattr(response, "status", response.getcode())
            content_type = response.headers.get_content_type().lower()
            if content_type in {"text/html", "application/xhtml+xml"} and not response.headers.get("Content-Disposition"):
                raise PageResponseError(
                    "The URL returned an HTML page instead of a file. "
                    "This site requires a dedicated adapter."
                )
            actual_name = selected_name or item.filename or filename_from_headers(response.headers, response.geturl())
            actual_name = safe_filename(actual_name)

            if offset and status != 206:
                self._print("The server rejected the resume request; restarting the partial file.")
                offset = 0
                part.unlink(missing_ok=True)

            content_length = response.headers.get("Content-Length")
            remaining = int(content_length) if content_length and content_length.isdigit() else None
            total = offset + remaining if remaining is not None else None
            metadata = {
                "url": item.url,
                "final_url": response.geturl(),
                "filename": actual_name,
                "downloaded": offset,
                "total": total,
                "updated_at": time.time(),
            }
            self._write_state(state, metadata)

            mode = "ab" if offset else "wb"
            downloaded = offset
            last_update = time.monotonic()
            started = last_update
            with part.open(mode) as target:
                while True:
                    chunk = response.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    target.write(chunk)
                    downloaded += len(chunk)
                    now = time.monotonic()
                    if now - last_update >= 0.5:
                        metadata["downloaded"] = downloaded
                        metadata["updated_at"] = time.time()
                        self._write_state(state, metadata)
                        self._progress(downloaded, total, now - started)
                        last_update = now
                target.flush()
                os.fsync(target.fileno())

            if total is not None and downloaded != total:
                raise DownloadError(f"Incomplete transfer: {downloaded} of {total} bytes")

            final = self.output / actual_name
            if final.exists():
                raise DownloadError(f"The final file already exists: {final}")
            part.replace(final)
            state.unlink(missing_ok=True)
            self._progress(downloaded, total, max(time.monotonic() - started, 0.001), done=True)
            return final

    @staticmethod
    def _write_state(path: Path, metadata: dict[str, object]) -> None:
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(path)

    def _progress(self, downloaded: int, total: int | None, elapsed: float, *, done: bool = False) -> None:
        if self.quiet:
            return
        speed = downloaded / max(elapsed, 0.001)
        if total:
            percent = downloaded * 100 / total
            message = f"\r{percent:6.2f}%  {format_bytes(downloaded)} / {format_bytes(total)}  {format_bytes(speed)}/s"
        else:
            message = f"\r{format_bytes(downloaded)}  {format_bytes(speed)}/s"
        print(message, end="\n" if done else "", flush=True)

    def _print(self, message: str) -> None:
        if not self.quiet:
            print(message, flush=True)


def format_bytes(value: float) -> str:
    units = ("B", "KiB", "MiB", "GiB", "TiB")
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TiB"
