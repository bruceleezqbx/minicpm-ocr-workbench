# MiniCPM-OCR 1.0 本地部署（Windows + GTX 1050 Ti 4GB）

在本机把 MiniCPM-OCR 1.0 跑成「整页 PDF/图片 → Markdown」的流水线：Ollama 提供推理服务，
`minicpm-ocr` SDK 做版面检测与结果组装。

> **这是非官方的本机部署与改造**，不是 OpenBMB 官方项目。
> 上游项目：<https://github.com/OpenBMB/MiniCPM-OCR>（Apache License 2.0，Copyright OpenBMB）。
> 本仓的改编内容与归属声明见 [`CHANGES.md`](CHANGES.md) 与 [`NOTICE`](NOTICE)。
> 官方功能与支持请以上游仓库为准。
>
> 公开副本：<https://github.com/bruceleezqbx/minicpm-ocr-workbench>

---

## 1. 现状一览

| 组件 | 版本 / 路径 | 说明 |
|---|---|---|
| Ollama | 0.40.12 便携版 | `E:\OCR\sources\ollama-0.40.12\ollama.exe`，未安装系统服务 |
| 推理后端 | CUDA（`cuda_v12` 库，独显 GTX 1050 Ti, compute 6.1） | 驱动已升级到 581.57，见第 4 节 |
| 主模型 | `MiniCPM-OCR-1_0-Q8_0.gguf`（811 MB） | 752M 参数，Q8_0 |
| 视觉投影 | `mmproj-model-f16-4x.gguf`（901 MB） | 4× downsample 模式 |
| DSpark draft | `dspark-MiniCPM-OCR-1_0-Q8_0.gguf`（327 MB） | 推测解码，实测接受率 0.07–0.60 |
| SDK | `minicpm-ocr` 1.0.3 | `E:\OCR\.minicpm-ocr\Scripts\minicpmvocr.exe` |
| 版面检测 | PP-DocLayoutV3（paddlex 3.4.2 + paddlepaddle 3.3.1） | `%USERPROFILE%\.paddlex\official_models\PP-DocLayoutV3` |
| 服务地址 | `http://127.0.0.1:18499` | 模型名 `minicpm-ocr` |
| Word 导出 | Pandoc 3.13 便携版 | `E:\OCR\sources\pandoc\pandoc-3.13\pandoc.exe`，公式转 Word 原生公式 |
| 桌面壳 | pywebview 6.2.1 + 系统 Edge WebView2 | `E:\OCR\.desktop`，双击 `start_desktop.bat` 即用 |

实测单页（1240×1754，正文+5×5 表格+公式+手写签名+印章）：
**版面 4.6s + 识别 72s = 76.7s/页，15/15 区域全部成功，0 失败**。

---

## 2. 日常使用

```powershell
# ① 启动服务（后台常驻，端口 18499）
pwsh -File E:\OCR\scripts\start-ollama.ps1 -Mode gpu

# ② 解析文档（默认只跑 1 页做冒烟验证，加 -Full 跑整份）
pwsh -File E:\OCR\scripts\parse.ps1 -Input E:\OCR\work\sample_doc.png
pwsh -File E:\OCR\scripts\parse.ps1 -Input D:\扫描件\合同.pdf -Output D:\扫描件\合同.md -Full

# ③ 只想确认服务活着
curl http://127.0.0.1:18499/api/version      # {"version":"0.40.12"}
curl http://127.0.0.1:18499/api/tags         # 应含 minicpm-ocr:latest
```

`parse.ps1` 会自动做三件事，缺一不可：

- `FLAGS_use_mkldnn=0` —— paddle 3.3.1 的 oneDNN(PIR) 路径与 PP-DocLayoutV3 不兼容，
  否则报 `ConvertPirAttribute2RuntimeAttribute not support`；
- 解析前 `ollama stop minicpm-ocr` —— 先卸载模型给 PaddleX 让出 ~2.4GB 内存
  （本机 16GB 常被其他程序占满），识别阶段再自动加载一次；
- `engine.num_ctx=2048` —— 4GB 显存装不下 8192 上下文，会 OOM。

常用参数：`-Ctx`（上下文长度）、`-Workers`（并发，Ollama 单槽位保持 1）、
`-Threads`（Paddle 线程数）、`-KeepModel`（连续批处理时保留模型不卸载）。

---

## 3. 目录结构

