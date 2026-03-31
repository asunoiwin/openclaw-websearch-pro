#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import os
import re
import shutil
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
ENABLE_BROWSER_FALLBACK = os.environ.get("OPENCLAW_SEARCH_ENABLE_BROWSER_FALLBACK", "").strip() == "1"
HERE = Path(__file__).resolve().parent
BRIDGE = HERE / "browser_session_bridge.py"
DISTILL = HERE / "web_content_distill.py"
DOUYIN_PROJECT = Path(os.environ.get("OPENCLAW_DOUYIN_PROJECT", "/tmp/douyin_proj"))
XHS_PROJECT = Path(os.environ.get("OPENCLAW_XHS_PROJECT", "/tmp/xhs_mcp"))
MEDIACRAWLER_PROJECT = Path(os.environ.get("OPENCLAW_MEDIACRAWLER_PROJECT", "/tmp/MediaCrawler"))
PY311 = os.environ.get("OPENCLAW_PY311", "/opt/homebrew/bin/python3.11")
CHROME_BIN = os.environ.get("OPENCLAW_CHROME_BIN", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
XHS_BASE_URL = os.environ.get("OPENCLAW_XHS_BASE_URL", "http://127.0.0.1:18060")
XHS_PID_FILE = Path(os.environ.get("OPENCLAW_XHS_PID_FILE", "/tmp/openclaw_xhs_mcp.pid"))
XHS_LOG_FILE = Path(os.environ.get("OPENCLAW_XHS_LOG_FILE", "/tmp/openclaw_xhs_mcp.log"))
XHS_BINARY = Path(os.environ.get("OPENCLAW_XHS_BINARY", str(XHS_PROJECT / "xhs_mcp_bin")))
MEDIACRAWLER_VENV_PYTHON = Path(os.environ.get("OPENCLAW_MEDIACRAWLER_PYTHON", str(MEDIACRAWLER_PROJECT / ".venv" / "bin" / "python")))
DOUYIN_COOKIE_FILE = Path(os.environ.get("OPENCLAW_DOUYIN_COOKIE_FILE", "/Users/rico/.openclaw/workspace/secrets/douyin-cookie.txt"))
TIEBA_COOKIE_FILE = Path(os.environ.get("OPENCLAW_TIEBA_COOKIE_FILE", "/Users/rico/.openclaw/workspace/secrets/tieba-cookie.txt"))
DOUYIN_MEDIACRAWLER_PROFILE_TEMPLATE = os.environ.get("OPENCLAW_DOUYIN_MEDIACRAWLER_PROFILE_TEMPLATE", "dy_user_data_dir_clone_%s")
MEDIACRAWLER_OUTPUT_BASE = Path(os.environ.get("OPENCLAW_MEDIACRAWLER_OUTPUT_BASE", "/tmp/openclaw_mediacrawler"))
MEDIACRAWLER_TIMEOUT_SECONDS = int(os.environ.get("OPENCLAW_MEDIACRAWLER_TIMEOUT_SECONDS", "45"))
YT_DLP = ["python3", "-m", "yt_dlp"]
GALLERY_DL = ["python3", "-m", "gallery_dl"]
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
SITE_BROWSER_PREFERENCES = {
    "taobao.com": ["safari"],
    "tmall.com": ["safari"],
    "jd.com": ["safari"],
    "zhihu.com": ["safari"],
    "xiaohongshu.com": ["safari"],
    "douyin.com": ["safari"],
    "bilibili.com": ["safari", "chrome"],
    "weibo.com": ["chrome", "safari"],
    "x.com": ["chrome", "safari"],
    "reddit.com": ["chrome", "safari"],
    "producthunt.com": ["chrome", "safari"],
    "gitlab.com": ["chrome", "safari"],
    "yangkeduo.com": ["chrome", "safari"],
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
    r"欢迎登录",
    r"扫码登录",
    r"密码登录",
    r"短信登录",
    r"立即注册",
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
    "weibo": ["讨论", "教程", "经验"],
    "tieba": ["帖子", "吧", "讨论"],
    "x": ["thread", "post", "discussion"],
    "gitlab": ["repo", "project", "issue"],
    "producthunt": ["Product Hunt", "products", "posts"],
    "36kr": ["资讯", "报道", "文章"],
    "taobao": ["教程", "安装", "购买"],
    "jd": ["教程", "安装", "购买"],
    "yangkeduo": ["教程", "安装", "购买"],
}
EXTERNAL_DISCOVERY_EXTRA_SUFFIXES = {
    "xiaohongshu.com": ["GitHub", "skill", "MCP", "教程", "自动化"],
    "douyin.com": ["GitHub", "skill", "MCP", "教程", "自动化"],
    "weibo.com": ["GitHub", "发布", "教程"],
    "x.com": ["GitHub", "thread", "post", "discussion"],
    "reddit.com": ["GitHub", "discussion", "review"],
}
ACTIONABLE_DISCOVERY_DOMAINS = {
    "github.com",
    "clawhub.com",
    "docs.openclaw.ai",
    "docs.anthropic.com",
    "ai.google.dev",
    "zhihu.com",
    "bilibili.com",
}
COMMERCE_ROOTS = {
    "taobao.com",
    "tmall.com",
    "jd.com",
    "yangkeduo.com",
    "pinduoduo.com",
}
EXTERNAL_DISCOVERY_BRANDS = {
    "taobao.com": "淘宝 taobao",
    "tmall.com": "天猫 tmall",
    "xiaohongshu.com": "小红书 xiaohongshu",
    "douyin.com": "抖音 douyin",
    "weibo.com": "微博 weibo",
    "reddit.com": "reddit",
    "x.com": "x twitter",
    "gitlab.com": "gitlab",
    "producthunt.com": "product hunt",
    "36kr.com": "36kr",
    "jd.com": "京东",
    "yangkeduo.com": "拼多多",
}
SITE_FALLBACK_ORDER = {
    "xiaohongshu.com": ("external", "domain", "browser"),
    "douyin.com": ("external", "domain", "browser"),
    "weibo.com": ("external", "domain", "browser"),
    "x.com": ("external", "domain", "browser"),
    "gitlab.com": ("external", "domain", "browser"),
    "producthunt.com": ("domain", "external", "browser"),
    "reddit.com": ("domain", "external", "browser"),
    "taobao.com": ("domain", "external", "browser"),
    "tmall.com": ("domain", "external", "browser"),
    "jd.com": ("domain", "external", "browser"),
    "yangkeduo.com": ("domain", "external", "browser"),
    "pinduoduo.com": ("domain", "external", "browser"),
}
YTDLP_SUPPORTED_ROOTS = {
    "bilibili.com",
    "douyin.com",
    "xiaohongshu.com",
    "weibo.com",
    "x.com",
    "twitter.com",
    "reddit.com",
}
YTDLP_COOKIE_BROWSER = {
    "bilibili.com": "chrome",
    "douyin.com": "chrome",
    "xiaohongshu.com": "chrome",
    "weibo.com": "chrome",
    "x.com": "chrome",
    "twitter.com": "chrome",
    "reddit.com": "chrome",
}
GALLERY_DL_SUPPORTED_ROOTS = {
    "weibo.com",
    "reddit.com",
}
GALLERY_DL_COOKIE_BROWSER = {
    "weibo.com": "chrome",
    "reddit.com": "chrome",
}


def command_available(path: str) -> bool:
    return Path(path).exists()


def xhs_project_available() -> bool:
    return XHS_PROJECT.exists() and command_available("/opt/homebrew/bin/go")


def douyin_project_available() -> bool:
    return DOUYIN_PROJECT.exists() and command_available(PY311)


def mediacrawler_available() -> bool:
    return MEDIACRAWLER_PROJECT.exists() and MEDIACRAWLER_VENV_PYTHON.exists()


def load_cookie_file(path: Path) -> str:
    try:
        value = clean(path.read_text(encoding="utf-8"))
    except Exception:
        return ""
    if not value:
        return ""
    value = re.sub(r"^cookie:\s*", "", value, flags=re.I)
    return clean(value)


def local_http_get(url: str, timeout: int = 10) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def local_http_post_json(url: str, payload: Dict, timeout: int = 20) -> Dict:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "User-Agent": USER_AGENT,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="ignore"))


def xhs_service_health() -> Dict | None:
    try:
        raw = local_http_get(f"{XHS_BASE_URL}/health", timeout=3)
    except Exception:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return {"raw": raw}


def xhs_service_available() -> bool:
    if not xhs_project_available():
        return False
    health = xhs_service_health()
    if not health:
        return False
    text = json.dumps(health, ensure_ascii=False).lower()
    return "healthy" in text or "xiaohongshu-mcp" in text


def xhs_login_status() -> bool | None:
    if not xhs_service_available():
        return None
    try:
        payload = json.loads(local_http_get(f"{XHS_BASE_URL}/api/v1/login/status", timeout=8))
    except Exception:
        return None
    data = payload.get("data") or {}
    if "is_logged_in" not in data:
        return None
    return bool(data.get("is_logged_in"))


def xhs_service_pid() -> int | None:
    try:
        pid = int(XHS_PID_FILE.read_text().strip())
    except Exception:
        return None
    try:
        os.kill(pid, 0)
    except Exception:
        return None
    return pid


def cleanup_xhs_service() -> None:
    pid = xhs_service_pid()
    if pid:
        try:
            os.kill(pid, signal.SIGTERM)
        except Exception:
            pass
    try:
        XHS_PID_FILE.unlink()
    except Exception:
        pass


def xhs_runtime_bootstrap_blocked() -> bool:
    if not XHS_LOG_FILE.exists():
        return False
    text = XHS_LOG_FILE.read_text(errors="ignore")[-4000:]
    return "go: downloading github.com/gabriel-vasile/mimetype" in text


def ensure_xhs_service_started(wait_seconds: int = 12) -> bool:
    if not xhs_project_available():
        return False
    if xhs_service_available():
        return True
    if not xhs_service_pid():
        XHS_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        log_handle = open(XHS_LOG_FILE, "a", encoding="utf-8")
        if XHS_BINARY.exists() and os.access(XHS_BINARY, os.X_OK):
            cmd = [str(XHS_BINARY), "-headless=true", "-bin", CHROME_BIN]
        else:
            cmd = [
                "/opt/homebrew/bin/go",
                "run",
                ".",
                "-headless=true",
                "-bin",
                CHROME_BIN,
            ]
        proc = subprocess.Popen(
            cmd,
            cwd=str(XHS_PROJECT),
            env={
                **os.environ,
                "GOPROXY": os.environ.get("OPENCLAW_XHS_GOPROXY", "https://goproxy.cn,direct"),
                "GOSUMDB": os.environ.get("OPENCLAW_XHS_GOSUMDB", "off"),
            },
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            text=True,
        )
        XHS_PID_FILE.write_text(str(proc.pid), encoding="utf-8")
    deadline = time.time() + wait_seconds
    while time.time() < deadline:
        if xhs_service_available():
            return True
        time.sleep(1)
    cleanup_xhs_service()
    return False


