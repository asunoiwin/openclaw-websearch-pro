#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.parse


def clean(text: str) -> str:
    return " ".join((text or "").split()).strip()


def root_domain(value: str) -> str:
    host = clean(value).lower()
    if not host:
        return ""
    parsed = urllib.parse.urlparse(host)
    if parsed.netloc:
        host = parsed.netloc.lower()
    parts = [part for part in host.split(".") if part]
    if len(parts) <= 2:
        return host
    return ".".join(parts[-2:])


def infer_site_key(url: str) -> str:
    root = root_domain(url)
    if "taobao.com" in root or "tmall.com" in root:
        return "taobao"
    if "jd.com" in root:
        return "jd"
    if "zhihu.com" in root:
        return "zhihu"
    if "xiaohongshu.com" in root:
        return "xiaohongshu"
    if "douyin.com" in root:
        return "douyin"
    if "weibo.com" in root:
        return "weibo"
    if root == "x.com":
        return "x"
    if "gitlab.com" in root:
        return "gitlab"
    if "producthunt.com" in root:
        return "producthunt"
    if "reddit.com" in root:
        return "reddit"
    if "yangkeduo.com" in root:
        return "pinduoduo"
    if "bilibili.com" in root:
        return "bilibili"
    return root


def detect_auth_state(url: str, title: str, text: str = "") -> dict:
    site = infer_site_key(url)
    title_l = clean(title).lower()
    text_l = clean(text).lower()
    url_l = clean(url).lower()

    def ok(reason: str) -> dict:
        return {"site": site, "auth_state": "authenticated", "auth_reason": reason}

    def expired(reason: str) -> dict:
        return {"site": site, "auth_state": "expired", "auth_reason": reason}

    def unknown(reason: str) -> dict:
        return {"site": site, "auth_state": "unknown", "auth_reason": reason}

    if site == "gitlab":
        if "/users/sign_in" in url_l or "登录" in title or "sign in" in title_l:
            return expired("gitlab_login_page")
        return ok("gitlab_search_page")
    if site == "jd":
        if "passport.jd.com" in url_l or "欢迎登录" in title or "登录页面" in text:
            return expired("jd_login_shell")
        if "商品搜索" in title or "plus" in text_l or "购物车" in text:
            return ok("jd_search_page")
        return unknown("jd_unclassified")
    if site == "taobao":
        if "login.taobao.com" in url_l or "扫码登录" in text or "密码登录" in text:
            return expired("taobao_login_shell")
        if "淘宝搜索" in title or "人付款" in text or "店铺" in text:
            return ok("taobao_search_page")
        return unknown("taobao_unclassified")
    if site == "zhihu":
        if "登录" in title and "search" not in url_l:
            return expired("zhihu_login_shell")
        if "搜索结果" in title or "回答" in text or "浏览" in text:
            return ok("zhihu_search_page")
        return unknown("zhihu_unclassified")
    if site == "weibo":
        if "登录" in title or "扫码登录" in text:
            return expired("weibo_login_shell")
        if "微博搜索" in title or "/weibo/" in url_l:
            return ok("weibo_search_page")
        return unknown("weibo_unclassified")
    if site == "x":
        if "sign in" in title_l or "/i/flow/login" in url_l:
            return expired("x_login_shell")
        if "搜索 / x" in title or "/search?" in url_l:
            return ok("x_search_page")
        return unknown("x_unclassified")
    if site == "producthunt":
        if "/search" in url_l and "product hunt" in title_l:
            return ok("producthunt_search_page")
        return unknown("producthunt_unclassified")
    if site == "reddit":
        if "/search/" in url_l or "/search?" in url_l:
            return ok("reddit_search_page")
        return unknown("reddit_unclassified")
    if site == "pinduoduo":
        if "search_result" in url_l:
            return ok("pinduoduo_search_page")
        return unknown("pinduoduo_unclassified")
    if site == "bilibili":
        if "哔哩哔哩" in title or "/all?keyword=" in url_l:
            return ok("bilibili_search_page")
        return unknown("bilibili_unclassified")
    if site == "xiaohongshu":
        if "搜索" in title and "小红书" in title:
            return ok("xiaohongshu_search_page")
        if "登录" in text and "创作中心" in text:
            return unknown("xiaohongshu_shell_page")
        return unknown("xiaohongshu_unclassified")
    if site == "douyin":
        if "/search/" in url_l and "抖音" in text:
            return ok("douyin_search_page")
        return unknown("douyin_unclassified")
    return unknown("generic")


