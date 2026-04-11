#!/usr/bin/env python3
from __future__ import annotations

import base64
import importlib.util
import json
import os
import sys
import urllib.request
from pathlib import Path
from typing import Dict, List


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SEARCH_SCRIPT = HERE / "search_orchestrator.py"
BRIDGE = HERE / "browser_session_bridge.py"
WORKSPACE = Path.home() / ".openclaw" / "workspace"
QR_DIR = WORKSPACE / "auth-qrcodes"


spec = importlib.util.spec_from_file_location("websearch_pro_search_orchestrator", SEARCH_SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = module
spec.loader.exec_module(module)


SITE_CONFIG: Dict[str, Dict] = {
    "xiaohongshu": {
        "aliases": ["xhs", "小红书", "rednote"],
        "mode": "qr",
        "browser": "safari",
        "login_url": "https://www.xiaohongshu.com/explore",
        "status_url": "https://www.xiaohongshu.com/explore",
        "cookie_file": str(Path("/tmp/xhs_mcp/cookies.json")),
    },
    "douyin": {
        "aliases": ["抖音"],
        "mode": "browser",
        "browser": "safari",
        "login_url": "https://www.douyin.com/",
        "status_url": "https://www.douyin.com/",
        "cookie_file": str(module.DOUYIN_COOKIE_FILE),
        "profile_dir": str(module.MEDIACRAWLER_PROJECT / "browser_data" / (module.DOUYIN_MEDIACRAWLER_PROFILE_TEMPLATE % "dy")),
    },
    "zhihu": {
        "aliases": ["知乎"],
        "mode": "browser",
        "browser": "safari",
        "login_url": "https://www.zhihu.com/signin?next=%2F",
        "status_url": "https://www.zhihu.com/",
    },
    "csdn": {
        "aliases": ["博客园csdn"],
        "mode": "browser",
        "browser": "safari",
        "login_url": "https://passport.csdn.net/login?code=public",
        "status_url": "https://www.csdn.net/",
    },
    "tieba": {
        "aliases": ["贴吧", "百度贴吧"],
        "mode": "browser",
        "browser": "safari",
        "login_url": "https://tieba.baidu.com/",
        "status_url": "https://tieba.baidu.com/p/9219395000",
        "cookie_file": str(module.TIEBA_COOKIE_FILE),
    },
    "wenku": {
        "aliases": ["文库", "百度文库", "wenku"],
        "mode": "browser",
        "browser": "safari",
        "login_url": "https://wenku.baidu.com/",
        "status_url": "https://wenku.baidu.com/view/4baf6c42be1e650e52ea551810a6f524ccbfcbb7.html",
    },
    "weibo": {
        "aliases": ["微博"],
        "mode": "browser",
        "browser": "safari",
        "login_url": "https://weibo.com/login.php",
        "status_url": "https://weibo.com/",
    },
    "x": {
        "aliases": ["twitter", "x/twitter"],
        "mode": "browser",
        "browser": "safari",
        "login_url": "https://x.com/i/flow/login",
        "status_url": "https://x.com/",
    },
}


def clean(text: str) -> str:
    return module.clean(text)


def normalize_site(value: str) -> str:
    value_l = clean(value).lower()
    for site, config in SITE_CONFIG.items():
        aliases = [site, *config.get("aliases", [])]
        if any(value_l == clean(alias).lower() for alias in aliases):
            return site
    return value_l


def file_meta(path_value: str) -> Dict | None:
    if not path_value:
        return None
    path = Path(path_value).expanduser()
    exists = path.exists()
    payload = {
        "path": str(path),
        "exists": exists,
    }
    if exists:
        stat = path.stat()
        payload["size"] = stat.st_size
        payload["modified_at"] = stat.st_mtime
    return payload


def run_json(args: List[str], timeout: int = 25) -> Dict:
    return module.run_json(args, timeout=timeout)


def browser_status(site: str) -> Dict:
    config = SITE_CONFIG[site]
    browser = config["browser"]
    status_url = config["status_url"]
    payload = {
        "site": site,
        "mode": "browser",
        "browser": browser,
        "login_url": config["login_url"],
        "status_url": status_url,
    }
    try:
        audit = run_json(["python3", str(BRIDGE), "audit", browser, status_url], timeout=25)
    except Exception as exc:
        payload["auth_state"] = "unknown"
        payload["auth_reason"] = "audit_failed"
        payload["error"] = str(exc)
        return payload
    extract = audit.get("extract") or {}
    status = audit.get("status") or {}
    payload["auth_state"] = extract.get("auth_state") or status.get("auth_state") or "unknown"
    payload["auth_reason"] = extract.get("auth_reason") or status.get("auth_reason") or "unknown"
    payload["current_url"] = extract.get("url") or ""
    payload["title"] = extract.get("title") or ""
    payload["needs_login"] = payload["auth_state"] != "authenticated"
    cookie_meta = file_meta(config["cookie_file"]) if config.get("cookie_file") else None
    profile_meta = file_meta(config["profile_dir"]) if config.get("profile_dir") else None
    if cookie_meta:
        payload["cookie_file"] = cookie_meta
    if profile_meta:
        payload["profile_dir"] = profile_meta
    if site == "douyin" and payload["auth_state"] != "authenticated":
        has_artifact = bool((cookie_meta and cookie_meta.get("exists")) or (profile_meta and profile_meta.get("exists")))
        if has_artifact:
            payload["auth_state"] = "configured"
            payload["auth_reason"] = "douyin_profile_or_cookie_present"
            payload["needs_login"] = False
    return payload


def xhs_status() -> Dict:
    payload = {
        "site": "xiaohongshu",
        "mode": "qr",
        "login_url": SITE_CONFIG["xiaohongshu"]["login_url"],
    }
    service_ready = module.ensure_xhs_service_started(wait_seconds=6)
    payload["service_ready"] = service_ready
    payload["cookie_file"] = file_meta(SITE_CONFIG["xiaohongshu"]["cookie_file"])
    if not service_ready:
        payload["auth_state"] = "unknown"
        payload["auth_reason"] = "xhs_service_unavailable"
        return payload
    login_state = module.xhs_login_status()
    if login_state is True:
        payload["auth_state"] = "authenticated"
        payload["auth_reason"] = "xhs_logged_in"
        payload["needs_login"] = False
    elif login_state is False:
        payload["auth_state"] = "expired"
        payload["auth_reason"] = "xhs_login_required"
        payload["needs_login"] = True
    else:
        payload["auth_state"] = "unknown"
        payload["auth_reason"] = "xhs_status_unknown"
    return payload


def fetch_xhs_qrcode() -> Dict:
    payload = xhs_status()
    if payload.get("auth_state") == "authenticated":
        return payload | {"action": "already_authenticated"}
    if not payload.get("service_ready"):
        return payload | {"action": "service_unavailable"}
    raw = module.local_http_get(f"{module.XHS_BASE_URL}/api/v1/login/qrcode", timeout=10)
    data = json.loads(raw).get("data") or {}
    img = clean(str(data.get("img", "")))
    if not img.startswith("data:image/png;base64,"):
        return payload | {"action": "qr_unavailable"}
    QR_DIR.mkdir(parents=True, exist_ok=True)
    out = QR_DIR / "xhs-login-qrcode.png"
    out.write_bytes(base64.b64decode(img.split(",", 1)[1]))
    return payload | {
        "action": "scan_qr",
        "qr_image_path": str(out),
        "timeout_seconds": int(str(data.get("timeout", "300")) or "300"),
    }


def open_login(site: str) -> Dict:
    config = SITE_CONFIG[site]
    browser = config["browser"]
    login_url = config["login_url"]
    try:
        result = run_json(["python3", str(BRIDGE), "open", browser, login_url], timeout=12)
    except Exception as exc:
        return {
            "site": site,
            "action": "open_login_page",
            "browser": browser,
            "login_url": login_url,
            "ok": False,
            "error": str(exc),
        }
    return {
        "site": site,
        "action": "open_login_page",
        "browser": browser,
        "login_url": login_url,
        "ok": bool(result.get("ok")),
    }


def status_for_site(site: str) -> Dict:
    if site == "xiaohongshu":
        return xhs_status()
    if site not in SITE_CONFIG:
        return {"site": site, "auth_state": "unknown", "auth_reason": "unsupported_site"}
    return browser_status(site)


def main() -> int:
    if len(sys.argv) < 3:
        print(json.dumps({"error": "usage: auth_workflow.py <sites|status|login> <json_payload>"}, ensure_ascii=False))
        return 1
    command = sys.argv[1]
    payload = json.loads(sys.argv[2])
    if command == "sites":
        print(json.dumps({"sites": sorted(SITE_CONFIG.keys())}, ensure_ascii=False))
        return 0
    if command == "status":
        sites = [normalize_site(site) for site in payload.get("sites", [])]
        results = [status_for_site(site) for site in sites if site]
        print(json.dumps({"sites": results}, ensure_ascii=False))
        return 0
    if command == "login":
        site = normalize_site(payload.get("site", ""))
        if site not in SITE_CONFIG:
            print(json.dumps({"error": f"unsupported_site:{site}"}, ensure_ascii=False))
            return 1
        if site == "xiaohongshu":
            print(json.dumps(fetch_xhs_qrcode(), ensure_ascii=False))
            return 0
        print(json.dumps(open_login(site), ensure_ascii=False))
        return 0
    print(json.dumps({"error": f"unknown_command:{command}"}, ensure_ascii=False))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
