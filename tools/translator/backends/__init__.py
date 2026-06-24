"""Translator backends — consolidated LLM provider implementations.

All backends implement the TranslatorBackend interface (base.py).
"""
from .base import TranslatorBackend
from .openmodel import OpenModelBackend
from .openrouter import OpenRouterBackend

__all__ = ["TranslatorBackend", "OpenModelBackend", "OpenRouterBackend"]
