# OpenClaw Search Orchestrator

这是 OpenClaw 的统一搜索编排插件。它把多引擎搜索、站点定向查询、深度提取、结果再搜索、以及主动搜索提示整合到一条生产链里。

- 英文文档：[README.md](/Users/rico/.openclaw/extensions/openclaw-search-orchestrator/README.md)

## 功能

- 一个查询自动扩展出多个搜索变体
- 搜索 Bing、DuckDuckGo、Google、Baidu 结果页
- 对这些站点自动补定向查询：
  - GitHub
  - ClawHub
  - Reddit
  - 小红书
  - 抖音
  - 知乎
- 对高价值结果做深度提取，而不是停在 snippet
- 对 JS 重、DOM 难取或页面噪声重的站点优先走 reader 提取
- 首轮结果差时，会做一轮再搜索
- 在任务开始前，主动提示 agent 使用统一搜索工具，而不是等用户显式说“去搜索”
- 插件自带浏览器桥和网页蒸馏脚本，不依赖 `workspace/scripts` 才能工作
- 内置站点专属结果页提取器
- 内置可选的 `yt-dlp` 二级内容页适配器，优先处理 `Bilibili / Douyin / XiaoHongShu / Weibo / X / Reddit` 这类内容页
- 内置可选的 `gallery-dl` 内容页适配器，优先处理 `Weibo` 这类已有成熟提取器的平台
- 当目标页被挑战、拦截或质量过低时，会自动做域名限定再搜索并合成结构化结果

## 插件内脚本

以下脚本已经内置在插件内，可随插件一起迁移：

- `scripts/search_orchestrator.py`
- `scripts/browser_session_bridge.py`
- `scripts/browser_auth_audit.py`
- `scripts/web_content_distill.py`
- `src/site-adapter-policy.json`

这样做的目的：

- 保证插件可移植
- 避免换机器或其他用户安装时缺失依赖脚本
- 让旧入口只作为兼容代理，而不是主逻辑承载点

## 注册工具

- `search_orchestrator_status`
- `search_orchestrator_extract`
- `search_orchestrator_research`

## 配置位置

配置写在：

- `plugins.entries.openclaw-search-orchestrator`

示例：

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

## 配置项说明

- `enabled`
  - 总开关。
- `proactiveSearch`
  - 为 `true` 时，外部信息任务会在 `before_prompt_build` 阶段收到主动搜索提示。
- `injectBeforePromptBuild`
  - 是否启用搜索提示注入。
- `previewFile`
  - 保存最近一次搜索编排预览或结果。
- `defaultIntent`
  - 没有明显任务类型时的默认意图。
- `maxInitialResults`
  - 聚合和重排后最多保留多少条候选结果。
- `maxDeepResults`
  - 最多对多少条结果做深度提取。
- `maxRefineRounds`
  - 首轮质量差时，最多继续做几轮再搜索。
- `forceAgentIds`
  - 如果设置了，只对这些 agent 注入主动搜索提示。
- `skipAgentIds`
  - 这些 agent 不做主动搜索注入。
- `siteProfiles`
  - 覆盖默认站点分组。一般不需要改，插件内已有默认值。

## 主动搜索触发规则

这条插件不会等用户明确说“去搜索”。当任务明显属于外部信息任务时，会主动要求 agent 先用统一搜索工具。

典型触发场景：

- 查最新信息
- 找 GitHub / ClawHub / plugin / skill
- 查官网、文档、资料
- 做专利、竞品、商品、平台内容调研
- 查小红书、抖音、知乎、Reddit 等平台内容

典型不触发场景：

- `只回复 OK`
- `只返回状态`

## 推荐调用方式

### 统一调研

```json
{
  "query": "安装 clawhub 插件 github 搜索相关 skill",
  "intent": "plugin_discovery",
  "max_results": 8,
  "max_deep_results": 5,
  "max_refine_rounds": 2
}
```

### 深度提取单页

```json
{
  "url": "https://github.com/openclaw-ai-opc/openclaw-cn/blob/main/docs/zh-CN/tools/clawhub.md",
  "query": "clawhub install skill"
}
```