```
E:\OCR
├─ .minicpm-ocr\          Python 3.13 venv（1.0 SDK + paddlex + paddlepaddle）
├─ .jev-score\            Python 3.13 venv（官方 jev_score 打分服务层）
├─ .jev-render\           Python 3.13 venv（playwright 1.62.0 + KaTeX 渲染环境）
├─ .desktop\              Python 3.13 venv（pywebview 桌面壳）
├─ models\
│  ├─ MiniCPM-OCR-1.0-gguf\   三个 GGUF 源文件 + Modelfile
│  ├─ MiniCPM-OCR-Jev-gguf\   Jev Q4_K_M + mmproj
│  └─ ollama\                  Ollama 模型库（注册后的副本，2.0GB）
├─ sources\
│  ├─ ollama-0.40.12\     Ollama 便携版
│  ├─ llama-b12032\       llama.cpp 预编译（CUDA 12.4）+ CUDA 运行时 DLL
│  ├─ pandoc\pandoc-3.13\ Pandoc 便携版（Word 原生公式导出用，免管理员）
│  └─ MiniCPM-OCR-main\   官方仓库源码（含 jev_score 服务层与渲染器）
├─ scripts\
│  ├─ start-ollama.ps1     启动 1.0 服务（gpu / vulkan / cpu 模式）
│  ├─ parse.ps1            1.0 一键解析
│  ├─ build-frontend.ps1   前端生产构建 + 补 pdfjs 资源 + 产物自检
│  ├─ desktop_app.py       桌面壳总控（清残留 → 拉服务 → 探活 → 开窗 → 关窗停服务）
│  ├─ start-jev-engine.ps1 启动 Jev 引擎（llama-server）
│  ├─ start-jev-score.ps1  启动 Jev 打分服务
│  ├─ jev_loop.ps1         读判闭环总入口（解析 + 渲染 + 打分 + 报告）
│  ├─ verify_jev.py        官方三例验证（分数口径）
│  ├─ score_blocks.py      对一次解析的每个块打分并出报告
│  ├─ category_probe.py    类别敏感性对照实验
│  ├─ render_check.py      渲染保真度检查
│  ├─ check_backend.py     1.0 单区域识别连通性验证
│  ├─ make_sample.py       生成测试样例图
│  ├─ fetch-models.ps1     断点续传下载三个 GGUF
│  ├─ fetch-ollama.ps1     下载并解压 Ollama
│  ├─ apply_license_notices.py  给改过的上游文件批量加 Apache-2.0 §4(b) 改动声明
│  ├─ normalize_eol.py     把被改文件行尾统一回 LF（与上游一致）
│  ├─ make_patch.py        生成并自证 upstream-local.patch
│  └─ health_check.ps1     全链路自检（静态 + 动态）
├─ runs\                   每次解析的产物：summary.json / per_page_metrics.csv / 分页 Markdown / 裁块
├─ logs\                   ollama-gpu.log、jev-engine.log、jev-score.log
├─ work\                   样例、输出、质检报告
├─ .git\                   本机层的 git 仓库（上游副本与模型权重不入库）
├─ start_desktop.bat       ★ 桌面版一键入口（双击这个）
├─ upstream-local.patch    本机改造的标准 unified diff（可重放到新的上游检出上）
├─ CHANGES.md              本机改造清单（兼作 Apache-2.0 §4(b) 声明索引）
├─ LICENSE                 Apache License 2.0（与上游一致）
├─ NOTICE                  归属声明：改编自 OpenBMB/MiniCPM-OCR，Copyright OpenBMB
└─ README.md
```

---

## 4. 推理后端：CUDA / Vulkan / CPU

**现状：驱动已升级到 581.57（CUDA 13.0），CUDA 路径已可用，默认用 `-Mode gpu`。**

之前驱动是 560.94（CUDA 12.6），Ollama 自带的 `cuda_v12` 库是更新的工具链编译的（内含新版本 PTX），
旧驱动无法 JIT，直接报：

```
CUDA error: the provided PTX was compiled with an unsupported toolchain.
  current device: 0, in function ggml_cuda_kernel_can_use_pdl
```

升级驱动后该错误消失，日志确认：

```
llama_prepare_model_devices: using device CUDA0 (NVIDIA GeForce GTX 1050 Ti) - 2201 MiB free
inference compute id=0 library=CUDA compute=6.1 libdirs=ollama,cuda_v12 driver=13.0
```

**注意仍要显式指定 `cuda_v12` 库**（脚本已写死 `OLLAMA_LLM_LIBRARY=cuda_v12`）：
CUDA 13 官方已移除 Maxwell/Pascal/Volta 支持，1050 Ti 是 sm_61，
用 `cuda_v13` 构建会报 `no kernel image is available for execution`。

### 三种后端实测（同一页样例、ctx 2048、15 个识别区域）

| 后端 | 整页耗时 | 识别耗时 | 每区域 | 输出 |
|---|---|---|---|---|
| CUDA `cuda_v12` | 80.6s | 77.2s | 5.15s | 与 Vulkan **逐字节一致** |
| Vulkan | 76.7s / 94.3s | 72.0s / 89.9s | 4.8–6.0s | 同上 |
| CUDA ctx 4096 | 107.8s | 102.6s | 6.84s | 同上 |

CUDA 与 Vulkan 在这张卡上基本持平（Pascal 算力弱，瓶颈在带宽而非后端），
差异在运行间抖动范围内。三者输出完全相同，说明后端不影响识别质量。

### 上下文长度与显存

- `num_ctx=2048` → 显存 2201–3357 MiB 富余，**推荐默认值**；
- `num_ctx=4096` → 显存冲到 **3930 / 4096 MiB**，几乎顶满，且单页慢约 33%，不划算；
- `num_ctx=8192` → 视觉投影（0.9GB）分配失败，OOM。

