# 启动 MiniCPM-OCR Jev 质检服务（Windows 便携版）
#   1) 引擎：llama-server b12032（预编译 CUDA 12.4）加载 Jev Q4_K_M + mmproj，端口 18498
#   2) 服务层：官方 jev_score（纯 Python），端口 18501
# 用法:
#   pwsh -File E:\OCR\scripts\start-jev.ps1              # 后台起两个服务
#   pwsh -File E:\OCR\scripts\start-jev.ps1 -Foreground  # 前台运行（便于看日志）
param(
  [switch] $Foreground,
  [int] $EnginePort = 18498,
  [int] $ScorePort = 18501,
  [int] $Ctx = 8192,
  # 0 = 纯 CPU（与 1.0 的 GPU 模型共存，本机默认）；99 = 全部上 GPU（更快，但要和 1.0 抢显存）
  [int] $Ngl = 0
)
$ErrorActionPreference = 'Continue'
$root = 'E:\OCR'
$llama = "$root\sources\llama-b12032\llama-server.exe"
$gguf = "$root\models\MiniCPM-OCR-Jev-gguf\MiniCPM-OCR-Jev-Q4_K_M.gguf"
$mmproj = "$root\models\MiniCPM-OCR-Jev-gguf\mmproj-model-f16.gguf"
$sdk = "$root\sources\MiniCPM-OCR-main\scripts\minicpm-ocr-jev\sdk"
$vpy = "$root\.jev-score\Scripts\python.exe"

foreach ($p in @($llama, $gguf, $mmproj, $vpy)) {
  if (-not (Test-Path $p)) { Write-Output "缺少: $p"; exit 1 }
}
New-Item -ItemType Directory -Force -Path "$root\logs" | Out-Null

# 4GB 显存放不下两个模型：Jev 上线前先把 Ollama 上的 1.0 模型卸载
$ollama = "$root\sources\ollama-0.40.12\ollama.exe"
if (Test-Path $ollama) {
  $env:OLLAMA_HOST = '127.0.0.1:18499'
  & $ollama stop minicpm-ocr 2>&1 | Out-Null
  Start-Sleep -Seconds 2
}

Write-Output "启动 Jev 引擎 (llama-server, port $EnginePort, ctx $Ctx, ngl $Ngl) ..."
$env:LLAMA_ARG_LOG_LEVEL = 'info'
& $llama -m $gguf --mmproj $mmproj -ngl $Ngl -c $Ctx --host 127.0.0.1 --port $EnginePort *>> "$root\logs\jev-engine.log"

Write-Output "引擎退出，检查 $root\logs\jev-engine.log"
exit 1
