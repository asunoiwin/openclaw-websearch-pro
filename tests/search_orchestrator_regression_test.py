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


def test_bilibili_search_card_extractor():
    html = """
    <div class="bili-video-card__wrap">
      <a href="//www.bilibili.com/video/BV1abc123456/" target="_blank">
        <div class="bili-video-card__image">
          <img alt="OpenClaw 保姆级安装教程">
        </div>
      </a>
      <a href="//www.bilibili.com/video/BV9xyz654321/" target="_blank">
        <div class="bili-video-card__image">
          <img alt="OpenClaw Skills 实战">
        </div>
      </a>
    </div>
    """
    result = module.extract_search_page_special("https://search.bilibili.com/all?keyword=openclaw", html, "openclaw")
    assert result is not None
    assert result["fetch_mode"] == "bilibili_search_cards"
    assert "bilibili_search_cards" in result["applied_rules"]
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
    original_flag = module.ENABLE_BROWSER_FALLBACK

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
    module.ENABLE_BROWSER_FALLBACK = True
    try:
        result = module.deep_extract("https://www.zhihu.com/question/123", "openclaw 优化")
    finally:
        module.fetch_with_reader_fallback = original_fetch
        module.browser_assisted_extract = original_browser
        module.ENABLE_BROWSER_FALLBACK = original_flag

    assert result["fetch_mode"] == "browser_session"
    assert "browser_session_fallback" in result["applied_rules"]


def test_yt_dlp_adapter_for_content_page():
    original_run = module.subprocess.run
    original_available = module.yt_dlp_available

    class FakeProc:
        def __init__(self, stdout="", returncode=0):
            self.stdout = stdout
            self.stderr = ""
            self.returncode = returncode

    def fake_run(cmd, text=True, capture_output=True, timeout=35):
        if cmd[:3] == ["python3", "-m", "yt_dlp"] and "--dump-single-json" in cmd:
            return FakeProc(
                stdout='{"title":"OpenClaw Bilibili Tutorial","description":"完整安装与优化教程","uploader":"AI 学长","tags":["OpenClaw","教程"],"view_count":12345,"like_count":321,"duration":456}'
            )
        if cmd[:3] == ["python3", "-m", "yt_dlp"] and "--version" in cmd:
            return FakeProc(stdout="2025.10.14")
        raise AssertionError(cmd)

    module.subprocess.run = fake_run
    module.yt_dlp_available = lambda: True
    try:
        result = module.extract_yt_dlp_special("https://www.bilibili.com/video/BV1abc123456", "OpenClaw 教程")
    finally:
        module.subprocess.run = original_run
        module.yt_dlp_available = original_available

    assert result is not None
    assert result["fetch_mode"] == "yt_dlp"
    assert "yt_dlp_adapter" in result["applied_rules"]
    assert "browser_cookies_chrome" in result["applied_rules"]


def test_yt_dlp_adapter_for_reddit_content_page():
    original_run = module.subprocess.run
    original_available = module.yt_dlp_available

    class FakeProc:
        def __init__(self, stdout="", returncode=0):
            self.stdout = stdout
            self.stderr = ""
            self.returncode = returncode

    def fake_run(cmd, text=True, capture_output=True, timeout=35):
        if cmd[:3] == ["python3", "-m", "yt_dlp"] and "--dump-single-json" in cmd:
            return FakeProc(
                stdout='{"title":"OpenClaw Reddit Discussion","description":"Users shared install notes and failure fixes","uploader":"r/OpenClaw","tags":["OpenClaw","discussion"],"like_count":42,"comment_count":17}'
            )
        if cmd[:3] == ["python3", "-m", "yt_dlp"] and "--version" in cmd:
            return FakeProc(stdout="2025.10.14")
        raise AssertionError(cmd)

    module.subprocess.run = fake_run
    module.yt_dlp_available = lambda: True
    try:
        result = module.extract_yt_dlp_special(
            "https://www.reddit.com/r/openclaw/comments/abc123/openclaw_install_notes/",
            "OpenClaw install notes",
        )
    finally:
        module.subprocess.run = original_run
        module.yt_dlp_available = original_available

    assert result is not None
    assert result["fetch_mode"] == "yt_dlp"
    assert "yt_dlp_adapter" in result["applied_rules"]
    assert "browser_cookies_chrome" in result["applied_rules"]