## 输出结构

`search_orchestrator_research` 会返回：

- `query`
- `intent`
- `quality`
- `rounds`
- `results`
- `followup_queries`

其中每条 `result` 包含：

- `title`
- `url`
- `engine`
- `query_variant`
- `site_focus`
- `snippet`
- `score`
- `extraction`

`extraction` 里会包含：

- `fetch_mode`
- `title`
- `summary`
- `sections`
- `links`
- `quality`

常见的 `fetch_mode` 现在包括：

- `github_raw`
- `reddit_json`
- `search_results`
- `browser_session`
- `domain_search_fallback`
- `domain_search_deep_fallback`
- `external_discovery_fallback`
- `meta_search_fallback`
- `reader`
- `direct`
- `yt_dlp`
- `gallery_dl`

## 站点专属提取

这条搜索器不会把所有网页都当成同一种页面处理。

当前已经有专属路径的包括：

- GitHub 仓库页和 blob 页
  - 优先抓原始 README / 原始文件内容
- Reddit 讨论页
  - 优先尝试 `.json` 结构化提取
  - 内容页可进一步走 `yt-dlp + 浏览器 cookies` 提取正文和统计信息
- Bilibili 搜索页
  - 直接从 SSR HTML 中抽视频卡片和二级视频链接
- Weibo 状态页
  - 当命中真实微博状态页时，可通过 `gallery-dl` 提取结构化内容
- 搜索结果页
  - Google
  - Baidu
  - YouTube
  - PyPI
  - Hugging Face
  - Kubernetes Docs search

如果目标页本身被验证页、挑战页或半加载页面挡住，搜索器会自动退到：

- 同 query 的域名限定再搜索
- 再把搜索结果整理成结构化证据

这样即使拿不到原页面 DOM，也不会直接停在低质量结果。

## 浏览器登录态回退

默认情况下，这条路径现在是关闭的。

原因：

- 反复打开站点页会干扰用户真实登录态
- 某些平台会把高频标签页打开视为异常行为
- 搜索插件现在优先走：
  - `direct`
  - `reader`
  - `domain_search_fallback`
  - `external_discovery_fallback`
  - `yt_dlp`

只有在你显式设置环境变量后，才会重新启用浏览器回退：

- `OPENCLAW_SEARCH_ENABLE_BROWSER_FALLBACK=1`

当网站满足下面条件之一时，搜索器会尝试复用本地 Safari 会话：

- 需要登录后才能看到正文或搜索结果
- 机器人挑战、验证页、强 JS 渲染导致原始抓取只得到壳页
- 页面本身是有效搜索页，但真正有用的信息只在浏览器加载后的结果列表里

当前这条路径主要服务于：

- 淘宝 / 天猫
- 知乎
- 小红书
- 抖音
- Bilibili
- 微博
- X
- Reddit
- Product Hunt
- GitLab

在真正走浏览器回退前，搜索器现在会先做一次登录态预审：

1. 检查目标浏览器是否在运行
2. 检查当前会话是否已过期
3. 检查打开后是否落到正确域名
4. 检查当前页是不是登录壳页、控制台页或低信号页

只有预审通过，才会把浏览器结果当成有效信息源。

### 浏览器登录态批量审计

插件内还带了一个批量审计脚本：

- `scripts/browser_auth_audit.py`

默认站点清单：

- `data/browser_auth_sites.json`

用法：

```bash
python3 scripts/browser_auth_audit.py data/browser_auth_sites.json
```

它会输出每个站点当前的：

- 浏览器
- 请求 URL
- 登录态
- 登录态原因
- 如果是 Safari，还会附带可提取正文结果

### 测试窗口关闭规则

浏览器测试现在遵循一条强制规则：

1. 优先复用当前浏览器窗口
2. 在同一窗口中新增测试标签页，而不是新增多个窗口
3. 提取结束后自动关闭刚打开的测试标签页
4. 不再保留一堆临时测试窗口

对应命令：

