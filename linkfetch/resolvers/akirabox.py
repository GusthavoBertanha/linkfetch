from __future__ import annotations

from urllib.parse import urlsplit

from linkfetch.models import ResolvedDownload
from linkfetch.resolvers.base import Resolver
from linkfetch.webview_capture import capture_download_click

AKIRABOX_HOSTS = {"akirabox.com", "www.akirabox.com", "akirabox.to", "www.akirabox.to"}


def is_akirabox_file(url: str) -> bool:
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower()
    parts = [part for part in parsed.path.split("/") if part]
    return parsed.scheme in {"http", "https"} and host in AKIRABOX_HOSTS and len(parts) == 2 and parts[1] == "file"


class AkiraBoxResolver(Resolver):
    def supports(self, url: str) -> bool:
        return is_akirabox_file(url)

    def resolve(self, url: str) -> ResolvedDownload:
        return capture_download_click(url, button_selector="#download")
