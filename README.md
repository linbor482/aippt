# FORM / AI PPT

一个基于 Flask 的演示文稿工作台：可编辑大纲 + 可编辑 PPTX 导出，帮你快速产出一份[能用]的 PPT 初稿。
A Flask presentation workspace with an editable outline and editable PPTX export — a fast first draft, not a finished deck.

> 声明：本作品在开发过程中使用了 AI 工具（Claude Code 等）辅助编写与审查代码。
> Note: this project was developed with the help of AI tools (Claude Code, etc.) for writing and reviewing code.

## 定位 / Positioning

这个项目帮你**快速产出一份能用的 PPT 初稿**，适合：

- 课程作业、小组汇报、日常工作总结
- 内容框架清晰、不需要深度研究的小型演示
- 想先要个草稿再改，而不是从空白页开始

不适合：

- 学术论文答辩 / 期刊投稿 —— 数据、引用、结论需要自己逐条核对
- 竞赛路演、商业融资、对外正式发布 —— 版式与措辞需要深度定制
- 任何「错了后果很严重」的场景

---

This tool produces a **usable first draft**, good for class assignments, routine reports and small presentations. It is **not** a finished product for thesis defenses, competitions or public releases — data, citations, wording and layout there need your own review.

## 运行 / Run

```powershell
python -m pip install -r requirements.txt
python app.py
```

打开 http://127.0.0.1:5000。`app.py` 同时也是 Vercel 入口。

Open http://127.0.0.1:5000. `app.py` is also the Vercel entry point.

## 配置 / Configuration

在 `.env`（参考 `.env.example`）里填：

| 变量 | 用途 |
| --- | --- |
| `DEEPSEEK_API_KEY` | 大纲 / 文案生成（DeepSeek） |
| `VISION_API_KEY` | 图片视觉校验（任意 OpenAI 兼容视觉模型） |
| `VISION_API_URL` / `VISION_MODEL` | 可选：覆盖默认视觉端点与模型 |
| `PROXY_URL` | 访问非国内 API 时的代理（Clash/V2Ray，不需要可留空） |
| `ACCESS_USERNAME` / `ACCESS_PASSWORD` | 局域网共享访问口令（留空则不启用鉴权） |

优先级：应用内「API 密钥设置」页写入的 `config.json` > 环境变量 > `.env`。
默认图片模式为 `none`（不调用图片服务、无 API 费用），另有 `blank` / `real` / `ai` 可选。

---

Set `DEEPSEEK_API_KEY` (outline text) and `VISION_API_KEY` (vision check) in `.env`; see `.env.example`. Optional: `VISION_API_URL` / `VISION_MODEL`, `PROXY_URL`, and `ACCESS_USERNAME` / `ACCESS_PASSWORD` for LAN access. Priority: in-app `config.json` > environment variables > `.env`. Default image mode is `none` (no API charge); `blank`, `real` and `ai` remain available.

## 它是怎么工作的 / How it works

- 输入 1–200 字的主题描述（受众、目标、约束），默认开启 AI 生成大纲；缺 Key 或请求失败会明确提示，不再静默替换模板。
- 内容页支持 `layout: auto | editorial | columns | timeline`；密集内容会自动续页，最终页数可能多于大纲页数，所有内容都会保留。
- 不会凭空编造数据或图表。字体渲染在不同浏览器与 PowerPoint 之间可能略有差异（尤其缺少微软雅黑时）。

---

A 1–200 character brief (audience, goals, constraints) drives an AI-generated outline; a missing key or failed request is shown explicitly. Content slides accept `layout: auto | editorial | columns | timeline`; dense content flows onto extra slides and all text is retained. No factual metrics or charts are invented. Font rendering can vary between browsers and PowerPoint, especially without Microsoft YaHei.

## 生成流程 / Generation flow

- `POST /api/outline/stream`：以 NDJSON 流式返回阶段状态与大纲页。
- `POST /api/generate/stream`：流式生成场景到工作区，随后返回 PPTX 下载。
- 使用请求级生成器，无任务数据库、无实例内轮询、无落盘输出；取消即关闭浏览器请求。

---

`/api/outline/stream` streams NDJSON stage updates and outline pages; `/api/generate/stream` streams completed scenes then the PPTX download. Both use request-scoped generators — no job database, polling or filesystem output. Cancelling closes the browser request.

## 内置风格 / Styles

四种独立风格：商务（深蓝侧栏 + 结构化卡片）、极简（留白 + 细线）、创意（圆形 + 海报式排版 + 粉彩卡片）、提案（深色章节侧栏 + 论证模块）。时间线支持横向 / 纵向，长要点自动续页。工作区含页面轨道、画布与设计检查器，适配移动端，对话框支持键盘焦点与 Esc。

---

Four styles: business (navy side panel + cards), minimal (whitespace + thin rules), creative (circles + poster typography + pastel cards), and proposal (dark chapter sidebars + argument modules). Timelines switch between horizontal and vertical. The workspace includes a page rail, canvas and design inspector, is mobile-responsive, and dialogs support keyboard focus containment and Escape.

## 部署 / Deployment (Vercel)

入口保持 `app.py`，安装 `requirements.txt`，在 Vercel 环境变量里填 AI Key。配置请求 300 秒函数时长（需所选套餐支持并开启流式）。流式工作预算 240 秒，浏览器 285 秒停止等待。图片下载上限 8 MiB、等比缩至最大 1280×960；PPTX 上限 3 MiB、NDJSON 上限 4.2 MB（含预览图 base64）。超限可拆分页面或改用纯排版模式。API 响应不缓存，静态资源缓存 1 小时并使用带版本号的 URL。`.vercelignore` 已排除密钥、备份、review 与本地测试脚本。

---

Keep `app.py` as the entry point, install `requirements.txt`, and set the AI keys in Vercel's environment settings. The config requests a 300-second function duration (the plan must allow it and streaming). Streaming uses a 240-second work budget; the browser stops waiting at 285 seconds. Images are capped at 8 MiB and resized to ≤1280×960; PPTX is capped at 3 MiB and NDJSON at 4.2 MB. Split large decks or use pure layout if a limit is reached. API responses are not cached; static assets cache for one hour with versioned URLs. `.vercelignore` excludes secrets, backups, review files and local test scripts.

## 项目结构 / Structure

| 文件 | 作用 |
| --- | --- |
| `app.py` | Flask / Vercel 入口 |
| `generation_service.py` / `generation_api.py` | 请求校验 / NDJSON 流式生成 |
| `outline_service.py` | 大纲生成 |
| `image_service.py` | 图片服务与视觉校验 |
| `pptx_export.py` / `presentation_design.py` | 场景到 PPTX 的渲染与导出 |
| `style_layouts.py` | 四种风格构图 |
| `index.html` + `static/` | 工作区 UI 与设计令牌 |

## 测试 / Testing

```powershell
python -B -m unittest discover -v
node --check static/studio.js
```

覆盖预览 / 导出一致性、可编辑文本、元素边界、密集内容、图片插入、API 生成与单页输出。

---

Covers preview/export consistency, editable text, element bounds, dense content, image insertion, API generation and one-page output.

## 许可证 / License

[MIT](LICENSE)