### 想彻底用 CUDA 13

把驱动升到 581 之后，**这个卡依然用不了 CUDA 13 构建**（Pascal 已不被 CUDA 13 支持），
所以保持 `cuda_v12` 即可。需要验证时可用 `-Mode cuda13`，大概率报 `no kernel image`。

### 纯 CPU 兜底

`-Mode cpu`：16GB 内存 + 24 线程可跑，但速度约为 GPU 的 1/5～1/10，
仅在驱动出问题时使用。

---

## 5. Jev 质检服务（读判分离）

### 它是什么

MiniCPM-OCR Jev 是 2B 的**结果判别模型**（`Qwen3_5` 主干 + `[2,2048]` 二分类打分头，权重里**没有 `lm_head`**，物理上不会生成文本）。
输入「原图块 + 待判 OCR 文本 + 文本渲染图」三元组，输出 0~1 的一致性分数。

用途：解析模型把「数量 300」读成「数量 30」时，表格看着照样整齐、总额照样对，
只有独立判别模型能发现这种**读起来通顺但与原图不符**的错误。

### 本机部署形态

| 组件 | 版本 / 路径 | 说明 |
|---|---|---|
| 推理引擎 | llama.cpp **b12032** 预编译（CUDA 12.4） | `E:\OCR\sources\llama-b12032\llama-server.exe`，端口 18498 |
| CUDA 运行时 | `cudart-llama-bin-win-cuda-12.4-x64.zip` | 单独一个压缩包，必须解压到引擎目录，否则静默退回 CPU |
| 权重 | `MiniCPM-OCR-Jev-Q4_K_M.gguf`（1215MB）+ `mmproj-model-f16.gguf`（640MB） | ModelScope 下载 |
| 打分服务 | 官方 `jev_score`（纯 Python） | 端口 18501，`POST /v1/score` |
| 渲染环境 | playwright 1.62.0 + KaTeX 0.16.47 + Pillow 12.3.0 | 独立 venv `E:\OCR\.jev-render` |

**为什么不用 Ollama 跑 Jev**：官方 SKILL 明确写了，Ollama 0.40.11/0.40.12 自带的 llama.cpp 是 0.7.x，
**不认识这个 decision 模型**。我验证过：本机 Ollama 的 `libllama-server-impl.dll` 只有通用的
`decision model type` 字符串，没有 `minicpm-ocr-jev`；而预编译的 b12032 里
`llama-common.dll` 同时含 `minicpm-ocr-jev` 与 `openbmb-minicpm-ocr-jev` → 直接可用，**不需要编译**。

### 官方样例验证（唯一客观的"装对了"标准）

`scripts\verify_jev.py` 打官方随包的三块样例，与 `case.json` 里的参考值比对（容差 0.02）：

| case | 类别 | 参考值 | 实测 | 偏差 |
|---|---|---|---|---|
| 01_text_putnam | text | 0.00702 | 0.00320 | 0.0038 |
| 02_formula_putnam | formula | 0.96552 | 0.96931 | 0.0038 |
| 03_table_gb_standard | table | 0.00116 | 0.00115 | 0.00001 |

**全部 PASS**。CPU 与 GPU 两种模式都跑过，结论一致。

### 读判闭环

```powershell
# 一条命令：1.0 解析 -> 渲染 -> Jev 打分 -> 报告
pwsh -File E:\OCR\scripts\jev_loop.ps1 -Input E:\OCR\work\sample_doc.png
# 批量整份
pwsh -File E:\OCR\scripts\jev_loop.ps1 -Input D:\扫描件\合同.pdf -Full
```

产物：`E:\OCR\work\jev_report.md`（人看）+ `jev_report.json`（机读）。
样例页 15 块 → 14 块打分（`seal` 版面无对应类别，按官方口径跳过）、渲染 14/14 成功、
打分耗时约 22 秒。

### 闭环结果长什么样

```
| 9  | table          | table   | 0.98176 | 通过 | <table><tr><td>序号</td>…      |
| 11 | display_formula| formula | 0.19296 | 建议复核 | Total = sum(q_i * p_i) + 0.05%… |
| 12 | display_formula| formula | 0.03438 | 建议复核 | T = \backslash \text{frac}\{…   |
```

两个公式块被判为需复核。用 `scripts\category_probe.py` 做对照实验后可以区分二者：

| 块 | 按 formula 打分 | 按 text 打分 | 结论 |
|---|---|---|---|
| 010 | 0.19636 | 0.90182 | **版面类别误标**：图里其实是 ASCII 文本，被版面模型判成公式，公式模式渲染后与原图不符 |
| 011 | 0.03235 | 0.01379 | **真阳性**：识别结果本身退化成 `\backslash \text{frac}\{…`，Jev 正确报警 |

### Jev 的边界（务必知道）

- **只吃块级裁图，不吃整页**。整页必须先切块再逐块打分。
- 分数的含义是「文本与它渲染出来的样子是否与原图相符」，**不等于语义正确**。
  官方自己有个表格样例，人工确认的原文只得 0.047（因为渲染版式与原图不同）。
