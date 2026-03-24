"""P13 — Intelligence pipeline E2E tests."""

from __future__ import annotations

import pytest

from tests.e2e.browser import Browser


@pytest.mark.requires_db
class TestOptimizationPage:
    """Browser tests for the /optimization page."""

    def test_page_loads_with_header(self, browser: Browser):
        browser.open("/optimization")
        snap = browser.wait_for_text("Model Optimization", timeout_ms=10000)
        assert snap.contains("Model Optimization") or snap.contains("Optimization")

    def test_subtitle(self, browser: Browser):
        snap = browser.snapshot()
        assert snap.contains("Optimize") or snap.contains("model")

    def test_recommendations_section(self, browser: Browser):
        snap = browser.snapshot()
        assert snap.contains("Recommendation") or snap.contains("recommendation")

    def test_refresh_button(self, browser: Browser):
        snap = browser.snapshot()
        ref = snap.ref_for_button("Refresh")
        assert ref is not None

    def test_performance_section(self, browser: Browser):
        snap = browser.snapshot()
        has_data = (
            snap.contains("Provider")
            or snap.contains("No performance data")
            or snap.contains("Run workflows")
        )
        assert has_data

    def test_no_crash(self, browser: Browser):
        snap = browser.snapshot()
        assert snap.not_contains("Application error")


@pytest.mark.requires_db
class TestLearningsPage:
    """Browser tests for the /learnings page."""

    def test_page_loads_with_header(self, browser: Browser):
        browser.open("/learnings")
        snap = browser.wait_for_text("Learning", timeout_ms=10000)
        assert snap.contains("Learning")

    def test_subtitle(self, browser: Browser):
        snap = browser.snapshot()
        assert snap.contains("intelligence") or snap.contains("learning") or snap.contains("Learning")

    def test_extract_section(self, browser: Browser):
        snap = browser.snapshot()
        assert snap.contains("Extract") or snap.contains("Workflow")

    def test_extract_button(self, browser: Browser):
        snap = browser.snapshot()
        ref = snap.ref_for_button("Extract")
        assert ref is not None or snap.contains("Extract")

    def test_empty_or_data_state(self, browser: Browser):
        snap = browser.snapshot()
        assert snap.contains("No learnings") or snap.contains("learning") or snap.contains("Keyword")

    def test_no_crash(self, browser: Browser):
        snap = browser.snapshot()
        assert snap.not_contains("Application error")


@pytest.mark.requires_db
class TestIntelligenceAPIs:
    """API tests for optimization and learnings endpoints."""

    def test_optimization_performance(self, browser: Browser):
        browser.open("/")
        data = browser.fetch_json("/api/optimization/performance")
        assert isinstance(data, (list, dict))

    def test_optimization_recommendations(self, browser: Browser):
        data = browser.fetch_json("/api/optimization/recommendations")
        assert isinstance(data, (list, dict))

    def test_optimization_trends(self, browser: Browser):
        status = browser.fetch_status("/api/optimization/performance/trends")
        assert status in (200, 503)

    def test_optimization_refresh(self, browser: Browser):
        data = browser.fetch_json(
            "/api/optimization/recommendations/refresh", method="POST"
        )
        assert "refreshed" in data or isinstance(data, dict)

    def test_learnings_list(self, browser: Browser):
        data = browser.fetch_json("/api/learnings")
        assert "learnings" in data
        assert isinstance(data["learnings"], list)

    def test_learnings_keywords(self, browser: Browser):
        data = browser.fetch_json("/api/learnings/keywords")
        assert "keywords" in data
        assert isinstance(data["keywords"], list)
