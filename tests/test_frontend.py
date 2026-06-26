"""Frontend smoke tests — HTTP + HTML checks, no Playwright needed."""

import json
import urllib.request
import urllib.error
import pytest

SERVER_URL = "http://127.0.0.1:4173"


class TestFrontend:
    def test_server_running(self):
        with urllib.request.urlopen(SERVER_URL, timeout=3) as r:
            assert r.status == 200
            html = r.read().decode("utf-8")
            assert "NovelClaw" in html
            assert "side" in html

    def test_css_loads(self):
        with urllib.request.urlopen(SERVER_URL + "/design-system.css", timeout=3) as r:
            assert r.status == 200
            css = r.read().decode("utf-8")
            assert "c-hero" in css

    def test_api_novels(self):
        with urllib.request.urlopen(SERVER_URL + "/api/novels", timeout=3) as r:
            assert r.status == 200
            data = json.loads(r.read().decode("utf-8"))
            assert isinstance(data, list)
            assert len(data) > 0
            assert "slug" in data[0]
            assert "title" in data[0]

    def test_api_chapters(self):
        with urllib.request.urlopen(SERVER_URL + "/api/novels", timeout=2) as r:
            novels = json.loads(r.read().decode("utf-8"))
        if not novels:
            pytest.skip("No novels")
        slug = novels[0]["slug"]
        with urllib.request.urlopen(SERVER_URL + f"/api/novel/{slug}/chapters", timeout=3) as r:
            data = json.loads(r.read().decode("utf-8"))
            assert "chapters" in data
            assert len(data["chapters"]) > 0