- **没有官方阈值**，阈值属于调用方。报告里的 0.5 只是给个提示线。
- 字体/行距会改分数。本机是 Windows + Segoe UI，渲染出的图与官方参考渲染
  尺寸略有差异（文本类宽度差约 20px），因此**绝对值与官方公布值可能差在第三位小数**，
  排序与判别力不受影响。
- 官方 SKILL 给的 llama.cpp/Ollama 显存下限是 **≥8GB**，本机 4GB 低于该下限，
  分数已用官方样例校准过，但属于"验证可用、未做压力测试"。

---

## 6. Web 工作台（官方 webdemo + Jev 集成）

界面就是截图那个 **官方 OCR Playground**（OpenBMB 仓库里的 `webdemo/`），本机把它跑起来并接上了 Jev。

### 五个服务

| 服务 | 地址 | 说明 |
|---|---|---|
| 1.0 识别 | http://127.0.0.1:18499 | Ollama 0.40.12 + `cuda_v12`（GPU） |
| Jev 判别引擎 | http://127.0.0.1:18498 | llama.cpp b12032 预编译，**CPU**（`-ngl 0`），与 1.0 共存 |
| Jev 打分服务 | http://127.0.0.1:18501 | 官方 `jev_score`，`/v1/score` |
| Web 后端 | http://127.0.0.1:8966 | 官方 webdemo backend（FastAPI） |
| Web 前端 | http://127.0.0.1:5173 | Vite dev server |

```powershell
# 一键全起
pwsh -File E:\OCR\scripts\start-ocr-workbench.ps1
# 然后打开
start http://127.0.0.1:5173/playground/document-parse
```

### 做了哪些本机改造（都在 `E:\OCR\sources\MiniCPM-OCR-main` 副本里）

| 文件 | 改动 |
|---|---|
| `webdemo/backend/jev_quality.py`（新增） | 解析完成后按块调 Jev 打分，把 `prob_1` 写进 `crop_blocks[].jev_score` |
| `webdemo/backend/jev_regenerate.py`（新增） | `POST /api/jev/regenerate`：裁块 → 1.0 重识别 → 渲染 → Jev 重新打分 |
| `webdemo/backend/word_export.py`（新增） | `POST /api/export/word`：Markdown → pandoc → 公式是 Word 原生公式（OMML），见第 7 节 |
| `webdemo/backend/server.py` | 新增 `/api/jev/regenerate`、`/api/export/word` 路由；`_block_to_api` 在没有 TTS 分时用 `jev_score` 当 `score` |
| `webdemo/backend/document_jobs.py` | 解析任务结束后触发 Jev 打分 |
| `webdemo/backend/page_fleet.py` | 裁块文件名随 block 带出，供 Jev 使用 |
| `webdemo/backend/model_manager.py` | `OCRWEB_SAVE_ARTIFACTS=1` 时把裁块与页面图落盘 |
| `webdemo/frontend/.../imageParseFeatureFlags.ts` | 复核入口默认打开（官方默认关闭），可用 `VITE_IMAGE_PARSE_REVIEW=false` 关回 |
| `webdemo/frontend/.../ImageParseResultPane.tsx` | 标准模式也开放复核面板（官方只给算法流水线模式开） |
| `webdemo/frontend/.../imageParseRegenerationRequest.ts` | 本机重识别走 `/api/jev/regenerate` 而不是云端 `tts_block` |
| `webdemo/frontend/.../useImageParseRegeneration.ts` | 本机不校验云端页面凭证与 API Key |
| `webdemo/frontend/.../ImageParseUploadSurface.tsx` | 上传 input 由 `hidden` 改 `sr-only`（自动化可定位） |
| `webdemo/frontend/.../imageParseExport.ts` | 新增 `word-math` 格式，走本机 `/api/export/word` |
| `webdemo/frontend/.../ImageParseDownloadMenu.tsx` | 下载菜单新增「Word（公式可编辑）」菜单项 |
| `webdemo/frontend/.../i18n/messages/playground.ts` | 下载提示与新手引导文案说明两种 Word 导出的区别 |
| `webdemo/frontend/vite.config.ts` | 代理补上 `/api/jev`、`/api/export` |

### 效果

- 解析完右侧多出 **「To review」标签 + 红色徽标**，数字就是 Jev 判出的低分块数；
- 复核面板逐块列出 Jev 一致性分数（0% / 2% 这种），官方 UI 的低分标红与复核筛选直接生效；
- 每个低分块有 **「重生成此块」** 按钮：点一下就重识别 + 重新打分，并排显示「当前最佳结果 / 原始结果」；
- 本机实测：15 块页面 → 14 块打分（`seal` 无对应类别跳过），两个公式块被判 0% / 2%，
  点重生成后徽标从 2 变 1。

### 本机适配要点

- 官方 5 个 bash 脚本（`env.sh` / `setup_env.sh` / `prepare_upright_models.sh` /
  `start_local_worker.sh` / `start_upright_service.sh`）改写成 PowerShell（`E:\OCR\scripts\start-webdemo-*.ps1`）；
