#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import List, Dict, Tuple

USER_AGENT = "Mozilla/5.0 OpenClaw Search Orchestrator"
MAX_TEXT = 5000
HERE = Path(__file__).resolve().parent
BRIDGE = HERE / "browser_session_bridge.py"
DISTILL = HERE / "web_content_distill.py"
READER_FIRST_DOMAINS = {
    "github.com",
    "www.github.com",
    "zhihu.com",
    "www.zhihu.com",
    "xiaohongshu.com",
    "www.xiaohongshu.com",
    "douyin.com",
    "www.douyin.com",
    "reddit.com",
    "www.reddit.com",
}
BROWSER_ASSIST_DOMAINS = {
    "zhihu.com",
    "www.zhihu.com",
    "xiaohongshu.com",
    "www.xiaohongshu.com",
    "douyin.com",
    "www.douyin.com",
    "search.bilibili.com",
    "bilibili.com",
    "www.bilibili.com",
    "s.weibo.com",
    "weibo.com",
    "www.weibo.com",
    "x.com",
    "www.x.com",
    "reddit.com",
    "www.reddit.com",
    "producthunt.com",
    "www.producthunt.com",
    "gitlab.com",
    "www.gitlab.com",
    "s.taobao.com",
    "search.jd.com",
    "mobile.yangkeduo.com",
}
LOW_SIGNAL_PATTERNS = [
    r"请完成以下验证",
    r"登录后查看更多",
    r"unsupported browser",
    r"enable javascript",
    r"验证码",
    r"复制链接到浏览器",
    r"this page maybe not yet fully loaded",
    r"performing security verification",
    r"security verification",
    r"not a bot",
    r"forbidden",
    r"returned error 403",
]
SEARCH_PAGE_HINTS = [
    "search",
    "搜索",
    "results",
    "结果",
    "client challenge",
]
SITE_QUERY_SUFFIXES = {
    "github": ["README", "repo", "install", "usage"],
    "clawhub": ["skill", "plugin", "install"],
    "reddit": ["discussion", "review"],
    "xiaohongshu": ["教程", "测评"],
    "douyin": ["教程", "实测"],
    "zhihu": ["经验", "回答"],
}


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str
    engine: str
    query_variant: str
    site_focus: str
    score: float = 0.0


def with_rules(payload: Dict, *rules: str) -> Dict:
    merged = list(payload.get("applied_rules") or [])
    for rule in rules:
        if rule and rule not in merged:
            merged.append(rule)
    payload["applied_rules"] = merged
    return payload