def test_external_discovery_deep_fallback_prefers_nested_content():
    original_search = module.search_engine
    original_deep = module.deep_extract

    def fake_search_engine(engine, variant, site_focus):
        return [
            module.SearchResult("Weibo post", "https://www.weibo.com/123/abcdef", "OpenClaw release", engine, variant, site_focus),
            module.SearchResult("Weibo search", "https://s.weibo.com/weibo/openclaw", "Search", engine, variant, site_focus),
        ]

    def fake_deep_extract(url, query, allow_fallback=True):
        if "www.weibo.com/123/abcdef" in url:
            return {
                "url": url,
                "fetch_mode": "yt_dlp",
                "title": "OpenClaw 发布",
                "summary": ["OpenClaw 2026.3.22 版本发布，ClawHub 插件市场上线"],
                "sections": [],
                "links": [],
                "quality": "medium",
                "applied_rules": ["yt_dlp_adapter"],
            }
        return {"url": url, "fetch_mode": "direct", "summary": [], "quality": "low"}

    module.search_engine = fake_search_engine
    module.deep_extract = fake_deep_extract
    try:
        result = module.extract_external_discovery_fallback("https://s.weibo.com/weibo/openclaw", "OpenClaw 插件市场")
    finally:
        module.search_engine = original_search
        module.deep_extract = original_deep

    assert result is not None
    assert result["fetch_mode"] == "external_discovery_deep_fallback"
    assert "followup_refinement" in result["applied_rules"]


def test_gallery_dl_adapter_for_weibo_status():
    original_run = module.subprocess.run
    original_available = module.gallery_dl_available

    class FakeProc:
        def __init__(self, stdout="", returncode=0):
            self.stdout = stdout
            self.stderr = ""
            self.returncode = returncode

    def fake_run(cmd, text=True, capture_output=True, timeout=35):
        if cmd[:3] == ["python3", "-m", "gallery_dl"] and "-j" in cmd:
            return FakeProc(
                stdout='[[2, {"text_raw":"OpenClaw 2026.3.22 版本发布 ClawHub 插件市场上线","comments_count":16,"attitudes_count":89,"reposts_count":13,"source":"iPhone 15 Pro","user":{"screen_name":"OpenClaw官方微博"}}]]'
            )
        if cmd[:3] == ["python3", "-m", "gallery_dl"] and "--version" in cmd:
            return FakeProc(stdout="1.31.10")
        raise AssertionError(cmd)

    module.subprocess.run = fake_run
    module.gallery_dl_available = lambda: True
    try:
        result = module.extract_gallery_dl_special("https://www.weibo.com/8343600249/QxsidtsPf", "OpenClaw 插件市场")
    finally:
        module.subprocess.run = original_run
        module.gallery_dl_available = original_available

    assert result is not None
    assert result["fetch_mode"] == "gallery_dl"
    assert "gallery_dl_adapter" in result["applied_rules"]


def test_gallery_dl_adapter_for_reddit_submission():
    original_run = module.subprocess.run
    original_available = module.gallery_dl_available

    class FakeProc:
        def __init__(self, stdout="", returncode=0):
            self.stdout = stdout
            self.stderr = ""
            self.returncode = returncode

    def fake_run(cmd, text=True, capture_output=True, timeout=35):
        if cmd[:3] == ["python3", "-m", "gallery_dl"] and "-j" in cmd:
            return FakeProc(
                stdout='[[2, {"title":"OpenClaw Reddit Discussion","selftext":"Users shared install notes and failure fixes","author":"alice","subreddit":"openclaw","score":42,"num_comments":17,"url":"https://example.com/details","domain":"example.com"}]]'
            )
        if cmd[:3] == ["python3", "-m", "gallery_dl"] and "--version" in cmd:
            return FakeProc(stdout="1.31.10")
        raise AssertionError(cmd)

    module.subprocess.run = fake_run
    module.gallery_dl_available = lambda: True
    try:
        result = module.extract_gallery_dl_special(
            "https://www.reddit.com/r/openclaw/comments/abc123/openclaw_install_notes/",
            "OpenClaw install notes",
        )
    finally:
        module.subprocess.run = original_run
        module.gallery_dl_available = original_available

    assert result is not None
    assert result["fetch_mode"] == "gallery_dl"
    assert "gallery_dl_adapter" in result["applied_rules"]
    assert "browser_cookies_chrome" in result["applied_rules"]
    assert result["links"][0]["url"] == "https://example.com/details"


