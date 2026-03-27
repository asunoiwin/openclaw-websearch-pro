#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import re
import sys
import urllib.request
from pathlib import Path
from html.parser import HTMLParser


class SimpleExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self.current_link = None
        self.links = []
        self.sections = []
        self.bullets = []
        self.paragraphs = []
        self._buffer = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            for key, value in attrs:
                if key == "href":
                    self.current_link = value
                    break

    def handle_endtag(self, tag):
        text = clean_text("".join(self._buffer))
        if tag == "title" and text:
            self.title = text
        elif tag in {"h1", "h2", "h3"} and text:
            self.sections.append({"heading": text, "level": tag})
        elif tag in {"p", "article", "section"} and text:
            self.paragraphs.append(text)
        elif tag == "li" and text:
            self.bullets.append(text)
        elif tag == "a" and text and self.current_link:
            self.links.append({"text": text, "href": self.current_link})
            self.current_link = None
        self._buffer = []

    def handle_data(self, data):
        if data:
            self._buffer.append(data)


def clean_text(text: str) -> str:
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def strip_noise(text: str) -> str:
    text = re.sub(r"<script\b.*?</script>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<style\b.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.S)
    return text


def load_source(target: str) -> tuple[str, str]:
    if re.match(r"^https?://", target):
        req = urllib.request.Request(target, headers={"User-Agent": "OpenClaw Distill/1.0"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
        return raw, "url"
    raw = Path(target).read_text(encoding="utf-8", errors="ignore")
    return raw, "file"


def main() -> int:
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: web_content_distill.py <url_or_file>"}))
        return 1

    target = sys.argv[1]
    raw, source_type = load_source(target)
    raw = strip_noise(raw)

    if "<html" not in raw.lower():
        text = clean_text(raw)
        chunks = [chunk.strip() for chunk in re.split(r"(?<=[。！？.!?])\s+", text) if chunk.strip()]
        print(json.dumps({
            "source": target,
            "source_type": source_type,
            "title": "",
            "summary": chunks[:5],
            "sections": [],
            "bullets": [],
            "links": [],
        }, ensure_ascii=False))
        return 0

    parser = SimpleExtractor()
    parser.feed(raw)

    summary = []
    for paragraph in parser.paragraphs:
        if len(paragraph) < 20:
            continue
        if paragraph in summary:
            continue
        summary.append(paragraph)
        if len(summary) >= 5:
            break

    print(json.dumps({
        "source": target,
        "source_type": source_type,
        "title": parser.title,
        "summary": summary,
        "sections": parser.sections[:12],
        "bullets": parser.bullets[:20],
        "links": parser.links[:20],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