def adapter_blocker_rules(url: str) -> List[str]:
    parsed = urllib.parse.urlparse(url)
    root = root_domain(parsed.netloc.lower())
    path = parsed.path.lower()
    rules: List[str] = []
    if root == "douyin.com" and "/video/" in path:
        if mediacrawler_available():
            if not load_cookie_file(DOUYIN_COOKIE_FILE):
                rules.append("douyin_cookie_file_missing")
            else:
                rules.append("douyin_mediacrawler_probe_failed")
        elif not douyin_project_available():
            rules.append("douyin_adapter_runtime_missing")
        else:
            rules.append("douyin_adapter_probe_failed")
    if root == "xiaohongshu.com" and "/explore/" in path:
        xsec = urllib.parse.parse_qs(parsed.query).get("xsec_token", [""])[0]
        if not xsec:
            rules.append("xhs_missing_xsec_token")
        elif xsec.lower() in {"abc123", "test", "demo"} or len(xsec) < 8:
            rules.append("xhs_invalid_xsec_token")
        elif xhs_service_available() and xhs_login_status() is False:
            rules.append("xhs_adapter_login_required")
        elif xhs_runtime_bootstrap_blocked() and not xhs_service_available():
            rules.append("xhs_adapter_bootstrap_blocked")
        elif not ensure_xhs_service_started():
            rules.append("xhs_adapter_service_unavailable")
        elif xhs_login_status() is False:
            rules.append("xhs_adapter_login_required")
        else:
            rules.append("xhs_adapter_probe_failed")
    return rules


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
    if host.endswith("tieba.baidu.com"):
        return "tieba.baidu.com"
    parts = [part for part in host.split(".") if part]
    if len(parts) <= 2:
        return host
    return ".".join(parts[-2:])


def actionable_discovery_bonus(url: str, target_root: str) -> float:
    item_domain = urllib.parse.urlparse(url).netloc.lower()
    item_root = root_domain(item_domain)
    if item_root in ACTIONABLE_DISCOVERY_DOMAINS:
        return 0.35
    if item_root == target_root:
        return 0.15
    return 0.0


def commerce_root_for_url(url: str) -> str:
    return root_domain(urllib.parse.urlparse(url).netloc.lower())


def is_commerce_item_url(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    root = root_domain(parsed.netloc.lower())
    path = parsed.path.lower()
    query = urllib.parse.parse_qs(parsed.query)
    if root in {"taobao.com", "tmall.com"}:
        if any(token in path for token in ("/item", "/detail", "/list/item/")):
            return True
        if path.endswith(".htm") and any(token in path for token in ("/item", "/list/")):
            return True
    if root in {"yangkeduo.com", "pinduoduo.com"}:
        if any(token in path for token in ("/goods", "/goods.html", "/goods_detail")):
            return True
        if any(key in query for key in ("goods_id", "goodsID", "goods_id_list")):
            return True
    if root == "jd.com":
        return "item.jd.com" in parsed.netloc.lower() and path.endswith(".html")
    return False


def extract_commerce_signals(text: str) -> List[str]:
    sample = clean(text)
    signals: List[str] = []
    patterns = [
        r"(?:¥|￥)\s?\d+(?:\.\d+)?",
        r"\d+(?:\.\d+)?万?\+?人付款",
        r"\d+(?:\.\d+)?万?\+?已售",
        r"\d+(?:\.\d+)?万?\+?销量",
        r"\d+(?:,\d+)?条评价",
        r"\d+(?:\.\d+)?分",
        r"券后\s?(?:¥|￥)\s?\d+(?:\.\d+)?",
        r"(?:官方旗舰店|旗舰店|专营店|自营)",
        r"(?:包邮|满减|优惠券|领券)",
    ]
    for pattern in patterns:
        match = re.search(pattern, sample, re.I)
        if match:
            value = clean(match.group(0))
            if value and value not in signals:
                signals.append(value)
    return signals[:5]


def extract_json_ld_objects(raw: str) -> List[dict]:
    if not raw:
        return []
    matches = re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        raw,
        flags=re.I | re.S,
    )
    objects: List[dict] = []
    for match in matches[:6]:
        payload = clean(match)
        if not payload:
            continue
        try:
            data = json.loads(payload)
        except Exception:
            continue
        queue = data if isinstance(data, list) else [data]
        for item in queue:
            if isinstance(item, dict):
                objects.append(item)
    return objects


def extract_commerce_structured_fields(raw: str) -> List[str]:
    fields: List[str] = []
    seen = set()
    for item in extract_json_ld_objects(raw):
        name = clean(str(item.get("name", "")))
        sku = clean(str(item.get("sku", "")))
        if sku and sku not in seen:
            seen.add(sku)
            fields.append(f"SKU {sku}")
        offers = item.get("offers")
        offer_list = offers if isinstance(offers, list) else ([offers] if isinstance(offers, dict) else [])
        for offer in offer_list[:2]:
            price = clean(str(offer.get("price", "")))
            currency = clean(str(offer.get("priceCurrency", "")))
            seller = offer.get("seller")
            if price:
                value = f"{currency} {price}".strip()
                value = value.replace("CNY ", "¥ ").replace("RMB ", "¥ ")
                if value not in seen:
                    seen.add(value)
                    fields.append(value)
            if isinstance(seller, dict):
                seller_name = clean(str(seller.get("name", "")))
                if seller_name and seller_name not in seen:
                    seen.add(seller_name)
                    fields.append(seller_name)
        rating = item.get("aggregateRating")
        if isinstance(rating, dict):
            review_count = clean(str(rating.get("reviewCount", "")))
            rating_value = clean(str(rating.get("ratingValue", "")))
            if review_count:
                label = f"{review_count}条评价"
                if label not in seen:
                    seen.add(label)
                    fields.append(label)
            if rating_value:
                label = f"{rating_value}分"
                if label not in seen:
                    seen.add(label)
                    fields.append(label)
        if name and name not in seen:
            seen.add(name)
            fields.append(name)
    return fields[:6]


def format_commerce_line(title: str, snippet: str, url: str) -> str:
    title = clean(title)
    snippet = clean(snippet)
    combined = " ".join(part for part in (title, snippet) if part)
    signals = extract_commerce_signals(combined)
    if not signals:
        return f"{title}: {snippet[:180]}".strip(": ") if snippet else title
    signal_text = " | ".join(signals)
    if title:
        return f"{title} | {signal_text}"
    return signal_text


def commerce_result_bonus(title: str, snippet: str, query: str) -> float:
    combined = f"{title} {snippet}"
    bonus = 0.0
    bonus += min(len(extract_commerce_signals(combined)), 4) * 0.18
    if query_overlap_score(combined, query) >= 1:
        bonus += 0.12
    if any(token in combined for token in ("官方旗舰店", "自营", "天猫", "京东")):
        bonus += 0.12
    return bonus


def commerce_external_penalty(url: str) -> float:
    parsed = urllib.parse.urlparse(url)
    domain = parsed.netloc.lower()
    path = parsed.path.lower()
    penalty = 0.0
    if looks_like_search_or_shell_url(url):
        penalty += 0.45
    if any(domain.endswith(site) for site in ("douyin.com", "xiaohongshu.com", "weibo.com")) and "/search" in path:
        penalty += 0.35
    if any(token in path for token in ("/guide/", "/topic/", "/k/")):
        penalty += 0.18
    return penalty


def commerce_external_source_bonus(url: str, title: str, snippet: str) -> float:
    parsed = urllib.parse.urlparse(url)
    item_root = root_domain(parsed.netloc.lower())
    combined = clean(f"{title} {snippet}")
    bonus = 0.0
    if item_root == "zhizhizhi.com":
        bonus += 0.42
    elif item_root in {"smzdm.com", "zol.com.cn"}:
        bonus += 0.30
    if item_root in {"bilibili.com"} and any(token in combined for token in ("测评", "评测", "开箱")):
        bonus += 0.18
    if any(token in combined for token in ("优惠券", "到手价", "价格", "测评", "评测", "推荐")):
        bonus += 0.12
    return bonus


def commerce_external_source_penalty(url: str, title: str, snippet: str) -> float:
    parsed = urllib.parse.urlparse(url)
    item_root = root_domain(parsed.netloc.lower())
    combined = clean(f"{title} {snippet}")
    penalty = 0.0
    if item_root == "zhihu.com":
        penalty += 0.14
        if any(token in combined for token in ("能买吗", "怎么这么便宜", "值不值得", "好用吗", "靠谱吗")):
            penalty += 0.28
    if item_root == "baidu.com" or item_root == "zhidao.baidu.com":
        penalty += 0.14
    return penalty


def commerce_external_rank(url: str, title: str, snippet: str) -> float:
    return commerce_external_source_bonus(url, title, snippet) - commerce_external_source_penalty(url, title, snippet)


def has_commerce_content_signal(lines: List[str]) -> bool:
    sample = " ".join(clean(line) for line in lines if line)
    return len(extract_commerce_signals(sample)) >= 1


def has_brand_context(text: str, brand: str) -> bool:
    sample = clean(text).lower()
    brand_tokens = re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]{2,}", brand.lower())
    return any(token and token in sample for token in brand_tokens)


def extract_commerce_detail_summary(title: str, desc: str, raw: str) -> List[str]:
    sample = clean(re.sub(r"<[^>]+>", " ", raw or ""))[:8000]
    candidates: List[str] = []
    if clean(title):
        candidates.append(clean(title))
    if clean(desc):
        candidates.append(clean(desc)[:220])
    for field in extract_commerce_structured_fields(raw):
        if field not in candidates:
            candidates.append(field)

    detail_patterns = [
        r"(?:¥|￥)\s?\d+(?:\.\d+)?",
        r"\d+(?:,\d+)?条评价",
        r"\d+(?:\.\d+)?万?\+?人付款",
        r"\d+(?:\.\d+)?万?\+?已售",
        r"(?:官方旗舰店|旗舰店|专营店|自营|官方补贴)",
        r"(?:颜色分类|规格|型号|套餐类型|版本|尺码)\s*[:：]?\s*[^\s,，;；]{1,24}",
    ]
    seen = set(clean(value) for value in candidates if clean(value))
    for pattern in detail_patterns:
        for match in re.finditer(pattern, sample, re.I):
            value = clean(match.group(0))
            if not value or value in seen:
                continue
            seen.add(value)
            candidates.append(value)
            break
    return candidates[:6]


def extract_commerce_detail_sections(summary: List[str]) -> List[Dict[str, str]]:
    sections: List[Dict[str, str]] = []
    for line in summary:
        item = clean(line)
        if not item:
            continue
        level = "meta"
        lowered = item.lower()
        if item.startswith("SKU "):
            level = "sku"
        elif re.search(r"(?:¥|￥)\s?\d+(?:\.\d+)?", item):
            level = "price"
        elif "评价" in item or item.endswith("分"):
            level = "rating"
        elif "付款" in item or "已售" in item:
            level = "sales"
        elif any(token in item for token in ("旗舰店", "专营店", "自营", "官方补贴")):
            level = "shop"
        elif any(token in item for token in ("颜色分类", "规格", "型号", "套餐类型", "版本", "尺码")):
            level = "spec"
        elif "淘宝" in item or "京东" in item or "拼多多" in item:
            level = "title"
        sections.append({"level": level, "text": item[:220]})
    return sections[:8]


