#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "search_orchestrator.py"

spec = importlib.util.spec_from_file_location("search_orchestrator", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def test_pypi_search_page_extractor():
    html = """
    <html><head><title>PyPI Search</title></head><body>
      <a class="package-snippet" href="/project/openclaw/">
        <span class="package-snippet__name">openclaw</span>
        <p class="package-snippet__description">OpenClaw package</p>
      </a>
      <a class="package-snippet" href="/project/openclaw-sdk/">
        <span class="package-snippet__name">openclaw-sdk</span>
        <p class="package-snippet__description">SDK package</p>
      </a>
    </body></html>
    """
    result = module.extract_search_page_special("https://pypi.org/search/?q=openclaw", html, "openclaw")
    assert result is not None
    assert result["fetch_mode"] == "search_results"
    assert result["quality"] in {"medium", "high"}
    assert len(result["links"]) >= 2


def test_youtube_search_page_extractor():
    html = """
    {"videoRenderer":{"videoId":"abc123","title":{"runs":[{"text":"OpenClaw Tutorial"}]}}}
    {"videoRenderer":{"videoId":"def456","title":{"runs":[{"text":"OpenClaw Update Review"}]}}}
    """
    result = module.extract_search_page_special("https://www.youtube.com/results?search_query=openclaw", html, "openclaw")
    assert result is not None
    assert result["fetch_mode"] == "search_results"
    assert len(result["links"]) >= 2


def test_domain_search_fallback_for_blocked_page():
    original = module.search_engine

    def fake_search_engine(engine, variant, site_focus):
        return [
            module.SearchResult("openclaw · PyPI", "https://pypi.org/project/openclaw/", "OpenClaw package", engine, variant, site_focus),
            module.SearchResult("openclaw-sdk · PyPI", "https://pypi.org/project/openclaw-sdk/", "SDK package", engine, variant, site_focus),
        ]

    module.search_engine = fake_search_engine
    try:
        result = module.extract_domain_search_fallback("https://pypi.org/search/?q=openclaw", "openclaw")
    finally:
        module.search_engine = original

    assert result is not None
    assert result["fetch_mode"] == "domain_search_fallback"
    assert result["quality"] == "medium"
    assert len(result["links"]) >= 2


if __name__ == "__main__":
    test_pypi_search_page_extractor()
    test_youtube_search_page_extractor()
    test_domain_search_fallback_for_blocked_page()
    print("search orchestrator regression tests passed")
