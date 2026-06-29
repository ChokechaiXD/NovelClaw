"""Adapter registry for source imports."""

from __future__ import annotations

from .base import SourceAdapter
from .static_sites import ADAPTERS


def list_adapters() -> list[SourceAdapter]:
    return list(ADAPTERS)


def get_adapter(url: str, site: str = "auto") -> SourceAdapter:
    adapters = list_adapters()
    if site and site != "auto":
        for adapter in adapters:
            if adapter.id == site:
                if adapter.detect(url):
                    return adapter
                raise ValueError(f"Adapter '{site}' does not support this URL")
        raise ValueError(f"Unknown import adapter: {site}")

    for adapter in adapters:
        if adapter.detect(url):
            return adapter
    supported = ", ".join(adapter.id for adapter in adapters)
    raise ValueError(f"Unsupported source URL. Supported adapters: {supported}")