def is_actionable_non_product_query(query: str) -> bool:
    sample = clean(query).lower()
    tokens = [
        "openclaw",
        "clawhub",
        "plugin",
        "skill",
        "mcp",
        "github",
        "教程",
        "安装",
        "配置",
        "自动化",
        "优化",
        "文档",
        "脚本",
        "部署",
        "开发",
    ]
    return any(token in sample for token in tokens)


def target_slug_terms(url: str) -> List[str]:
    parsed = urllib.parse.urlparse(url)
    path = parsed.path.strip("/")
    if not path:
        return []
    tail = path.split("/")[-1]
    tail = clean(tail.replace("-", " "))
    terms = [term for term in re.findall(r"[a-z0-9][a-z0-9._/-]{1,}|[\u4e00-\u9fff]{2,}", tail.lower()) if len(term) >= 2]
    deduped = []
    seen = set()
    for term in terms:
        if term in seen:
            continue
        seen.add(term)
        deduped.append(term)
    return deduped[:6]


def target_slug_value(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    path = parsed.path.strip("/")
    if not path:
        return ""
    return clean(path.split("/")[-1].lower())


def normalized_target_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    scheme = parsed.scheme or "https"
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/")
    if not path:
        path = "/"
    return urllib.parse.urlunparse((scheme, netloc, path, "", "", ""))


def fallback_order_for_url(url: str) -> Tuple[str, ...]:
    domain = urllib.parse.urlparse(url).netloc.lower()
    root = root_domain(domain)
    return SITE_FALLBACK_ORDER.get(root, ("browser", "domain", "external"))


def url_path_depth(url: str) -> int:
    parsed = urllib.parse.urlparse(url)
    return len([segment for segment in parsed.path.split("/") if segment])


def commerce_url_rank(url: str) -> Tuple[int, int]:
    item_like = 0 if is_commerce_item_url(url) else 1
    generic_channel = 1 if is_generic_commerce_channel_url(url) else 0
    return (item_like, generic_channel)


def is_homepage_like(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    path = parsed.path.strip("/")
    if not path:
        return True
    return path in {"search", "search_result", "results", "all", "blog", "models"}


def is_generic_commerce_channel_url(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    domain = parsed.netloc.lower()
    root = root_domain(domain)
    path = parsed.path.lower().strip("/")
    if root in {"yangkeduo.com", "pinduoduo.com"}:
        return path.startswith("home/") or path in {"", "index.html"}
    if root in {"taobao.com", "tmall.com"}:
        if "/list/category/" in parsed.path.lower() or "/list/product/" in parsed.path.lower():
            return True
        if any(token in path for token in ("topic/", "/topic/", "guide/", "/guide/", "k/")):
            return True
        if domain.startswith("bk.taobao.com") or domain.startswith("shuma.taobao.com"):
            return True
        if domain.startswith("goods.taobao.com") and path.startswith("t/"):
            return True
    return False


def http_get(url: str, timeout: int = 20) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def http_post_json(url: str, payload: Dict, timeout: int = 20) -> Dict:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "User-Agent": USER_AGENT,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="ignore"))


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


def yt_dlp_available() -> bool:
    try:
        proc = subprocess.run(
            YT_DLP + ["--version"],
            text=True,
            capture_output=True,
            timeout=8,
        )
    except Exception:
        return False
    return proc.returncode == 0


def gallery_dl_available() -> bool:
    try:
        proc = subprocess.run(
            GALLERY_DL + ["--version"],
            text=True,
            capture_output=True,
            timeout=8,
        )
    except Exception:
        return False
    return proc.returncode == 0


def looks_like_search_or_shell_url(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    path = parsed.path.lower()
    if any(token in path for token in ("/search", "/results", "/all", "/explore", "/discover")):
        return True
    query_params = urllib.parse.parse_qs(parsed.query)
    return any(key in query_params for key in ("q", "query", "search", "keyword", "wd"))


def looks_like_known_error_shell(title: str, raw: str, url: str) -> bool:
    lowered_title = clean(title).lower()
    lowered_raw = clean(raw[:3000]).lower()
    domain = root_domain(urllib.parse.urlparse(url).netloc.lower())
    parsed = urllib.parse.urlparse(url)
    path = parsed.path.lower()
    if domain == "xiaohongshu.com" and (
        "你访问的页面不见了" in title
        or "你访问的页面不见了" in raw[:3000]
        or "page not found" in lowered_title
    ):
        return True
    if domain in {"taobao.com", "tmall.com"}:
        if "jiantiseos.taobao.com" in raw[:6000] or "_____tmd_____/punish" in raw[:6000] or "x5secdata=" in raw[:6000]:
            return True
    if domain == "douyin.com":
        if re.search(r"<body>\s*</body>", raw[:5000], flags=re.I | re.S):
            return True
        if len(lowered_raw) < 120 and not lowered_title:
            return True
    if domain == "yangkeduo.com":
        if "风靡全国的拼团商城" in raw[:6000] or "优质商品新鲜直供" in raw[:6000]:
            if any(token in path for token in ("/search_result", "/goods", "/goods.html")):
                return True
        if lowered_title == "拼多多" and any(token in path for token in ("/search_result", "/goods", "/goods.html")):
            return True
    if domain == "jd.com":
        combined = f"{lowered_title} {lowered_raw}"
        if "search.jd.com" in parsed.netloc.lower() or "/search" in path.lower():
            if any(token in combined for token in ("京东验证", "请完成验证", "安全验证", "验证中心", "verify")):
                return True
        if "item.jd.com" in parsed.netloc.lower() and any(token in combined for token in ("京东验证", "请完成验证", "安全验证")):
            return True
    return False


def yt_dlp_cookie_browser_for_url(url: str) -> str | None:
    root = root_domain(urllib.parse.urlparse(url).netloc.lower())
    return YTDLP_COOKIE_BROWSER.get(root)


def extract_yt_dlp_special(url: str, query: str) -> Dict | None:
    parsed = urllib.parse.urlparse(url)
    root = root_domain(parsed.netloc.lower())
    if root not in YTDLP_SUPPORTED_ROOTS:
        return None
    if looks_like_search_or_shell_url(url):
        return None
    if not yt_dlp_available():
        return None

    cmd = YT_DLP + ["--dump-single-json", "--skip-download", "--no-warnings"]
    cookie_browser = yt_dlp_cookie_browser_for_url(url)
    if cookie_browser:
        cmd += ["--cookies-from-browser", cookie_browser]
    cmd.append(url)
    try:
        proc = subprocess.run(cmd, text=True, capture_output=True, timeout=35)
    except Exception:
        return None
    if proc.returncode != 0 or not clean(proc.stdout):
        return None
    try:
        payload = json.loads(proc.stdout)
    except Exception:
        return None

    title = clean(payload.get("title", ""))
    description = clean(payload.get("description", ""))
    uploader = clean(payload.get("uploader", "") or payload.get("channel", "") or payload.get("creator", ""))
    tags = [clean(tag) for tag in (payload.get("tags") or []) if clean(tag)]
    stats = []
    for field in ("view_count", "like_count", "comment_count", "duration"):
        value = payload.get(field)
        if value not in (None, "", 0):
            stats.append(f"{field}={value}")
    text = " ".join(part for part in [title, description, uploader, " ".join(tags[:12]), " ".join(stats)] if part)
    summary = summarize_text(text, query)
    if not summary and title:
        summary = [title]
        if description:
            summary.append(description[:220])
    if not summary:
        return None

    sections = []
    if uploader:
        sections.append({"level": "meta", "text": f"uploader: {uploader}"})
    if stats:
        sections.append({"level": "meta", "text": ", ".join(stats)})
    if tags:
        sections.append({"level": "meta", "text": "tags: " + ", ".join(tags[:10])})

    rules = ["yt_dlp_adapter"]
    if cookie_browser:
        rules.append(f"browser_cookies_{cookie_browser}")
    return {
        "url": url,
        "fetch_mode": "yt_dlp",
        "title": title or clean(parsed.netloc),
        "summary": summary[:5],
        "sections": sections[:8],
        "links": [],
        "quality": "high" if len(summary) >= 2 else "medium",
        "uploader": uploader,
        "applied_rules": rules,
    }


def extract_gallery_dl_special(url: str, query: str) -> Dict | None:
    parsed = urllib.parse.urlparse(url)
    root = root_domain(parsed.netloc.lower())
    if root not in GALLERY_DL_SUPPORTED_ROOTS:
        return None
    if looks_like_search_or_shell_url(url):
        return None
    if not gallery_dl_available():
        return None
    cmd = GALLERY_DL + ["-j"]
    cookie_browser = GALLERY_DL_COOKIE_BROWSER.get(root)
    if cookie_browser:
        cmd += ["--cookies-from-browser", cookie_browser]
    cmd.append(url)
    try:
        proc = subprocess.run(
            cmd,
            text=True,
            capture_output=True,
            timeout=35,
        )
    except Exception:
        return None
    if proc.returncode != 0 or not clean(proc.stdout):
        return None
    try:
        payload = json.loads(proc.stdout)
    except Exception:
        return None
    if not payload or not isinstance(payload, list):
        return None
    meta = payload[0][1] if isinstance(payload[0], list) and len(payload[0]) > 1 else {}
    if not isinstance(meta, dict):
        return None
    if root == "reddit.com":
        title = clean(meta.get("title", ""))
        selftext = clean(meta.get("selftext", ""))
        author = clean(meta.get("author", ""))
        subreddit = clean(meta.get("subreddit", ""))
        domain = clean(meta.get("domain", ""))
        outbound = clean(meta.get("url", ""))
        stats = []
        for field in ("score", "num_comments"):
            value = meta.get(field)
            if value not in (None, "", 0):
                stats.append(f"{field}={value}")
        text = " ".join(part for part in [title, selftext, author, subreddit, domain, " ".join(stats)] if part)
        summary = summarize_text(text, query)
        if not summary and title:
            summary = [title]
            if selftext:
                summary.append(selftext[:280])
        if not summary:
            return None
        sections = []
        if author:
            sections.append({"level": "meta", "text": f"author: {author}"})
        if subreddit:
            sections.append({"level": "meta", "text": f"subreddit: {subreddit}"})
        if domain:
            sections.append({"level": "meta", "text": f"domain: {domain}"})
        if stats:
            sections.append({"level": "meta", "text": ", ".join(stats)})
        links = [{"label": "outbound", "url": outbound}] if outbound.startswith("http") else []
        return {
            "url": url,
            "fetch_mode": "gallery_dl",
            "title": title or clean(parsed.netloc),
            "summary": summary[:5],
            "sections": sections[:8],
            "links": links[:10],
            "quality": "high" if len(summary) >= 2 else "medium",
            "applied_rules": ["gallery_dl_adapter", "browser_cookies_chrome"],
        }
    text_raw = clean(meta.get("text_raw", ""))
    user = meta.get("user") or {}
    author = clean(user.get("screen_name", "") if isinstance(user, dict) else "")
    stats = []
    for field in ("comments_count", "attitudes_count", "reposts_count"):
        value = meta.get(field)
        if value not in (None, "", 0):
            stats.append(f"{field}={value}")
    text = " ".join(part for part in [text_raw, author, " ".join(stats)] if part)
    summary = summarize_text(text, query)
    if not summary and text_raw:
        summary = [text_raw[:280]]
    if not summary:
        return None
    sections = []
    if author:
        sections.append({"level": "meta", "text": f"author: {author}"})
    if stats:
        sections.append({"level": "meta", "text": ", ".join(stats)})
    source = clean(meta.get("source", ""))
    if source:
        sections.append({"level": "meta", "text": f"source: {source}"})
    return {
        "url": url,
        "fetch_mode": "gallery_dl",
        "title": author or clean(parsed.netloc),
        "summary": summary[:5],
        "sections": sections[:8],
        "links": [],
        "quality": "high" if len(summary) >= 2 else "medium",
        "applied_rules": ["gallery_dl_adapter"],
    }


def extract_twitter_oembed_special(url: str, query: str) -> Dict | None:
    parsed = urllib.parse.urlparse(url)
    root = root_domain(parsed.netloc.lower())
    if root not in {"x.com", "twitter.com"}:
        return None
    path = parsed.path.lower()
    if "/status/" not in path:
        return None
    endpoint = "https://publish.twitter.com/oembed?omit_script=1&url=" + urllib.parse.quote(url, safe="")
    raw = try_fetch(endpoint, timeout=15)
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except Exception:
        return None
    html_snippet = payload.get("html", "") or ""
    author = clean(payload.get("author_name", ""))
    author_url = clean(payload.get("author_url", ""))
    text_match = re.search(r"<p[^>]*>(.*?)</p>", html_snippet, flags=re.S | re.I)
    if not text_match:
        return None
    text = clean(re.sub(r"<[^>]+>", " ", text_match.group(1)))
    if not text:
        return None
    summary = summarize_text(" ".join(part for part in [text, author] if part), query)
    if not summary:
        summary = [text[:280]]
    sections = []
    if author:
        sections.append({"level": "meta", "text": f"author: {author}"})
    links = [{"label": "author", "url": author_url}] if author_url.startswith("http") else []
    return {
        "url": url,
        "fetch_mode": "twitter_oembed",
        "title": author or clean(parsed.netloc),
        "summary": summary[:5],
        "sections": sections[:8],
        "links": links[:10],
        "quality": "medium" if summary else "low",
        "applied_rules": ["twitter_oembed"],
    }


def extract_douyin_project_special(url: str, query: str) -> Dict | None:
    parsed = urllib.parse.urlparse(url)
    root = root_domain(parsed.netloc.lower())
    if root != "douyin.com" or "/video/" not in parsed.path.lower():
        return None
    if not douyin_project_available():
        return None
    cmd = [
        PY311,
        "-c",
        (
            "import sys, asyncio, json; "
            f"sys.path.insert(0, {json.dumps(str(DOUYIN_PROJECT))}); "
            "from crawlers.hybrid.hybrid_crawler import HybridCrawler; "
            "async def main():\n"
            f"  data = await HybridCrawler().hybrid_parsing_single_video({json.dumps(url)}, minimal=True)\n"
            "  print(json.dumps(data, ensure_ascii=False))\n"
            "asyncio.run(main())"
        ),
    ]
    try:
        proc = subprocess.run(cmd, text=True, capture_output=True, timeout=40)
    except Exception:
        return None
    if proc.returncode != 0:
        return None
    stdout = clean(proc.stdout)
    if not stdout:
        return None
    try:
        payload = json.loads(stdout)
    except Exception:
        return None
    desc = clean(payload.get("desc", ""))
    author = payload.get("author") or {}
    author_name = clean(author.get("nickname", "") if isinstance(author, dict) else "")
    statistics = payload.get("statistics") or {}
    stats = []
    for field in ("play_count", "admire_count", "comment_count", "collect_count", "share_count"):
        value = statistics.get(field)
        if value not in (None, "", 0):
            stats.append(f"{field}={value}")
    text = " ".join(part for part in [desc, author_name, " ".join(stats)] if part)
    summary = summarize_text(text, query)
    if not summary and desc:
        summary = [desc[:280]]
    if not summary:
        return None
    sections = []
    if author_name:
        sections.append({"level": "meta", "text": f"author: {author_name}"})
    if stats:
        sections.append({"level": "meta", "text": ", ".join(stats)})
    return {
        "url": url,
        "fetch_mode": "douyin_project",
        "title": author_name or "Douyin Video",
        "summary": summary[:5],
        "sections": sections[:8],
        "links": [],
        "quality": "high" if len(summary) >= 2 else "medium",
        "applied_rules": ["douyin_project_adapter"],
    }


def extract_mediacrawler_douyin_special(url: str, query: str) -> Dict | None:
    parsed = urllib.parse.urlparse(url)
    root = root_domain(parsed.netloc.lower())
    if root != "douyin.com" or "/video/" not in parsed.path.lower():
        return None
    if not mediacrawler_available():
        return None
    cookie_str = load_cookie_file(DOUYIN_COOKIE_FILE)
    if not cookie_str:
        return None

    stamp = str(int(time.time() * 1000))
    out_dir = MEDIACRAWLER_OUTPUT_BASE / stamp
    cmd = [
        str(MEDIACRAWLER_VENV_PYTHON),
        "main.py",
        "--platform",
        "dy",
        "--lt",
        "cookie",
        "--type",
        "detail",
        "--specified_id",
        url,
        "--cookies",
        cookie_str,
        "--headless",
        "true",
        "--save_data_option",
        "json",
        "--save_data_path",
        str(out_dir),
        "--get_comment",
        "false",
        "--get_sub_comment",
        "false",
        "--max_concurrency_num",
        "1",
    ]
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(MEDIACRAWLER_PROJECT),
            text=True,
            capture_output=True,
            timeout=MEDIACRAWLER_TIMEOUT_SECONDS,
        )
        if proc.returncode != 0:
            return None

        candidates = sorted((out_dir / "douyin" / "json").glob("detail_contents_*.json"))
        if not candidates:
            return None
        try:
            payload = json.loads(candidates[-1].read_text(encoding="utf-8"))
        except Exception:
            return None
    except subprocess.TimeoutExpired:
        return None
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)
    if isinstance(payload, list):
        item = payload[-1] if payload else {}
    else:
        item = payload
    if not isinstance(item, dict):
        return None

    title = clean(item.get("title", "") or item.get("desc", ""))
    author = clean(item.get("nickname", ""))
    stats = []
    for field in ("liked_count", "collected_count", "comment_count", "share_count"):
        value = item.get(field)
        if value not in (None, "", 0, "0"):
            stats.append(f"{field}={value}")
    text = " ".join(part for part in [title, author, " ".join(stats)] if part)
    summary = summarize_text(text, query)
    if not summary and title:
        summary = [title[:280]]
    if not summary:
        return None
    sections = []
    if author:
        sections.append({"level": "meta", "text": f"author: {author}"})
    if stats:
        sections.append({"level": "meta", "text": ", ".join(stats)})
    links = []
    for field in ("cover_url", "video_download_url", "music_download_url"):
        value = clean(item.get(field, ""))
        if value.startswith("http"):
            links.append({"label": field, "url": value})
    return {
        "url": url,
        "fetch_mode": "mediacrawler_douyin",
        "title": title or author or "Douyin Video",
        "summary": summary[:5],
        "sections": sections[:8],
        "links": links[:10],
        "quality": "high" if len(summary) >= 2 else "medium",
        "applied_rules": ["mediacrawler_douyin", "cookie_file_login"],
    }