- 布局检测走 CPU（`OCR_LAYOUT_DEVICE=cpu`）+ `FLAGS_use_mkldnn=0` 绕开 paddle oneDNN(PIR)；
- 旋转自适应关闭（`OCR_UPRIGHT_WORKERS=0`），省掉 3 个 PP-* 模型的下载；
- 识别指向本机 Ollama（`OCR_ENGINE_TYPE=ollama`），Ollama 的 OpenAI 兼容接口带图可用；
- 前端依赖走 npmmirror 源（`corepack pnpm install --registry https://registry.npmmirror.com`）。

---

## 7. Word 导出：公式可编辑（Pandoc）

### 先定性：公式不一致不是"缺 LaTeX"

下载出来的 Word 里公式是 `\frac{...}` 这种源码，跟预览区渲染出来的样子不一样——
这**不是**本机缺 LaTeX 造成的，也不需要装任何 LaTeX 发行版。

根因在官方前端自己的导出实现（`frontend/src/pages/playground/utils/imageParseWord.ts`）：
它的公式分支明确写着"保留 LaTeX 源码为纯文本"。也就是说，官方前端导出的 docx
**设计上**就是 LaTeX 源码，而不是 Word 公式对象。装 TeX Live 也不会改变它。

### 方案：加一个走 Pandoc 的导出格式

本机新增了 **「Word（公式可编辑）」** 格式（格式 ID `word-math`），
走后端 `POST /api/export/word`，链路是：

```
Markdown ──► HTML 表格 → pipe 表格 ──► pandoc -f markdown+tex_math_dollars -t docx ──► docx
```

关键点：

- **不需要 LaTeX**。pandoc 自带 LaTeX 数学 → OMML（Word 原生公式）的转换器，
  不调用外部 tex 引擎；
- **HTML 表格要先转 pipe 表格**。pandoc 的 markdown reader 不认 `<table>`，
  `webdemo/backend/word_export.py` 里的 `_TableParser` 把 HTML 表格拆成行/单元格再转成 pipe 格式；
- **图片要去掉**。远程图片链接会让 pandoc 抓取失败、整份导出一起挂掉，
  所以导出按 `full → no_images → plain` 三级降级，任一级成功即返回。

### 两种 Word 导出对比（同一份样例解析结果，两份文件都是从工作台点「下载」实际下载下来的）

| 检查项 | 官方前端导出（Word） | 本机新增（Word 公式可编辑） |
|---|---|---|
| Word 原生公式 `m:oMath` | **0** | **2**（另含 2 个 `m:oMathPara`，公式独立成行） |
| Word 真实表格 `w:tbl` / 行数 | 1 / 5 | 1 / 5（一致） |
| 残留 LaTeX 源码 | `\backslash`×2、`\text`×6 | **0** |
| 文件大小 | 10.6 KB（10823 字节） | 11.8 KB（12046 字节） |

官方那份 docx 里的公式段落实际长这样（**纯文本 LaTeX 源码**）：

```
\text{Total}=\text{sum}(q_{-}i*p_{-}i)+0.05%\ast\text{Days}\ast\text{Total}
T=\backslash\text{frac}\{\backslash\text{sum}_{-}\{i=1\}^{\wedge}\{n\}q_{-}i p_{-}i\}\{1-r\}
```

Pandoc 那份里同样的内容位于 `m:oMath` 节点中，Word / WPS 打开是**公式对象**，可双击继续编辑。

> 两种格式都是 `.docx`，连续下载两次时第二个会被浏览器改名成 `sample_doc1.docx`，别认错。

### 怎么用

界面里：解析完成 → 右上角「下载」菜单 → 选 **「Word（公式可编辑）」**。
（菜单里现在有四项：Markdown / JSON / Word / Word（公式可编辑）。）

也可以直接调后端：

```powershell
# body.json 形如 {"markdown": "<解析出的 Markdown>", "name": "sample_doc.png"}
curl.exe -sS --noproxy 127.0.0.1 -o out.docx -w "%{http_code}" `
  -H "Content-Type: application/json" --data-binary "@body.json" `
  http://127.0.0.1:8966/api/export/word
```

样例请求体已备好：`E:\OCR\work\export-word-body.json`（就是这次样例页解析出的 Markdown）。
直接跑上面那条命令 → `HTTP 200`、11.8 KB docx、2 个 `m:oMath` 原生公式、1 个 5 行表格、0 处残留 LaTeX。

本机实测：从工作台点一次「Word（公式可编辑）」→ 后端 `POST /api/export/word 200 OK`，
2.1 秒产出 11.8 KB docx，落到桌面。

### Pandoc 从哪来

GitHub 直连下不动，所以用 `gh-proxy.com` 下的官方 zip 解压到
`E:\OCR\sources\pandoc\pandoc-3.13\pandoc.exe`，**免管理员、不写注册表、不改 PATH**。

