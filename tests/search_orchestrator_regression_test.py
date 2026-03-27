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
    assert len(result["links"]) >= 1


def test_youtube_search_page_extractor():
    html = """
    {"videoRenderer":{"videoId":"abc123","title":{"runs":[{"text":"OpenClaw Tutorial"}]}}}
    {"videoRenderer":{"videoId":"def456","title":{"runs":[{"text":"OpenClaw Update Review"}]}}}
    """
    result = module.extract_search_page_special("https://www.youtube.com/results?search_query=openclaw", html, "openclaw")
    assert result is not None
    assert result["fetch_mode"] == "search_results"
    assert len(result["links"]) >= 1


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
    assert result["fetch_mode"] in {"domain_search_fallback", "domain_search_deep_fallback"}
    assert result["quality"] in {"medium", "high"}
    assert len(result["links"]) >= 1


def test_root_domain_relaxation_for_subdomain_sites():
    original = module.search_engine

    def fake_search_engine(engine, variant, site_focus):
        return [
            module.SearchResult("Weibo topic", "https://weibo.com/topic/openclaw", "Discussion", engine, variant, site_focus),
            module.SearchResult("Weibo user", "https://www.weibo.com/u/123", "Profile", engine, variant, site_focus),
        ]

    module.search_engine = fake_search_engine
    try:
        result = module.extract_domain_search_fallback("https://s.weibo.com/weibo/openclaw", "openclaw")
    finally:
        module.search_engine = original

    assert result is not None
    assert result["fetch_mode"] in {"domain_search_fallback", "domain_search_deep_fallback"}
    assert len(result["links"]) >= 1


def test_meta_search_fallback_for_search_engines():
    original = module.search_engine

    def fake_search_engine(engine, variant, site_focus):
        return [
            module.SearchResult("OpenClaw GitHub", "https://github.com/openclaw/openclaw", "Repo", engine, variant, site_focus),
            module.SearchResult("OpenClaw Docs", "https://docs.openclaw.ai", "Docs", engine, variant, site_focus),
        ]

    module.search_engine = fake_search_engine
    try:
        result = module.extract_domain_search_fallback("https://www.google.com/search?q=openclaw", "openclaw")
    finally:
        module.search_engine = original

    assert result is not None
    assert result["fetch_mode"] == "meta_search_fallback"
    assert result["quality"] == "medium"
    assert len(result["links"]) >= 2
    assert "meta_search_proxy" in result["applied_rules"]


def test_github_rule_tagging():
    original = module.try_fetch

    def fake_try_fetch(url, timeout=15):
        if "raw.githubusercontent.com" in url:
            return "# OpenClaw\\nclawhub install usage"
        return ""

    module.try_fetch = fake_try_fetch
    try:
        result = module.extract_github_special("https://github.com/openclaw/clawhub", "clawhub install")
    finally:
        module.try_fetch = original

    assert result is not None
    assert result["fetch_mode"] == "github_raw"
    assert "github_raw" in result["applied_rules"]


def test_browser_session_fallback_for_low_signal_pages():
    original_fetch = module.fetch_with_reader_fallback
    original_browser = module.browser_assisted_extract

    def fake_fetch(url):
        return "<html><head><title>Zhihu</title></head><body>登录后查看更多</body></html>", "direct"

    def fake_browser(url, query):
        return {
            "url": url,
            "fetch_mode": "browser_session",
            "title": "知乎问题页",
            "summary": ["命中真实问题内容", "提取到了登录态可见正文"],
            "sections": ["回答摘要"],
            "links": [],
            "quality": "high",
            "applied_rules": ["browser_session_fallback"],
        }

    module.fetch_with_reader_fallback = fake_fetch
    module.browser_assisted_extract = fake_browser
    try:
        result = module.deep_extract("https://www.zhihu.com/question/123", "openclaw 优化")
    finally:
        module.fetch_with_reader_fallback = original_fetch
        module.browser_assisted_extract = original_browser

    assert result["fetch_mode"] == "browser_session"
    assert "browser_session_fallback" in result["applied_rules"]


def test_browser_session_fallback_rejects_wrong_page():
    original_status = module.run_json

    responses = [
        {"running": True, "dom_extract": True, "url": "https://www.zhihu.com/question/123"},
        {"url": "http://127.0.0.1:18789/chat", "title": "OpenClaw Control", "text": "控制台 页面", "headings": [], "links": []},
    ]

    def fake_run_json(args, timeout=45):
        if args[1] == str(module.BRIDGE):
            if args[2] == "status":
                return responses[0]
            if args[2] == "open":
                return {"ok": True}
            if args[2] == "extract":
                return responses[1]
        raise AssertionError(args)

    module.run_json = fake_run_json
    try:
        result = module.browser_assisted_extract("https://www.zhihu.com/question/123", "openclaw 优化")
    finally:
        module.run_json = original_status

    assert result is None


def test_generic_search_shell_extraction_from_sections():
    html = """
    <html><head><title>openclaw-哔哩哔哩_bilibili</title></head><body>
      <h3>OpenClaw 全网最细教学：安装→Skills实战→多Agent协作</h3>
      <h3>OpenClaw 多智能体团队搭建经验</h3>
      <h3>OpenClaw 本地部署与接入飞书教程</h3>
    </body></html>
    """
    parser = module.Extractor()
    parser.feed(html)
    result = module.extract_parser_search_results(
        "https://search.bilibili.com/all?keyword=openclaw",
        parser,
        "openclaw 优化",
    )

    assert result["fetch_mode"] == "search_results"
    assert "search_shell_fallback" in result["applied_rules"]
    assert len(result["summary"]) >= 3



if __name__ == "__main__":
    test_pypi_search_page_extractor()
    test_youtube_search_page_extractor()
    test_domain_search_fallback_for_blocked_page()
    test_root_domain_relaxation_for_subdomain_sites()
    test_meta_search_fallback_for_search_engines()
    test_github_rule_tagging()
    test_browser_session_fallback_for_low_signal_pages()
    test_browser_session_fallback_rejects_wrong_page()
    test_generic_search_shell_extraction_from_sections()
    print("search orchestrator regression tests passed")
