from __future__ import annotations

from urllib.parse import urlsplit

from linkfetch.models import ResolvedDownload
from linkfetch.resolvers.base import Resolver
from linkfetch.webview_capture import capture_filecrypt_links

FILECRYPT_HOSTS = {"filecrypt.cc", "www.filecrypt.cc"}


class FileCryptResolutionError(ValueError):
    pass


def is_filecrypt_container(url: str) -> bool:
    parsed = urlsplit(url)
    return (
        parsed.scheme in {"http", "https"}
        and (parsed.hostname or "").lower() in FILECRYPT_HOSTS
        and parsed.path.lower().startswith("/container/")
        and parsed.path.lower().endswith(".html")
    )


class FileCryptResolver(Resolver):
    def supports(self, url: str) -> bool:
        return is_filecrypt_container(url)

    def resolve(self, url: str) -> ResolvedDownload:
        if not is_filecrypt_container(url):
            raise FileCryptResolutionError("Invalid FileCrypt container URL.")
        destinations, _headers = capture_filecrypt_links(url)
        if len(destinations) != 1:
            raise FileCryptResolutionError(
                f"This FileCrypt container has {len(destinations)} destinations. "
                "Batch containers are not supported yet."
            )
        destination = destinations[0]
        from linkfetch.resolvers.akirabox import AkiraBoxResolver
        from linkfetch.resolvers.buzzheavier import BuzzHeavierResolver
        from linkfetch.resolvers.direct import DirectResolver
        from linkfetch.resolvers.google_drive import GoogleDriveResolver
        from linkfetch.resolvers.mediafire import MediaFireResolver
        from linkfetch.resolvers.mega import MegaResolver
        from linkfetch.resolvers.onefichier import OneFichierResolver
        from linkfetch.resolvers.pixeldrain import PixelDrainResolver
        from linkfetch.resolvers.vikingfile import VikingFileResolver

        adapters = (
            MediaFireResolver(), MegaResolver(), OneFichierResolver(), PixelDrainResolver(),
            AkiraBoxResolver(), VikingFileResolver(), BuzzHeavierResolver(),
            GoogleDriveResolver(), DirectResolver(),
        )
        for adapter in adapters:
            if adapter.supports(destination):
                return adapter.resolve(destination)
        raise FileCryptResolutionError(
            f"FileCrypt resolved to an unsupported destination host: {urlsplit(destination).hostname}"
        )