def run_osascript(script: str) -> str:
    proc = subprocess.run(
        ["osascript", "-"],
        input=script,
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "osascript failed")
    return proc.stdout.strip()


def chrome_status() -> dict:
    script = r'''
tell application "Google Chrome"
  if it is running then
    set wcount to count of windows
    if wcount > 0 then
      set tabTitle to title of active tab of front window
      set tabURL to URL of active tab of front window
      return tabTitle & linefeed & tabURL
    else
      return linefeed
    end if
  else
    error "chrome_not_running"
  end if
end tell
'''
    try:
        output = run_osascript(script)
        lines = output.splitlines()
        payload = {
            "browser": "chrome",
            "running": True,
            "title": lines[0] if lines else "",
            "url": lines[1] if len(lines) > 1 else "",
            "dom_extract": False,
            "reason": "chrome_applescript_js_disabled_or_unavailable",
        }
        payload.update(detect_auth_state(payload["url"], payload["title"]))
        return payload
    except Exception as exc:
        return {"browser": "chrome", "running": False, "error": str(exc)}


def safari_status() -> dict:
    script = r'''
tell application "Safari"
  if it is running then
    if (count of windows) > 0 then
      set tabTitle to name of front document
      set tabURL to URL of front document
      return tabTitle & linefeed & tabURL
    else
      return linefeed
    end if
  else
    error "safari_not_running"
  end if
end tell
'''
    try:
        output = run_osascript(script)
        lines = output.splitlines()
        payload = {
            "browser": "safari",
            "running": True,
            "title": lines[0] if lines else "",
            "url": lines[1] if len(lines) > 1 else "",
            "dom_extract": True,
        }
        payload.update(detect_auth_state(payload["url"], payload["title"]))
        return payload
    except Exception as exc:
        return {"browser": "safari", "running": False, "error": str(exc)}


def safari_extract() -> dict:
    js = (
        "JSON.stringify((function(){"
        "var bodyText=document.body&&document.body.innerText?document.body.innerText:'';"
        "bodyText=bodyText.split('\\n').join(' ').replace(/\\s+/g,' ').trim().slice(0,4000);"
        "var headings=Array.from(document.querySelectorAll('h1,h2,h3')).slice(0,12).map(function(el){return {tag:el.tagName.toLowerCase(),text:(el.innerText||'').trim()};});"
        "var links=Array.from(document.querySelectorAll('a[href]')).slice(0,20).map(function(a){return {text:(a.innerText||'').trim(),href:a.href};});"
        "return {title:document.title||'',url:location.href,text:bodyText,headings:headings,links:links};"
        "})())"
    )
    script = f'''
tell application "Safari"
  if it is not running then error "safari_not_running"
  if (count of windows) = 0 then error "safari_no_window"
  tell front document
    set payload to do JavaScript {json.dumps(js)}
    return payload
  end tell
end tell
'''
    output = run_osascript(script)
    payload = json.loads(output)
    payload.update(detect_auth_state(payload.get("url", ""), payload.get("title", ""), payload.get("text", "")))
    return payload


def browser_status(which: str) -> dict:
    if which == "chrome":
        return chrome_status()
    if which == "safari":
        return safari_status()
    chrome = chrome_status()
    if chrome.get("running"):
        return chrome
    return safari_status()


def all_browser_status() -> dict:
    return {
        "chrome": chrome_status(),
        "safari": safari_status(),
    }


def open_url(which: str, url: str) -> dict:
    if which == "chrome":
        script = f'''
tell application "Google Chrome"
  activate
  if (count of windows) = 0 then make new window
  tell active tab of front window to set URL to "{url}"
end tell
'''
    else:
        script = f'''
tell application "Safari"
  activate
  set newDoc to make new document
  set URL of newDoc to "{url}"
end tell
'''
    run_osascript(script)
    return {"ok": True, "browser": which, "url": url}