```bash
python3 scripts/browser_session_bridge.py close-front safari
```

默认 `audit` 已经内置自动关闭，不需要额外手动调用。

## 站点适配层策略

插件现在带一个站点适配层策略文件：

- `src/site-adapter-policy.json`

这个文件的作用不是直接执行抓取，而是定义：

- 哪些站点继续走通用回退
- 哪些站点值得接专属提取器
- 哪些站点后续适合接 GitHub 上现成的 Python 项目

当前策略大意：

- `taobao.com`
  - 优先做专属搜索结果提取
- `jd.com`
  - 先走域内回退，后续再补专属器
- `xiaohongshu.com / douyin.com / weibo.com`
  - 当前优先站外发现，后续再补专属适配器
- `reddit.com`
  - 搜索页先回退，帖子页继续优先 JSON
- `gitlab.com`
  - 登录稳定前优先站外发现

这条回退不是简单“把浏览器页读一遍”，而是：

1. 用本地 Safari 打开目标页
2. 读取真实 DOM 文本、标题、链接、标题层级
3. 如果页面是搜索结果页，优先抽取与 query 强相关的局部片段
4. 如果拿到的是控制台页、登录壳页、错误域名页，则直接判失败，不把它误算成高质量命中

## 站点语义外部发现兜底

当目标站点本身完全不可取，且站内 `site:` 回退仍然拿不到可用结果时，搜索器会进入最后一层兜底：

1. 识别站点品牌词，例如：
   - `x twitter`
   - `gitlab`
   - `36kr`
   - `京东`
   - `拼多多`
2. 把品牌词和 query 以及站点专属补充词拼成新查询
3. 在 Bing / DuckDuckGo 上重新做通用搜索
4. 返回与该站点场景强相关的可用结果，而不是空结果

这条路径主要解决：

- 目标站点搜索页只剩 JavaScript/验证提示
- 目标站点搜索页被 403/反爬完全挡住
- 电商站点搜索页只能看到平台介绍页、但站外仍能找到相关教程、文档、讨论和替代信息

## 通用失败原因与恢复规则

这次大规模回归后，已经能把常见失败模式归成几类。后续即使遇到未专门适配的网站，也优先按这些规则处理：

1. 搜索结果壳页
   - 现象：
     - 标题像 `Search Results`
     - 页面正文只有导航、站点说明或一条泛摘要
   - 处理：
     - 不直接信正文
     - 改走 `search_results` 结果页抽取

2. 挑战页 / 验证页 / 反爬页
   - 现象：
     - `Client Challenge`
     - `Just a moment`
     - `安全验证`
     - `Please enable JavaScript`
     - `403`
   - 处理：
     - 直接降级
     - 再走 `domain_search_fallback` 或 `meta_search_fallback`

3. 子域名过滤过严
   - 现象：
     - 目标页在 `s.xxx.com`、`m.xxx.com`、`search.xxx.com`
     - 但有效内容落在根域名其他页面
   - 处理：
     - 放宽到根域名级别再过滤

4. JS 重页面 / DOM 不可用
   - 现象：
     - 页面能打开，但抓不到有效正文
     - 只有 reader 或 distill 才能拿到内容
   - 处理：
     - `reader -> distill`
     - 再做质量判断

5. 泛站点介绍误判
   - 现象：
     - 搜索页明明是目标站点，但正文只剩“这是一个网站/平台”
   - 处理：
     - 不把这类内容当命中
     - 改做域名限定再搜索

## 设计原则

- 这条插件是新的主搜索链，不再依赖“脚本 A 搜一下，脚本 B 再补一下”的散点模式。
- 目标不是只返回搜索结果，而是：
  - 搜索
  - 提取
  - 判断质量
  - 需要时再搜索
  - 最后交给 agent 使用

- 现有模块应该逐步委托给这条统一搜索编排器，而不是继续维护各自独立的搜索逻辑。
- `workspace/scripts/web-search.sh` 和 `workspace/scripts/web-search-structured.sh` 现在只保留兼容入口，内部已经代理到本插件。