def clean(text: str) -> str:
    text = html.unescape(text or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def root_domain(value: str) -> str:
    host = clean(value).lower()
    if not host:
        return ""
    parts = [part for part in host.split(".") if part]
    if len(parts) <= 2:
        return host
    return ".".join(parts[-2:])


def url_path_depth(url: str) -> int:
    parsed = urllib.parse.urlparse(url)
    return len([segment for segment in parsed.path.split("/") if segment])


def is_homepage_like(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    path = parsed.path.strip("/")
    if not path:
        return True
    return path in {"search", "search_result", "results", "all", "blog", "models"}


def http_get(url: str, timeout: int = 20) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def run_json(cmd: List[str], timeout: int = 45) -> Dict:
    proc = subprocess.run(cmd, text=True, capture_output=True, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "command_failed")
    return json.loads(proc.stdout)


def fetch_with_reader_fallback(url: str) -> Tuple[str, str]:
    domain = urllib.parse.urlparse(url).netloc.lower()
    prefer_reader = domain in READER_FIRST_DOMAINS
    if prefer_reader:
        reader_url = f"https://r.jina.ai/http://{url.removeprefix('https://').removeprefix('http://')}"
        try:
            return http_get(reader_url), "reader"
        except Exception:
            pass
    try:
        return http_get(url), "direct"
    except Exception:
        pass
    reader_url = f"https://r.jina.ai/http://{url.removeprefix('https://').removeprefix('http://')}"
    try:
        return http_get(reader_url), "reader"
    except Exception:
        return "", "unavailable"


def try_fetch(url: str, timeout: int = 15) -> str:
    try:
        return http_get(url, timeout=timeout)
    except Exception:
        return ""


def browser_assisted_extract(url: str, query: str) -> Dict | None:
    parsed = urllib.parse.urlparse(url)
    domain = parsed.netloc.lower()
    if domain not in BROWSER_ASSIST_DOMAINS:
        return None
    try:
        status = run_json(["python3", str(BRIDGE), "status", "safari"], timeout=8)
    except Exception:
        return None
    if not status.get("running") or not status.get("dom_extract"):
        return None
    original_url = status.get("url", "")
    try:
        run_json(["python3", str(BRIDGE), "open", "safari", url], timeout=12)
        time.sleep(2.2)
        payload = run_json(["python3", str(BRIDGE), "extract", "safari"], timeout=12)
    except Exception:
        payload = None
    finally:
        if original_url and original_url != url:
            try:
                run_json(["python3", str(BRIDGE), "open", "safari", original_url], timeout=8)
            except Exception:
                pass
    if not payload:
        return None
    payload_url = clean(payload.get("url", ""))
    payload_domain = urllib.parse.urlparse(payload_url).netloc.lower() if payload_url else ""
    if payload_domain and root_domain(payload_domain) != root_domain(domain):
        return None
    text = clean(payload.get("text", ""))[:MAX_TEXT]
    if is_low_signal_text(text):
        return None
    title = clean(payload.get("title", ""))
    summary = summarize_browser_text(text, query, title, payload_url or url)
    if not summary or looks_like_generic_site_blurb(title, summary, query):
        return None
    return {
        "url": url,
        "fetch_mode": "browser_session",
        "title": title,
        "summary": summary,
        "sections": payload.get("headings", [])[:12],
        "links": payload.get("links", [])[:20],
        "quality": "high" if len(summary) >= 2 else "medium",
        "applied_rules": ["browser_session_fallback"],
    }


def summarize_browser_text(text: str, query: str, title: str, url: str) -> List[str]:
    parsed = urllib.parse.urlparse(url)
    path = parsed.path.lower()
    title_l = clean(title).lower()
    looks_like_search = (
        any(token in path for token in ("/search", "/s", "/results", "/all"))
        or any(token in title_l for token in ("搜索", "search", "results"))
    )
    if not looks_like_search:
        return summarize_text(text, query)

    snippets = []
    lowered = text.lower()
    query_tokens = [
        token for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9._/-]{2,}|[\u4e00-\u9fff]{2,}", query.lower())
        if len(token) >= 2
    ]
    for token in dict.fromkeys(query_tokens):
        start = 0
        while True:
            index = lowered.find(token, start)
            if index < 0:
                break
            left = max(0, index - 24)
            right = min(len(text), index + 84)
            snippet = clean(text[left:right])
            if snippet and snippet not in snippets:
                snippets.append(snippet)
            start = index + len(token)
            if len(snippets) >= 5:
                break
        if len(snippets) >= 5:
            break
    return snippets[:5] or summarize_text(text, query)


def extract_github_special(url: str, query: str) -> Dict | None:
    parsed = urllib.parse.urlparse(url)
    if parsed.netloc.lower() not in {"github.com", "www.github.com"}:
        return None
    parts = [segment for segment in parsed.path.split("/") if segment]
    if len(parts) < 2:
        return None
    owner, repo = parts[0], parts[1]
    raw_targets = []
    if len(parts) >= 5 and parts[2] == "blob":
        branch = parts[3]
        blob_path = "/".join(parts[4:])
        raw_targets.append(f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{blob_path}")
    raw_targets.extend([
        f"https://raw.githubusercontent.com/{owner}/{repo}/main/README.md",
        f"https://raw.githubusercontent.com/{owner}/{repo}/master/README.md",
        f"https://raw.githubusercontent.com/{owner}/{repo}/main/readme.md",
        f"https://raw.githubusercontent.com/{owner}/{repo}/master/readme.md",
    ])
    for candidate in raw_targets:
        raw = try_fetch(candidate, timeout=15)
        if not raw:
            continue
        normalized = clean(raw[:12000])
        summary = summarize_text(normalized, query)
        if not summary:
            continue
        return {
            "url": url,
            "fetch_mode": "github_raw",
            "title": f"{owner}/{repo}",
            "summary": summary,
            "sections": [],
            "links": [],
            "quality": "high",
            "source_url": candidate,
        } | {"applied_rules": ["github_raw"]}
    return None


def extract_reddit_special(url: str, query: str) -> Dict | None:
    parsed = urllib.parse.urlparse(url)
    if parsed.netloc.lower() not in {"reddit.com", "www.reddit.com", "old.reddit.com"}:
        return None
    json_url = url.rstrip("/") + ".json?raw_json=1"
    raw = try_fetch(json_url, timeout=15)
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except Exception:
        return None
    try:
        post = payload[0]["data"]["children"][0]["data"]
    except Exception:
        return None
    post_title = clean(post.get("title", ""))
    selftext = clean(post.get("selftext", ""))
    comments = []
    try:
        for child in payload[1]["data"]["children"][:5]:
            data = child.get("data", {})
            body = clean(data.get("body", ""))
            if body:
                comments.append(body[:280])
    except Exception:
        pass
    text = " ".join(filter(None, [post_title, selftext] + comments))
    summary = summarize_text(text, query)
    return {
        "url": url,
        "fetch_mode": "reddit_json",
        "title": post_title,
        "summary": summary,
        "sections": [],
        "links": [],
        "quality": "high" if summary else "medium",
        "comments": comments[:3],
        "applied_rules": ["reddit_json"],
    }


def extract_search_page_special(url: str, raw: str, query: str) -> Dict | None:
    parsed = urllib.parse.urlparse(url)
    domain = parsed.netloc.lower()
    path = parsed.path.lower()
    query_params = urllib.parse.parse_qs(parsed.query)
    looks_like_search = any(hint in clean(raw[:4000]).lower() for hint in SEARCH_PAGE_HINTS)
    has_search_param = any(key in query_params for key in ("q", "query", "search", "keyword", "wd"))
    if not looks_like_search and not has_search_param and not any(token in path for token in ("/search", "/s", "/results")):
        return None

    def mk(title: str, items: List[Tuple[str, str, str]], mode: str) -> Dict | None:
        cleaned = []
        seen = set()
        for item_title, item_url, item_snippet in items:
            item_title = clean(re.sub(r"<[^>]+>", " ", item_title))
            item_url = clean(html.unescape(item_url))
            item_snippet = clean(re.sub(r"<[^>]+>", " ", item_snippet))
            if not item_title or not item_url:
                continue
            key = item_url.lower()
            if key in seen:
                continue
            seen.add(key)
            cleaned.append((item_title, item_url, item_snippet))
            if len(cleaned) >= 5:
                break
        if len(cleaned) < 1:
            return None
        summary = []
        links = []
        for item_title, item_url, item_snippet in cleaned:
            line = item_title
            if item_snippet:
                line = f"{item_title}: {item_snippet[:180]}"
            summary.append(line)
            links.append({"text": item_title, "href": item_url})
        quality = "high" if len(cleaned) >= 4 else "medium"
        return {
            "url": url,
            "fetch_mode": mode,
            "title": clean(title),
            "summary": summary[:5],
            "sections": [{"level": "results", "text": item[0]} for item in cleaned[:5]],
            "links": links[:10],
            "quality": quality,
            "applied_rules": ["search_results_extraction"],
        }

    if domain in {"www.google.com", "google.com"}:
        items = []
        for match in re.finditer(r'<a href="/url\\?q=(?P<href>https?://[^"&]+)[^"]*".*?<h3.*?>(?P<title>.*?)</h3>(?P<rest>.*?)(?=<a href="/url\\?q=|$)', raw, re.S):
            snippet_match = re.search(r'<span[^>]*>(?P<snippet>.*?)</span>', match.group("rest"), re.S)
            items.append((match.group("title"), match.group("href"), snippet_match.group("snippet") if snippet_match else ""))
        return mk("Google Search", items, "search_results")

    if domain in {"www.baidu.com", "baidu.com"}:
        items = []
        for match in re.finditer(r'<h3[^>]*class="t[^"]*"[^>]*>.*?<a[^>]*href="(?P<href>[^"]+)"[^>]*>(?P<title>.*?)</a>(?P<rest>.*?)(?=<h3[^>]*class="t|$)', raw, re.S):
            snippet_match = re.search(r'<div[^>]*class="c-abstract[^"]*"[^>]*>(?P<snippet>.*?)</div>', match.group("rest"), re.S)
            items.append((match.group("title"), match.group("href"), snippet_match.group("snippet") if snippet_match else ""))
        return mk("Baidu Search", items, "search_results")

    if domain.endswith("youtube.com"):
        items = []
        for match in re.finditer(r'"videoRenderer".*?"videoId":"(?P<id>[^"]+)".*?"title":\{"runs":\[\{"text":"(?P<title>[^"]+)"', raw, re.S):
            items.append((match.group("title"), f"https://www.youtube.com/watch?v={match.group('id')}", ""))
        return mk("YouTube Search", items, "search_results")

    if domain.endswith("pypi.org"):
        items = []
        for match in re.finditer(r'<a[^>]*class="package-snippet"[^>]*href="(?P<href>[^"]+)"[^>]*>.*?<span[^>]*class="package-snippet__name">(?P<title>.*?)</span>(?P<rest>.*?)(?=</a>)', raw, re.S):
            snippet_match = re.search(r'package-snippet__description">(?P<snippet>.*?)</p>', match.group("rest"), re.S)
            items.append((match.group("title"), urllib.parse.urljoin("https://pypi.org", match.group("href")), snippet_match.group("snippet") if snippet_match else ""))
        return mk("PyPI Search", items, "search_results")

    if domain.endswith("huggingface.co") and (path.startswith("/search") or path.startswith("/models") or has_search_param):
        items = []
        for match in re.finditer(r'<a[^>]*href="(?P<href>/(?:models|datasets|spaces)/[^"]+)"[^>]*>(?P<title>.*?)</a>', raw, re.S):
            items.append((match.group("title"), urllib.parse.urljoin("https://huggingface.co", match.group("href")), ""))
        return mk("Hugging Face Search", items, "search_results")

    if "kubernetes.io" in domain and any(token in path for token in ("/search", "/docs/search")):
        items = []
        for match in re.finditer(r'<a[^>]*href="(?P<href>/docs/[^"]+)"[^>]*>(?P<title>.*?)</a>', raw, re.S):
            items.append((match.group("title"), urllib.parse.urljoin("https://kubernetes.io", match.group("href")), ""))
        return mk("Kubernetes Docs Search", items, "search_results")

    return None


def extract_parser_search_results(url: str, parser: "Extractor", query: str) -> Dict | None:
    parsed = urllib.parse.urlparse(url)
    path = parsed.path.lower()
    query_params = urllib.parse.parse_qs(parsed.query)
    if not (
        any(key in query_params for key in ("q", "query", "search", "keyword", "wd"))
        or any(token in path for token in ("/search", "/s", "/results", "/all"))
        or looks_like_search_shell(parser.title, parser.sections, parser.links)
    ):
        return None

    items = []
    seen = set()
    for link in parser.links:
        text = clean(link.get("text", ""))
        href = clean(link.get("href", ""))
        if not text or not href or href in seen:
            continue
        if text in {"搜索", "登录", "注册", "首页"}:
            continue
        seen.add(href)
        items.append((text, href, ""))
        if len(items) >= 5:
            break

    if len(items) < 2:
        for section in parser.sections:
            text = clean(section.get("heading", "") or section.get("text", ""))
            if not text or text in seen:
                continue
            if len(text) < 4:
                continue
            seen.add(text)
            items.append((text, url, ""))
            if len(items) >= 5:
                break

    if len(items) < 2:
        return None

    summary = []
    links = []
    sections = []
    for item_title, item_url, item_snippet in items[:5]:
        line = item_title
        if item_snippet:
            line = f"{item_title}: {item_snippet[:180]}"
        summary.append(line)
        links.append({"text": item_title, "href": item_url})
        sections.append({"level": "results", "text": item_title})

    return {
        "url": url,
        "fetch_mode": "search_results",
        "title": clean(parser.title),
        "summary": summary,
        "sections": sections,
        "links": links,
        "quality": "high" if len(items) >= 4 else "medium",
        "applied_rules": ["search_results_extraction", "search_shell_fallback"],
    }


def extract_domain_search_fallback(url: str, query: str, follow_depth: bool = True) -> Dict | None:
    parsed = urllib.parse.urlparse(url)
    domain = parsed.netloc.lower()
    root = root_domain(domain)
    if not domain or not query:
        return None
    if domain in {"www.google.com", "google.com", "www.baidu.com", "baidu.com"}:
        collected: List[SearchResult] = []
        seen = set()
        for engine in ("bing", "ddg"):
            for item in search_engine(engine, query, "general"):
                key = (item.url or item.title).strip().lower()
                if not key or key in seen:
                    continue
                seen.add(key)
                item.score = score_result(item, query)
                collected.append(item)
        collected.sort(key=lambda item: item.score, reverse=True)
        useful = collected[:5]
        if len(useful) < 1:
            return None
        return {
            "url": url,
            "fetch_mode": "meta_search_fallback",
            "title": "Search results proxy",
            "summary": [
                f"{item.title}: {item.snippet[:180]}".strip(": ")
                if item.snippet else item.title
                for item in useful
            ],
            "sections": [{"level": "results", "text": item.title} for item in useful],
            "links": [{"text": item.title, "href": item.url} for item in useful],
            "quality": "medium",
            "source_query": query,
            "applied_rules": ["quality_gating", "meta_search_proxy"],
        }
    variant = f"{query} site:{root or domain}"
    collected: List[SearchResult] = []
    seen = set()
    for engine in ("bing", "ddg"):
        for item in search_engine(engine, variant, domain):
            key = (item.url or item.title).strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            item.score = score_result(item, query)
            collected.append(item)
    collected.sort(key=lambda item: item.score, reverse=True)
    useful = []
    for item in collected:
        item_domain = urllib.parse.urlparse(item.url).netloc.lower()
        item_root = root_domain(item_domain)
        if root:
            if item_root != root:
                continue
        elif domain not in item_domain:
            continue
        useful.append(item)
        if len(useful) >= 5:
            break
    if len(useful) < 1:
        return None
    useful.sort(key=lambda item: (is_homepage_like(item.url), -url_path_depth(item.url), -item.score))
    deep_hits = []
    if follow_depth:
        for item in useful[:3]:
            if is_homepage_like(item.url):
                continue
            nested = deep_extract(item.url, query, allow_fallback=False)
            if nested.get("summary"):
                deep_hits.append((item, nested))
            if len(deep_hits) >= 2:
                break
    if deep_hits:
        summary = []
        links = []
        sections = []
        for item, nested in deep_hits:
            nested_summary = nested.get("summary") or []
            line = nested_summary[0] if nested_summary else item.title
            summary.append(line)
            links.append({"text": nested.get("title") or item.title, "href": item.url})
            sections.append({"level": "follow", "text": nested.get("title") or item.title})
        return {
            "url": url,
            "fetch_mode": "domain_search_deep_fallback",
            "title": clean(root or domain),
            "summary": summary[:5],
            "sections": sections[:10],
            "links": links[:10],
            "quality": "high" if len(deep_hits) >= 2 else "medium",
            "source_query": variant,
            "applied_rules": list(dict.fromkeys(["quality_gating", "domain_search_fallback", "followup_refinement", "root_domain_relaxation" if root and root != domain else ""])),
        }
    return {
        "url": url,
        "fetch_mode": "domain_search_fallback",
        "title": clean(domain),
        "summary": [
            f"{item.title}: {item.snippet[:180]}".strip(": ")
            if item.snippet else item.title
            for item in useful
        ],
        "sections": [{"level": "results", "text": item.title} for item in useful],
        "links": [{"text": item.title, "href": item.url} for item in useful],
        "quality": "medium",
        "source_query": variant,
        "applied_rules": list(dict.fromkeys(["quality_gating", "domain_search_fallback", "root_domain_relaxation" if root and root != domain else ""])),
    }


def build_variants(query: str, intent: str, site_profiles: Dict[str, List[str]]) -> List[Tuple[str, str]]:
    base = clean(query)
    variants: List[Tuple[str, str]] = [(base, "general")]
    lowered = base.lower()
    if intent == "plugin_discovery" or any(k in lowered for k in ["github", "clawhub", "plugin", "skill", "安装"]):
      variants.extend([
          (f"{base} site:github.com", "github"),
          (f"{base} site:clawhub.com", "clawhub"),
      ])
    if intent == "social_research" or any(k in lowered for k in ["小红书", "抖音", "知乎", "bilibili", "微博"]):
      variants.extend([
          (f"{base} site:xiaohongshu.com", "xiaohongshu"),
          (f"{base} site:douyin.com", "douyin"),
          (f"{base} site:zhihu.com", "zhihu"),
      ])
    if any(k in lowered for k in ["reddit", "rebbit"]):
      variants.append((f"{base} site:reddit.com", "reddit"))
    if any(k in lowered for k in ["google", "百度", "baidu", "bing"]):
      variants.append((f"{base} best source", "general"))
    for focus, suffixes in SITE_QUERY_SUFFIXES.items():
        if focus in lowered:
            for suffix in suffixes[:2]:
                variants.append((f"{base} {suffix}", focus))
    deduped = []
    seen = set()
    for item in variants:
        if item[0] in seen:
            continue
        seen.add(item[0])
        deduped.append(item)
    return deduped[:6]


def parse_ddg(doc: str, variant: str, site_focus: str) -> List[SearchResult]:
    items: List[SearchResult] = []
    pattern = re.compile(
        r'<a[^>]*class="result__a"[^>]*href="(?P<href>[^"]+)"[^>]*>(?P<title>.*?)</a>(?P<rest>.*?)(?=<div class="result results_links|<div class="nav-link|$)',
        re.S,
    )
    for match in pattern.finditer(doc):
        href = html.unescape(match.group("href"))
        if "uddg=" in href:
            href = urllib.parse.parse_qs(urllib.parse.urlparse(href).query).get("uddg", [href])[0]
        title = clean(re.sub(r"<[^>]+>", " ", match.group("title")))
        rest = match.group("rest")
        snippet_match = re.search(r'(?:result__snippet[^>]*>|class="result__snippet"[^>]*>)(?P<snippet>.*?)(?:</a>|</div>)', rest, re.S)
        snippet = clean(re.sub(r"<[^>]+>", " ", snippet_match.group("snippet"))) if snippet_match else ""
        if title and href:
            items.append(SearchResult(title, href, snippet, "ddg", variant, site_focus))
    return items


def parse_bing(doc: str, variant: str, site_focus: str) -> List[SearchResult]:
    items: List[SearchResult] = []
    pattern = re.compile(
        r'<li class="b_algo".*?<h2[^>]*>\s*<a[^>]*href="(?P<href>[^"]+)"[^>]*>(?P<title>.*?)</a>\s*</h2>(?P<rest>.*?)(?=</li>)',
        re.S,
    )
    for match in pattern.finditer(doc):
        href = html.unescape(match.group("href"))
        title = clean(re.sub(r"<[^>]+>", " ", match.group("title")))
        rest = match.group("rest")
        snippet_match = re.search(r'<p[^>]*>(?P<snippet>.*?)</p>', rest, re.S)
        snippet = clean(re.sub(r"<[^>]+>", " ", snippet_match.group("snippet"))) if snippet_match else ""
        if title and href:
            items.append(SearchResult(title, href, snippet, "bing", variant, site_focus))
    return items


def parse_google(doc: str, variant: str, site_focus: str) -> List[SearchResult]:
    items: List[SearchResult] = []
    pattern = re.compile(r'<a href="/url\?q=(?P<href>https?://[^"&]+)[^"]*".*?<h3.*?>(?P<title>.*?)</h3>', re.S)
    for match in pattern.finditer(doc):
        href = html.unescape(match.group("href"))
        title = clean(re.sub(r"<[^>]+>", " ", match.group("title")))
        if title and href:
            items.append(SearchResult(title, href, "", "google", variant, site_focus))
    return items


def parse_baidu(doc: str, variant: str, site_focus: str) -> List[SearchResult]:
    items: List[SearchResult] = []
    pattern = re.compile(r'<h3[^>]*class="t[^"]*"[^>]*>.*?<a[^>]*href="(?P<href>[^"]+)"[^>]*>(?P<title>.*?)</a>', re.S)
    for match in pattern.finditer(doc):
        href = html.unescape(match.group("href"))
        title = clean(re.sub(r"<[^>]+>", " ", match.group("title")))
        if title and href:
            items.append(SearchResult(title, href, "", "baidu", variant, site_focus))
    return items


def search_engine(engine: str, variant: str, site_focus: str) -> List[SearchResult]:
    query = urllib.parse.quote_plus(variant)
    urls = {
        "ddg": f"https://html.duckduckgo.com/html/?q={query}",
        "bing": f"https://www.bing.com/search?q={query}&count=10",
        "google": f"https://www.google.com/search?q={query}&num=10",
        "baidu": f"https://www.baidu.com/s?wd={query}&rn=10",
    }
    parsers = {
        "ddg": parse_ddg,
        "bing": parse_bing,
        "google": parse_google,
        "baidu": parse_baidu,
    }
    try:
        doc = http_get(urls[engine], timeout=15)
    except Exception:
        return []
    return parsers[engine](doc, variant, site_focus)


def engines_for_intent(intent: str) -> Tuple[str, ...]:
    normalized = clean(intent).lower()
    if normalized == "plugin_discovery":
        return ("bing", "ddg")
    if normalized == "social_research":
        return ("bing", "ddg", "baidu")
    if normalized == "web_search":
        return ("bing", "ddg", "google", "baidu")
    if normalized == "research":
        return ("bing", "ddg", "google", "baidu")
    return ("bing", "ddg", "baidu")


def score_result(item: SearchResult, query: str) -> float:
    hay = f"{item.title} {item.snippet} {item.url}".lower()
    tokens = re.findall(r"[a-z0-9][a-z0-9._/-]{1,}|[\u4e00-\u9fff]{2,}", query.lower())
    overlap = sum(1 for token in dict.fromkeys(tokens) if token in hay)
    score = overlap * 10
    domain = urllib.parse.urlparse(item.url).netloc.lower()
    if item.site_focus in domain:
        score += 18
    if "github.com" in domain:
        score += 12
    if "clawhub.com" in domain:
        score += 16
    if any(domain.endswith(site) for site in ("zhihu.com", "xiaohongshu.com", "douyin.com", "reddit.com")):
        score += 8
    if item.snippet:
        score += 3
    if any(token in hay for token in ("readme", "install", "教程", "指南", "文档", "skill", "plugin")):
        score += 4
    return score


def query_overlap_score(text: str, query: str) -> int:
    hay = clean(text).lower()
    tokens = re.findall(r"[a-z0-9][a-z0-9._/-]{1,}|[\u4e00-\u9fff]{2,}", query.lower())
    return sum(1 for token in dict.fromkeys(tokens) if token in hay)


def is_low_signal_text(text: str) -> bool:
    sample = clean(text)[:1200]
    if len(sample) < 80:
        return True
    lowered = sample.lower()
    return any(re.search(pattern, sample, re.I) for pattern in LOW_SIGNAL_PATTERNS) or (
        sample.count("...") > 8 or lowered.count("javascript") > 2
    )


def effective_quality(summary: List[str], raw_text: str, mode: str, base_quality: str) -> str:
    if not summary:
        return "low"
    joined = " ".join(summary)
    if is_low_signal_text(joined) or is_low_signal_text(raw_text):
        return "low"
    if mode == "reader" and base_quality == "high":
        return "high"
    return base_quality


def looks_like_search_shell(title: str, sections: List[Dict], links: List[Dict]) -> bool:
    title_l = clean(title).lower()
    if any(token in title_l for token in ("search results", "搜索", "search")):
        return True
    if len(links) >= 8 and len(sections) <= 3:
        return True
    return False


def looks_like_generic_site_blurb(title: str, summary: List[str], query: str) -> bool:
    joined = " ".join(summary[:2])
    if not joined:
        return False
    overlap = query_overlap_score(joined, query)
    generic_tokens = [
        "知名",
        "平台",
        "网站",
        "大家可以在这里",
        "搜索引擎",
        "blog",
        "support",
        "documentation",
        "resource for web developers",
        "个性化搜索体验",
        "优质商品",
        "新鲜直供",
        "活跃的acg氛围",
    ]
    generic = any(token.lower() in joined.lower() for token in generic_tokens)
    return overlap == 0 and generic


class Extractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self.meta_description = ""
        self.links = []
        self.sections = []
        self.bullets = []
        self.paragraphs = []
        self._buf = []
        self._current_link = None
        self._title_mode = False
        self._current_tag = None

    def handle_starttag(self, tag, attrs):
        self._current_tag = tag
        attrs_map = dict(attrs)
        if tag == "title":
            self._title_mode = True
        if tag == "a":
            href = attrs_map.get("href")
            if href:
                self._current_link = href
        if tag == "meta":
            name = clean(attrs_map.get("name", "")).lower()
            prop = clean(attrs_map.get("property", "")).lower()
            if name == "description" or prop == "og:description":
                self.meta_description = clean(attrs_map.get("content", ""))

    def handle_endtag(self, tag):
        text = clean(" ".join(self._buf))
        if tag == "title" and text:
            self.title = text
        elif tag in {"h1", "h2", "h3"} and text:
            self.sections.append({"level": tag, "text": text})
        elif tag in {"p", "article", "section"} and text:
            self.paragraphs.append(text)
        elif tag == "li" and text:
            self.bullets.append(text)
        elif tag == "a" and text and self._current_link:
            self.links.append({"text": text, "href": self._current_link})
            self._current_link = None
        self._buf = []
        self._current_tag = None

    def handle_data(self, data):
        if data:
            self._buf.append(data)


def summarize_text(text: str, query: str) -> List[str]:
    clean_text = clean(re.sub(r"<[^>]+>", " ", text))
    sentences = [s.strip() for s in re.split(r"(?<=[。！？.!?])\s+", clean_text) if s.strip()]
    tokens = re.findall(r"[a-z0-9][a-z0-9._/-]{1,}|[\u4e00-\u9fff]{2,}", query.lower())
    ranked = []
    for sentence in sentences:
      hay = sentence.lower()
      score = sum(1 for token in dict.fromkeys(tokens) if token in hay)
      if len(sentence) > 20:
          ranked.append((score, len(sentence), sentence[:280]))
    ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
    unique = []
    seen = set()
    for _, _, sentence in ranked:
        if sentence in seen:
            continue
        seen.add(sentence)
        unique.append(sentence)
        if len(unique) >= 5:
            break
    return unique


def normalize_reader_text(text: str) -> Tuple[str, str]:
    raw = text or ""
    title_match = re.search(r"Title:\s*(.+)", raw)
    title = clean(title_match.group(1)) if title_match else ""
    if title.lower().startswith("url source:"):
        title = ""
    raw = re.sub(r"^Title:\s*.+?$", " ", raw, flags=re.M)
    raw = re.sub(r"^URL Source:\s*.+?$", " ", raw, flags=re.M)
    raw = re.sub(r"^Published Time:\s*.+?$", " ", raw, flags=re.M)
    raw = re.sub(r"^Markdown Content:\s*", " ", raw, flags=re.M)
    raw = re.sub(r"^============+\s*$", " ", raw, flags=re.M)
    raw = re.sub(r"\[(.*?)\]\((.*?)\)", r"\1", raw)
    raw = re.sub(r"(^|\n)#{1,6}\s*", r"\1", raw)
    raw = re.sub(r"(```.*?```)", " ", raw, flags=re.S)
    return title, clean(raw)


def deep_extract(url: str, query: str, allow_fallback: bool = True) -> Dict:
    special = extract_github_special(url, query) or extract_reddit_special(url, query)
    if special:
        return special
    domain = urllib.parse.urlparse(url).netloc.lower()
    raw, mode = fetch_with_reader_fallback(url)
    if not raw:
        browser_result = browser_assisted_extract(url, query)
        if browser_result:
            return browser_result
        fallback = extract_domain_search_fallback(url, query) if allow_fallback else None
        if fallback:
            return fallback
        return with_rules({"url": url, "fetch_mode": mode, "title": "", "summary": [], "sections": [], "links": [], "quality": "low"}, "unavailable")
    search_special = extract_search_page_special(url, raw, query)
    if search_special:
        return search_special
    if is_low_signal_text(raw):
        browser_result = browser_assisted_extract(url, query)
        if browser_result:
            return browser_result
        fallback = extract_domain_search_fallback(url, query) if allow_fallback else None
        if fallback:
            return fallback
    if "<html" not in raw.lower():
        reader_title, normalized = normalize_reader_text(raw[:MAX_TEXT]) if mode == "reader" else ("", clean(raw[:MAX_TEXT]))
        summary = summarize_text(normalized, query)
        if (not summary or is_low_signal_text(normalized)) and DISTILL.exists():
            try:
                distilled = run_json(["python3", str(DISTILL), url])
                summary = distilled.get("summary", [])[:5] or summary
                reader_title = distilled.get("title") or reader_title
            except Exception:
                pass
        if is_low_signal_text(normalized) or looks_like_generic_site_blurb(reader_title, summary, query):
            browser_result = browser_assisted_extract(url, query)
            if browser_result:
                return browser_result
            fallback = extract_domain_search_fallback(url, query) if allow_fallback else None
            if fallback:
                return fallback
        return {
            "url": url,
            "fetch_mode": mode,
            "title": reader_title,
            "summary": summary,
            "sections": [],
            "links": [],
            "quality": effective_quality(summary, normalized, mode, "high" if summary and mode == "reader" else "medium")
        } | {"applied_rules": ["reader_then_distill"] if mode == "reader" else []}
    parser = Extractor()
    parser.feed(raw[:250000])
    parser_search = extract_parser_search_results(url, parser, query)
    if parser_search and (
        looks_like_search_shell(parser.title, parser.sections, parser.links)
        or looks_like_generic_site_blurb(parser.title, [item["text"] for item in parser_search["sections"]], query)
        or looks_like_generic_site_blurb(parser.title, [parser.meta_description] if parser.meta_description else [], query)
    ):
        return parser_search
    summary_source = " ".join(([parser.meta_description] if parser.meta_description else []) + parser.paragraphs[:20] + parser.bullets[:20])
    summary = summarize_text(summary_source, query)
    quality = "high" if summary and (parser.sections or parser.links or parser.meta_description or mode == "reader") else "medium" if summary else "low"
    if (not summary or is_low_signal_text(summary_source)) and DISTILL.exists():
        try:
            distilled = run_json(["python3", str(DISTILL), url])
            summary = distilled.get("summary", [])[:5] or summary
            if distilled.get("sections"):
                parser.sections = distilled["sections"][:12]
            if distilled.get("links"):
                parser.links = distilled["links"][:20]
            if distilled.get("title"):
                parser.title = distilled["title"]
            quality = "medium" if summary else quality
        except Exception:
            pass
    if (
        is_low_signal_text(summary_source)
        or not summary
        or (len(summary) <= 1 and looks_like_search_shell(parser.title, parser.sections, parser.links))
        or looks_like_generic_site_blurb(parser.title, summary, query)
    ):
        browser_result = browser_assisted_extract(url, query)
        if browser_result:
            return browser_result
        fallback = extract_domain_search_fallback(url, query) if allow_fallback else None
        if fallback:
            return fallback
    quality = effective_quality(summary, summary_source, mode, quality)
    if quality == "low" and domain in BROWSER_ASSIST_DOMAINS:
        browser_result = browser_assisted_extract(url, query)
        if browser_result:
            return browser_result
    return {
        "url": url,
        "fetch_mode": mode,
        "title": parser.title,
        "meta_description": parser.meta_description,
        "summary": summary,
        "sections": parser.sections[:12],
        "links": parser.links[:20],
        "quality": quality
    } | {"applied_rules": ["reader_then_distill"] if mode == "reader" else []}


def refine_queries(base_query: str, ranked_results: List[SearchResult]) -> List[Tuple[str, str]]:
    refinements = []
    for item in ranked_results[:3]:
        domain = urllib.parse.urlparse(item.url).netloc.lower()
        title_tokens = re.findall(r"[A-Za-z0-9][A-Za-z0-9._/-]{2,}|[\u4e00-\u9fff]{2,}", item.title)
        if title_tokens:
            refinements.append((f"{base_query} {' '.join(title_tokens[:4])}", domain or "refine"))
        if domain:
            refinements.append((f"{base_query} site:{domain}", domain))
    deduped = []
    seen = set()
    for query, focus in refinements:
        if query in seen:
            continue
        seen.add(query)
        deduped.append((query, focus))
    return deduped[:3]


def coverage_signals(extractions: List[Dict]) -> Dict[str, int]:
    high = sum(1 for item in extractions if item["extraction"]["quality"] == "high")
    medium = sum(1 for item in extractions if item["extraction"]["quality"] == "medium")
    useful = sum(1 for item in extractions if item["extraction"].get("summary"))
    return {"high": high, "medium": medium, "useful": useful}


def research(payload: Dict) -> Dict:
    query = clean(payload.get("query", ""))
    if not query:
        return {
            "query": "",
            "intent": payload.get("intent", "auto"),
            "quality": "low",
            "error": "empty_query",
            "rounds": [],
            "results": [],
            "coverage": {"high": 0, "medium": 0, "useful": 0},
            "followup_queries": [],
        }
    intent = payload.get("intent", "auto")
    max_results = int(payload.get("max_results", 8))
    max_deep_results = int(payload.get("max_deep_results", 5))
    max_refine_rounds = int(payload.get("max_refine_rounds", 2))
    site_profiles = payload.get("site_profiles", {})
    variants = build_variants(query, intent, site_profiles)
    engines = engines_for_intent(intent)
    rounds = []
    collected: List[SearchResult] = []
    seen = set()

    def run_round(round_queries: List[Tuple[str, str]], depth: int):
        for variant, site_focus in round_queries:
            for engine in engines:
                items = search_engine(engine, variant, site_focus)
                rounds.append({"depth": depth, "engine": engine, "query": variant, "site_focus": site_focus, "count": len(items)})
                for item in items:
                    key = (item.url or item.title).strip().lower()
                    if not key or key in seen:
                        continue
                    seen.add(key)
                    item.score = score_result(item, query)
                    collected.append(item)

    run_round(variants, 1)
    collected.sort(key=lambda item: item.score, reverse=True)

    refine_round = 1
    while refine_round <= max_refine_rounds:
        top_score = collected[0].score if collected else 0
        if collected and top_score >= 28 and len(collected) >= max_results:
            break
        followups = refine_queries(query, collected)
        if not followups:
            break
        run_round(followups, refine_round + 1)
        collected.sort(key=lambda item: item.score, reverse=True)
        refine_round += 1

    top = collected[:max_results]

    def build_deep(items: List[SearchResult]) -> List[Dict]:
        deep_items = []
        for candidate in items[:max_deep_results]:
            extraction = deep_extract(candidate.url, query)
            deep_items.append({
                "title": candidate.title,
                "url": candidate.url,
                "engine": candidate.engine,
                "query_variant": candidate.query_variant,
                "site_focus": candidate.site_focus,
                "snippet": candidate.snippet,
                "score": candidate.score,
                "extraction": extraction
            })
        return deep_items

    deep = build_deep(top)
    coverage = coverage_signals(deep)
    if max_refine_rounds > 0 and coverage["useful"] < min(2, max_deep_results):
        followups = refine_queries(query, collected)
        if followups:
            run_round(followups, refine_round + 1)
            collected.sort(key=lambda item: item.score, reverse=True)
            top = collected[:max_results]
            deep = build_deep(top)
            coverage = coverage_signals(deep)

    quality = "high" if deep and coverage["high"] >= 2 else "medium" if deep and coverage["useful"] else "low"
    return {
        "query": query,
        "intent": intent,
        "quality": quality,
        "rounds": rounds,
        "results": deep,
        "coverage": coverage,
        "followup_queries": refine_queries(query, collected),
    }


def main() -> int:
    if len(sys.argv) < 3:
        print(json.dumps({"error": "usage: search_orchestrator.py <research|extract> <json_payload>"}, ensure_ascii=False))
        return 1
    command = sys.argv[1]
    payload = json.loads(sys.argv[2])
    if command == "research":
        print(json.dumps(research(payload), ensure_ascii=False))
        return 0
    if command == "extract":
        print(json.dumps(deep_extract(payload["url"], payload.get("query", "")), ensure_ascii=False))
        return 0
    if command == "status":
        print(json.dumps({"ok": True}, ensure_ascii=False))
        return 0
    print(json.dumps({"error": f"unknown_command:{command}"}, ensure_ascii=False))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
