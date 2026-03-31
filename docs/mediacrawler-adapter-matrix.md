# MediaCrawler Adapter Matrix

这份矩阵只解决一个问题：`MediaCrawler` 在当前搜索插件里应该怎么用，哪些站点应该优先用它，哪些站点不该强行切过去。

## MediaCrawler 原生支持

根据本地 README 和文档，`MediaCrawler` 原生支持：

- 小红书 `xhs`
- 抖音 `dy`
- 快手 `ks`
- Bilibili `bili`
- 微博 `wb`
- 贴吧 `tieba`
- 知乎 `zhihu`

能力范围包括：

- 关键词搜索
- 指定帖子 ID / 内容页 detail
- 二级评论
- 创作者主页
- 登录态缓存
- `qrcode / phone / cookie`
- `xhs / dy` 还支持 CDP 连接本地浏览器

## 当前插件已接路径与建议

### 小红书

- 当前路径：
  - `xiaohongshu-mcp`
- 当前状态：
  - 已打通
  - 支持 `search -> detail`
  - URL 缺 `xsec_token` 时可自动补齐
- 结论：
  - 当前环境 **继续以 `xiaohongshu-mcp` 为主**
  - `MediaCrawler` 作为统一社媒层备选，不替代当前主路径
- 原因：
  - 当前 `xiaohongshu-mcp` 已经能稳定返回正文、作者、互动数据、评论和图片
  - 再切到 `MediaCrawler` 没有立刻收益，反而会增加切换成本

### 抖音

- 当前路径：
  - `MediaCrawler persistent profile DOM extract`
  - `MediaCrawler detail`
  - 本地 Douyin 项目备用
- 当前状态：
  - 二维码登录链有效
  - 已能复用 `MediaCrawler` 浏览器资料目录直接打开真实视频页
  - profile 路径已能稳定返回标题和 meta description
  - cookie detail 仍作为次级回退
- 结论：
  - 当前环境 **优先继续推进 `MediaCrawler`**
- 原因：
  - 它支持 `qrcode / cookie / CDP`
  - 能复用自己的持久化浏览器资料目录
  - 比零散脚本更适合作为抖音主适配器

### 微博

- 当前路径：
  - `gallery-dl`
- 当前状态：
  - 对状态页结构化提取已可用
- 结论：
  - 当前环境 **继续以 `gallery-dl` 为主**
  - `MediaCrawler` 作为未来统一评论/创作者抓取候选
- 原因：
  - `gallery-dl` 对真实微博状态页更轻、更稳、集成成本更低

### 贴吧

- 当前路径：
  - `MediaCrawler search`
- 当前状态：
  - 已接入
  - 在本机可直接执行搜索流程
  - 是否有结果取决于关键词命中情况
- 结论：
  - 当前环境 **贴吧以 `MediaCrawler` 为主路径**
- 原因：
  - 贴吧本来就没有更强的现成专属器
  - `MediaCrawler` 已经覆盖搜索、详情、评论和创作者主页

### Bilibili

- 当前路径：
  - 搜索页 `bilibili_search_cards`
  - 内容页 `yt-dlp`
- 当前状态：
  - 已稳定
- 结论：
  - 当前环境 **继续以 `yt-dlp` 为主**
  - `MediaCrawler` 暂不替换
- 原因：
  - `yt-dlp` 对视频详情元数据提取足够稳定且更简单

### 知乎

- 当前路径：
  - 域内重搜
  - 搜索结果页提取
  - 搜索结果后的详情跟进
- 当前状态：
  - 当前主链已经会继续进入详情页，不再只停在搜索页
  - `MediaCrawler` 在本机完成二维码登录后，可以抓到搜索结果与评论
  - 但登录态暂时无法稳定在无头复跑中复用
- 结论：
  - 当前环境 **先保留现有主路径**
  - 等 `MediaCrawler` 的 cookie / 会话复用稳定后，再考虑切主
- 原因：
  - 现有路径已经不只是搜索壳页
  - 直接切 `MediaCrawler` 会把当前链路换成一个还需要人工扫码恢复的路径

### Reddit / X / GitHub / 电商站

- 结论：
  - **不应为了统一而硬切到 `MediaCrawler`**
- 原因：
  - `MediaCrawler` 不覆盖 Reddit / X / GitHub / 淘宝 / 京东 / 拼多多
  - 当前现有路径已经更合适：
    - Reddit：`gallery-dl / yt-dlp`
    - X：`oEmbed`
    - GitHub：`github_raw`
    - 电商：域内重搜 + 卡片提纯

## 当前推荐策略

### 继续保留现有主路径

- 小红书：`xiaohongshu-mcp`
- 微博：`gallery-dl`
- Bilibili：`yt-dlp`
- Reddit：`gallery-dl / yt-dlp`
- X：`oEmbed`
- GitHub：`github_raw`

### 继续推进 MediaCrawler

- 抖音：作为主适配器继续推进
- 知乎：后续站内深抓取首选

## 原则

1. 不为了统一而牺牲稳定性。
2. 已经稳定的站点不强行迁移到 `MediaCrawler`。
3. `MediaCrawler` 优先用在：
   - 原生支持
   - 需要登录态
   - 需要搜索 / detail / 评论 / 创作者主页整套能力
4. 对非覆盖站点，继续使用现有最优路径。
