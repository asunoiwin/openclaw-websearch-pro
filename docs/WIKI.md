# OpenClaw WebSearch Pro Wiki

## Architecture

The project has four layers:

1. Query orchestration
   - query expansion
   - site-aware ranking
   - follow-up refinement
2. Extraction
   - direct HTML
   - reader fallback
   - distill fallback
   - site adapters
3. Auth-aware execution
   - browser session audit
   - access-wall detection
   - cookie/profile artifact inspection
   - login assist
4. Presentation
   - structured sections
   - detail blocks
   - media links
   - auth preview payloads

## Supported Site Classes

### Commerce

- JD
- Taobao
- Pinduoduo
- Tmall
- 1688
- AliExpress
- Walmart / Best Buy / Newegg / eBay / Etsy fallback coverage

Core output:

- price
- sales
- shop
- sku
- rating
- spec
- detail blocks
- media links

### Social / Community

- Xiaohongshu
- Douyin
- Weibo
- Reddit
- X/Twitter
- Bilibili
- Tieba

### Content / Docs

- Zhihu
- CSDN
- Baidu Wenku
- Medium
- Quora
- 51CTO
- InfoQ
- Juejin
- CNBlogs

## Login and Session Model

### What the plugin monitors

- browser session state
- cookie file existence
- persistent profile existence
- access-wall state
- expired / missing page state

### What the plugin can do directly

- open browser login pages
- generate Xiaohongshu QR PNGs
- attach auth status to extraction / research results

### What the plugin does not do

- bypass paywalls
- bypass VIP/member-only restrictions
- bypass copy-protection controls

## Tools

### `websearch_pro_extract`

Deep extract a single URL and attach auth status when relevant.

### `websearch_pro_research`

Run multi-engine search plus deep extraction and auth-aware site hints.

### `websearch_pro_auth_status`

Check supported site login/session state.

### `websearch_pro_login_assist`

Open a login page or generate a QR PNG.

## Supported Login Assist Flows

### QR

- Xiaohongshu

The tool writes:

- `/Users/rico/.openclaw/workspace/auth-qrcodes/xhs-login-qrcode.png`

### Browser-open

- Douyin
- Zhihu
- CSDN
- Tieba
- Wenku
- Weibo
- X

## Upstream Projects Used

- MediaCrawler
  - social platform extraction and profile-backed sessions
- xiaohongshu-mcp
  - local Xiaohongshu service and QR login
- yt-dlp
  - content media extraction
- gallery-dl
  - Reddit / Weibo extraction

## Operational Notes

- Browser fallback is for lawful session reuse.
- Browser extraction should run serially to avoid disturbing real sessions.
- QR images are returned as local absolute paths so chat surfaces can render them.
- If a site exposes only partial visible content, the plugin extracts only the visible portion.

## Recommended OpenClaw Config

- plugin id: `openclaw-websearch-pro`
- preview file:
  - `/Users/rico/.openclaw/workspace/.openclaw/websearch-pro-preview.json`
- auth preview file:
  - `/Users/rico/.openclaw/workspace/.openclaw/websearch-pro-auth-preview.json`
