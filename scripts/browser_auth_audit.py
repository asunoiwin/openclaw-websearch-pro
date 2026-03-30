#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
BRIDGE = HERE / "browser_session_bridge.py"


def run_json(args: list[str], timeout: int = 20) -> dict:
    proc = subprocess.run(args, text=True, capture_output=True, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "command_failed")
    return json.loads(proc.stdout)


def main() -> int:
    if len(sys.argv) < 2:
        print(json.dumps({"error": "usage: browser_auth_audit.py <sites.json>"}, ensure_ascii=False))
        return 1
    site_file = Path(sys.argv[1]).expanduser().resolve()
    sites = json.loads(site_file.read_text(encoding="utf-8"))
    results = []
    for item in sites:
        browser = item.get("browser", "safari")
        url = item["url"]
        payload = {
            "name": item.get("name") or url,
            "browser": browser,
            "url": url,
        }
        try:
            payload["audit"] = run_json(["python3", str(BRIDGE), "audit", browser, url], timeout=25)
        except Exception as exc:
            payload["error"] = str(exc)
        results.append(payload)
    print(json.dumps({"sites": results}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
