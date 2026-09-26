from __future__ import annotations

from linkfetch.models import ResolvedDownload
from linkfetch.resolvers.base import Resolver
from linkfetch.resolvers.buzzheavier import BuzzHeavierResolver
from linkfetch.resolvers.akirabox import AkiraBoxResolver
from linkfetch.resolvers.direct import DirectResolver
from linkfetch.resolvers.filecrypt import FileCryptResolver
from linkfetch.resolvers.google_drive import GoogleDriveResolver
from linkfetch.resolvers.known_hosts import KnownHostResolver
from linkfetch.resolvers.mediafire import MediaFireResolver
from linkfetch.resolvers.mega import MegaResolver
from linkfetch.resolvers.onefichier import OneFichierResolver
from linkfetch.resolvers.pixeldrain import PixelDrainResolver
from linkfetch.resolvers.vikingfile import VikingFileResolver

_resolvers: list[Resolver] = [
    MediaFireResolver(),
    MegaResolver(),
    OneFichierResolver(),
    PixelDrainResolver(),
    AkiraBoxResolver(),
    VikingFileResolver(),
    BuzzHeavierResolver(),
    GoogleDriveResolver(),
    FileCryptResolver(),
    KnownHostResolver(),
    DirectResolver(),
]


def register(resolver: Resolver, *, first: bool = True) -> None:
    if first:
        _resolvers.insert(0, resolver)
    else:
        _resolvers.append(resolver)


def resolve(url: str) -> ResolvedDownload:
    for resolver in _resolvers:
        if resolver.supports(url):
            return resolver.resolve(url)
    raise ValueError("Unsupported link. Use an HTTP or HTTPS URL.")