后端按这个顺序找 pandoc：环境变量 `OCR_PANDOC` → 便携版路径 →
`C:\Program Files\Pandoc` → `AppData\Local\Pandoc` → PATH。
要用别的版本，设 `OCR_PANDOC` 环境变量指过去即可。

> 附带的说明：pandoc 导出的是 **OMML**，Word / WPS 打开后公式是公式对象、可双击继续编辑；
> 但它不保留预览区 KaTeX 的字号与间距，与浏览器预览不会像素级一致。

---

## 8. 桌面版（start_desktop.bat）

### 怎么用

双击 `E:\OCR\start_desktop.bat`，一条命令做完所有事：

1. **清理残留** —— 占端口的旧进程、Ollama 加载失败留下的僵尸 `llama-server`
2. **拉起服务** —— 1.0 识别 / Jev 引擎 / Jev 打分 / Web 后端，逐个探活
3. **弹启动页** —— 逐行显示每个服务的状态和进度条
4. **切到工作台** —— 全部就绪后窗口自动跳到工作台
5. **关窗即停** —— 只停掉这次自己拉起来的服务，之前就在跑的保留

### 桌面壳是什么

pywebview 6.2.1 + 系统自带的 **Edge WebView2 Runtime**（本机 156.0.4314.58），
不额外下载 Chromium，独立 venv 在 `E:\OCR\.desktop`。
窗口 1440×920，最小 1024×680。

### 下载：桌面壳不能靠浏览器那套

**现象**：桌面壳里点「下载」的四个选项（Markdown / JSON / Word / Word 公式可编辑），
点了完全没反应，也没有新建下载任务；同一个页面在浏览器里却是好的。

**根因**：桌面壳用的是 Edge WebView2，而 **pywebview 没有接 `CoreWebView2.DownloadStarting`**。
WebView2 在没有下载处理器时会把下载**静默取消**。实测（`scripts\diagnose_webview_download.py`，
可单独跑，会在 Downloads 目录里试两种方式并打印结论）：

| 方式 | 结果 |
|---|---|
| blob URL + `<a download>` 点击 | 不落盘 |
| 跳转到带 `Content-Disposition` 的 URL | 不落盘 |

两条路都不通，所以不是前端哪个分支写错了，而是**桌面壳里根本没有浏览器下载机制可用**。

**解法**：桌面壳改走 pywebview 官方的 **JS ↔ Python 桥**（`js_api`）。

```
浏览器：Blob → objectURL → <a download> → 系统下载弹窗          （保持原样，一行没改）
桌面壳：Blob → base64 → window.pywebview.api.save_bytes() → Python 直接写盘
```

- 桌面壳打开工作台时带 `?shell=desktop`（`scripts\desktop_app.py`），
  前端在模块加载时同步判定，**浏览器里不会为等桌面桥白等几秒**；
- Python 侧 `DesktopApi.save_bytes()` 把文件写到 `%USERPROFILE%\Downloads`，
  同名文件自动加序号不覆盖；目录可用环境变量 `OCR_DESKTOP_DOWNLOAD_DIR` 改；
- 落盘后前端弹 toast 显示完整路径，用户知道文件去哪了；
- 拿不到 JS 桥时直接报「文件生成失败」，而不是像以前那样**毫无反应**。

涉及文件：`webdemo/frontend/.../imageParseExport.ts`、`hooks/useImageParseDownload.ts`、
`i18n/messages/playground.ts`（新增 `imageParseDownloadSaved`）、`scripts/desktop_app.py`。

#### 实测（真桌面窗口，WebView2）

真开一个 pywebview 窗口加载工作台 → 用 DataTransfer 塞样例图 → 走完整解析 →
逐个点下载菜单的四个选项，结果：

| 点击项 | 落盘文件（Downloads） | 大小 | 内容 |
|---|---|---|---|
| `JSON .json` | `sample_doc.json` | 12976 B | 布局块 + Markdown 快照 |
| `Markdown .md` | `sample_doc(1).md` | 1372 B | — |
| `Word .docx` | `sample_doc(3).docx` | 10824 B | 官方前端导出：`oMath=0`，残留 LaTeX 源码 8 处 |
| `Word（公式可编辑） .docx` | `sample_doc(4).docx` | 12045 B | Pandoc 导出：`oMath=2`、`oMathPara=2`、残留 0 |

同名文件自动加序号不覆盖。浏览器路径回归验证：同一页面在 Chrome 里点
「Word（公式可编辑）」仍走系统下载，`sample_doc.docx`（12045 B）正常落盘、后端
`POST /api/export/word 200`。

### 为什么是 4 个服务而不是 5 个

生产模式：前端 `pnpm build` 成静态文件后，**由 Web 后端自己托管**（同源 `/api`，不需要 proxy，也不需要 CORS），
所以 Vite dev server 不用起了 —— 少一个进程、省内存、启动更快、不会因为 dev server 崩了整个用不了。

后端的静态托管加在 `webdemo/backend/server.py`：