def sanitize_douyin_profile_text(text: str) -> str:
    sample = clean(text)
    if not sample:
        return ""
    if "你要观看的视频不存在" in sample:
        return ""
    markers = [
        "广告投放 用户服务协议",
        "网络谣言曝光台",
        "违法和不良信息举报",
        "京ICP备16016397号",
        "下载抖音 抖音电商",
        "开启读屏标签",
    ]
    for marker in markers:
        if marker in sample:
            sample = sample.split(marker, 1)[0].strip()
    return clean(sample[:1600])


def extract_douyin_profile_stats(text: str) -> List[str]:
    sample = clean(text)
    if not sample:
        return []
    patterns = [
        r"\d+(?:\.\d+)?万?个喜欢",
        r"\d+(?:\.\d+)?万?个赞",
        r"\d+(?:\.\d+)?万?次播放",
        r"\d+(?:\.\d+)?万?条评论",
        r"\d+(?:\.\d+)?万?次分享",
        r"\d+(?:\.\d+)?万?次收藏",
        r"\d+(?:\.\d+)?万?人看过",
    ]
    results: List[str] = []
    seen = set()
    for pattern in patterns:
        match = re.search(pattern, sample)
        if not match:
            continue
        value = clean(match.group(0))
        if value and value not in seen:
            seen.add(value)
            results.append(value)
    return results[:5]


def build_douyin_profile_result(url: str, query: str, payload: Dict) -> Dict | None:
    if not isinstance(payload, dict):
        return None
    title = clean(payload.get("title", ""))
    description = clean(payload.get("description", ""))
    body_text = sanitize_douyin_profile_text(payload.get("text", ""))
    stats = extract_douyin_profile_stats(" ".join(part for part in (description, body_text) if part))
    for field, label in (
        ("like_count", "like_count"),
        ("liked_count", "liked_count"),
        ("comment_count", "comment_count"),
        ("share_count", "share_count"),
        ("collect_count", "collect_count"),
        ("collected_count", "collected_count"),
        ("play_count", "play_count"),
    ):
        value = payload.get(field)
        if value not in (None, "", 0, "0"):
            stats.append(f"{label}={value}")
    deduped_stats = []
    seen_stats = set()
    for stat in stats:
        if stat in seen_stats:
            continue
        seen_stats.add(stat)
        deduped_stats.append(stat)
    stats = deduped_stats[:6]
    summary = summarize_text(" ".join(part for part in (description, body_text) if part), query)
    if not summary and description:
        summary = [description[:280]]
    if not summary and title:
        summary = [title[:280]]
    for stat in stats:
        if stat not in summary:
            summary.append(stat)
    if not summary:
        return None
    sections = []
    if description:
        sections.append({"level": "meta", "text": description[:220]})
    if stats:
        sections.append({"level": "meta", "text": " | ".join(stats)})
    for heading in payload.get("headings", [])[:5]:
        heading = clean(heading)
        if heading:
            sections.append({"level": "heading", "text": heading[:160]})
    quality = "high" if body_text and len(summary) >= 2 else "medium"
    return {
        "url": url,
        "fetch_mode": "mediacrawler_douyin_profile",
        "title": title or "Douyin Video",
        "summary": summary[:5],
        "sections": sections[:8],
        "links": [],
        "quality": quality,
        "applied_rules": ["mediacrawler_douyin_profile", "persistent_profile_login"],
    }


