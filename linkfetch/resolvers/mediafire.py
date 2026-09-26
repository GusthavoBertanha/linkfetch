from __future__ import annotations

from http.cookiejar import CookieJar
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urljoin, urlsplit
from urllib.request import HTTPCookieProcessor, Request, build_opener

from linkfetch.models import ResolvedDownload
from linkfetch.resolvers.base import Resolver

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 LinkFetch/0.1"
MEDIAFIRE_PAGE_HOSTS = {"mediafire.com", "www.mediafire.com"}


class MediaFireResolutionError(ValueError):
    pass


class _DownloadButtonParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.candidates: list[tuple[int, str, str | None]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        values = {key.lower(): value for key, value in attrs}
        href = values.get("href")
        if not href:
            return
        element_id = (values.get("id") or "").lower()
        classes = (values.get("class") or "").lower().split()
        aria = (values.get("aria-label") or "").lower()
        score = 0
        if element_id == "downloadbutton":
            score += 100
        if "input" in classes and "popsok" in classes:
            score += 50
        if "download" in aria:
            score += 20
        if values.get("download") is not None:
            score += 10
        if score:
            self.candidates.append((score, href, values.get("download")))


def is_mediafire_page(url: str) -> bool:
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower()
    return parsed.scheme in {"http", "https"} and host in MEDIAFIRE_PAGE_HOSTS and parsed.path.startswith("/file/")


def is_mediafire_download(url: str) -> bool:
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower()
    return parsed.scheme in {"http", "https"} and (
        host.endswith(".mediafire.com") or host.endswith(".mediafireusercontent.com")
    ) and host not in MEDIAFIRE_PAGE_HOSTS


def extract_mediafire_download(html: str, page_url: str) -> tuple[str, str | None]:
    parser = _DownloadButtonParser()
    parser.feed(html)
    for _score, href, download_name in sorted(parser.candidates, reverse=True):
        candidate = urljoin(page_url, href)
        if is_mediafire_download(candidate):
            filename = download_name or Path(urlsplit(candidate).path).name or None
            return candidate, unquote(filename) if filename else None
    raise MediaFireResolutionError(
        "The official MediaFire download button was not found. "
        "The link may have expired, been removed, or require browser interaction."
    )


class MediaFireResolver(Resolver):
    def supports(self, url: str) -> bool:
        return is_mediafire_page(url)

    def resolve(self, url: str) -> ResolvedDownload:
        cookies = CookieJar()
        opener = build_opener(HTTPCookieProcessor(cookies))
        request = Request(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "en-US,en;q=0.9",
            },
        )
        try:
            with opener.open(request, timeout=30) as response:
                content_type = response.headers.get_content_charset() or "utf-8"
                html = response.read(4 * 1024 * 1024).decode(content_type, errors="replace")
                page_url = response.geturl()
        except (HTTPError, URLError, OSError) as exc:
            raise MediaFireResolutionError(f"Could not open the MediaFire page: {exc}") from exc

        direct_url, filename = extract_mediafire_download(html, page_url)
        cookie_header = "; ".join(f"{cookie.name}={cookie.value}" for cookie in cookies)
        headers = {"Referer": page_url, "User-Agent": USER_AGENT}
        if cookie_header:
            headers["Cookie"] = cookie_header
        return ResolvedDownload(url=direct_url, filename=filename, headers=headers)
