"""Tests for tools/glossary.py — glossary loading, search, save."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest
import yaml

# Module-level patches
from tools.glossary import (
    NOVELS_DIR,
    PROJECT_ROOT,
    get_glossary_yml_path,
    get_novel_root,
    get_style_yml_path,
    load_style_rules,
    load_terms,
    save_style_rules,
    save_terms,
)


SAMPLE_TERMS = [
    {"source": "测试", "thai": "ทดสอบ", "lock": "locked", "priority": 1,
     "category": "ทั่วไป", "explanation": "", "notes": ""},
    {"source": "系统", "thai": "ระบบ", "lock": "reference", "priority": 2,
     "category": "ทั่วไป", "explanation": "", "notes": ""},
    {"source": "技能", "thai": "สกิล", "lock": "reference", "priority": 2,
     "category": "ทั่วไป", "explanation": "", "notes": ""},
    {"source": "冰霜新星", "thai": "น้ำแข็ง nova", "lock": "auto", "priority": 3,
     "category": "สกิล", "explanation": "", "notes": ""},
]


def test_get_novel_root_default():
    """Default novel root points to global-descent."""
    root = get_novel_root()
    assert root.name == "global-descent"
    assert root.parent.name == "novels"


def test_get_novel_root_env_var(monkeypatch):
    """NOVEL_SLUG env var changes default root (uses schema's cached default)."""
    # Note: _DEFAULT_SLUG is loaded at schema import time,
    # so monkeypatch must happen before any test imports schema.
    # For explicit slug, pass directly:
    root = get_novel_root("test-novel", check_exists=False)
    assert root.name == "test-novel"
    assert root.parent.name == "novels"

def test_get_glossary_yml_path():
    """Glossary path is under glossary/glossary.yml."""
    path = get_glossary_yml_path("test-novel")
    assert path.name == "glossary.yml"
    assert "glossary" in str(path)


def test_get_style_yml_path():
    """Style path is under glossary/style_rules.yml."""
    path = get_style_yml_path("test-novel")
    assert path.name == "style_rules.yml"


def test_load_terms_empty_when_missing(tmp_path, monkeypatch):
    """load_terms returns [] when no glossary.yml exists."""
    monkeypatch.setattr("tools.glossary.NOVELS_DIR", tmp_path / "novels")
    load_terms.cache_clear()
    terms = load_terms("missing-slug")
    assert terms == []


def test_save_and_load_terms_roundtrip(tmp_path, monkeypatch):
    """Save terms → load terms → same data."""
    monkeypatch.setattr("tools.glossary.NOVELS_DIR", tmp_path / "novels")
    load_terms.cache_clear()
    
    slug = "test-roundtrip"
    save_terms(SAMPLE_TERMS, slug)
    
    loaded = load_terms(slug)
    assert len(loaded) == len(SAMPLE_TERMS)
    assert loaded[0]["source"] == "测试"
    assert loaded[0]["thai"] == "ทดสอบ"
    assert loaded[0]["priority"] == 1


def test_save_terms_creates_yaml(tmp_path, monkeypatch):
    """After save, glossary.yml exists and is valid YAML."""
    monkeypatch.setattr("tools.glossary.NOVELS_DIR", tmp_path / "novels")
    load_terms.cache_clear()
    
    slug = "test-create"
    save_terms(SAMPLE_TERMS, slug)
    
    yml_path = get_glossary_yml_path(slug)
    assert yml_path.exists()
    
    data = yaml.safe_load(yml_path.read_text(encoding="utf-8"))
    assert "terms" in data
    assert len(data["terms"]) == 4


def test_load_style_rules_save_and_load(tmp_path, monkeypatch):
    """Save style rules → load back."""
    monkeypatch.setattr("tools.glossary.NOVELS_DIR", tmp_path / "novels")
    load_style_rules.cache_clear()
    
    slug = "test-style"
    rules = {
        "term_choices": [{"text": "Use consistent terminology"}],
        "punctuation": [{"text": "Use Thai punctuation"}],
    }
    save_style_rules(rules, slug)
    
    loaded = load_style_rules(slug)
    assert "term_choices" in loaded
    assert loaded["term_choices"][0]["text"] == "Use consistent terminology"


def test_load_style_rules_empty_when_missing(tmp_path, monkeypatch):
    """load_style_rules returns {} when missing."""
    monkeypatch.setattr("tools.glossary.NOVELS_DIR", tmp_path / "novels")
    load_style_rules.cache_clear()
    rules = load_style_rules("no-style-slug")
    assert rules == {}
