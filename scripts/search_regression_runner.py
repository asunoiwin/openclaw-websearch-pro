#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
ORCHESTRATOR = ROOT / "scripts" / "search_orchestrator.py"


def run_case(case: dict, timeout: int) -> dict:
    start = time.time()
    try:
        proc = subprocess.run(
            [
                "python3",
                str(ORCHESTRATOR),
                "extract",
                json.dumps({"url": case["url"], "query": case["query"]}, ensure_ascii=False),
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        duration_ms = int((time.time() - start) * 1000)
        try:
            payload = json.loads(proc.stdout)
        except Exception:
            payload = {
                "quality": "error",
                "fetch_mode": "error",
                "title": proc.stdout[:120],
                "summary": [],
                "links": [],
            }
    except subprocess.TimeoutExpired:
        duration_ms = int((time.time() - start) * 1000)
        payload = {
            "quality": "error",
            "fetch_mode": "timeout",
            "title": "",
            "summary": [],
            "links": [],
        }
    payload["site"] = case["site"]
    payload["input_url"] = case["url"]
    payload["query"] = case["query"]
    payload["duration_ms"] = duration_ms
    return payload


def summarize(results: list[dict]) -> dict:
    counts = {"high": 0, "medium": 0, "low": 0, "error": 0}
    for item in results:
        quality = item.get("quality", "error")
        counts[quality] = counts.get(quality, 0) + 1
    usable = counts.get("high", 0) + counts.get("medium", 0)
    avg_duration = int(sum(item.get("duration_ms", 0) for item in results) / max(len(results), 1))
    return {
        "total": len(results),
        "high": counts.get("high", 0),
        "medium": counts.get("medium", 0),
        "low": counts.get("low", 0),
        "error": counts.get("error", 0),
        "usable": usable,
        "avg_duration_ms": avg_duration,
    }


def to_markdown(title: str, summary: dict, results: list[dict]) -> str:
    lines = [
        f"# {title}",
        "",
        "## Summary",
        "",
        f"- total: {summary['total']}",
        f"- high: {summary['high']}",
        f"- medium: {summary['medium']}",
        f"- low: {summary['low']}",
        f"- error: {summary['error']}",
        f"- usable: {summary['usable']}",
        f"- avg_duration_ms: {summary['avg_duration_ms']}",
        "",
        "## Results",
        "",
        "| Site | Quality | Mode | Duration(ms) | Title |",
        "| --- | --- | --- | ---: | --- |",
    ]
    for item in results:
        lines.append(
            f"| {item.get('site','')} | {item.get('quality','')} | {item.get('fetch_mode','')} | {item.get('duration_ms',0)} | {str(item.get('title','')).replace('|','/')} |"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    if len(sys.argv) < 4:
        print(json.dumps({"error": "usage: search_regression_runner.py <cases.json> <report.json> <report.md> [timeout_seconds]"}))
        return 1
    case_file = Path(sys.argv[1])
    report_json = Path(sys.argv[2])
    report_md = Path(sys.argv[3])
    timeout = int(sys.argv[4]) if len(sys.argv) > 4 else 25
    cases = json.loads(case_file.read_text())
    results: list[dict] = []
    for case in cases:
        results.append(run_case(case, timeout))
        summary = summarize(results)
        payload = {
            "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "source": str(case_file),
            "timeoutSeconds": timeout,
            "summary": summary,
            "results": results,
        }
        report_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
        report_md.write_text(to_markdown(case_file.stem, summary, results))
    summary = summarize(results)
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