| 路径 | 处理 |
|---|---|
| `/assets` `/voices` `/pdfjs` | `StaticFiles` 挂载 |
| 其它未知路径 | 回 `index.html`（SPA），`/playground/*` 直接刷新也能进 |
| `/api/*` `/v1/*` 未知路径 | 仍然 404 JSON，不会把 HTML 当接口响应 |
| 路径穿越 | `is_relative_to` 挡住；实测 `/../server.py`、`/%2e%2e/server.py`、`/..%2fserver.py`、`/assets/../../server.py` 四种写法都只回 index.html，无源码泄漏 |

### 命令行用法

| 场景 | 命令 |
|---|---|
| 双击启动 | `E:\OCR\start_desktop.bat` |
| 只起服务不开窗 | `E:\OCR\.desktop\Scripts\python.exe E:\OCR\scripts\desktop_app.py --serve-only` |
| 改前端代码时用开发模式 | 同上加 `--dev`（额外起 Vite，从 5173 进，可热更新） |
| 无人值守自检 | 同上加 `--selftest`（开窗 → 读页面状态 → 关窗） |
| 退出后保留服务 | 同上加 `--keep` |
| **全链路体检** | `pwsh -File E:\OCR\scripts\health_check.ps1`（加 `-Start` 会先拉起服务再查） |

### 改了前端要重新构建

```powershell
pwsh -File E:\OCR\scripts\build-frontend.ps1
```

它做三件事：`pnpm build`（`tsc --noEmit && vite build`）→ 补 pdf.js 的
`cmaps` / `standard_fonts` / `wasm` → 产物自检。

两个坑：

- **`viteStaticCopy` 没把 pdfjs 那三个目录落进 `dist/`**，脚本里手工补的。
  缺了的话 PDF 预览的 CJK 字会显示不出来。
- **界面默认语言在构建时定**（脚本默认 `zh-CN`，可用 `-Locale en-US` 改）。
  官方 `.env.example` 是 `en-US`，不定的话首屏先按英文渲染、再被浏览器语言探测改一次，
  会闪一下英文，解析中途还可能因为整页刷新把任务取消掉。

### 顺带修掉的两个真 bug

1. **`start-jev-engine.ps1` 里 `-ngl 99` 是写死的**，声明的 `-Ngl` 参数根本没被用上
   → Jev 一直跑在 **GPU** 上，和"4GB 显存、Jev 走 CPU"的规划冲突。
   修好后 Jev 回到 CPU，**显存从 3798 MiB 降到 2226 MiB**，给 1.0 腾出约 1.6GB。
2. **`imageParseExport.ts` 引用了 `input.name`**，但公共入参类型 `ImageParseExportInput` 里没有 `name` 字段
   （它只声明在 hook 的接口上）。Vite dev server 不做类型检查所以运行时没暴露，
   `tsc --noEmit` 一抓一个准。

### 桌面版实测（冷启动）

全杀进程后从零拉起：

| 步骤 | 结果 |
|---|---|
| 清理残留 | 占端口旧进程清掉 |
| 1.0 识别 | 就绪（18499） |
| Jev 引擎 | 就绪（18498，CPU 模式，进程参数确认 `-ngl 0`） |
| Jev 打分 | 就绪（18501） |
| Web 后端 | 就绪（8966） |
| 窗口 | 打开并自动切到 `http://127.0.0.1:8966/playground/document-parse` |
| 页面自检 | `title='MiniCPM-OCR'`、`#root` 已渲染、上传控件存在 → **通过** |
| 关窗 | 本次拉起的 4 个服务全部停止，无残留 |

生产模式下的完整业务链路（浏览器直连 8966 验证，与桌面壳同一个后端）：

上传样例图 → 解析完成（左侧块框叠加 + 右侧 Markdown 预览）→ 「待复核 2」Jev 徽标出现 →
下载菜单 →「Word（公式可编辑）」→ `POST /api/export/word 200` → 桌面落地 12046 字节 docx。

---

## 9. 许可与合规

### 上游许可

