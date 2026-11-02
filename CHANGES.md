# 本机改造清单（CHANGES）

本文件是 `E:\OCR` 这一层与上游 [OpenBMB/MiniCPM-OCR](https://github.com/OpenBMB/MiniCPM-OCR)
之间的完整差异说明，**同时充当 Apache-2.0 第 4(b) 条要求的改动声明索引**。

上游基线：`sources\minicpm-ocr-main.tar.gz`（GitHub tarball，2026-10-30 的 main 分支）
解包后与 `sources\MiniCPM-OCR-main` 逐文件 MD5 比对得出，**修改 21 个文件、新增 4 个、删除 0 个**。

所有被修改的上游文件都已在文件头部加入：

```
# 本机改造：本文件在上游 OpenBMB/MiniCPM-OCR 版本基础上被修改。
# Apache-2.0 §4(b) 要求被修改的文件声明改动；完整改动清单见 E:\OCR\CHANGES.md
```

（TS/TSX 用等价的 `/** ... */` 注释块。）

---

## 一、上游副本的改动（`sources\MiniCPM-OCR-main`）

### 后端（`webdemo\backend`）

| 文件 | 状态 | 改动 |
|---|---|---|
| `server.py` | 修改 | 新增 `POST /api/jev/regenerate`、`POST /api/export/word`；`_block_to_api` 在没有 TTS 分时用 `jev_score` 当 `score`；新增生产模式静态托管（`/assets` `/voices` `/pdfjs` + SPA fallback，路径穿越用 `is_relative_to` 挡住） |
| `document_jobs.py` | 修改 | 解析任务结束后调用 `jev_quality.score_job()` 触发逐块质检（失败不影响识别结果） |
| `page_fleet.py` | 修改 | 新增 Jev 质检段：把一致性分数填进 `block["confidence"]`，官方前端的低分标注/复核面板/一键重识别直接生效；渲染走独立 venv，用子进程调用 |
| `model_manager.py` | 修改 | `OCRWEB_SAVE_ARTIFACTS=1` 时把裁块与页面图落盘（Jev 需要模型实际看到的原图块） |
| `jev_quality.py` | **新增** | 解析完成后按块调 Jev 打分，把 `prob_1` 写进 `crop_blocks[].jev_score` |
| `jev_regenerate.py` | **新增** | `POST /api/jev/regenerate`：裁块 → 1.0 重识别 → 渲染 → Jev 重新打分 |
| `word_export.py` | **新增** | Markdown → pandoc → 公式是 Word 原生公式（OMML）；HTML 表格先转 pipe 表格，图片三级降级 `full → no_images → plain` |

### 前端（`webdemo\frontend`）

| 文件 | 状态 | 改动 |
|---|---|---|
| `vite.config.ts` | 修改 | 代理补上 `/api/jev`、`/api/export` |
| `src/api/map/request.ts` | 修改 | 新增 `IMAGE_PARSE_LOCAL_BACKEND` 标记（本机部署、单块重识别走本机后端而非云端 L2） |
| `src/i18n/messages/playground.ts` | 修改 | 下载提示与新手引导文案说明两种 Word 导出的区别（普通 Word 留 LaTeX 源码 /「Word（公式可编辑）」是原生公式） |
| `utils/imageParseFeatureFlags.ts` | 修改 | 复核入口改为环境变量开关、**默认打开**（官方默认关闭）；设 `VITE_IMAGE_PARSE_REVIEW=false` 可关回 |
| `utils/imageParseExport.ts` | 修改 | 新增 `word-math` 格式，走本机 `/api/export/word`；入参类型补 `name?: string`；**桌面壳下载改走 pywebview JS 桥**（见下） |
| `utils/imageParseRegenerationRequest.ts` | 修改 | 本机重识别请求改发 `/api/jev/regenerate` 而不是云端 `tts_block` |
| `hooks/useImageParseRegeneration.ts` | 修改 | 本机不校验云端页面凭证与 API Key |
| `hooks/useImageParseResultState.ts` | 修改 | 接入 `useImageParseRegeneration`，把重识别能力串进结果状态 |
| `hooks/useImageParseDownload.ts` | 修改 | `name` 字段上移到公共入参类型，去掉重复声明；桌面壳落盘后弹 toast 显示保存路径 |
| `components/experiences/ImageParseDownloadMenu.tsx` | 修改 | 下载菜单新增「Word（公式可编辑）」菜单项（Σ 图标） |
| `components/experiences/ImageParseResultPane.tsx` | 修改 | 标准模式也开放复核面板（官方只给算法流水线模式开） |
| `components/experiences/ImageParseExperience.tsx` | 修改 | 串起 regeneration 状态 |
| `components/experiences/ImageParseDocumentWorkspace.tsx` | 修改 | 串起 regeneration 状态 |
| `components/experiences/ImageParseUploadSurface.tsx` | 修改 | 上传 input 由 `hidden` 改 `sr-only`（自动化可定位） |

### 新增的仓库卫生文件

| 文件 | 说明 |
|---|---|
| `.gitignore` | 上游仓库本身**没有** `.gitignore`，不补的话 `node_modules`（317MB）、`dist`、`__pycache__` 会被一并提交 |

### 顺带修掉的两个仓库卫生问题

| 问题 | 现象 | 处理 |
|---|---|---|
| **行尾被整体改写成 CRLF** | 上游 tarball 里所有文件是 LF，本机编辑工具把 21 个被改文件整个重写成了 CRLF。后果：diff 凭空从 58KB 膨胀到 579KB（每个文件都算"全文改动"），以后合并上游会逐行冲突 | `scripts\normalize_eol.py` 统一改回 LF（只动行尾，其余字节不变） |
| **删掉的运行时垃圾** | 上游副本里留了 5 个 `__pycache__` 和 `webdemo/backend/data/page-workers/*.json` | 已清理，并写进 `.gitignore` |

---

## 二、可回溯的补丁

`E:\OCR\upstream-local.patch` 是本机改造的标准 unified diff（`a/`= 上游基线，`b/`= 本机当前），
覆盖全部 22 个文件（21 个修改/新增 + `.gitignore`）。

生成脚本 `scripts\make_patch.py`，它同时会**自证**：

1. 把上游 tarball 解出的原始基线复制一份；
2. 在这份干净副本上 `git apply --check`；
3. 实际 `git apply` 后逐文件比对 MD5。

实测结果：**补丁应用成功，22 个文件与当前副本逐字节一致**。

用法——重新拉上游后重放本机改造：

```powershell
git clone https://github.com/OpenBMB/MiniCPM-OCR.git
cd MiniCPM-OCR
git apply --whitespace=nowarn E:\OCR\upstream-local.patch
```

---

## 三、本机自有层（`E:\OCR`，不含上游代码）

| 文件 | 说明 |
|---|---|
| `README.md` | 本机部署完整文档（11 章：现状 / 用法 / 目录 / 后端选型 / Jev / Web 工作台 / Word 导出 / 桌面版 / 已知限制 / 验证记录 / 后续） |
| `LICENSE` | Apache License 2.0 全文（与上游一致） |
| `NOTICE` | 归属声明：改编自 OpenBMB/MiniCPM-OCR，Copyright OpenBMB |
| `CHANGES.md` | 本文件 |
| `start_desktop.bat` | 桌面版一键入口（纯 ASCII，避免 cmd.exe 读 UTF-8 批处理出问题） |
| `scripts\desktop_app.py` | 桌面壳总控：清残留 → 拉服务 → 探活 → 开窗 → 关窗停服务 |
| `scripts\build-frontend.ps1` | 前端生产构建 + 补 pdfjs 资源 + 产物自检 |
| `scripts\start-*.ps1` | 五个服务的 Windows 版启动脚本 |
| `scripts\parse.ps1` / `jev_loop.ps1` / `verify_jev.py` 等 | CLI 版解析与质检流水线 |
| `scripts\apply_license_notices.py` | 给被修改的上游文件批量加 §4(b) 声明（幂等） |
| `scripts\normalize_eol.py` | 把被改文件行尾统一回 LF（只动行尾，其余字节不变） |
| `scripts\make_patch.py` | 生成并**自证** `upstream-local.patch`（apply --check + 实际 apply 后逐文件比对 MD5） |
| `scripts\health_check.ps1` | 全链路自检：静态（文件/依赖/许可/前端产物）+ 动态（四个服务/显存/Jev 是否在 CPU/官方三例分数口径/Word 导出/静态托管） |
| `scripts\diagnose_webview_download.py` | 诊断 pywebview(WebView2) 里下载能不能落盘（试 blob 链接与 Content-Disposition 两种方式并打印结论） |
| `upstream-local.patch` | 本机改造的标准 unified diff，可直接打到新的上游检出上 |

---

## 四、不属于本仓的东西

* **模型权重**：`models\` 下的 GGUF 来自 ModelScope，上游声明其权重同样适用 Apache-2.0。
* **第三方二进制**：`sources\ollama-0.40.12`（MIT，Copyright (c) Ollama）、
  `sources\llama-b12032`（MIT，Copyright (c) 2023-2026 The ggml authors）、
  `sources\pandoc`（官方 zip 内附 `COPYING.rtf`，为 GNU GPL v2 全文；单独可执行文件，
  未修改未链接，随本仓分发时保留其许可）。
  注：本机下载的分发包内**未附**这些 LICENSE 文本，此处许可信息取自各自上游仓库的 LICENSE。
* **模型权重**：`models\` 下的 GGUF 来自 ModelScope；上游声明其权重同样适用 Apache-2.0。
  权重**不入本仓**（单文件 800MB–1.2GB，超 GitHub 单文件 100MB 限制），
  用 `scripts\fetch-models.ps1` 按需下载。
