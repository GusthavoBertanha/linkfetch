from __future__ import annotations

from abc import ABC, abstractmethod

from linkfetch.models import ResolvedDownload


class Resolver(ABC):
    @abstractmethod
    def supports(self, url: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def resolve(self, url: str) -> ResolvedDownload:
        raise NotImplementedError

