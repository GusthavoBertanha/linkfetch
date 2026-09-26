from __future__ import annotations

import re
from urllib.parse import urlsplit

from linkfetch.models import ResolvedDownload
from linkfetch.resolvers.base import Resolver

FILE_ID = re.compile(r"^[A-Za-z0-9_-]+$")
PIXELDRAIN_HOSTS = {"pixeldrain.com", "www.pixeldrain.com"}


def pixeldrain_file_id(url: str) -> str | None:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or (parsed.hostname or "").lower() not in PIXELDRAIN_HOSTS:
        return None
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) == 2 and parts[0] == "u":
        candidate = parts[1]
    elif len(parts) >= 3 and parts[:2] == ["api", "file"]:
        candidate = parts[2]
    else:
        return None
    return candidate if FILE_ID.fullmatch(candidate) else None


class PixelDrainResolver(Resolver):
    def supports(self, url: str) -> bool:
        return pixeldrain_file_id(url) is not None

    def resolve(self, url: str) -> ResolvedDownload:
        file_id = pixeldrain_file_id(url)
        if not file_id:
            raise ValueError("Invalid PixelDrain file link.")
        return ResolvedDownload(
            url=f"https://pixeldrain.com/api/file/{file_id}?download",
            headers={"Referer": f"https://pixeldrain.com/u/{file_id}"},
        )