def test_twitter_oembed_adapter_for_text_status():
    original_try_fetch = module.try_fetch

    def fake_try_fetch(url, timeout=15):
        assert "publish.twitter.com/oembed" in url
        return '{"author_name":"jack","author_url":"https://twitter.com/jack","html":"<blockquote class=\\"twitter-tweet\\"><p lang=\\"en\\" dir=\\"ltr\\">just setting up my twttr</p>&mdash; jack (@jack) <a href=\\"https://twitter.com/jack/status/20\\">March 21, 2006</a></blockquote>"}'

    module.try_fetch = fake_try_fetch
    try:
        result = module.extract_twitter_oembed_special("https://x.com/jack/status/20", "twttr")
    finally:
        module.try_fetch = original_try_fetch

    assert result is not None
    assert result["fetch_mode"] == "twitter_oembed"
    assert "twitter_oembed" in result["applied_rules"]
    assert result["summary"][0].startswith("just setting up my twttr")


def test_known_error_shell_triggers_fallback_for_xiaohongshu():
    original_fetch = module.fetch_with_reader_fallback
    original_run_fallbacks = module.run_fallbacks

    def fake_fetch(url):
        return '<html><head><title>小红书 - 你访问的页面不见了</title></head><body>错误页</body></html>', 'direct'

    def fake_run_fallbacks(url, query, allow_fallback=True, follow_depth=True):
        return {
            'url': url,
            'fetch_mode': 'external_discovery_fallback',
            'title': '外部发现',
            'summary': ['命中站外有效内容'],
            'sections': [],
            'links': [],
            'quality': 'medium',
            'applied_rules': ['external_discovery_fallback'],
        }

    module.fetch_with_reader_fallback = fake_fetch
    module.run_fallbacks = fake_run_fallbacks
    try:
        result = module.deep_extract('https://www.xiaohongshu.com/explore/demo', 'OpenClaw 优化')
    finally:
        module.fetch_with_reader_fallback = original_fetch
        module.run_fallbacks = original_run_fallbacks

    assert result['fetch_mode'] == 'external_discovery_fallback'
    assert 'known_error_shell' in result['applied_rules']


def test_known_error_shell_triggers_fallback_for_douyin_empty_body():
    original_fetch = module.fetch_with_reader_fallback
    original_run_fallbacks = module.run_fallbacks

    def fake_fetch(url):
        return '<html><head><meta charset=\"UTF-8\" /></head><body></body></html>', 'direct'

    def fake_run_fallbacks(url, query, allow_fallback=True, follow_depth=True):
        return {
            'url': url,
            'fetch_mode': 'external_discovery_fallback',
            'title': '外部发现',
            'summary': ['命中站外有效内容'],
            'sections': [],
            'links': [],
            'quality': 'medium',
            'applied_rules': ['external_discovery_fallback'],
        }

    module.fetch_with_reader_fallback = fake_fetch
    module.run_fallbacks = fake_run_fallbacks
    try:
        result = module.deep_extract('https://www.douyin.com/video/demo', 'OpenClaw 优化')
    finally:
        module.fetch_with_reader_fallback = original_fetch
        module.run_fallbacks = original_run_fallbacks

    assert result['fetch_mode'] == 'external_discovery_fallback'
    assert 'known_error_shell' in result['applied_rules']


def test_known_error_shell_triggers_fallback_for_pinduoduo_shell():
    original_fetch = module.fetch_with_reader_fallback
    original_run_fallbacks = module.run_fallbacks

    def fake_fetch(url):
        return '<html><head><title>拼多多</title><meta property="og:description" content="风靡全国的拼团商城，优质商品新鲜直供，快来一起拼多多吧"></head><body>拼多多商城</body></html>', 'direct'

    def fake_run_fallbacks(url, query, allow_fallback=True, follow_depth=True):
        return {
            'url': url,
            'fetch_mode': 'external_discovery_fallback',
            'title': '外部发现',
            'summary': ['命中站外有效内容'],
            'sections': [],
            'links': [],
            'quality': 'medium',
            'applied_rules': ['external_discovery_fallback'],
        }

    module.fetch_with_reader_fallback = fake_fetch
    module.run_fallbacks = fake_run_fallbacks
    try:
        result = module.deep_extract('https://mobile.yangkeduo.com/search_result.html?search_key=openclaw', 'OpenClaw 优化')
    finally:
        module.fetch_with_reader_fallback = original_fetch
        module.run_fallbacks = original_run_fallbacks

    assert result['fetch_mode'] == 'external_discovery_fallback'
    assert 'known_error_shell' in result['applied_rules']


