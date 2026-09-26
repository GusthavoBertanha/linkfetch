from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class ResolvedDownload:
    url: str
    filename: str | None = None
    headers: dict[str, str] = field(default_factory=dict)
    transport: str = "http"
