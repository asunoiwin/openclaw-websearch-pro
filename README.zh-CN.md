# OpenClaw WebSearch Pro

OpenClaw WebSearch Pro 是一个面向 OpenClaw 的统一搜索与提取插件，重点解决多引擎搜索、深度提取、登录态复用、登录过期提醒和登录引导。

- 英文文档：[README.md](/Users/rico/.openclaw/extensions/openclaw-websearch-pro/README.md)
- 详细 Wiki：[docs/WIKI.zh-CN.md](/Users/rico/.openclaw/extensions/openclaw-websearch-pro/docs/WIKI.zh-CN.md)

## 能力范围

- 一个查询自动扩展多个搜索变体
- 搜索 Bing、DuckDuckGo、Google、Baidu
- 对高价值结果做深度提取，不停在 snippet
- 首轮结果弱时自动再搜索
- 识别登录墙、访问墙、空壳页、挑战页、错误页
- 合法复用用户已经登录且当前可见的浏览器会话
- 提供直接登录辅助：
  - 打开登录页
  - 生成小红书二维码 PNG
- 针对电商、社媒、内容站输出结构化结果

## 注册工具

- `websearch_pro_status`
- `websearch_pro_extract`
- `websearch_pro_research`
- `websearch_pro_auth_status`
- `websearch_pro_login_assist`

## 已深度优化的网站

- `GitHub`
  - README / raw 直提
- `小红书`
  - `search -> detail`
  - 登录态和二维码登录检测
- `抖音`
  - MediaCrawler 资料目录 / detail / comments 摘要链
- `知乎`
  - 问题页/回答页优先
  - 登录墙/盐选/荒原页识别
- `CSDN`
  - 文章页优先
  - 404/访问墙识别
  - 正文块和图片提取
- `贴吧`
  - 帖子页/吧页识别
  - 登录壳页识别
- `百度文库`
  - `/view/` `/share/` 文档页识别
  - 试读/VIP 墙识别
- `微博`
  - `gallery-dl`
- `Reddit`
  - `gallery-dl / yt-dlp`
- `X/Twitter`
  - `oEmbed`
- `Bilibili`
  - 搜索卡片 + `yt-dlp`
- `京东 / 淘宝 / 拼多多`
  - 商品详情信号、结构化 sections、图片/媒体提取
- `GitLab`
  - meta 提取
- `Product Hunt`
  - `meta + fallback-only`

## 登录态检测与提醒

插件现在有显式的登录态监控：

- `websearch_pro_auth_status`
  - 返回：
    - `auth_state`
    - `auth_reason`
    - cookie/profile 文件路径
    - 是否需要重新登录
- `websearch_pro_login_assist`
  - `小红书`：直接生成二维码 PNG，并返回文件路径
  - 浏览器登录站点：直接在 Safari 打开登录页
- `websearch_pro_extract`
  - 在命中登录敏感站点时，会自动附带该站点的登录状态
- `websearch_pro_research`
  - 会对结果中的敏感站点附带登录状态回收

二维码使用文件返回，不依赖固定 UI。工具会返回绝对 PNG 路径，桌面对话窗口、Web 容器、飞书桥接层都可以直接渲染或转发。

## 目前支持的登录辅助

- `xiaohongshu`
  - 二维码登录
- `douyin`
  - 浏览器登录页打开
  - 持久化 profile / cookie 文件状态检查
- `zhihu`
  - 浏览器登录页打开
- `csdn`
  - 浏览器登录页打开
- `tieba`
  - 浏览器登录页打开
- `wenku`
  - 浏览器登录页打开
- `weibo`
  - 浏览器登录页打开
- `x`
  - 浏览器登录页打开

## 使用示例

### 深提取页面

```json
{
  "url": "https://www.zhihu.com/question/530454987",
  "query": "向量检索 重排"
}
```

### 执行统一搜索调研

```json
{
  "query": "爱普生 XP-4100 驱动 安装 教程",
  "intent": "research",
  "max_results": 8,
  "max_deep_results": 5
}
```

### 检查登录状态

```json
{
  "sites": ["xiaohongshu", "douyin", "zhihu", "csdn"]
}
```

### 打开登录页或生成二维码

```json
{
  "site": "xiaohongshu"
}
```

## 安装

1. 将项目放到：
   - `/Users/rico/.openclaw/extensions/openclaw-websearch-pro`
2. 应用本地配置：

```bash
cd /Users/rico/.openclaw/extensions/openclaw-websearch-pro
npm run install:local
```

3. 推荐预览文件：
   - `/Users/rico/.openclaw/workspace/.openclaw/websearch-pro-preview.json`
   - `/Users/rico/.openclaw/workspace/.openclaw/websearch-pro-auth-preview.json`

## 使用到的基础项目

基础适配器来自：

- `MediaCrawler`
  - 社媒搜索和内容提取
- `xiaohongshu-mcp`
  - 小红书本地服务与二维码登录
- `yt-dlp`
  - 内容页提取
- `gallery-dl`
  - Reddit / 微博提取

OpenClaw 自己提供的层包括：

- 多引擎搜索编排
- 内容回退排序
- 浏览器会话桥接
- 登录态检测与提醒

## 合规边界

这个插件不会接入以绕过付费墙、会员墙、反复制控制、关注后可见限制为目标的工具。

会做的事：

- 识别访问墙
- 复用用户自己已授权的会话
- 提取用户当前已经可见的内容

不会做的事：

- 绕过付费内容
- 绕过会员/VIP 限制
- 绕过关注后可见限制

## 测试

```bash
cd /Users/rico/.openclaw/extensions/openclaw-websearch-pro
npm test
```