def test_external_discovery_adds_extra_suffixes_for_xiaohongshu():
    original = module.search_engine
    seen_queries = []

    def fake_search_engine(engine, variant, site_focus):
        seen_queries.append(variant)
        return []

    module.search_engine = fake_search_engine
    try:
        module.extract_external_discovery_fallback(
            'https://www.xiaohongshu.com/search_result?keyword=openclaw',
            'OpenClaw 优化',
        )
    finally:
        module.search_engine = original

    joined = " | ".join(seen_queries)
    assert "OpenClaw 优化 小红书 xiaohongshu GitHub" in joined
    assert "OpenClaw 优化 小红书 xiaohongshu skill" in joined


def test_external_discovery_prefers_actionable_domains():
    original = module.search_engine

    def fake_search_engine(engine, variant, site_focus):
        return [
            module.SearchResult("普通平台介绍", "https://example.com/platform", "平台介绍", engine, variant, site_focus),
            module.SearchResult("GitHub OpenClaw Skill", "https://github.com/demo/openclaw-skill", "真实仓库", engine, variant, site_focus),
        ]

    module.search_engine = fake_search_engine
    try:
        result = module.extract_external_discovery_fallback(
            'https://www.xiaohongshu.com/search_result?keyword=openclaw',
            'OpenClaw 优化',
        )
    finally:
        module.search_engine = original

    assert result is not None
    assert result["links"][0]["href"] == "https://github.com/demo/openclaw-skill"


def test_jd_item_meta_extractor():
    html = """
    <html><head>
      <title>《OpenClaw 实战指南》(作者名)【摘要 书评 试读】- 京东图书</title>
      <meta name="description" content="京东JD.COM图书频道为您提供《OpenClaw 实战指南》在线选购，本书作者：，出版社：机械工业出版社。">
    </head><body></body></html>
    """
    result = module.extract_jd_item_special("https://item.jd.com/123456.html", html, "OpenClaw 实战指南")
    assert result is not None
    assert result["fetch_mode"] == "jd_item_meta"
    assert "jd_item_meta" in result["applied_rules"]


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


def test_browser_session_fallback_rejects_shell_without_query_overlap():
    original_run_json = module.run_json

    def fake_run_json(args, timeout=45):
        if args[1] != str(module.BRIDGE):
            raise AssertionError(args)
        if args[2] == "status" and args[3] == "safari":
            return {"running": True, "dom_extract": True, "url": "https://www.douyin.com/search/openclaw"}
        if args[2] == "audit" and args[3] == "safari":
            return {
                "browser": "safari",
                "status": {"auth_state": "authenticated", "auth_reason": "douyin_search_page"},
                "extract": {
                    "url": "https://www.douyin.com/search/openclaw",
                    "title": "抖音搜索",
                    "text": "精选 推荐 搜索 关注 朋友 我的 直播 放映厅 短剧 下载抖音精选 算法推荐专项举报 广告投放 用户服务协议 隐私政策",
                    "headings": [],
                    "links": [],
                    "auth_state": "authenticated",
                    "auth_reason": "douyin_search_page",
                },
            }
        if args[2] == "open" and args[3] == "safari":
            return {"ok": True}
        raise AssertionError(args)

    module.run_json = fake_run_json
    try:
        result = module.browser_assisted_extract("https://www.douyin.com/search/openclaw", "openclaw 优化")
    finally:
        module.run_json = original_run_json

    assert result is None


