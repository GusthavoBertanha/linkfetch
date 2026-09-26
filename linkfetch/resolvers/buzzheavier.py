from __future__ import annotations

import re
from urllib.parse import urlsplit

from linkfetch.models import ResolvedDownload
from linkfetch.resolvers.base import Resolver
from linkfetch.webview_capture import capture_download_click

BUZZ_HOSTS = {"buzzheavier.com", "www.buzzheavier.com", "bzzhr.co", "www.bzzhr.co", "bzzhr.to", "www.bzzhr.to"}
FILE_ID = re.compile(r"^[A-Za-z0-9_-]+$")
RESERVED = {"api", "developers", "help", "login", "pricing", "proxy"}


def buzzheavier_file_id(url: str) -> str | None:
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower()
    parts = [part for part in parsed.path.split("/") if part]
    if parsed.scheme != "https" or host not in BUZZ_HOSTS or not parts:
        return None
    if len(parts) == 2 and parts[0] in {"d", "f"}:
        candidate = parts[1]
    elif len(parts) in {1, 2}:
        candidate = parts[0]
    else:
        return None
    if candidate.lower() in RESERVED or not FILE_ID.fullmatch(candidate):
        return None
    return candidate


class BuzzHeavierResolver(Resolver):
    def supports(self, url: str) -> bool:
        return buzzheavier_file_id(url) is not None

    def resolve(self, url: str) -> ResolvedDownload:
        file_id = buzzheavier_file_id(url)
        if not file_id:
            raise ValueError("Invalid BuzzHeavier file link.")
        return capture_download_click(
            url,
            button_selector='a[href*="/download"], button[type="submit"]',
        )
