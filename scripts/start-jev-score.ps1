# 启动 Jev 打分服务层（官方 jev_score，纯 Python；渲染图由调用方提供）
#   endpoint: POST http://127.0.0.1:18501/v1/score
#   health:   GET  http://127.0.0.1:18501/healthz
param(
  [int] $ScorePort = 18501,
  [int] $EnginePort = 18498
)
$ErrorActionPreference = 'Continue'
$root = 'E:\OCR'
$sdk = "$root\sources\MiniCPM-OCR-main\scripts\minicpm-ocr-jev\sdk"
$vpy = "$root\.jev-score\Scripts\python.exe"
if (-not (Test-Path $vpy)) { Write-Output "缺少 venv: $vpy"; exit 1 }

$env:JEV_BACKEND_CONFIG = "$root\scripts\jev\backends\llamacpp.yaml"
$env:JEV_BACKEND_URL = "http://127.0.0.1:$EnginePort"
$env:JEV_MAX_ITEMS = '64'
$env:PYTHONIOENCODING = 'utf-8'
# 官方口径：llama.cpp 的 prompt 由 GGUF 内置模板组装，无法回读校验，
# 启动自检会把它报成 "server_template"（不可校验）而不是绿灯。
# 若自检因该项拒绝启动，可设 JEV_ALLOW_UNVERIFIED=1 —— 但那意味着分数不可与官方公布值直接比较。
$env:JEV_ALLOW_UNVERIFIED = $env:JEV_ALLOW_UNVERIFIED

New-Item -ItemType Directory -Force -Path "$root\logs" | Out-Null
Set-Location $sdk
Write-Output "启动打分服务 $ScorePort -> 引擎 $EnginePort"
& $vpy -m uvicorn jev_score.server:app --host 127.0.0.1 --port $ScorePort --workers 1 --no-access-log *>> "$root\logs\jev-score.log"