def test_browser_auth_audit_prefers_authenticated_safari():
    original_run_json = module.run_json
    status_calls = {"count": 0}

    def fake_run_json(args, timeout=45):
        if args[1] != str(module.BRIDGE):
            raise AssertionError(args)
        if args[2] == "status" and args[3] == "safari":
            status_calls["count"] += 1
            return {"running": True, "dom_extract": True, "url": "https://www.zhihu.com/question/123"}
        if args[2] == "audit" and args[3] == "safari":
            return {
                "browser": "safari",
                "status": {"auth_state": "authenticated", "auth_reason": "zhihu_search_page"},
                "extract": {
                    "url": "https://www.zhihu.com/question/123",
                    "title": "知乎问题页",
                    "text": "OpenClaw 优化 经验 总结 回答 内容 很完整，包含安装步骤、失败原因、修复思路、对比实验和多个真实案例，能够证明这不是登录壳页也不是低信号页面。这里还有继续深入的方案比较、配置差异、插件组合建议、运行链说明、真实失败案例和恢复方案，确保文本长度足够并且和查询保持强相关。",
                    "auth_state": "authenticated",
                    "auth_reason": "zhihu_search_page",
                },
            }
        if args[2] == "open" and args[3] == "safari":
            return {"ok": True}
        raise AssertionError(args)

    module.run_json = fake_run_json
    try:
        result = module.audit_browser_session("https://www.zhihu.com/question/123")
    finally:
        module.run_json = original_run_json

    assert result is not None
    assert result["browser"] == "safari"
    assert result["auth_state"] == "authenticated"


def test_browser_auth_audit_rejects_expired_session():
    original_run_json = module.run_json

    def fake_run_json(args, timeout=45):
        if args[1] != str(module.BRIDGE):
            raise AssertionError(args)
        if args[2] == "status" and args[3] == "safari":
            return {"running": True, "dom_extract": True, "url": "https://gitlab.com/users/sign_in"}
        if args[2] == "audit" and args[3] == "safari":
            return {
                "browser": "safari",
                "status": {"auth_state": "expired", "auth_reason": "gitlab_login_page"},
                "extract": {
                    "url": "https://gitlab.com/users/sign_in",
                    "title": "Sign in · GitLab",
                    "text": "Sign in to GitLab",
                    "auth_state": "expired",
                    "auth_reason": "gitlab_login_page",
                },
            }
        if args[2] == "open" and args[3] == "safari":
            return {"ok": True}
        raise AssertionError(args)

    module.run_json = fake_run_json
    try:
        result = module.audit_browser_session("https://gitlab.com/search?search=openclaw")
    finally:
        module.run_json = original_run_json

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


def test_external_discovery_fallback_for_chinese_social_sites():
    original = module.search_engine

    def fake_search_engine(engine, variant, site_focus):
        return [
            module.SearchResult("小红书 OpenClaw 安装教程", "https://www.xiaohongshu.com/explore/demo", "安装与优化经验", engine, variant, site_focus),
            module.SearchResult("抖音 OpenClaw 实测", "https://www.douyin.com/video/demo", "实测效果总结", engine, variant, site_focus),
        ]

    module.search_engine = fake_search_engine
    try:
        result = module.extract_external_discovery_fallback("https://www.xiaohongshu.com/search_result?keyword=openclaw", "openclaw 优化")
    finally:
        module.search_engine = original

    assert result is not None
    assert result["fetch_mode"] == "external_discovery_fallback"
    assert result["quality"] == "medium"
    assert "external_discovery_fallback" in result["applied_rules"]


def test_douyin_project_adapter():
    original_run = module.subprocess.run
    original_available = module.douyin_project_available

    class FakeProc:
        def __init__(self, stdout="", returncode=0):
            self.stdout = stdout
            self.stderr = ""
            self.returncode = returncode

    def fake_run(cmd, text=True, capture_output=True, timeout=40):
        return FakeProc(
            stdout='{"desc":"OpenClaw 抖音自动化实测","author":{"nickname":"测试作者"},"statistics":{"play_count":1234,"comment_count":56,"share_count":7}}'
        )

    module.subprocess.run = fake_run
    module.douyin_project_available = lambda: True
    try:
        result = module.extract_douyin_project_special("https://www.douyin.com/video/7488202296297166114", "OpenClaw 自动化")
    finally:
        module.subprocess.run = original_run
        module.douyin_project_available = original_available

    assert result is not None
    assert result["fetch_mode"] == "douyin_project"
    assert "douyin_project_adapter" in result["applied_rules"]


