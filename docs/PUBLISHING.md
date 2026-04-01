# Publishing

## Current State

This repository is prepared for publishing but does not yet have a remote.

- local repo path:
  - `/Users/rico/.openclaw/extensions/openclaw-websearch-pro`
- release archive:
  - `/Users/rico/.openclaw/workspace/releases/openclaw-websearch-pro-1.0.0.tar.gz`

## Create a Remote Repository

Example using git once a remote exists:

```bash
cd /Users/rico/.openclaw/extensions/openclaw-websearch-pro
git remote add origin <your-remote-url>
git push -u origin main
```

Recommended repository name:

- `openclaw-websearch-pro`

## What Should Be Included

- `README.md`
- `README.zh-CN.md`
- `docs/WIKI.md`
- `docs/WIKI.zh-CN.md`
- `openclaw.plugin.json`
- `package.json`
- `src/`
- `scripts/`
- `tests/`
- `data/`

## Pre-publish Checks

```bash
cd /Users/rico/.openclaw/extensions/openclaw-websearch-pro
npm test
python3 scripts/auth_workflow.py status '{"sites":["xiaohongshu","douyin","zhihu","csdn","tieba","wenku"]}'
```

## OpenClaw Activation

The local OpenClaw config already contains:

- plugin id: `openclaw-websearch-pro`
- preview file:
  - `/Users/rico/.openclaw/workspace/.openclaw/websearch-pro-preview.json`
- auth preview file:
  - `/Users/rico/.openclaw/workspace/.openclaw/websearch-pro-auth-preview.json`

## Known Environment Dependencies

- `python3`
- `node`
- `MediaCrawler` environment
- `xiaohongshu-mcp` runtime when using Xiaohongshu QR login
- `yt-dlp`
- `gallery-dl`

## Packaging

Rebuild release archive:

```bash
mkdir -p /Users/rico/.openclaw/workspace/releases
cd /Users/rico/.openclaw/extensions
tar -czf /Users/rico/.openclaw/workspace/releases/openclaw-websearch-pro-1.0.0.tar.gz openclaw-websearch-pro
```
