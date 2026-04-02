# OpenClaw WebSearch Pro Wiki

## 架构

项目分四层：

1. 查询编排
   - 查询扩展
   - 站点感知排序
   - 二次搜索 refinement
2. 提取层
   - direct HTML
   - reader fallback
   - distill fallback
   - 站点专属 adapter
3. 登录态感知层
   - 浏览器会话审计
   - 访问墙识别
   - cookie/profile 资产检查
   - 登录辅助
4. 输出层
   - 结构化 sections
   - 正文 detail blocks
   - 图片/媒体 links
   - auth preview

## 已覆盖站点类型

### 电商

- 京东
- 淘宝
- 拼多多
- 天猫
- 1688
- AliExpress
- Walmart / Best Buy / Newegg / eBay / Etsy 的通用回退覆盖

核心输出字段：

- `price`
- `sales`
- `shop`
- `sku`
- `rating`
- `spec`
- `detail`
- `media links`

### 社媒 / 社区

- 小红书
- 抖音
- 微博
- Reddit
- X/Twitter
- Bilibili
- 贴吧

### 内容 / 文档

- 知乎
- CSDN
- 百度文库
- Medium
- Quora
- 51CTO
- InfoQ
- 掘金
- 博客园

## 登录与会话模型

### 插件会监控什么

- 浏览器登录状态
- cookie 文件是否存在
- 持久化 profile 是否存在
- 是否命中访问墙
- 是否命中过期页 / 错页

### 插件能直接做什么

- 打开浏览器登录页
- 生成小红书二维码 PNG
- 在 `extract / research` 结果里附带登录状态

### 插件不会做什么

- 绕过付费墙
- 绕过会员/VIP 限制
- 绕过复制限制

## 工具

### `websearch_pro_extract`

深提取单个 URL，并在需要时附带登录状态。

### `websearch_pro_research`

多引擎搜索 + 深提取 + 登录敏感站点状态提示。

### `websearch_pro_auth_status`

检查支持站点的登录/会话状态。

### `websearch_pro_login_assist`

打开登录页或生成二维码 PNG。

## 登录辅助方式

### 二维码

- 小红书

二维码默认输出到：

- `/Users/rico/.openclaw/workspace/auth-qrcodes/xhs-login-qrcode.png`

### 浏览器打开登录页

- 抖音
- 知乎
- CSDN
- 贴吧
- 百度文库
- 微博
- X

## 使用到的基础项目

- `MediaCrawler`
  - 社媒搜索和持久化 session 适配
- `xiaohongshu-mcp`
  - 小红书本地服务与二维码登录
- `yt-dlp`
  - 内容媒体提取
- `gallery-dl`
  - Reddit / 微博提取

## 运行说明

- 浏览器回退用于合法复用你已经登录且当前可见的会话。
- 浏览器提取应串行执行，避免把真实会话打乱。
- 二维码通过绝对路径返回，桌面对话、Web 容器、飞书桥接层都可以渲染或转发。
- 如果站点只给当前可见的部分内容，插件也只提取当前可见部分。

## 推荐配置

- 插件 id：`openclaw-websearch-pro`
- preview file：
  - `/Users/rico/.openclaw/workspace/.openclaw/websearch-pro-preview.json`
- auth preview file：
  - `/Users/rico/.openclaw/workspace/.openclaw/websearch-pro-auth-preview.json`