def test_xhs_mcp_adapter():
    original_start = module.ensure_xhs_service_started
    original_login = module.xhs_login_status
    original_post = module.local_http_post_json

    def fake_post(url, payload, timeout=20):
        return {
            "success": True,
            "data": {
                "title": "OpenClaw 小红书自动化实测",
                "desc": "记录 OpenClaw 在小红书内容运营中的自动化实践",
                "user": {"nickname": "测试博主"},
                "interact_info": {"liked_count": 321, "comment_count": 18, "share_count": 4},
            },
        }

    module.ensure_xhs_service_started = lambda: True
    module.xhs_login_status = lambda: True
    module.local_http_post_json = fake_post
    try:
        result = module.extract_xhs_mcp_special(
            "https://www.xiaohongshu.com/explore/65f2d9f50000000001027d63?xsec_token=abc123",
            "OpenClaw 自动化",
        )
    finally:
        module.ensure_xhs_service_started = original_start
        module.xhs_login_status = original_login
        module.local_http_post_json = original_post

    assert result is not None
    assert result["fetch_mode"] == "xhs_mcp"
    assert "xhs_mcp_adapter" in result["applied_rules"]


def test_adapter_blocker_rules_for_xhs_and_douyin():
    original_douyin_available = module.douyin_project_available
    original_xhs_start = module.ensure_xhs_service_started
    original_xhs_bootstrap = module.xhs_runtime_bootstrap_blocked
    module.douyin_project_available = lambda: False
    module.ensure_xhs_service_started = lambda: False
    module.xhs_runtime_bootstrap_blocked = lambda: False
    try:
        douyin_rules = module.adapter_blocker_rules("https://www.douyin.com/video/7488202296297166114")
        xhs_rules = module.adapter_blocker_rules("https://www.xiaohongshu.com/explore/65f2d9f50000000001027d63?xsec_token=abc123")
    finally:
        module.douyin_project_available = original_douyin_available
        module.ensure_xhs_service_started = original_xhs_start
        module.xhs_runtime_bootstrap_blocked = original_xhs_bootstrap

    assert "douyin_adapter_runtime_missing" in douyin_rules
    assert "xhs_adapter_service_unavailable" in xhs_rules


def test_adapter_blocker_rules_for_xhs_login_required():
    original_xhs_start = module.ensure_xhs_service_started
    original_xhs_login = module.xhs_login_status
    original_xhs_bootstrap = module.xhs_runtime_bootstrap_blocked
    module.ensure_xhs_service_started = lambda: True
    module.xhs_login_status = lambda: False
    module.xhs_runtime_bootstrap_blocked = lambda: False
    try:
        xhs_rules = module.adapter_blocker_rules(
            "https://www.xiaohongshu.com/explore/65f2d9f50000000001027d63?xsec_token=abc123"
        )
    finally:
        module.ensure_xhs_service_started = original_xhs_start
        module.xhs_login_status = original_xhs_login
        module.xhs_runtime_bootstrap_blocked = original_xhs_bootstrap

    assert "xhs_adapter_login_required" in xhs_rules


def test_adapter_blocker_rules_for_xhs_bootstrap_blocked():
    original_bootstrap = module.xhs_runtime_bootstrap_blocked
    module.xhs_runtime_bootstrap_blocked = lambda: True
    try:
        xhs_rules = module.adapter_blocker_rules(
            "https://www.xiaohongshu.com/explore/65f2d9f50000000001027d63?xsec_token=abc123"
        )
    finally:
        module.xhs_runtime_bootstrap_blocked = original_bootstrap

    assert "xhs_adapter_bootstrap_blocked" in xhs_rules


def test_commerce_line_formatting_extracts_price_and_sales():
    line = module.format_commerce_line(
        "OpenClaw 实战指南",
        "券后￥39.80 已售1234件 官方旗舰店 包邮",
        "https://item.jd.com/123.html",
    )
    assert "￥39.80" in line or "39.80" in line
    assert "官方旗舰店" in line


