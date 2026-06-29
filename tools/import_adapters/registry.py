"""Adapter registry for source imports."""

from __future__ import annotations

from .base import SourceAdapter
from .static_sites import ADAPTERS


def list_adapters() -> list[SourceAdapter]:
    return list(ADAPTERS)


def adapter_info(adapter: SourceAdapter) -> dict:
    adapter_type = getattr(adapter, "adapter_type", "static_html")
    return {
        "id": adapter.id,
        "displayName": getattr(adapter, "display_name", adapter.id),
        "sourceLang": getattr(adapter, "source_lang", "cn"),
        "domains": list(getattr(adapter, "domains", ())),
        "adapterType": adapter_type,
        "status": getattr(adapter, "status", "supported"),
        "quality": getattr(adapter, "quality", "beta"),
        "capabilities": {
            "toc": hasattr(adapter, "fetch_toc"),
            "chapter": hasattr(adapter, "fetch_chapter"),
            "pattern": adapter_type == "pattern",
            "embeddedJson": adapter_type == "embedded_json",
            "ocr": False,
        },
        "access": {
            "requiresJs": bool(getattr(adapter, "requires_js", False)),
            "requiresLogin": bool(getattr(adapter, "requires_login", False)),
            "hasPaywall": bool(getattr(adapter, "has_paywall", False)),
        },
        "notes": getattr(adapter, "notes", ""),
    }


def list_site_catalog() -> dict:
    return {
        "sites": [adapter_info(adapter) for adapter in list_adapters()],
        "fallbackAdapters": [
            {
                "id": "manual-paste",
                "displayName": "Manual Paste",
                "adapterType": "manual",
                "status": "supported",
                "quality": "review",
                "capabilities": {"toc": False, "chapter": True, "pattern": False, "embeddedJson": False, "ocr": False},
                "access": {"requiresJs": False, "requiresLogin": False, "hasPaywall": False},
                "notes": "Use when a site blocks scraping or when source text is already available.",
            },
            {
                "id": "ocr",
                "displayName": "OCR",
                "adapterType": "ocr",
                "status": "planned",
                "quality": "needs_review",
                "capabilities": {"toc": False, "chapter": True, "pattern": False, "embeddedJson": False, "ocr": True},
                "access": {"requiresJs": False, "requiresLogin": False, "hasPaywall": False},
                "notes": "Reserved for image/PDF/scanned sources. Not part of the core HTML import path.",
            },
        ],
    }


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
