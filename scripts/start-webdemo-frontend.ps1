# 启动官方 webdemo 前端（Vite dev server）
# 对应官方: VITE_OCR_TARGET=http://127.0.0.1:8966 corepack pnpm dev --host --port 5173 --strictPort
param(
  [int] $Port = 5173,
  [string] $Target = 'http://127.0.0.1:8966'
)
$ErrorActionPreference = 'Continue'
$frontend = 'E:\OCR\sources\MiniCPM-OCR-main\webdemo\frontend'
Set-Location $frontend
$env:VITE_OCR_TARGET = $Target
$env:COREPACK_NPM_REGISTRY = 'https://registry.npmmirror.com'
$env:npm_config_registry = 'https://registry.npmmirror.com'
Write-Output "webdemo 前端 -> http://127.0.0.1:$Port  (后端 $Target)"
corepack pnpm dev --host --port $Port --strictPort *>> 'E:\OCR\logs\webdemo-frontend.log'