def extract_mediacrawler_douyin_profile_special(url: str, query: str) -> Dict | None:
    parsed = urllib.parse.urlparse(url)
    root = root_domain(parsed.netloc.lower())
    if root != "douyin.com" or "/video/" not in parsed.path.lower():
        return None
    if not mediacrawler_available():
        return None
    profile_dir = MEDIACRAWLER_PROJECT / "browser_data" / (DOUYIN_MEDIACRAWLER_PROFILE_TEMPLATE % "dy")
    if not profile_dir.exists():
        return None
    js = """() => ({
      title: document.title || '',
      url: location.href,
      text: ((document.body && document.body.innerText) || '').split('\\n').join(' ').replace(/\\s+/g,' ').trim().slice(0,3000),
      description: (document.querySelector('meta[name="description"]') && document.querySelector('meta[name="description"]').content) || '',
      headings: Array.from(document.querySelectorAll('h1,h2,h3')).slice(0,8).map(el => el.innerText.trim()),
    })"""
    code = f"""
import asyncio, json, config
from playwright.async_api import async_playwright
from media_platform.douyin.core import DouYinCrawler
VIDEO = {json.dumps(url)}
JS = {json.dumps(js)}
async def main():
    config.PLATFORM='dy'
    config.HEADLESS=True
    config.ENABLE_CDP_MODE=False
    config.SAVE_LOGIN_STATE=True
    config.USER_DATA_DIR={json.dumps(DOUYIN_MEDIACRAWLER_PROFILE_TEMPLATE)}
    crawler = DouYinCrawler()
    async with async_playwright() as playwright:
        chromium = playwright.chromium
        crawler.browser_context = await crawler.launch_browser(chromium, None, None, headless=True)
        page = await crawler.browser_context.new_page()
        await page.goto(VIDEO)
        await asyncio.sleep(4)
        payload = await page.evaluate(JS)
        print(json.dumps(payload, ensure_ascii=False))
        await crawler.browser_context.close()
asyncio.run(main())
"""
    try:
        proc = subprocess.run(
            [str(MEDIACRAWLER_VENV_PYTHON), "-c", code],
            cwd=str(MEDIACRAWLER_PROJECT),
            text=True,
            capture_output=True,
            timeout=35,
        )
        if proc.returncode != 0:
            return None
        lines = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
        if not lines:
            return None
        payload = json.loads(lines[-1])
    except Exception:
        return None
    return build_douyin_profile_result(url, query, payload)


def extract_mediacrawler_tieba_special(url: str, query: str) -> Dict | None:
    parsed = urllib.parse.urlparse(url)
    root = root_domain(parsed.netloc.lower())
    path = parsed.path.lower()
    if root != "tieba.baidu.com":
        return None
    if not query:
        return None
    if "/f/search" not in path and "/f" not in path:
        return None
    if not mediacrawler_available():
        return None

    cookie_str = load_cookie_file(TIEBA_COOKIE_FILE) or "BDUSS=dummy"
    stamp = str(int(time.time() * 1000))
    out_dir = MEDIACRAWLER_OUTPUT_BASE / stamp
    cmd = [
        str(MEDIACRAWLER_VENV_PYTHON),
        "main.py",
        "--platform",
        "tieba",
        "--lt",
        "cookie",
        "--cookies",
        cookie_str,
        "--type",
        "search",
        "--keywords",
        query,
        "--headless",
        "true",
        "--save_data_option",
        "json",
        "--save_data_path",
        str(out_dir),
        "--get_comment",
        "false",
        "--get_sub_comment",
        "false",
        "--max_concurrency_num",
        "1",
    ]
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(MEDIACRAWLER_PROJECT),
            text=True,
            capture_output=True,
            timeout=MEDIACRAWLER_TIMEOUT_SECONDS,
        )
        if proc.returncode != 0:
            return None
        candidates = sorted((out_dir / "tieba" / "json").glob("search_contents_*.json"))
        if not candidates:
            return None
        try:
            payload = json.loads(candidates[-1].read_text(encoding="utf-8"))
        except Exception:
            return None
    except subprocess.TimeoutExpired:
        return None
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)

    if not isinstance(payload, list) or not payload:
        return None
    summary = []
    sections = []
    links = []
    for item in payload[:5]:
        if not isinstance(item, dict):
            continue
        title = clean(item.get("title", ""))
        desc = clean(item.get("desc", "") or item.get("content_text", ""))
        note_url = clean(item.get("note_url", "") or item.get("content_url", ""))
        tieba_name = clean(item.get("tieba_name", ""))
        if not title and not desc:
            continue
        line = f"{title}: {desc[:180]}".strip(": ") if desc else title
        if tieba_name:
            line = f"{line} | tieba={tieba_name}" if line else f"tieba={tieba_name}"
        summary.append(line)
        sections.append({"level": "results", "text": title or desc[:80]})
        if note_url.startswith("http"):
            links.append({"text": title or note_url, "href": note_url})
    if not summary:
        return None
    return {
        "url": url,
        "fetch_mode": "mediacrawler_tieba",
        "title": "Tieba Search",
        "summary": summary[:5],
        "sections": sections[:10],
        "links": links[:10],
        "quality": "high" if len(summary) >= 2 else "medium",
        "applied_rules": ["mediacrawler_tieba", "cookie_file_login"],
    }


def extract_xhs_mcp_special(url: str, query: str) -> Dict | None:
    parsed = urllib.parse.urlparse(url)
    root = root_domain(parsed.netloc.lower())
    if root != "xiaohongshu.com":
        return None
    match = re.search(r"/explore/([0-9a-zA-Z]+)", parsed.path)
    if not ensure_xhs_service_started():
        return None
    if xhs_login_status() is False:
        return None

    feed_id = match.group(1) if match else ""
    xsec_token = urllib.parse.parse_qs(parsed.query).get("xsec_token", [""])[0]

    def valid_xsec_token(value: str) -> bool:
        value = clean(value)
        if not value:
            return False
        if value.lower() in {"abc123", "test", "demo"}:
            return False
        return len(value) >= 8

    def fetch_xhs_detail(target_feed_id: str, target_xsec_token: str) -> Dict | None:
        if not target_feed_id or not valid_xsec_token(target_xsec_token):
            return None
        for _ in range(2):
            try:
                payload = local_http_post_json(
                    f"{XHS_BASE_URL}/api/v1/feeds/detail",
                    {"feed_id": target_feed_id, "xsec_token": target_xsec_token},
                    timeout=20,
                )
            except Exception:
                payload = None
            if isinstance(payload, dict) and payload.get("success") is not False:
                return payload
            time.sleep(0.5)
        return None

    def search_xhs_feed_candidate(keyword: str, preferred_feed_id: str = "") -> Tuple[str, str]:
        keyword = clean(keyword)
        if not keyword:
            return "", ""
        try:
            payload = local_http_post_json(
                f"{XHS_BASE_URL}/api/v1/feeds/search",
                {"keyword": keyword},
                timeout=20,
            )
        except Exception:
            return "", ""
        feeds = (((payload or {}).get("data") or {}).get("feeds") or []) if isinstance(payload, dict) else []
        if not isinstance(feeds, list):
            return "", ""
        query_tokens = re.findall(r"[a-z0-9][a-z0-9._/-]{1,}|[\u4e00-\u9fff]{2,}", keyword.lower())
        best_score = -1
        best_pair = ("", "")
        for item in feeds:
            if not isinstance(item, dict):
                continue
            item_id = clean(item.get("id", ""))
            item_token = clean(item.get("xsecToken", "") or item.get("xsec_token", ""))
            note_card = item.get("noteCard") if isinstance(item.get("noteCard"), dict) else {}
            title = clean(note_card.get("displayTitle", "") or item.get("title", ""))
            score = 0
            if preferred_feed_id and item_id == preferred_feed_id:
                score += 100
            if valid_xsec_token(item_token):
                score += 10
            if title:
                title_tokens = re.findall(r"[a-z0-9][a-z0-9._/-]{1,}|[\u4e00-\u9fff]{2,}", title.lower())
                score += sum(1 for token in query_tokens if token in title_tokens) * 3
                if keyword.lower() in title.lower():
                    score += 10
            if score > best_score:
                best_score = score
                best_pair = (item_id, item_token)
        return best_pair

    def unpack_xhs_detail_payload(payload: Dict) -> Tuple[Dict, List[Dict]]:
        if not isinstance(payload, dict):
            return {}, []
        outer = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        data = outer.get("data") if isinstance(outer.get("data"), dict) else outer
        note = data.get("note") if isinstance(data.get("note"), dict) else data
        comments_obj = data.get("comments") if isinstance(data.get("comments"), dict) else {}
        comments = comments_obj.get("list") if isinstance(comments_obj.get("list"), list) else []
        return note if isinstance(note, dict) else {}, comments

    payload = None
    if feed_id and valid_xsec_token(xsec_token):
        payload = fetch_xhs_detail(feed_id, xsec_token)

    if payload is None:
        candidate_feed_id, candidate_xsec_token = search_xhs_feed_candidate(query, preferred_feed_id=feed_id)
        if candidate_feed_id and candidate_xsec_token:
            payload = fetch_xhs_detail(candidate_feed_id, candidate_xsec_token)

    note, comments = unpack_xhs_detail_payload(payload or {})
    if not note:
        return None

    title = clean(note.get("title", ""))
    desc = clean(note.get("desc", "") or note.get("content", ""))
    user = note.get("user") or note.get("userInfo") or note.get("user_info") or {}
    author = clean(user.get("nickname", "") if isinstance(user, dict) else "")
    interact = note.get("interactInfo") or note.get("interact_info") or note.get("interactions") or {}
    stats = []
    if isinstance(interact, dict):
        for field in (
            "liked_count",
            "likedCount",
            "collected_count",
            "collectedCount",
            "comment_count",
            "commentCount",
            "share_count",
            "sharedCount",
        ):
            value = interact.get(field)
            if value not in (None, "", 0, "0"):
                stats.append(f"{field}={value}")
    comment_bits = []
    for item in comments[:3]:
        if not isinstance(item, dict):
            continue
        content = clean(item.get("content", ""))
        if content:
            comment_bits.append(content[:120])
    text = " ".join(part for part in [title, desc, author, " ".join(stats), " ".join(comment_bits)] if part)
    summary = summarize_text(text, query)
    if not summary:
        if title:
            summary.append(title)
        if desc:
            summary.append(desc[:280])
    for comment in comment_bits:
        if len(summary) >= 5:
            break
        summary.append(comment)
    if not summary:
        return None
    sections = []
    if author:
        sections.append({"level": "meta", "text": f"author: {author}"})
    if stats:
        sections.append({"level": "meta", "text": ", ".join(stats)})
    if comment_bits:
        sections.append({"level": "comments", "text": " | ".join(comment_bits[:2])})
    links = []
    image_list = note.get("imageList")
    if isinstance(image_list, list):
        for image in image_list[:4]:
            if not isinstance(image, dict):
                continue
            image_url = clean(image.get("urlDefault", "") or image.get("urlPre", ""))
            if image_url.startswith("http"):
                links.append({"label": "image", "url": image_url})
    return {
        "url": url,
        "fetch_mode": "xhs_mcp",
        "title": title or author or "Xiaohongshu Feed",
        "summary": summary[:5],
        "sections": sections[:8],
        "links": links[:10],
        "quality": "high" if len(summary) >= 2 else "medium",
        "applied_rules": ["xhs_mcp_adapter"],
    }


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
    audit = audit_browser_session(url)
    if not audit:
        return None
    browser = audit.get("browser")
    payload = audit.get("extract")
    if not browser or not payload:
        return None
    payload_url = clean(payload.get("url", ""))
    payload_domain = urllib.parse.urlparse(payload_url).netloc.lower() if payload_url else ""
    if payload_domain and root_domain(payload_domain) != root_domain(domain):
        return None
    text = clean(payload.get("text", ""))[:MAX_TEXT]
    if is_low_signal_text(text):
        return None
    title = clean(payload.get("title", ""))
    if looks_like_login_shell(title, text):
        return None
    site = payload.get("site") or infer_site_from_url(payload_url or url)
    if not has_site_specific_result_signal(site, text, query):
        return None
    summary = summarize_browser_text(text, query, title, payload_url or url)
    if not summary or looks_like_generic_site_blurb(title, summary, query):
        return None
    if query_overlap_score(" ".join(summary), query) < 1:
        return None
    return {
        "url": url,
        "fetch_mode": "browser_session",
        "title": title,
        "summary": summary,
        "sections": payload.get("headings", [])[:12],
        "links": payload.get("links", [])[:20],
        "quality": "high" if len(summary) >= 2 else "medium",
        "browser": browser,
        "site": site,
        "auth_state": audit.get("auth_state"),
        "auth_reason": audit.get("auth_reason"),
        "applied_rules": ["browser_session_fallback", "browser_auth_audit"],
    }


