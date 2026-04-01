# 发布说明

## 当前状态

仓库已经整理成可发布状态，但还没有远端仓库。

- 本地仓库路径：
  - `/Users/rico/.openclaw/extensions/openclaw-websearch-pro`
- 本地打包文件：
  - `/Users/rico/.openclaw/workspace/releases/openclaw-websearch-pro-1.0.0.tar.gz`

## 创建远端仓库

当远端仓库创建好之后，执行：

```bash
cd /Users/rico/.openclaw/extensions/openclaw-websearch-pro
git remote add origin <你的远端地址>
git push -u origin main
```

推荐仓库名：

- `openclaw-websearch-pro`

## 发布内容

- `README.md`
- `README.zh-CN.md`
- `docs/WIKI.md`
- `docs/WIKI.zh-CN.md`
- `docs/PUBLISHING.md`
- `docs/PUBLISHING.zh-CN.md`
- `openclaw.plugin.json`
- `package.json`
- `src/`
- `scripts/`
- `tests/`
- `data/`

## 发布前检查

```bash
cd /Users/rico/.openclaw/extensions/openclaw-websearch-pro
npm test
python3 scripts/auth_workflow.py status '{"sites":["xiaohongshu","douyin","zhihu","csdn","tieba","wenku"]}'
```

## OpenClaw 本地启用

应用或刷新本地配置：

```bash
cd /Users/rico/.openclaw/extensions/openclaw-websearch-pro
npm run install:local
```

本地 OpenClaw 配置应包含：

- 插件 id：`openclaw-websearch-pro`
- preview file：
  - `/Users/rico/.openclaw/workspace/.openclaw/websearch-pro-preview.json`
- auth preview file：
  - `/Users/rico/.openclaw/workspace/.openclaw/websearch-pro-auth-preview.json`

## 环境依赖

- `python3`
- `node`
- `MediaCrawler` 运行环境
- `xiaohongshu-mcp` 运行环境
- `yt-dlp`
- `gallery-dl`

## 重新打包

```bash
mkdir -p /Users/rico/.openclaw/workspace/releases
cd /Users/rico/.openclaw/extensions
tar -czf /Users/rico/.openclaw/workspace/releases/openclaw-websearch-pro-1.0.0.tar.gz openclaw-websearch-pro
```
