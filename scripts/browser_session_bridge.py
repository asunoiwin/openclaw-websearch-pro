#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import urllib.parse


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
        return {
            "browser": "chrome",
            "running": True,
            "title": lines[0] if lines else "",
            "url": lines[1] if len(lines) > 1 else "",
            "dom_extract": False,
            "reason": "chrome_applescript_js_disabled_or_unavailable",
        }
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
        return {
            "browser": "safari",
            "running": True,
            "title": lines[0] if lines else "",
            "url": lines[1] if len(lines) > 1 else "",
            "dom_extract": True,
        }
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
    return json.loads(output)


def browser_status(which: str) -> dict:
    if which == "chrome":
        return chrome_status()
    if which == "safari":
        return safari_status()
    chrome = chrome_status()
    if chrome.get("running"):
        return chrome
    return safari_status()


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
  if (count of windows) = 0 then make new document
  set URL of front document to "{url}"
end tell
'''
    run_osascript(script)
    return {"ok": True, "browser": which, "url": url}


def main() -> int:
    if len(sys.argv) < 2:
        print(json.dumps({"error": "usage: browser_session_bridge.py <status|extract|open|search> [args...]"}, ensure_ascii=False))
        return 1

    cmd = sys.argv[1]
    browser = sys.argv[2] if len(sys.argv) > 2 else "auto"

    if cmd == "status":
        print(json.dumps(browser_status(browser), ensure_ascii=False))
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
