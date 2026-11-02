# 启动官方 webdemo 后端（Windows 适配版）
# 对应官方 bash: webdemo/backend/start_local_worker.sh
# 差异：不用 bash、布局检测走 CPU、关闭旋转自适应(OCR_UPRIGHT_WORKERS=0)、
#       识别服务指向本机 Ollama(18499)、paddle 关闭 oneDNN(PIR)。
param(
  [int] $Port = 8966,
  [string] $EngineUrl = 'http://127.0.0.1:18499',
  [string] $ServedName = 'minicpm-ocr',
  [int] $Threads = 4,
  [switch] $NoJev
)
$ErrorActionPreference = 'Continue'
$Jev = -not $NoJev
$repo = 'E:\OCR\sources\MiniCPM-OCR-main'
$backend = "$repo\webdemo\backend"
$py = 'E:\OCR\.minicpm-ocr\Scripts\python.exe'

$env:PYTHONNOUSERSITE = '1'
$env:OCRWEB_PYTHON = $py
$env:OCRWEB_DATA_DIR = 'E:\OCR\work\webdemo-data'
$env:OCR_SERVER_URL = $EngineUrl
$env:VLLM_URL = $EngineUrl
$env:OCR_SERVED_NAME = $ServedName
$env:OCR_ENGINE_TYPE = 'ollama'
$env:OCR_LAYOUT_MODEL_DIR = "$env:USERPROFILE\.paddlex\official_models\PP-DocLayoutV3"
$env:OCR_LAYOUT_DEVICE = 'cpu'
$env:OCR_LAYOUT_WORKERS = '1'
$env:OCR_LAYOUT_DEVICES = 'cpu'
# 旋转自适应：官方默认开会加载 3 个 PP-* 模型，本机没下载，关掉
$env:OCR_UPRIGHT_WORKERS = '0'
$env:OCR_UPRIGHT_DEVICE = 'cpu'
$env:OCR_UPRIGHT_DIR = "$repo\models\paddle_upright"
$env:OCR_PAGE_SLOTS = '4'
$env:OCR_CROP_WORKERS = '16'
$env:OCR_SHARED_CROP_POOL = '1'
$env:OCR_PAGE_ROLE = 'worker'
$env:PORT = "$Port"
# Jev 逐块质检：把 prob_1 填进 block["confidence"]，官方前端的低分标注/复核/一键重识别据此工作
$env:OCRWEB_JEV = if ($Jev) { '1' } else { '0' }
$env:OCRWEB_JEV_PYTHON = 'E:\OCR\.jev-render\Scripts\python.exe'
$env:OCRWEB_JEV_WORKER = 'E:\OCR\scripts\jev_render_score.py'
$env:OCRWEB_JEV_SCORE_URL = 'http://127.0.0.1:18501'
# Pandoc（便携版）：Word 导出用，公式转成 Word 原生 OMML
$env:OCR_PANDOC = 'E:\OCR\sources\pandoc\pandoc-3.13\pandoc.exe'
# Jev 需要模型实际看到的裁块与页面图
$env:OCRWEB_SAVE_ARTIFACTS = if ($Jev) { '1' } else { '0' }
# paddle 3.3.1 的 oneDNN(PIR) 与 PP-DocLayoutV3 不兼容
$env:FLAGS_use_mkldnn = '0'
$env:PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK = 'True'
$env:OMP_NUM_THREADS = "$Threads"
$env:MKL_NUM_THREADS = "$Threads"
$env:PYTHONIOENCODING = 'utf-8'
$env:CUDA_VISIBLE_DEVICES = ''

New-Item -ItemType Directory -Force -Path $env:OCRWEB_DATA_DIR, 'E:\OCR\logs' | Out-Null

# 端口上如果还挂着旧进程（任务被停掉时子进程常常会留下），先清掉再起
$stale = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'uvicorn server:app' -and $_.CommandLine -match "port $Port" }
foreach ($p in $stale) { Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue }
if ($stale) { Start-Sleep -Seconds 2; Write-Output "已清理 $($stale.Count) 个占用 $Port 的旧进程" }

Set-Location $backend
Write-Output "webdemo 后端 -> http://127.0.0.1:$Port (engine $EngineUrl / $ServedName)"
& $py -s -m uvicorn server:app --host 127.0.0.1 --port $Port --workers 1 *>> 'E:\OCR\logs\webdemo-backend.log'
