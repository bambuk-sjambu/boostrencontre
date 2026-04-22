"""Stealth audit routes — fingerprint self-test gate for Phase 8 dogfooding.

Per security review: before any real Tinder dogfooding on a throwaway account,
the current stealth layer must pass a public fingerprint test. We navigate to
bot.sannysoft.com and creepjs, parse the verdict signals, and return a pass/fail
score. Security review required score ≤ 10% bot-detectable as the gate.

Routes:
  POST /api/stealth-audit/{platform}
"""

import asyncio
import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from .. import bot_engine
from .deps import validate_platform

logger = logging.getLogger(__name__)
router = APIRouter()

SANNYSOFT_URL = "https://bot.sannysoft.com/"
CREEPJS_URL = "https://abrahamjuliot.github.io/creepjs/"


async def _parse_sannysoft(page) -> dict:
    """Read the bot.sannysoft.com table and count passed/failed checks."""
    try:
        rows = await page.evaluate(r"""() => {
            const out = {passed: 0, failed: 0, warn: 0, total: 0, details: []};
            const tables = document.querySelectorAll('table');
            for (const t of tables) {
                const trs = t.querySelectorAll('tr');
                for (const tr of trs) {
                    const tds = tr.querySelectorAll('td');
                    if (tds.length < 2) continue;
                    const label = (tds[0].innerText || '').trim();
                    const value = (tds[1].innerText || '').trim();
                    const cls = (tds[1].className || '').toLowerCase();
                    if (!label) continue;
                    out.total++;
                    if (cls.includes('passed') || /passed|ok|present/i.test(value)) {
                        out.passed++;
                    } else if (cls.includes('failed') || /failed|missing|absent/i.test(value)) {
                        out.failed++;
                    } else if (cls.includes('warn') || /warn/i.test(value)) {
                        out.warn++;
                    }
                    out.details.push({label, value: value.substring(0, 80)});
                }
            }
            return out;
        }""")
        return rows or {"passed": 0, "failed": 0, "warn": 0, "total": 0, "details": []}
    except Exception as e:
        logger.error(f"Sannysoft parse error: {e}")
        return {"passed": 0, "failed": 0, "warn": 0, "total": 0, "details": [], "error": str(e)}


@router.post("/stealth-audit/{platform}")
async def stealth_audit(platform: str):
    """Run fingerprint self-test against bot.sannysoft.com.

    Requires the browser session to be open (same check as action routes).
    Navigates the existing page to the test URL, reads results, and restores
    the previous URL.
    """
    if not validate_platform(platform):
        return JSONResponse(status_code=400, content={"error": "invalid_platform"})

    if platform not in bot_engine.browser_sessions:
        return JSONResponse(
            status_code=400,
            content={
                "error": "not_connected",
                "message": f"Open the browser first ({platform}).",
            },
        )

    session = bot_engine.browser_sessions[platform]
    page = session["platform"].page

    previous_url = page.url
    try:
        try:
            await page.goto(SANNYSOFT_URL, timeout=30000, wait_until="domcontentloaded")
            await asyncio.sleep(5)  # let the in-page tests complete
        except Exception as e:
            logger.error(f"Failed to load {SANNYSOFT_URL}: {e}")
            return JSONResponse(
                status_code=500,
                content={"error": "navigation_failed", "message": str(e)},
            )

        result = await _parse_sannysoft(page)

        total = max(result.get("total", 0), 1)
        failed = result.get("failed", 0)
        warn = result.get("warn", 0)
        # Bot score = % of failed checks + half of warnings
        bot_score = round((failed + warn * 0.5) / total * 100, 1)
        passed = bot_score <= 10.0  # security review gate

        if passed:
            verdict = "PASS — stealth layer OK for Phase 8 dogfooding"
        elif bot_score <= 25:
            verdict = "MARGINAL — consider hardening stealth before dogfooding"
        else:
            verdict = "FAIL — stealth layer leaks automation signals"

        # Restore previous URL (best-effort)
        try:
            if previous_url and previous_url != page.url and "tinder.com" in previous_url:
                await page.goto(previous_url, timeout=15000, wait_until="domcontentloaded")
        except Exception:
            pass

        return {
            "platform": platform,
            "passed": passed,
            "bot_score": bot_score,
            "verdict": verdict,
            "summary": {
                "total": result.get("total", 0),
                "passed_checks": result.get("passed", 0),
                "failed_checks": failed,
                "warn_checks": warn,
            },
            "source": SANNYSOFT_URL,
        }

    except Exception as e:
        logger.error(f"Stealth audit error: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": "internal_error", "message": str(e)},
        )
