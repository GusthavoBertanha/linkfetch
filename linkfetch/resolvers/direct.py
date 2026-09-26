from __future__ import annotations

from urllib.parse import urlsplit

from linkfetch.models import ResolvedDownload
from linkfetch.resolvers.base import Resolver


class DirectResolver(Resolver):
    def supports(self, url: str) -> bool:
        return urlsplit(url).scheme.lower() in {"http", "https"}

    def resolve(self, url: str) -> ResolvedDownload:
        return ResolvedDownload(url=url)