def close_front(which: str) -> dict:
    if which == "chrome":
        script = r'''
tell application "Google Chrome"
  if it is not running then return "chrome_not_running"
  if (count of windows) = 0 then return "chrome_no_window"
  close front window
  return "ok"
end tell
'''
    else:
        script = r'''
tell application "Safari"
  if it is not running then return "safari_not_running"
  if (count of windows) = 0 then return "safari_no_window"
  if (count of documents) = 0 then return "safari_no_document"
  close front document
  return "ok"
end tell
'''
    return {"ok": run_osascript(script) == "ok", "browser": which}


def wait_for_page(which: str, url: str, timeout: float = 8.0) -> dict:
    target_root = root_domain(url)
    deadline = time.time() + timeout
    last = {}
    while time.time() < deadline:
        status = browser_status(which)
        last = status
        current_root = root_domain(status.get("url", ""))
        if current_root and current_root == target_root:
            return status
        time.sleep(0.35)
    return last


def audit_page(which: str, url: str) -> dict:
    target_root = root_domain(url)
    open_url(which, url)
    status = wait_for_page(which, url)
    if root_domain(status.get("url", "")) != target_root:
        open_url(which, url)
        status = wait_for_page(which, url, timeout=10.0)
    payload = {
        "browser": which,
        "requested_url": url,
        "status": status,
    }
    if which == "safari":
        if root_domain(status.get("url", "")) == target_root:
            try:
                payload["extract"] = safari_extract()
            except Exception as exc:
                payload["extract_error"] = str(exc)
        else:
            payload["extract_error"] = "target_page_not_reached"
    try:
        payload["closed_temp_page"] = close_front(which)
    except Exception as exc:
        payload["close_error"] = str(exc)
    return payload


def main() -> int:
    if len(sys.argv) < 2:
        print(json.dumps({"error": "usage: browser_session_bridge.py <status|status-all|extract|open|close-front|search|audit> [args...]"}, ensure_ascii=False))
        return 1

    cmd = sys.argv[1]
    browser = sys.argv[2] if len(sys.argv) > 2 else "auto"

    if cmd == "status":
        print(json.dumps(browser_status(browser), ensure_ascii=False))
        return 0

    if cmd == "status-all":
        print(json.dumps(all_browser_status(), ensure_ascii=False))
        return 0

    if cmd == "extract":
        if browser == "auto":
            browser = "safari"
        if browser != "safari":
            print(json.dumps({"browser": browser, "error": "full_dom_extract_supported_in_safari_only"}, ensure_ascii=False))
            return 0
        print(json.dumps(safari_extract(), ensure_ascii=False))
        return 0

    if cmd == "open":
        if len(sys.argv) < 4:
            print(json.dumps({"error": "usage: browser_session_bridge.py open <browser> <url>"}, ensure_ascii=False))
            return 1
        print(json.dumps(open_url(browser, sys.argv[3]), ensure_ascii=False))
        return 0

    if cmd == "close-front":
        if browser == "auto":
            browser = "safari"
        print(json.dumps(close_front(browser), ensure_ascii=False))
        return 0

    if cmd == "audit":
        if len(sys.argv) < 4:
            print(json.dumps({"error": "usage: browser_session_bridge.py audit <browser> <url>"}, ensure_ascii=False))
            return 1
        print(json.dumps(audit_page(browser, sys.argv[3]), ensure_ascii=False))
        return 0

    if cmd == "search":
        if len(sys.argv) < 5:
            print(json.dumps({"error": "usage: browser_session_bridge.py search <browser> <engine> <query>"}, ensure_ascii=False))
            return 1
        engine = sys.argv[3]
        query = urllib.parse.quote(sys.argv[4])
        base = {
            "google": f"https://www.google.com/search?q={query}",
            "bing": f"https://www.bing.com/search?q={query}",
            "baidu": f"https://www.baidu.com/s?wd={query}",
        }.get(engine)
        if not base:
            print(json.dumps({"error": f"unsupported_engine:{engine}"}, ensure_ascii=False))
            return 1
        print(json.dumps(open_url(browser, base), ensure_ascii=False))
        return 0

    print(json.dumps({"error": f"unknown_command:{cmd}"}, ensure_ascii=False))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
