from __future__ import annotations

from urllib.parse import urlsplit

from linkfetch.models import ResolvedDownload
from linkfetch.resolvers.base import Resolver


class KnownHostUnavailableError(ValueError):
    pass


MESSAGES = {
    "qiwi.gg": (
        "Qiwi returns a Cloudflare verification page before the file page. "
        "The adapter cannot yet confirm a safe final destination."
    ),
    "ranoz.gg": (
        "The Ranoz domain currently does not resolve in DNS. "
        "The link may belong to a discontinued or temporarily unavailable service."
    ),
    "rootz.so": (
        "Rootz gates its button behind advertising and did not expose a verifiable "
        "file destination. LinkFetch will not continue through this flow."
    ),
    "transfer.it": (
        "Transfer.it uses MEGA's cryptographic client inside the page but does not expose "
        "a reusable public MEGA link and key. This format is not supported yet."
    ),
    "letsupload.io": (
        "The LetsUpload domain is parked and listed for sale. "
        "Old links no longer provide the requested file."
    ),
    "uptobox.com": (
        "Uptobox does not currently provide a usable download flow. "
        "Old links from this service are treated as unavailable."
    ),
}


def normalized_known_host(url: str) -> str | None:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"}:
        return None
    host = (parsed.hostname or "").lower()
    host = host[4:] if host.startswith("www.") else host
    return host if host in MESSAGES else None


class KnownHostResolver(Resolver):
    def supports(self, url: str) -> bool:
        return normalized_known_host(url) is not None

    def resolve(self, url: str) -> ResolvedDownload:
        host = normalized_known_host(url)
        if not host:
            raise ValueError("Unrecognized file host.")
        raise KnownHostUnavailableError(MESSAGES[host])
