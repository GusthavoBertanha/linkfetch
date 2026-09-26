from __future__ import annotations

import re
from urllib.parse import urlsplit

from linkfetch.models import ResolvedDownload
from linkfetch.resolvers.base import Resolver

MEGA_HOSTS = {"mega.nz", "www.mega.nz"}
PUBLIC_PATH = re.compile(r"^/(file|folder)/[A-Za-z0-9_-]+$")


def is_mega_public_link(url: str) -> bool:
    parsed = urlsplit(url)
    return (
        parsed.scheme == "https"
        and (parsed.hostname or "").lower() in MEGA_HOSTS
        and bool(PUBLIC_PATH.fullmatch(parsed.path))
        and bool(parsed.fragment)
    )


class MegaResolver(Resolver):
    def supports(self, url: str) -> bool:
        return is_mega_public_link(url)

    def resolve(self, url: str) -> ResolvedDownload:
        if not is_mega_public_link(url):
            raise ValueError("Invalid MEGA public link or missing decryption key.")
        return ResolvedDownload(url=url, transport="mega")