def preferred_browsers_for_domain(domain: str) -> List[str]:
    root = root_domain(domain)
    for key, browsers in SITE_BROWSER_PREFERENCES.items():
        if key in domain or key == root:
            return browsers[:]
    return ["safari", "chrome"]


def audit_browser_session(url: str) -> Dict | None:
    parsed = urllib.parse.urlparse(url)
    domain = parsed.netloc.lower()
    for browser in preferred_browsers_for_domain(domain):
        try:
            status = run_json(["python3", str(BRIDGE), "status", browser], timeout=8)
        except Exception:
            continue
        if not status.get("running"):
            continue
        if browser != "safari":
            continue
        original_url = status.get("url", "")
        try:
            audit = run_json(["python3", str(BRIDGE), "audit", browser, url], timeout=18)
        except Exception:
            audit = None
        finally:
            if original_url and original_url != url:
                try:
                    run_json(["python3", str(BRIDGE), "open", browser, original_url], timeout=8)
                except Exception:
                    pass
        if not audit:
            continue
        page_status = audit.get("extract") or audit.get("status") or {}
        auth_state = page_status.get("auth_state") or audit.get("status", {}).get("auth_state")
        if auth_state == "expired":
            continue
        text = clean(page_status.get("text", ""))
        title = clean(page_status.get("title", ""))
        if looks_like_login_shell(title, text):
            continue
        if is_low_signal_text(text):
            continue
        return {
            "browser": browser,
            "auth_state": auth_state or "unknown",
            "auth_reason": page_status.get("auth_reason") or audit.get("status", {}).get("auth_reason"),
            "extract": page_status,
        }
    return None


def run_fallbacks(url: str, query: str, allow_fallback: bool = True, follow_depth: bool = True) -> Dict | None:
    if not allow_fallback:
        return None
    order = fallback_order_for_url(url)
    root = root_domain(urllib.parse.urlparse(url).netloc.lower())
    if root in COMMERCE_ROOTS and is_actionable_non_product_query(query):
        order = tuple(mode for mode in ("external", "domain", "browser") if mode in order)
    for mode in order:
        if mode == "browser":
            if not ENABLE_BROWSER_FALLBACK:
                continue
            browser_result = browser_assisted_extract(url, query)
            if browser_result:
                return browser_result
        elif mode == "domain":
            fallback = extract_domain_search_fallback(url, query, follow_depth=follow_depth)
            if fallback:
                return fallback
        elif mode == "external":
            external = extract_external_discovery_fallback(url, query)
            if external:
                return external
    return None


def infer_site_from_url(url: str) -> str:
    domain = urllib.parse.urlparse(url).netloc.lower()
    root = root_domain(domain)
    if "taobao.com" in root or "tmall.com" in root:
        return "taobao"
    if "jd.com" in root:
        return "jd"
    if "yangkeduo.com" in root:
        return "pinduoduo"
    if "douyin.com" in root:
        return "douyin"
    if "xiaohongshu.com" in root:
        return "xiaohongshu"
    if "bilibili.com" in root:
        return "bilibili"
    return root


def has_site_specific_result_signal(site: str, text: str, query: str) -> bool:
    lowered = clean(text).lower()
    if site in {"taobao", "jd", "pinduoduo"}:
        markers = ["商品", "店铺", "销量", "评价", "价格", "人付款", "￥", "¥", "领券"]
        if "加载中" in text and sum(1 for marker in markers if marker in text) < 2:
            return False
        return sum(1 for marker in markers if marker in text) >= 1
    if site in {"douyin", "xiaohongshu", "bilibili"}:
        return query_overlap_score(text, query) >= 1 or any(marker in text for marker in ["教程", "视频", "笔记", "合集"])
    return True


def summarize_browser_text(text: str, query: str, title: str, url: str) -> List[str]:
    site = infer_site_from_url(url)
    if site == "taobao":
        cards = extract_taobao_browser_results(text, query)
        if cards:
            return cards
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


def extract_taobao_browser_results(text: str, query: str) -> List[str]:
    sample = clean(text)
    if not sample or "人付款" not in sample:
        return []
    matches = list(re.finditer(r"¥\s*\d+(?:\s*\.\s*\d+)?", sample))
    results = []
    seen = set()
    for match in matches[:12]:
        left = max(0, match.start() - 90)
        right = min(len(sample), match.end() + 120)
        chunk = clean(sample[left:right])
        if query_overlap_score(chunk, query) < 1:
            continue
        if "人付款" not in chunk:
            continue
        chunk = re.sub(r"^(?:综合|销量|价格|区间|春上新|品牌|新品|百亿补贴|淘宝秒杀|淘金币抵钱|包邮|开票服务|天猫超市|退货宝|公益宝贝|对公支付|筛选商品)\s*", "", chunk)
        if chunk in seen:
            continue
        seen.add(chunk)
        results.append(chunk[:220])
        if len(results) >= 5:
            break
    return results


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


def extract_jd_item_special(url: str, raw: str, query: str) -> Dict | None:
    parsed = urllib.parse.urlparse(url)
    domain = parsed.netloc.lower()
    if "item.jd.com" not in domain:
        return None
    if not parsed.path.lower().endswith(".html"):
        return None
    title_match = re.search(r"<title>(.*?)</title>", raw, re.I | re.S)
    desc_match = re.search(r'<meta name="description" content="(.*?)"', raw, re.I | re.S)
    title = clean(re.sub(r"<[^>]+>", " ", title_match.group(1))) if title_match else ""
    desc = clean(html.unescape(desc_match.group(1))) if desc_match else ""
    if query_overlap_score(" ".join([title, desc]), query) < 1:
        return None
    summary = []
    if title:
        summary.append(title)
    if desc:
        summary.append(desc[:220])
    if not summary:
        return None
    sections = extract_commerce_detail_sections(summary)
    return {
        "url": url,
        "fetch_mode": "jd_item_meta",
        "title": title or "JD Item",
        "summary": summary[:5],
        "sections": sections,
        "links": [],
        "quality": "high" if len(summary) >= 2 else "medium",
        "applied_rules": ["jd_item_meta"],
    }


def extract_jd_search_special(url: str, raw: str, query: str) -> Dict | None:
    parsed = urllib.parse.urlparse(url)
    domain = parsed.netloc.lower()
    if "search.jd.com" not in domain:
        return None
    title = extract_title_value(raw)
    if any(token in clean(f"{title} {raw[:3000]}").lower() for token in ("京东验证", "请完成验证", "安全验证", "验证中心", "verify")):
        return None
    cards = extract_commerce_search_cards_from_raw(raw, query, ("京东价", "评价", "自营", "到手价", "券", "好评"))
    if not cards:
        return None
    return {
        "url": url,
        "fetch_mode": "jd_search_cards",
        "title": title or "JD Search",
        "summary": cards[:5],
        "sections": [{"level": "results", "text": line[:120]} for line in cards[:5]],
        "links": [],
        "quality": "high" if len(cards) >= 3 else "medium",
        "applied_rules": ["jd_search_cards"],
    }


def extract_meta_value(raw: str, keys: Tuple[str, ...]) -> str:
    for key in keys:
        pattern = re.compile(
            rf'<meta[^>]+(?:name|property)=["\']{re.escape(key)}["\'][^>]+content=["\'](.*?)["\']',
            re.I | re.S,
        )
        match = pattern.search(raw)
        if match:
            value = clean(html.unescape(match.group(1)))
            if value:
                return value
    return ""


def extract_title_value(raw: str) -> str:
    match = re.search(r"<title>(.*?)</title>", raw, re.I | re.S)
    if not match:
        return ""
    return clean(re.sub(r"<[^>]+>", " ", html.unescape(match.group(1))))


