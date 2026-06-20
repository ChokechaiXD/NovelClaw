import importlib.util
import urllib.request

import pytest

SERVER_URL = "http://localhost:4173"


def _playwright_available() -> bool:
    return importlib.util.find_spec("playwright") is not None


def _server_available() -> bool:
    try:
        with urllib.request.urlopen(SERVER_URL, timeout=1) as response:
            return response.status < 500
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _playwright_available() or not _server_available(),
    reason="Playwright and a running reader server are required for frontend tests.",
)


def test_frontend_navigation():
    from playwright.sync_api import sync_playwright  # noqa: PLC0415

    with sync_playwright() as p:
        # Launch browser in headless mode
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 800, "height": 300})
        page = context.new_page()
        page.on("console", lambda msg: print(f"CONSOLE: {msg.type}: {msg.text}"))
        page.on("pageerror", lambda exc: print(f"PAGE ERROR: {exc}"))
        page.on(
            "requestfailed",
            lambda req: print(f"REQ FAILED: {req.method} {req.url} - {req.failure}"),
        )

        # 1. Load Homepage
        css_response = page.request.get(f"{SERVER_URL}/design-system.css")
        print(
            f"\nDEBUG CSS LOAD: status={css_response.status}, content-type={css_response.headers.get('content-type')}, body_len={len(css_response.text())}"
        )
        page.goto(f"{SERVER_URL}/#home")
        page.wait_for_load_state("networkidle")

        # Verify branding title and sidebar structure
        brand_el = page.locator(".topbar-title")
        page.wait_for_selector(".topbar-title")
        assert brand_el.inner_text() == "NovelClaw"

        # Check active nav item
        home_nav = page.locator('[data-page="home"]')
        assert "active" in home_nav.get_attribute("class")

        # 2. Go to Library page
        page.locator('[data-page="library"]').click()
        page.wait_for_load_state("networkidle")
        assert "#library" in page.url

        # 3. Go to Search page
        page.locator('[data-page="search"]').click()
        page.wait_for_load_state("networkidle")
        assert "#search" in page.url

        # 4. Navigate directly to a Novel page
        page.goto(f"{SERVER_URL}/#novel/global-descent")
        page.wait_for_load_state("networkidle")
        assert "global-descent" in page.url

        # Wait for detail title to load
        page.wait_for_selector(".detail-title")
        novel_title = page.locator(".detail-title").inner_text()
        assert len(novel_title) > 0

        # 5. Load Chapter Reader
        # Click on the first chapter (ตอนที่ 123 or whatever exists)
        # To be safe and deterministic, let's navigate to chapter 123 directly
        page.goto(f"{SERVER_URL}/#novel/global-descent/123")
        page.wait_for_load_state("networkidle")
        assert "123" in page.url

        # Check chapter content is loaded
        page.wait_for_selector("#reader-title")
        page.wait_for_function(
            "document.getElementById('reader-title').textContent !== 'กำลังโหลด...'"
        )
        chapter_title = page.locator("#reader-title").inner_text()
        assert "123" in chapter_title

        # 6. Verify scroll container reset and back-to-top functionality
        # Scroll down using JS
        main_content = page.locator(".main-content")
        body_h = page.evaluate("() => document.body.clientHeight")
        body_overflow = page.evaluate("() => window.getComputedStyle(document.body).overflow")
        app_h = page.evaluate("() => document.getElementById('app-layout').clientHeight")
        app_class = page.evaluate("() => document.getElementById('app-layout').className")
        app_style_height = page.evaluate(
            "() => window.getComputedStyle(document.getElementById('app-layout')).height"
        )
        app_style_overflow = page.evaluate(
            "() => window.getComputedStyle(document.getElementById('app-layout')).overflow"
        )
        main_h = page.evaluate("() => document.querySelector('.main').clientHeight")
        sh = main_content.evaluate("el => el.scrollHeight")
        ch = main_content.evaluate("el => el.clientHeight")
        # Query all stylesheets
        sheets_info = page.evaluate(
            "() => Array.from(document.styleSheets).map(s => ({href: s.href, title: s.title}))"
        )
        print(
            f"\nDEBUG SCROLL HIERARCHY: body={body_h} ({body_overflow}), app_class={app_class}, app={app_h} ({app_style_height}, {app_style_overflow}), main={main_h}, main-content={ch}, scrollHeight={sh}"
        )
        print("\nALL STYLE SHEETS:", sheets_info)

        main_content.evaluate("el => el.scrollTop = 500")
        # Assert scroll position is greater than 0
        scroll_top = main_content.evaluate("el => el.scrollTop")
        assert scroll_top > 0

        # Click the back-to-top button
        page.locator("#reader-back-top").click()
        page.wait_for_timeout(300)  # Wait for smooth scrolling animation

        # Assert scroll is reset to 0
        new_scroll_top = main_content.evaluate("el => el.scrollTop")
        assert new_scroll_top == 0

        # 7. Verify scrolling reset upon chapter navigation
        # Click next chapter button at bottom
        next_btn = page.locator("#reader-next-2")
        if next_btn.is_visible() and not next_btn.is_disabled():
            # Scroll down first
            main_content.evaluate("el => el.scrollTop = 400")

            # Click next chapter
            next_btn.click()
            page.wait_for_load_state("networkidle")
            page.wait_for_selector("#reader-title")

            # Scroll top should be reset automatically to 0 on new chapter load
            ch2_scroll_top = main_content.evaluate("el => el.scrollTop")
            assert ch2_scroll_top == 0

        browser.close()
