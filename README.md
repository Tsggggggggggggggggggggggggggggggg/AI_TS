# AI Weekly Digest (100% Free, Auto)

一个 **零成本自动化** 的 AI 新闻周报生成器。特点：
- **自动抓取** RSS（可自定义来源）
- **自动抽取正文**（readability）
- **自动摘要**（提取式，中文/英文都可以；不依赖付费大模型）
- **自动生成 Markdown 周报**（`output/weekly_digest.md`）
- **自动按周运行**（GitHub Actions 定时任务）

> 适合：个人学习、知识沉淀、每周邮件/微信推送（把生成的 Markdown 复制即可）。

---

## 快速开始（无需服务器）

1. **在 GitHub 创建一个新仓库**（例如 `ai-weekly-digest`）。
2. 下载本项目的 ZIP 并把里面所有文件上传到你的仓库根目录。
3. 在 GitHub 仓库的 **Actions** 页面启用 Workflow（首次可能需要点击“Enable”）。
4. 等待定时任务触发（默认 **每周一 09:00 UTC** 运行），或在 Actions 里 **手动 Run workflow** 一次。
5. 生成的周报会保存在仓库的 `output/weekly_digest.md`，同时会作为 **Workflow artifacts** 可下载。

> 想立即测试：进入仓库 Actions -> 选中 `AI Weekly Digest` -> `Run workflow`。

---

## 自定义

- **RSS 列表**：编辑 `rss.txt`，每行一个 RSS 源。
- **抓取时间窗**：默认抓取最近 7 天，可在脚本顶部调整。
- **定时周期**：编辑 `.github/workflows/weekly.yml` 的 `cron` 表达式。
- **输出样式**：修改 `fetch_and_summarize.py` 里的模板函数。

---

## 可选：自动通知/发布（延伸）

- 邮件：使用 GitHub Actions 的邮件 Action，或后续接入 SMTP（需配置密钥）。
- 微信/飞书：接入群机器人 Webhook（需要你在企业微信/飞书里新建机器人并配置 Secret）。
- Notion：可在脚本中调用 Notion API 创建页面（需要令牌）。

---

## 本地运行（可选）

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python fetch_and_summarize.py
```

生成结果在 `output/weekly_digest.md`。

---

## 依赖说明

- `feedparser`：读取 RSS
- `readability-lxml` + `beautifulsoup4`：抽取网页正文
- `lxml`：HTML 解析
- 无需任何付费模型；摘要使用中文/英文通用的**提取式**方法（首段+句子抽取）。

---

## 免责声明
本项目仅抓取公开 RSS/网页内容并生成摘要，务必保留原链接与来源；若对外发布，请遵循各站点的使用条款与版权要求。
