# MiniCPM-OCR 读判闭环：1.0 解析 -> 渲染 -> Jev 质检 -> 报告
#
# 本机只有 4GB 显存，1.0 与 Jev 不能同时占卡（Ollama 加载 mmproj 时需要 0.9GB，
# 而 Jev 常驻 3.1GB），所以脚本按阶段交替占用显卡：
#   阶段 1  卸载 1.0 -> 跑版面检测+识别 -> 产出裁块与逐块文本
#   阶段 2  起 Jev 引擎 -> 渲染每块文本 -> 逐块打分 -> 出报告
#
# 用法:
#   pwsh -File E:\OCR\scripts\jev_loop.ps1 -Input E:\OCR\work\sample_doc.png
#   pwsh -File E:\OCR\scripts\jev_loop.ps1 -Input D:\扫描件\合同.pdf -Full
param(
  [Parameter(Mandatory = $true)][Alias('Input')][string] $Doc,
  [string] $Out = '',
  [int] $Ctx = 2048,
  [switch] $Full,
  [double] $Threshold = 0.5
)
$ErrorActionPreference = 'Continue'
$root = 'E:\OCR'
$ollamaExe = "$root\sources\ollama-0.40.12\ollama.exe"
$llamaExe = "$root\sources\llama-b12032\llama-server.exe"
$gguf = "$root\models\MiniCPM-OCR-Jev-gguf\MiniCPM-OCR-Jev-Q4_K_M.gguf"
$mmproj = "$root\models\MiniCPM-OCR-Jev-gguf\mmproj-model-f16.gguf"
$renderPy = "$root\.jev-render\Scripts\python.exe"
$scorePy = "$root\.jev-score\Scripts\python.exe"
$enginePort = 18498
$scorePort = 18501

function Log($m) { Write-Output ("[{0}] {1}" -f (Get-Date -Format 'HH:mm:ss'), $m) }

function Stop-JevEngine {
  # 只杀我们这个 Jev 引擎，Ollama 自己的 runner 不动
  Get-CimInstance Win32_Process | Where-Object {
    $_.Name -match '^llama-server' -and $_.CommandLine -match 'MiniCPM-OCR-Jev'
  } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
  Start-Sleep -Seconds 2
}

function Wait-Health($url, $seconds) {
  for ($i = 0; $i -lt $seconds; $i++) {
    try {
      $r = Invoke-WebRequest -Uri $url -TimeoutSec 5 -UseBasicParsing
      if ($r.StatusCode -eq 200) { return $true }
    } catch { }
    Start-Sleep -Seconds 2
  }
  return $false
}

# ── 阶段 0：腾地儿 ──────────────────────────────────────────────────────────
Log "阶段 0：释放显存"
Stop-JevEngine
$env:OLLAMA_HOST = '127.0.0.1:18499'
& $ollamaExe stop minicpm-ocr 2>&1 | Out-Null
# 清掉上一次加载失败留下的 Ollama runner 僵尸（它们仍占着显存）
Get-CimInstance Win32_Process | Where-Object {
  $_.Name -match '^llama-server' -and $_.CommandLine -notmatch 'MiniCPM-OCR-Jev'
} | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 4
$free = (Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory / 1MB
Log ("可用内存 {0:n2} GB，显存占用 {1}" -f $free, (nvidia-smi --query-gpu=memory.used --format=csv,noheader))

# ── 阶段 1：1.0 解析（产出裁块 + 逐块文本）────────────────────────────────
Log "阶段 1：1.0 解析"
$env:PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK = 'True'
$env:FLAGS_use_mkldnn = '0'
$env:OMP_NUM_THREADS = '4'
$env:MKL_NUM_THREADS = '4'
$env:PYTHONIOENCODING = 'utf-8'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$setArgs = @('--set', "engine.num_ctx=$Ctx", '--set', "engine.max_model_len=$Ctx",
             '--set', 'pipeline.save_crops=true', '--set', 'pipeline.save_pages=true')
if (-not $Full) { $setArgs += @('--set', 'input.limit=1') }

$parseOut = if ($Out) { $Out } else { "$root\work\jev_loop_out.md" }
Set-Location $root
& "$root\.minicpm-ocr\Scripts\minicpmvocr.exe" parse --backend ollama `
  --server-url http://127.0.0.1:18499 --model minicpm-ocr `
  --device cpu --workers 1 `
  --layout-model "$env:USERPROFILE\.paddlex\official_models\PP-DocLayoutV3" `
  @setArgs --input $Doc --output $parseOut 2>&1 | Select-Object -Last 3 | Out-String | Write-Output
if ($LASTEXITCODE -ne 0) { Log "解析失败 exit=$LASTEXITCODE"; exit 1 }

$run = Get-ChildItem "$root\runs" -Directory | Sort-Object LastWriteTime -Descending | Select-Object -First 1
Log "解析产物: $($run.FullName)"

# ── 阶段 2：Jev 引擎 ───────────────────────────────────────────────────────
Log "阶段 2：启动 Jev 引擎"
Stop-JevEngine
& $ollamaExe stop minicpm-ocr 2>&1 | Out-Null
Start-Sleep -Seconds 3
$env:LLAMA_ARG_LOG_LEVEL = 'info'
$proc = Start-Process -FilePath $llamaExe `
  -ArgumentList @('-m', $gguf, '--mmproj', $mmproj, '-ngl', '99', '-c', "$Ctx",
                  '--host', '127.0.0.1', '--port', "$enginePort") `
  -WindowStyle Hidden -PassThru `
  -RedirectStandardOutput "$root\logs\jev-engine.log" -RedirectStandardError "$root\logs\jev-engine.err"
Log "llama-server PID=$($proc.Id)，等待就绪..."
if (-not (Wait-Health "http://127.0.0.1:$enginePort/health" 120)) {
  Log "Jev 引擎未就绪，见 $root\logs\jev-engine.log"; exit 1
}
Log "Jev 引擎就绪"

# 打分服务若未起则拉起
try { $h = Invoke-WebRequest -Uri "http://127.0.0.1:$scorePort/healthz" -TimeoutSec 5 -UseBasicParsing }
catch {
  Log "启动打分服务"
  $sdk = "$root\sources\MiniCPM-OCR-main\scripts\minicpm-ocr-jev\sdk"
  $env:JEV_BACKEND_CONFIG = "$root\scripts\jev\backends\llamacpp.yaml"
  $env:JEV_BACKEND_URL = "http://127.0.0.1:$enginePort"
  Start-Process -FilePath $scorePy -WorkingDirectory $sdk `
    -ArgumentList @('-m', 'uvicorn', 'jev_score.server:app', '--host', '127.0.0.1', '--port', "$scorePort", '--workers', '1', '--no-access-log') `
    -WindowStyle Hidden -RedirectStandardOutput "$root\logs\jev-score.log" -RedirectStandardError "$root\logs\jev-score.err"
  if (-not (Wait-Health "http://127.0.0.1:$scorePort/healthz" 120)) { Log "打分服务未就绪"; exit 1 }
}

# ── 阶段 3：渲染 + 打分 ────────────────────────────────────────────────────
Log "阶段 3：渲染并打分"
$report = "$root\work\jev_report.md"
& $renderPy "$root\scripts\score_blocks.py" --run $run.FullName --threshold $Threshold --out $report 2>&1 | Out-String | Write-Output
Log "完成，报告: $report"
exit 0
