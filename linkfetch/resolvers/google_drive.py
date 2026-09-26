from __future__ import annotations

import re
from urllib.parse import parse_qs, urlsplit

from linkfetch.models import ResolvedDownload
from linkfetch.resolvers.base import Resolver

DRIVE_HOSTS = {"drive.google.com", "www.drive.google.com"}
FILE_ID = re.compile(r"^[A-Za-z0-9_-]{10,}$")


def google_drive_file_id(url: str) -> str | None:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or (parsed.hostname or "").lower() not in DRIVE_HOSTS:
        return None
    parts = [part for part in parsed.path.split("/") if part]
    candidate: str | None = None
    if len(parts) >= 3 and parts[:2] == ["file", "d"]:
        candidate = parts[2]
    elif parsed.path in {"/open", "/uc"}:
        candidate = parse_qs(parsed.query).get("id", [None])[0]
    return candidate if candidate and FILE_ID.fullmatch(candidate) else None


class GoogleDriveResolver(Resolver):
    def supports(self, url: str) -> bool:
        return google_drive_file_id(url) is not None

    def resolve(self, url: str) -> ResolvedDownload:
        file_id = google_drive_file_id(url)
        if not file_id:
            raise ValueError("Invalid Google Drive public file link.")
        return ResolvedDownload(
            url=(
                "https://drive.usercontent.google.com/download"
                f"?id={file_id}&export=download&confirm=t"
            ),
            headers={"Referer": url},
        )
