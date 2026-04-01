# OpenClaw WebSearch Pro

OpenClaw WebSearch Pro is an OpenClaw extension for multi-engine web search, deep extraction, auth-aware session reuse, and guided login flows.

- Chinese documentation: [README.zh-CN.md](/Users/rico/.openclaw/extensions/openclaw-websearch-pro/README.zh-CN.md)
- Detailed wiki: [docs/WIKI.md](/Users/rico/.openclaw/extensions/openclaw-websearch-pro/docs/WIKI.md)

## What It Does

- Expands a query into multiple search variants
- Searches Bing, DuckDuckGo, Google, and Baidu
- Follows up with deep extraction instead of stopping at snippets
- Reruns follow-up search when first-pass quality is weak
- Detects login walls, access walls, empty shells, and challenge pages
- Reuses lawful logged-in browser sessions for sites where the user already has access
- Exposes direct login helpers:
  - open a login page in the browser
  - generate a QR PNG for Xiaohongshu login
- Returns structured output for commerce, social, community, and content sites

## Registered Tools

- `search_orchestrator_status`
- `search_orchestrator_extract`
- `search_orchestrator_research`
- `websearch_pro_auth_status`
- `websearch_pro_login_assist`

## Deep-Optimized Sites

Current deep optimization coverage:

- `GitHub`
  - README/raw extraction
- `Xiaohongshu`
  - `search -> detail`, token resolution, login-aware MCP flow
- `Douyin`
  - MediaCrawler-backed detail/profile extraction, comments summary on valid samples
- `Zhihu`
  - question/answer/detail preference, gated-content detection, browser-assisted extraction
- `CSDN`
  - article/detail preference, error/access-wall detection, cleaner detail extraction
- `Tieba`
  - post/forum routing, login-shell detection, browser-assisted extraction
- `Baidu Wenku`
  - doc/view detection, access-wall detection, browser-assisted extraction
- `Weibo`
  - `gallery-dl` plus fallback
- `Reddit`
  - `gallery-dl` / `yt-dlp`
- `X/Twitter`
  - `oEmbed`
- `Bilibili`
  - search cards + `yt-dlp`
- `JD / Taobao / Pinduoduo`
  - commerce detail signals, structured sections, image/media extraction
- `GitLab`
  - meta extraction
- `Product Hunt`
  - fallback-only strategy

## Auth-Aware Workflow

The extension now has explicit auth monitoring.

- `websearch_pro_auth_status`
  - audits login/session state for supported sites
  - returns:
    - `auth_state`
    - `auth_reason`
    - cookie/profile artifact paths
    - whether login is required
- `websearch_pro_login_assist`
  - `xiaohongshu`: creates a QR PNG and returns the image path
  - browser-login sites: opens the login page directly in Safari
- `search_orchestrator_extract`
  - automatically attaches auth status for supported sites when extraction hits login-sensitive paths
- `search_orchestrator_research`
  - attaches auth status for supported sites found in top results or query intent

The QR workflow is file-based by design. The tool returns an absolute PNG path so desktop chat surfaces can render or forward it directly.

## Supported Login Helpers

- `xiaohongshu`
  - QR login
  - stored through the local `xiaohongshu-mcp` service
- `douyin`
  - browser login page opening
  - persistent MediaCrawler profile/cookie artifact inspection
- `zhihu`
  - browser login page opening
- `csdn`
  - browser login page opening
- `tieba`
  - browser login page opening
- `wenku`
  - browser login page opening
- `weibo`
  - browser login page opening
- `x`
  - browser login page opening

## Example Usage

### Deep extract a URL

```json
{
  "url": "https://www.zhihu.com/question/530454987",
  "query": "向量检索 重排"
}
```

### Run research

```json
{
  "query": "爱普生 XP-4100 驱动 安装 教程",
  "intent": "research",
  "max_results": 8,
  "max_deep_results": 5
}
```

### Inspect auth state

```json
{
  "sites": ["xiaohongshu", "douyin", "zhihu", "csdn"]
}
```

### Open login or generate QR

```json
{
  "site": "xiaohongshu"
}
```

## Installation

1. Put this project under:
   - `/Users/rico/.openclaw/extensions/openclaw-websearch-pro`
2. Apply local config:

```bash
cd /Users/rico/.openclaw/extensions/openclaw-websearch-pro
npm run install:local
```

3. Recommended preview files:
   - `/Users/rico/.openclaw/workspace/.openclaw/websearch-pro-preview.json`
   - `/Users/rico/.openclaw/workspace/.openclaw/websearch-pro-auth-preview.json`

## Base Projects Used

This project is built on top of a mixed adapter stack:

- [MediaCrawler](https://github.com/NanmiCoder/MediaCrawler)
  - social platform extraction and profile/cookie-backed flows
- `xiaohongshu-mcp`
  - local Xiaohongshu service and QR login flow
- [yt-dlp](https://github.com/yt-dlp/yt-dlp)
  - content page extraction
- [gallery-dl](https://github.com/mikf/gallery-dl)
  - Reddit / Weibo extraction

Plus OpenClaw-native layers:

- multi-engine search orchestration
- content fallback ranking
- browser session bridge
- auth-state detection

## Compliance Boundary

This extension does not integrate tools whose primary purpose is bypassing paywalls, member-only access, anti-copy controls, or private content restrictions.

It does:

- detect access walls
- reuse user-authorized sessions
- extract content already visible to the user

It does not:

- bypass paid content
- bypass VIP/member-only resources
- bypass follow-to-view restrictions

## Testing

```bash
cd /Users/rico/.openclaw/extensions/openclaw-websearch-pro
npm test
```