[OpenBMB/MiniCPM-OCR](https://github.com/OpenBMB/MiniCPM-OCR) 整体采用 **Apache License 2.0**，
**涵盖代码、文档，以及 MiniCPM-OCR 1.0 与 MiniCPM-OCR Jev 的模型权重**。
上游 README 的 License 章节原文：

> The entire project is released under the [Apache License 2.0](./LICENSE),
> including code, documentation, and model weights for MiniCPM-OCR 1.0 and MiniCPM-OCR Jev.

仓库根 `LICENSE` 与 `sdk/LICENSE` 都是同一份 Apache-2.0 全文；
GitHub API 也确认 `"license": {"spdx_id": "Apache-2.0"}`。

### 本仓许可

本机部署层同样以 **Apache License 2.0** 发布 —— `E:\OCR\LICENSE` 就是上游那份原文（逐字节一致，
自检脚本会校验这一点）。理由很直接：本层包含并改编了上游的 Apache-2.0 代码，
按 Apache-2.0 第 4 条，衍生作品必须沿用同一许可。

### Apache-2.0 第 4 条要求的落实

| 条款要求 | 本仓怎么满足 |
|---|---|
| 4(a) 给接收者一份 License | `E:\OCR\LICENSE`（Apache-2.0 全文） |
| 4(b) 被修改的文件要有**醒目的改动声明** | 21 个被修改/新增的上游文件，头部都加了「本机改造 / Apache-2.0 §4(b)」声明；清单见 `CHANGES.md` |
| 4(c) 保留原有的版权与归属声明 | `NOTICE` 中保留 `Copyright OpenBMB` |
| 4(d) NOTICE 文件 | 上游没有 NOTICE 文件；本层新建 `NOTICE` 声明改编关系与归属 |

声明是幂等脚本批量加的（`scripts\apply_license_notices.py`），改动过的文件都过了
`tsc --noEmit` 与 Python 语法 + docstring 复验。

### 第三方组件

| 组件 | 许可 | 说明 |
|---|---|---|
| MiniCPM-OCR 1.0 / Jev 权重 | Apache-2.0 | 上游声明权重同许可 |
| Ollama 0.40.12 | MIT | `sources\ollama-0.40.12` |
| llama.cpp b12032 | MIT | `sources\llama-b12032` |
| Pandoc 3.13 | GNU GPL v2（官方 zip 内附 `COPYING.rtf`） | 单独可执行文件，未修改未链接 |
| Python / Node 依赖 | 各自原始许可 | 各 venv 与 `node_modules` 内自带 LICENSE |

### 版本控制

`E:\OCR` 是独立的 git 仓库（分支 `main`）。上游仓库副本**不入库**
（`sources/` 在 `.gitignore` 里），它的改动靠 `upstream-local.patch` 回溯——
这个补丁打过 `git apply --check`，并且实际 apply 后与当前副本逐字节一致。

```powershell
git -C E:\OCR log --oneline     # 查看本机层的提交历史
git -C E:\OCR status             # 工作区状态
```

---

## 10. 已知限制

1. **内存**：本机 16GB 被 AutoCAD / 微信 / QQ 等占满时，PaddleX 会报
   `MemoryError: bad allocation`。批量跑之前先关掉占内存的程序，或用 `-KeepModel` 之外
   的默认卸载策略（脚本已自动处理）。
2. **显存**：4GB 卡不支持 `num_ctx=8192`（视觉投影分配 0.9GB 时 OOM），4096 也会顶满 3930MiB，
   建议固定 2048。
3. **速度**：Vulkan + 单槽位约 4.8s/区域，一页 15 区域 ≈ 77s。批量处理建议夜间跑。
4. **paddle 版本**：官方 SKILL 建议 `paddlepaddle==3.2.1`，本机 3.13 解释器只能用 3.2.2/3.3.x，
   已装 3.3.1 并通过 `FLAGS_use_mkldnn=0` 绕过 oneDNN 兼容问题。
5. **网络**：本机 huggingface.co / hf-mirror.com 不可达，ModelScope 偶发 500。
   模型走 `hf-cdn.sufy.com`，Ollama 包走 `gh-proxy.com` 代理（脚本内已固化）。
6. **僵尸进程**：本机有 12 个 `llama-server.exe`（Ollama 早期加载失败留下的），
   `HasExited=True` 但进程对象还在，`taskkill` 返回 **Access is denied**，普通权限杀不掉。
   它们工作集 0MB，也没出现在 nvidia-smi 的计算进程里，**不占显存**，实测不影响使用。
   桌面版的清理逻辑按"端口"和"可执行文件路径"判断，不会去碰这些杀不掉的。
7. **桌面版窗口**：pywebview 用的是 Edge WebView2，本机装的是 156.0.4314.58。
   窗口关闭时桌面壳会停掉自己拉起的服务；如果进程被强杀，下次启动会先清残留再拉起。

---

## 11. 质量验证记录

样例图 `E:\OCR\work\sample_doc.png`（合成：中文正文 + 5×5 报价表 + 2 个公式 +
手写签名 + 红色印章 + 轻微倾斜/模糊），解析结果 `E:\OCR\work\out-ollama.md`：

- 标题输出为 `## 设备采购合同（样例）`；
- 正文、金额（1,286,400.00 / 壹佰贰拾捌万陆仟肆佰元整）、标准号（GB/T 2828.1-2012）逐字正确；
- 表格转成 HTML `<table>`，5 列 × 5 行数值全对；
- 公式转成 `$$...$$` LaTeX 块；
- 手写签名与红色印章文字均被识别。

---

## 12. 后续可做

- 换更强的卡（如 8GB+ 的 RTX 系列）后放开 `num_ctx=8192` 并开多 worker，可再快数倍；
- 把 Jev 的低分块自动回流成 1.0 的重识别候选（多候选打分择优，官方称 best-of-N）；
- 建本地 Web Demo（`webdemo/backend` + Node 22 前端）做交互式上传，并排显示原图/渲染图/分数；
- 换用官方 torch 版面检测（`ppdoclayout3_torch` + `PP-DocLayoutV3_safetensors`）彻底绕开
  paddle oneDNN 坑并降低内存占用；
- 批量脚本：按目录遍历 PDF，配合 `runs\<run>\per_page_metrics.csv` 汇总失败页。
