# OpenClaw Search Orchestrator

Unified search orchestration for OpenClaw. This plugin consolidates multi-engine web search, site-focused query expansion, deep page extraction, iterative refinement, and proactive search guidance into one production path.

- Chinese documentation: [README.zh-CN.md](/Users/rico/.openclaw/extensions/openclaw-search-orchestrator/README.zh-CN.md)

## What it does

- Expands one query into multiple search variants
- Searches across Bing, DuckDuckGo, Google, and Baidu result pages
- Adds site-focused variants for:
  - GitHub
  - ClawHub
  - Reddit
  - Xiaohongshu
  - Douyin
  - Zhihu
- Deep-extracts high-value pages instead of stopping at result snippets
- Falls back to reader mode for JS-heavy or noisy domains
- Runs one refinement loop when first-pass quality is weak
- Nudges agents to use search proactively on external-information tasks
- Bundles browser-bridge and content-distill helpers inside the plugin for portability
- Includes site-specific extractors for high-value result pages
- Falls back to domain-scoped re-search when the target page is blocked, challenged, or unusable

## Bundled scripts

The plugin now ships with:

- `scripts/search_orchestrator.py`
- `scripts/browser_session_bridge.py`
- `scripts/web_content_distill.py`

This keeps the plugin portable and avoids hidden runtime dependencies on `workspace/scripts`.

## Registered tools

- `search_orchestrator_status`
- `search_orchestrator_extract`
- `search_orchestrator_research`

## Config

Configure under:

- `plugins.entries.openclaw-search-orchestrator`

Example:

```json
{
  "plugins": {
    "entries": {
      "openclaw-search-orchestrator": {
        "enabled": true,
        "config": {
          "enabled": true,
          "proactiveSearch": true,
          "injectBeforePromptBuild": true,
          "previewFile": "/Users/rico/.openclaw/workspace/.openclaw/search-orchestrator-preview.json",
          "defaultIntent": "auto",
          "maxInitialResults": 8,
          "maxDeepResults": 5,
          "maxRefineRounds": 2,
          "skipAgentIds": [
            "ops-system"
          ]
        }
      }
    }
  }
}
```

### Fields

- `enabled`
  - Master switch.
- `proactiveSearch`
  - If true, injects search guidance for likely external-information tasks.
- `injectBeforePromptBuild`
  - Enables proactive prompt guidance at `before_prompt_build`.
- `previewFile`
  - Stores the latest orchestration preview/result.
- `defaultIntent`
  - Default intent when the task does not clearly map to a specialized search path.
- `maxInitialResults`
  - Max ranked search hits to keep after aggregation.
- `maxDeepResults`
  - Max results to deep-extract.
- `maxRefineRounds`
  - How many additional refinement rounds to run when quality is weak.
- `forceAgentIds`
  - If present, only these agent ids get proactive search injection.
- `skipAgentIds`
  - Agent ids excluded from proactive search injection.
- `siteProfiles`
  - Optional override for site-profile groups. The plugin ships with default profiles and does not require this in normal use.

## Proactive behavior

The plugin does not wait for the user to explicitly say “search”. It injects guidance when the prompt looks like an external-information task, such as:

- current facts
- plugin or skill discovery
- GitHub / ClawHub lookup
- social-platform research
- docs / official-site lookup
- patent / competitor / market research

It skips obvious no-search prompts such as:

- `只回复 OK`
- `只返回状态`

## Tool usage pattern

### Research

```json
{
  "query": "安装 clawhub 插件 github 搜索相关 skill",
  "intent": "plugin_discovery",
  "max_results": 8,
  "max_deep_results": 5,
  "max_refine_rounds": 2
}
```

### Extract

```json
{
  "url": "https://github.com/openclaw-ai-opc/openclaw-cn/blob/main/docs/zh-CN/tools/clawhub.md",
  "query": "clawhub install skill"
}
```

## Output shape

`search_orchestrator_research` returns:

- `query`
- `intent`
- `quality`
- `rounds`
- `results`
- `followup_queries`

Each result includes:

- `title`
- `url`
- `engine`
- `query_variant`
- `site_focus`
- `snippet`
- `score`
- `extraction`

The `extraction` object includes:

- `fetch_mode`
- `title`
- `summary`
- `sections`
- `links`
- `quality`

Common `fetch_mode` values now include:

- `github_raw`
- `reddit_json`
- `search_results`
- `domain_search_fallback`
- `meta_search_fallback`
- `reader`
- `direct`

## Site-specific extraction

The orchestrator does not treat all pages the same.

Current specialized paths include:

- GitHub repository and blob URLs
  - fetches raw README/blob content directly when possible
- Reddit discussion URLs
  - tries structured `.json` extraction first
- Search result pages
  - Google
  - Baidu
  - YouTube
  - PyPI
  - Hugging Face
  - Kubernetes Docs search

When a target page is blocked or degraded, the orchestrator can synthesize a usable extraction by re-searching the same query with a domain restriction and converting the best results into structured evidence.

## Design notes

- This plugin is the primary search path. It is intended to replace ad-hoc script selection at the task level.
- Existing modules can delegate into this plugin instead of maintaining their own search heuristics.
- The plugin is optimized for “search -> extract -> refine -> summarize”, not just “search -> stop”.
- `workspace/scripts/web-search.sh` and `workspace/scripts/web-search-structured.sh` remain only as compatibility shims and now delegate into this plugin.