def extract_commerce_search_cards_from_raw(raw: str, query: str, required_markers: Tuple[str, ...]) -> List[str]:
    sample = clean(re.sub(r"<[^>]+>", " ", raw))
    if not sample:
        return []
    price_matches = list(re.finditer(r"(?:¥|￥)\s?\d+(?:\.\d+)?", sample))
    if not price_matches:
        return []
    boundaries = [0]
    for left_match, right_match in zip(price_matches, price_matches[1:]):
        boundaries.append((left_match.start() + right_match.start()) // 2)
    boundaries.append(len(sample))
    results: List[str] = []
    seen = set()
    for idx, match in enumerate(price_matches[:18]):
        left = max(0, boundaries[idx] - 40)
        right = boundaries[idx + 1]
        chunk = clean(sample[left:right])
        if not chunk:
            continue
        if required_markers and not any(marker in chunk for marker in required_markers):
            continue
        if query_overlap_score(chunk, query) < 1:
            continue
        line = chunk[:240]
        if line in seen:
            continue
        seen.add(line)
        results.append(line)
        if len(results) >= 5:
            break
    return results


def extract_taobao_special(url: str, raw: str, query: str) -> Dict | None:
    parsed = urllib.parse.urlparse(url)
    root = root_domain(parsed.netloc.lower())
    if root not in {"taobao.com", "tmall.com"}:
        return None
    path = parsed.path.lower()
    title = extract_title_value(raw)
    desc = extract_meta_value(raw, ("description", "og:description", "twitter:description"))
    if any(token in path for token in ("/item", "/detail", "/chanpin/")):
        text = " ".join(part for part in (title, desc) if part)
        if query_overlap_score(text, query) < 1 and not has_commerce_content_signal([text]):
            return None
        summary = extract_commerce_detail_summary(title, desc, raw)
        if not summary:
            return None
        sections = extract_commerce_detail_sections(summary)
        return {
            "url": url,
            "fetch_mode": "taobao_item_meta",
            "title": title or "Taobao Item",
            "summary": summary[:5],
            "sections": sections,
            "links": [],
            "quality": "high" if len(summary) >= 2 else "medium",
            "applied_rules": ["taobao_item_meta"],
        }
    looks_like_search = any(token in path for token in ("/search", "/s")) or "q=" in parsed.query
    if not looks_like_search:
        return None
    cards = extract_commerce_search_cards_from_raw(raw, query, ("人付款", "旗舰店", "天猫", "包邮", "优惠券"))
    if not cards:
        return None
    return {
        "url": url,
        "fetch_mode": "taobao_search_cards",
        "title": title or "Taobao Search",
        "summary": cards[:5],
        "sections": [{"level": "results", "text": line[:120]} for line in cards[:5]],
        "links": [],
        "quality": "high" if len(cards) >= 3 else "medium",
        "applied_rules": ["taobao_search_cards"],
    }


def extract_pinduoduo_special(url: str, raw: str, query: str) -> Dict | None:
    parsed = urllib.parse.urlparse(url)
    root = root_domain(parsed.netloc.lower())
    if root not in {"yangkeduo.com", "pinduoduo.com"}:
        return None
    path = parsed.path.lower()
    title = extract_title_value(raw)
    desc = extract_meta_value(raw, ("description", "og:description", "twitter:description"))
    if any(token in path for token in ("/goods", "/goods.html")):
        text = " ".join(part for part in (title, desc) if part)
        if query_overlap_score(text, query) < 1 and not has_commerce_content_signal([text]):
            return None
        summary = extract_commerce_detail_summary(title, desc, raw)
        if not summary:
            return None
        sections = extract_commerce_detail_sections(summary)
        return {
            "url": url,
            "fetch_mode": "pinduoduo_item_meta",
            "title": title or "Pinduoduo Item",
            "summary": summary[:5],
            "sections": sections,
            "links": [],
            "quality": "high" if len(summary) >= 2 else "medium",
            "applied_rules": ["pinduoduo_item_meta"],
        }
    looks_like_search = any(token in path for token in ("/search", "/search_result")) or "search_key=" in parsed.query
    if not looks_like_search:
        return None
    cards = extract_commerce_search_cards_from_raw(raw, query, ("已拼", "券后", "好评", "官方补贴", "店"))
    if not cards:
        return None
    return {
        "url": url,
        "fetch_mode": "pinduoduo_search_cards",
        "title": title or "Pinduoduo Search",
        "summary": cards[:5],
        "sections": [{"level": "results", "text": line[:120]} for line in cards[:5]],
        "links": [],
        "quality": "high" if len(cards) >= 3 else "medium",
        "applied_rules": ["pinduoduo_search_cards"],
    }


def extract_gitlab_special(url: str, raw: str, query: str) -> Dict | None:
    parsed = urllib.parse.urlparse(url)
    if root_domain(parsed.netloc.lower()) != "gitlab.com":
        return None
    if "/users/sign_in" in parsed.path.lower():
        return None
    title = extract_meta_value(raw, ("og:title", "twitter:title")) or extract_title_value(raw)
    desc = extract_meta_value(raw, ("description", "og:description", "twitter:description"))
    text = " ".join(part for part in (title, desc) if part)
    if not text or query_overlap_score(text, query) < 1:
        return None
    summary = summarize_text(text, query) or [part for part in (title, desc[:220] if desc else "") if part]
    if not summary:
        return None
    sections = [{"level": "meta", "text": desc[:220]}] if desc else []
    return {
        "url": url,
        "fetch_mode": "gitlab_meta",
        "title": title or "GitLab",
        "summary": summary[:5],
        "sections": sections[:6],
        "links": [],
        "quality": "high" if len(summary) >= 2 else "medium",
        "applied_rules": ["gitlab_meta"],
    }


def extract_producthunt_special(url: str, raw: str, query: str) -> Dict | None:
    parsed = urllib.parse.urlparse(url)
    if root_domain(parsed.netloc.lower()) != "producthunt.com":
        return None
    path = parsed.path.lower()
    if not any(token in path for token in ("/posts/", "/products/")):
        return None
    title = extract_meta_value(raw, ("og:title", "twitter:title")) or extract_title_value(raw)
    desc = extract_meta_value(raw, ("description", "og:description", "twitter:description"))
    text = " ".join(part for part in (title, desc) if part)
    if not text or query_overlap_score(text, query) < 1:
        return None
    summary = summarize_text(text, query) or [part for part in (title, desc[:220] if desc else "") if part]
    if not summary:
        return None
    return {
        "url": url,
        "fetch_mode": "producthunt_meta",
        "title": title or "Product Hunt",
        "summary": summary[:5],
        "sections": [{"level": "meta", "text": desc[:220]}] if desc else [],
        "links": [],
        "quality": "high" if len(summary) >= 2 else "medium",
        "applied_rules": ["producthunt_meta"],
    }


def extract_search_page_special(url: str, raw: str, query: str) -> Dict | None:
    parsed = urllib.parse.urlparse(url)
    domain = parsed.netloc.lower()
    path = parsed.path.lower()
    if "item.jd.com" in domain and path.endswith(".html"):
        return None
    query_params = urllib.parse.parse_qs(parsed.query)
    looks_like_search = any(hint in clean(raw[:4000]).lower() for hint in SEARCH_PAGE_HINTS)
    has_search_param = any(key in query_params for key in ("q", "query", "search", "keyword", "wd"))
    if not looks_like_search and not has_search_param and not any(token in path for token in ("/search", "/s", "/results")):
        return None

    def mk(title: str, items: List[Tuple[str, str, str]], mode: str) -> Dict | None:
        cleaned = []
        seen = set()
        commerce_root = root_domain(domain)
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
            if commerce_root in COMMERCE_ROOTS:
                line = format_commerce_line(item_title, item_snippet, item_url)
            elif item_snippet:
                line = f"{item_title}: {item_snippet[:180]}"
            summary.append(line)
            links.append({"text": item_title, "href": item_url})
        quality = "high" if len(cleaned) >= 4 or (commerce_root in COMMERCE_ROOTS and len(cleaned) >= 2) else "medium"
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

    if "bilibili.com" in domain and any(token in path for token in ("/all", "/video", "/bangumi")):
        items = []
        pattern = re.compile(
            r'<a href="(?P<href>//www\.bilibili\.com/video/BV[0-9A-Za-z]+/?)"[^>]*>.*?<img[^>]*alt="(?P<title>[^"]+)"',
            re.S,
        )
        for match in pattern.finditer(raw):
            href = urllib.parse.urljoin("https:", html.unescape(match.group("href")))
            title = clean(match.group("title"))
            if title and href:
                items.append((title, href, ""))
        result = mk("Bilibili Search", items, "bilibili_search_cards")
        if result:
            result["applied_rules"] = ["search_results_extraction", "bilibili_search_cards"]
        return result

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
                item.score = score_result(item, query) + actionable_discovery_bonus(item.url, root)
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
    variants = [variant]
    focus = next((key for key in SITE_QUERY_SUFFIXES if key in domain or key in root), None)
    commerce_root = root or domain
    slug_terms = target_slug_terms(url) if root == "producthunt.com" else []
    slug_value = target_slug_value(url) if root == "producthunt.com" else ""
    target_url = normalized_target_url(url) if root == "producthunt.com" else ""
    if target_url:
        variants.append(f'"{target_url}"')
        variants.append(f'"{target_url}" site:{root or domain}')
    if commerce_root in COMMERCE_ROOTS and not is_actionable_non_product_query(query):
        for suffix in ("商品", "价格", "销量", "购买"):
            variants.append(f"{query} {suffix} site:{root or domain}")
    elif focus:
        for suffix in SITE_QUERY_SUFFIXES.get(focus, []):
            variants.append(f"{query} {suffix} site:{root or domain}")
    if slug_terms:
        variants.append(f"{' '.join(slug_terms)} site:{root or domain}")
        variants.append(f"{query} {' '.join(slug_terms)} site:{root or domain}")
    if slug_value:
        variants.append(f'"{slug_value}" site:{root or domain}')
    collected: List[SearchResult] = []
    seen = set()
    for engine in ("bing", "ddg"):
        for variant_query in variants:
            for item in search_engine(engine, variant_query, domain):
                key = (item.url or item.title).strip().lower()
                if not key or key in seen:
                    continue
                seen.add(key)
                item.score = score_result(item, query)
                item_url_lower = item.url.lower()
                item_url_normalized = normalized_target_url(item.url)
                if target_url and item_url_normalized == target_url:
                    item.score += 80
                if slug_value and slug_value in item_url_lower:
                    item.score += 40
                if slug_terms and query_overlap_score(f"{item.title} {item.snippet} {item.url}", " ".join(slug_terms)) >= min(2, len(slug_terms)):
                    item.score += 18
                if (root or domain) in COMMERCE_ROOTS:
                    item.score += commerce_result_bonus(item.title, item.snippet, query)
                    if is_commerce_item_url(item.url):
                        item.score += 0.55
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
        if commerce_root in COMMERCE_ROOTS and is_generic_commerce_channel_url(item.url):
            continue
        if commerce_root in COMMERCE_ROOTS:
            combined = f"{item.title} {item.snippet}"
            overlap = query_overlap_score(combined, query)
            signals = extract_commerce_signals(combined)
            if looks_like_generic_site_blurb(item.title, [item.snippet], query) and not signals:
                continue
            if is_homepage_like(item.url) and overlap < 1 and not signals:
                continue
            if looks_like_search_or_shell_url(item.url) and not is_commerce_item_url(item.url) and not signals:
                continue
        useful.append(item)
        if len(useful) >= 5:
            break
    if len(useful) < 1:
        return None
    if commerce_root in COMMERCE_ROOTS:
        useful.sort(key=lambda item: (commerce_url_rank(item.url), is_homepage_like(item.url), -url_path_depth(item.url), -item.score))
    else:
        useful.sort(key=lambda item: (is_homepage_like(item.url), -url_path_depth(item.url), -item.score))
    if commerce_root in COMMERCE_ROOTS:
        meaningful = 0
        for item in useful:
            combined = f"{item.title} {item.snippet}"
            path = urllib.parse.urlparse(item.url).path.lower()
            item_like = any(token in path for token in ("/goods", "goods.html", "/item", "item.html", "/detail"))
            if is_homepage_like(item.url) and not item_like:
                continue
            if query_overlap_score(combined, query) >= 1 or item_like:
                meaningful += 1
        if meaningful == 0:
            return None
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
            if query_overlap_score(" ".join(nested_summary), query) < 1:
                continue
            if looks_like_generic_site_blurb(nested.get("title") or item.title, nested_summary, query):
                continue
            if commerce_root in COMMERCE_ROOTS and not has_commerce_content_signal(nested_summary):
                continue
            line = nested_summary[0] if nested_summary else item.title
            summary.append(line)
            links.append({"text": nested.get("title") or item.title, "href": item.url})
            sections.append({"level": "follow", "text": nested.get("title") or item.title})
        if not summary:
            deep_hits = []
        else:
            return {
                "url": url,
                "fetch_mode": "domain_search_deep_fallback",
                "title": clean(root or domain),
                "summary": summary[:5],
                "sections": sections[:10],
                "links": links[:10],
                "quality": "high" if len(summary) >= 2 else "medium",
                "source_query": variant if len(variants) == 1 else variants[:4],
                "applied_rules": list(dict.fromkeys(["quality_gating", "domain_search_fallback", "followup_refinement", "root_domain_relaxation" if root and root != domain else ""])),
            }
    return {
        "url": url,
        "fetch_mode": "domain_search_fallback",
        "title": clean(domain),
        "summary": [
            format_commerce_line(item.title, item.snippet, item.url)
            if commerce_root in COMMERCE_ROOTS else
            (f"{item.title}: {item.snippet[:180]}".strip(": ") if item.snippet else item.title)
            for item in useful
        ],
        "sections": [{"level": "results", "text": item.title} for item in useful],
        "links": [{"text": item.title, "href": item.url} for item in useful],
        "quality": "medium",
        "source_query": variant if len(variants) == 1 else variants[:4],
        "applied_rules": list(dict.fromkeys(["quality_gating", "domain_search_fallback", "root_domain_relaxation" if root and root != domain else ""])),
    }


def extract_external_discovery_fallback(url: str, query: str) -> Dict | None:
    parsed = urllib.parse.urlparse(url)
    domain = parsed.netloc.lower()
    root = root_domain(domain)
    brand = EXTERNAL_DISCOVERY_BRANDS.get(root)
    if not brand:
        return None
    focus = next((key for key in SITE_QUERY_SUFFIXES if key in domain or key in root), None)
    slug_terms = target_slug_terms(url) if root == "producthunt.com" else []
    slug_value = target_slug_value(url) if root == "producthunt.com" else ""
    target_url = normalized_target_url(url) if root == "producthunt.com" else ""
    queries = [f"{query} {brand}"]
    if target_url:
        queries.append(f'"{target_url}"')
        queries.append(f'{query} {brand} "{target_url}"')
    if root in COMMERCE_ROOTS and not is_actionable_non_product_query(query):
        queries.extend(
            f"{query} {brand} {suffix}"
            for suffix in ("商品", "价格", "测评", "推荐")
        )
    elif focus:
        queries.extend(f"{query} {brand} {suffix}" for suffix in SITE_QUERY_SUFFIXES.get(focus, []))
    if slug_terms:
        queries.append(f"{query} {brand} {' '.join(slug_terms)}")
    if slug_value:
        queries.append(f'{query} {brand} "{slug_value}"')
    for suffix in EXTERNAL_DISCOVERY_EXTRA_SUFFIXES.get(root, []):
        queries.append(f"{query} {brand} {suffix}")
    collected: List[SearchResult] = []
    seen = set()
    for engine in ("bing", "ddg"):
        for variant_query in queries:
            for item in search_engine(engine, variant_query, "general"):
                key = (item.url or item.title).strip().lower()
                if not key or key in seen:
                    continue
                seen.add(key)
                item.score = score_result(item, query)
                item_url_lower = item.url.lower()
                item_url_normalized = normalized_target_url(item.url)
                if target_url and item_url_normalized == target_url:
                    item.score += 80
                if slug_value and slug_value in item_url_lower:
                    item.score += 40
                if slug_terms and query_overlap_score(f"{item.title} {item.snippet} {item.url}", " ".join(slug_terms)) >= min(2, len(slug_terms)):
                    item.score += 18
                if root in COMMERCE_ROOTS:
                    item.score += commerce_result_bonus(item.title, item.snippet, query)
                    if has_brand_context(f"{item.title} {item.snippet} {item.url}", brand):
                        item.score += 0.22
                    item.score += commerce_external_source_bonus(item.url, item.title, item.snippet)
                    item.score -= commerce_external_source_penalty(item.url, item.title, item.snippet)
                    item.score -= commerce_external_penalty(item.url)
                collected.append(item)
    collected.sort(key=lambda item: item.score, reverse=True)
    deep_hits = []
    for item in collected[:5]:
        item_domain = urllib.parse.urlparse(item.url).netloc.lower()
        if root_domain(item_domain) != root:
            continue
        if looks_like_search_or_shell_url(item.url):
            continue
        nested = deep_extract(item.url, query, allow_fallback=False)
        if not nested.get("summary"):
            continue
        if nested.get("quality") == "low":
            continue
        if query_overlap_score(" ".join(nested.get("summary") or []), query) < 1:
            continue
        if root in COMMERCE_ROOTS and not has_commerce_content_signal(nested.get("summary") or []):
            continue
        deep_hits.append((item, nested))
        if len(deep_hits) >= 2:
            break
    if deep_hits:
        summary = []
        links = []
        sections = []
        for item, nested in deep_hits:
            nested_summary = nested.get("summary") or []
            if not nested_summary:
                continue
            summary.append(nested_summary[0])
            links.append({"text": nested.get("title") or item.title, "href": item.url})
            sections.append({"level": "follow", "text": nested.get("title") or item.title})
        if summary:
            return {
                "url": url,
                "fetch_mode": "external_discovery_deep_fallback",
                "title": clean(root or domain),
                "summary": summary[:5],
                "sections": sections[:10],
                "links": links[:10],
                "quality": "high" if len(summary) >= 2 else "medium",
                "source_query": queries[:4],
                "applied_rules": ["quality_gating", "external_discovery_fallback", "followup_refinement"],
            }
    useful = []
    seen_titles = set()
    domain_counts: Dict[str, int] = {}
    for item in collected:
        if root in COMMERCE_ROOTS:
            combined = f"{item.title} {item.snippet} {item.url}"
            item_root = root_domain(urllib.parse.urlparse(item.url).netloc.lower())
            title_key = clean(item.title).lower()
            if not has_brand_context(combined, brand) and not has_commerce_content_signal([combined]):
                continue
            if query_overlap_score(combined, query) < 1 and not has_commerce_content_signal([combined]):
                continue
            if item_root != root and looks_like_search_or_shell_url(item.url) and not has_commerce_content_signal([combined]):
                continue
            if title_key and title_key in seen_titles:
                continue
            if item_root:
                limit = 2 if item_root == root else 1
                if domain_counts.get(item_root, 0) >= limit:
                    continue
                domain_counts[item_root] = domain_counts.get(item_root, 0) + 1
            if title_key:
                seen_titles.add(title_key)
        useful.append(item)
        if len(useful) >= 5:
            break
    if not useful:
        return None
    if root in COMMERCE_ROOTS:
        useful.sort(
            key=lambda item: (
                -commerce_external_rank(item.url, item.title, item.snippet),
                looks_like_search_or_shell_url(item.url),
                -score_result(item, query),
            )
        )
    return {
        "url": url,
        "fetch_mode": "external_discovery_fallback",
        "title": clean(root or domain),
        "summary": [
            format_commerce_line(item.title, item.snippet, item.url)
            if root in COMMERCE_ROOTS else
            (f"{item.title}: {item.snippet[:180]}".strip(": ") if item.snippet else item.title)
            for item in useful
        ],
        "sections": [{"level": "results", "text": item.title} for item in useful],
        "links": [{"text": item.title, "href": item.url} for item in useful],
        "quality": "medium",
        "source_query": queries[:4],
        "applied_rules": ["quality_gating", "external_discovery_fallback"],
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
    root = root_domain(domain)
    if item.site_focus in domain:
        score += 18
    if "github.com" in domain:
        score += 12
    if "clawhub.com" in domain:
        score += 16
    if any(domain.endswith(site) for site in ("zhihu.com", "xiaohongshu.com", "douyin.com", "reddit.com", "producthunt.com")):
        score += 8
    if item.snippet:
        score += 3
    if any(token in hay for token in ("readme", "install", "教程", "指南", "文档", "skill", "plugin")):
        score += 4
    if root in COMMERCE_ROOTS:
        path = urllib.parse.urlparse(item.url).path.lower()
        if any(token in path for token in ("/goods", "goods.html", "/item", "item.html", "/detail")):
            score += 8
        if is_homepage_like(item.url):
            score -= 8
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


def looks_like_login_shell(title: str, text: str) -> bool:
    sample = f"{clean(title)} {clean(text)[:800]}".lower()
    markers = [
        "登录页面",
        "欢迎登录",
        "扫码登录",
        "密码登录",
        "短信登录",
        "立即注册",
        "forgot password",
    ]
    hits = sum(1 for marker in markers if marker.lower() in sample)
    return hits >= 2


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
    special = (
        extract_github_special(url, query)
        or extract_reddit_special(url, query)
        or extract_twitter_oembed_special(url, query)
        or extract_xhs_mcp_special(url, query)
        or extract_mediacrawler_douyin_profile_special(url, query)
        or extract_mediacrawler_douyin_special(url, query)
        or extract_mediacrawler_tieba_special(url, query)
        or extract_douyin_project_special(url, query)
        or extract_gallery_dl_special(url, query)
        or extract_yt_dlp_special(url, query)
    )
    if special:
        return special
    domain = urllib.parse.urlparse(url).netloc.lower()
    raw, mode = fetch_with_reader_fallback(url)
    if not raw:
        fallback_result = run_fallbacks(url, query, allow_fallback=allow_fallback)
        if fallback_result:
            return fallback_result
        return with_rules({"url": url, "fetch_mode": mode, "title": "", "summary": [], "sections": [], "links": [], "quality": "low"}, "unavailable")
    site_special = (
        extract_taobao_special(url, raw, query)
        or extract_pinduoduo_special(url, raw, query)
        or extract_jd_search_special(url, raw, query)
        or extract_gitlab_special(url, raw, query)
        or extract_producthunt_special(url, raw, query)
    )
    if site_special:
        return site_special
    jd_special = extract_jd_item_special(url, raw, query)
    if jd_special:
        return jd_special
    search_special = extract_search_page_special(url, raw, query)
    if search_special:
        return search_special
    if looks_like_known_error_shell("", raw, url):
        fallback_result = run_fallbacks(url, query, allow_fallback=allow_fallback)
        if fallback_result:
            return with_rules(fallback_result, "known_error_shell", *adapter_blocker_rules(url))
    if is_low_signal_text(raw):
        fallback_result = run_fallbacks(url, query, allow_fallback=allow_fallback)
        if fallback_result:
            return fallback_result
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
            fallback_result = run_fallbacks(url, query, allow_fallback=allow_fallback)
            if fallback_result:
                return fallback_result
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
    if looks_like_known_error_shell(parser.title, raw, url):
        fallback_result = run_fallbacks(url, query, allow_fallback=allow_fallback)
        if fallback_result:
            return with_rules(fallback_result, "known_error_shell", *adapter_blocker_rules(url))
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
        fallback_result = run_fallbacks(url, query, allow_fallback=allow_fallback)
        if fallback_result:
            if looks_like_known_error_shell(parser.title, raw, url):
                return with_rules(fallback_result, "known_error_shell", *adapter_blocker_rules(url))
            return fallback_result
    quality = effective_quality(summary, summary_source, mode, quality)
    if quality == "low" and allow_fallback:
        fallback_result = run_fallbacks(url, query, allow_fallback=True, follow_depth=False)
        if fallback_result:
            return fallback_result
    if quality == "low" and ENABLE_BROWSER_FALLBACK and domain in BROWSER_ASSIST_DOMAINS:
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
                    if root_domain(urllib.parse.urlparse(item.url).netloc.lower()) in COMMERCE_ROOTS:
                        item.score += commerce_result_bonus(item.title, item.snippet, query)
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