def test_domain_search_fallback_formats_commerce_results():
    original = module.search_engine

    def fake_search_engine(engine, variant, site_focus):
        return [
            module.SearchResult(
                "OpenClaw 实战指南",
                "https://item.jd.com/123.html",
                "券后￥39.80 1234条评价 官方旗舰店 包邮",
                engine,
                variant,
                site_focus,
            ),
            module.SearchResult(
                "OpenClaw 龙虾教程",
                "https://item.jd.com/456.html",
                "￥59.00 已售2000件 自营",
                engine,
                variant,
                site_focus,
            ),
        ]

    module.search_engine = fake_search_engine
    try:
        result = module.extract_domain_search_fallback("https://search.jd.com/Search?keyword=openclaw", "openclaw")
    finally:
        module.search_engine = original

    assert result is not None
    assert result["fetch_mode"] in {"domain_search_fallback", "domain_search_deep_fallback"}
    assert any("￥39.80" in line or "39.80" in line for line in result["summary"])


def test_commerce_bonus_prefers_product_like_result():
    bonus_product = module.commerce_result_bonus(
        "蓝牙耳机 官方旗舰店",
        "券后￥199 已售3000件 官方旗舰店 包邮",
        "蓝牙耳机",
    )
    bonus_generic = module.commerce_result_bonus(
        "蓝牙耳机 选购指南",
        "购买建议和使用心得",
        "蓝牙耳机",
    )
    assert bonus_product > bonus_generic


def test_commerce_deep_fallback_rejects_non_product_tutorial_content():
    original = module.search_engine
    original_deep = module.deep_extract

    def fake_search_engine(engine, variant, site_focus):
        return [
            module.SearchResult(
                "蓝牙耳机使用教程",
                "https://s.taobao.com/guide/bluetooth-headset",
                "连接教程和选购建议",
                engine,
                variant,
                site_focus,
            )
        ]

    def fake_deep(url, query, allow_fallback=False):
        if url.endswith("bluetooth-headset"):
            return {
                "url": url,
                "fetch_mode": "direct",
                "title": "蓝牙耳机连接教程",
                "summary": ["打开手机蓝牙设置，按照说明配对耳机。", "教程和使用技巧总结。"],
                "quality": "high",
            }
        return {"url": url, "summary": [], "quality": "low"}

    module.search_engine = fake_search_engine
    module.deep_extract = fake_deep
    try:
        result = module.extract_domain_search_fallback("https://s.taobao.com/search?q=蓝牙耳机", "蓝牙耳机")
    finally:
        module.search_engine = original
        module.deep_extract = original_deep

    assert result is not None
    assert result["fetch_mode"] == "domain_search_fallback"



if __name__ == "__main__":
    test_pypi_search_page_extractor()
    test_youtube_search_page_extractor()
    test_domain_search_fallback_for_blocked_page()
    test_root_domain_relaxation_for_subdomain_sites()
    test_meta_search_fallback_for_search_engines()
    test_github_rule_tagging()
    test_browser_session_fallback_for_low_signal_pages()
    test_yt_dlp_adapter_for_content_page()
    test_yt_dlp_adapter_for_reddit_content_page()
    test_gallery_dl_adapter_for_reddit_submission()
    test_twitter_oembed_adapter_for_text_status()
    test_known_error_shell_triggers_fallback_for_xiaohongshu()
    test_known_error_shell_triggers_fallback_for_douyin_empty_body()
    test_known_error_shell_triggers_fallback_for_pinduoduo_shell()
    test_external_discovery_adds_extra_suffixes_for_xiaohongshu()
    test_external_discovery_prefers_actionable_domains()
    test_browser_session_fallback_rejects_wrong_page()
    test_browser_session_fallback_rejects_shell_without_query_overlap()
    test_browser_auth_audit_prefers_authenticated_safari()
    test_browser_auth_audit_rejects_expired_session()
    test_generic_search_shell_extraction_from_sections()
    test_external_discovery_fallback_for_chinese_social_sites()
    test_douyin_project_adapter()
    test_xhs_mcp_adapter()
    test_adapter_blocker_rules_for_xhs_and_douyin()
    test_adapter_blocker_rules_for_xhs_login_required()
    test_adapter_blocker_rules_for_xhs_bootstrap_blocked()
    test_commerce_line_formatting_extracts_price_and_sales()
    test_domain_search_fallback_formats_commerce_results()
    test_commerce_bonus_prefers_product_like_result()
    test_commerce_deep_fallback_rejects_non_product_tutorial_content()
    print("search orchestrator regression tests passed")
