from __future__ import annotations

from urllib.parse import urlsplit

from linkfetch.models import ResolvedDownload
from linkfetch.resolvers.base import Resolver
from linkfetch.webview_capture import capture_download_click

VIKINGFILE_HOSTS = {
    "vikingfile.com",
    "www.vikingfile.com",
    "vik1ngfile.site",
    "www.vik1ngfile.site",
}


def is_vikingfile_link(url: str) -> bool:
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower()
    parts = [part for part in parsed.path.split("/") if part]
    return (
        parsed.scheme in {"http", "https"}
        and host in VIKINGFILE_HOSTS
        and len(parts) == 2
        and parts[0] == "f"
    )


class VikingFileResolver(Resolver):
    def supports(self, url: str) -> bool:
        return is_vikingfile_link(url)

    def resolve(self, url: str) -> ResolvedDownload:
        return capture_download_click(url, button_selector="#download-link")
