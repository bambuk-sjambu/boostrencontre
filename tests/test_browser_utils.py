import asyncio

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.browser_utils import (
    find_tiptap_editor, click_send_button, type_in_editor,
    send_message_in_editor, _safe_goto,
)


# ─── MockPage helper ───

class MockMouse:
    async def click(self, x, y):
        pass


class MockKeyboard:
    async def type(self, text, delay=0):
        pass

    async def press(self, key):
        pass


class MockPage:
    """Lightweight mock for Playwright Page with configurable evaluate results."""

    def __init__(self, evaluate_results=None, url="https://example.com"):
        self._evaluate_results = evaluate_results if evaluate_results is not None else {}
        self._evaluate_call_count = 0
        self._evaluate_calls = []
        self.url = url
        self.mouse = MockMouse()
        self.keyboard = MockKeyboard()

    async def evaluate(self, js, *args):
        self._evaluate_calls.append((js, args))
        self._evaluate_call_count += 1
        # Return configured result or default
        if callable(self._evaluate_results):
            return self._evaluate_results(js, *args)
        if isinstance(self._evaluate_results, list):
            idx = min(self._evaluate_call_count - 1, len(self._evaluate_results) - 1)
            return self._evaluate_results[idx]
        return self._evaluate_results

    async def goto(self, url, **kwargs):
        self.url = url

    async def wait_for_timeout(self, ms):
        pass

    async def query_selector(self, selector):
        return None


# ─── find_tiptap_editor ───

@pytest.mark.asyncio
async def test_find_tiptap_editor_found():
    editor_result = {"found": True, "x": 400, "y": 300, "w": 512, "h": 40}
    page = MockPage(evaluate_results=editor_result)
    result = await find_tiptap_editor(page)
    assert result["found"] is True
    assert result["x"] == 400
    assert result["w"] == 512


@pytest.mark.asyncio
async def test_find_tiptap_editor_not_found():
    page = MockPage(evaluate_results={"found": False})
    result = await find_tiptap_editor(page)
    assert result["found"] is False


@pytest.mark.asyncio
async def test_find_tiptap_editor_with_min_width():
    """min_width parameter should be passed to evaluate."""
    page = MockPage(evaluate_results={"found": True, "x": 100, "y": 100, "w": 200, "h": 30})
    result = await find_tiptap_editor(page, min_width=150)
    assert result["found"] is True
    # Verify the min_width was passed as argument
    assert page._evaluate_calls[0][1] == (150,)


# ─── click_send_button ───

@pytest.mark.asyncio
async def test_click_send_button_found():
    page = MockPage(evaluate_results=True)
    result = await click_send_button(page)
    assert result is True


@pytest.mark.asyncio
async def test_click_send_button_not_found_uses_enter():
    """When no send button found, should press Enter as fallback."""
    page = MockPage(evaluate_results=False)
    page.keyboard = AsyncMock()
    page.keyboard.press = AsyncMock()
    result = await click_send_button(page)
    assert result is False
    page.keyboard.press.assert_called_once_with("Enter")


# ─── type_in_editor ───

@pytest.mark.asyncio
async def test_type_in_editor_clicks_and_types():
    page = MockPage()
    page.mouse = AsyncMock()
    page.mouse.click = AsyncMock()
    page.keyboard = AsyncMock()
    page.keyboard.type = AsyncMock()

    editor_pos = {"x": 400, "y": 300}
    with patch("src.browser_utils.asyncio.sleep", new_callable=AsyncMock):
        await type_in_editor(page, editor_pos, "Hello test message")

    page.mouse.click.assert_called_once_with(400, 300)
    # _human_type calls keyboard.type(char, delay=0) per character
    assert page.keyboard.type.call_count == len("Hello test message")


# ─── send_message_in_editor ───

@pytest.mark.asyncio
async def test_send_message_in_editor_success():
    """Full flow: find editor, type, send."""
    editor_result = {"found": True, "x": 400, "y": 300, "w": 512, "h": 40}
    # First evaluate = find_tiptap_editor, second = click_send_button
    page = MockPage(evaluate_results=[editor_result, True])
    page.mouse = AsyncMock()
    page.mouse.click = AsyncMock()
    page.keyboard = AsyncMock()
    page.keyboard.type = AsyncMock()

    with patch("src.browser_utils.asyncio.sleep", new_callable=AsyncMock):
        result = await send_message_in_editor(page, "Test message")

    assert result is True


@pytest.mark.asyncio
async def test_send_message_in_editor_no_editor():
    """Should return False when no editor found."""
    page = MockPage(evaluate_results={"found": False})

    with patch("src.browser_utils.asyncio.sleep", new_callable=AsyncMock):
        result = await send_message_in_editor(page, "Test message")

    assert result is False


# ─── _safe_goto ───

@pytest.mark.asyncio
async def test_safe_goto_success():
    """When goto succeeds and URL matches, no fallback needed."""
    page = MockPage()

    async def mock_goto(url, **kwargs):
        page.url = url

    page.goto = mock_goto

    with patch("src.browser_utils.asyncio.sleep", new_callable=AsyncMock):
        await _safe_goto(page, "https://app.wyylde.com/fr-fr")

    assert "wyylde" in page.url


@pytest.mark.asyncio
async def test_safe_goto_handles_exception():
    """When goto throws, should not raise and should try fallbacks."""
    page = MockPage(url="https://other.com")

    async def mock_goto_fail(url, **kwargs):
        raise Exception("Navigation failed")

    page.goto = mock_goto_fail
    # evaluate fallbacks also won't change URL, so all 3 attempts run
    page._evaluate_results = None

    with patch("src.browser_utils.asyncio.sleep", new_callable=AsyncMock):
        # Should NOT raise
        await _safe_goto(page, "https://app.wyylde.com/fr-fr")


@pytest.mark.asyncio
async def test_safe_goto_dashboard_url_counts_as_success():
    """If page ends up on /dashboard, it should be considered success (no more fallbacks)."""
    page = MockPage(url="https://app.wyylde.com/fr-fr/dashboard/wall")

    async def mock_goto(url, **kwargs):
        page.url = "https://app.wyylde.com/fr-fr/dashboard/wall"

    page.goto = mock_goto

    with patch("src.browser_utils.asyncio.sleep", new_callable=AsyncMock):
        await _safe_goto(page, "https://app.wyylde.com/fr-fr")

    # Should have stopped after first attempt since /dashboard is in URL
    assert page._evaluate_call_count == 0
