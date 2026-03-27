#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import re
import subprocess
import sys
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


def clean(text: str) -> str:
    text = html.unescape(text or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def http_get(url: str, timeout: int = 20) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def run_json(cmd: List[str]) -> Dict:
    proc = subprocess.run(cmd, text=True, capture_output=True, timeout=45)
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


def deep_extract(url: str, query: str) -> Dict:
    raw, mode = fetch_with_reader_fallback(url)
    if not raw:
        return {"url": url, "fetch_mode": mode, "title": "", "summary": [], "sections": [], "links": [], "quality": "low"}
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
        return {
            "url": url,
            "fetch_mode": mode,
            "title": reader_title,
            "summary": summary,
            "sections": [],
            "links": [],
            "quality": effective_quality(summary, normalized, mode, "high" if summary and mode == "reader" else "medium")
        }
    parser = Extractor()
    parser.feed(raw[:250000])
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
    quality = effective_quality(summary, summary_source, mode, quality)
    return {
        "url": url,
        "fetch_mode": mode,
        "title": parser.title,
        "meta_description": parser.meta_description,
        "summary": summary,
        "sections": parser.sections[:12],
        "links": parser.links[:20],
        "quality": quality
    }


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
