# 一键启动 MiniCPM-OCR 读判工作台（本机版）
#
# 起的服务：
#   1.0 识别      Ollama 0.40.12        http://127.0.0.1:18499   (GPU, cuda_v12)
#   Jev 判别引擎  llama.cpp b12032      http://127.0.0.1:18498   (CPU, -ngl 0，与 1.0 共存)
#   Jev 打分服务  官方 jev_score        http://127.0.0.1:18501
#   Web 后端      官方 webdemo backend  http://127.0.0.1:8966
#   Web 前端      Vite dev server       http://127.0.0.1:5173/playground/document-parse
#
# 依赖（Word 公式可编辑导出用，走 pandoc）：
#   E:\OCR\sources\pandoc\pandoc-3.13\pandoc.exe
#
# 用法:
#   pwsh -File E:\OCR\scripts\start-ocr-workbench.ps1
param([switch] $NoJev)
$ErrorActionPreference = 'Continue'
$root = 'E:\OCR'
$logs = "$root\logs"
New-Item -ItemType Directory -Force -Path $logs | Out-Null

function Wait-Url($url, $seconds) {
  for ($i = 0; $i -lt $seconds; $i++) {
    try { $r = Invoke-WebRequest -Uri $url -TimeoutSec 4 -UseBasicParsing; if ($r.StatusCode -eq 200) { return $true } } catch { }
    Start-Sleep -Seconds 2
  }
  return $false
}

# 1) 1.0 识别服务
if (-not (Wait-Url 'http://127.0.0.1:18499/api/version' 4)) {
  Write-Host "[1/5] 启动 1.0 识别服务 (Ollama)..."
  Start-Process -FilePath 'pwsh' -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "$root\scripts\start-ollama.ps1", '-Mode', 'gpu') -WindowStyle Hidden
  Wait-Url 'http://127.0.0.1:18499/api/version' 60 | Out-Null
}

# 2) Jev 引擎（CPU）
if (-not $NoJev -and -not (Wait-Url 'http://127.0.0.1:18498/health' 4)) {
  Write-Host "[2/5] 启动 Jev 判别引擎 (llama.cpp, CPU)..."
  Start-Process -FilePath 'pwsh' -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "$root\scripts\start-jev-engine.ps1", '-Ngl', '0') -WindowStyle Hidden
  Wait-Url 'http://127.0.0.1:18498/health' 120 | Out-Null
}

# 3) Jev 打分服务
if (-not $NoJev -and -not (Wait-Url 'http://127.0.0.1:18501/healthz' 4)) {
  Write-Host "[3/5] 启动 Jev 打分服务..."
  Start-Process -FilePath 'pwsh' -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "$root\scripts\start-jev-score.ps1") -WindowStyle Hidden
  Wait-Url 'http://127.0.0.1:18501/healthz' 60 | Out-Null
}

# 4) Web 后端
if (-not (Wait-Url 'http://127.0.0.1:8966/health' 4)) {
  Write-Host "[4/5] 启动 webdemo 后端..."
  Start-Process -FilePath 'pwsh' -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "$root\scripts\start-webdemo-backend.ps1") -WindowStyle Hidden
  Wait-Url 'http://127.0.0.1:8966/health' 90 | Out-Null
}

# 5) Web 前端
if (-not (Wait-Url 'http://127.0.0.1:5173/' 4)) {
  Write-Host "[5/5] 启动 webdemo 前端..."
  Start-Process -FilePath 'pwsh' -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "$root\scripts\start-webdemo-frontend.ps1") -WindowStyle Hidden
  Wait-Url 'http://127.0.0.1:5173/' 90 | Out-Null
}

Write-Host ''
Write-Host '  读判工作台:  http://127.0.0.1:5173/playground/document-parse'
Write-Host '  1.0 识别  :  http://127.0.0.1:18499'
Write-Host '  Jev 引擎  :  http://127.0.0.1:18498'
Write-Host '  Jev 打分  :  http://127.0.0.1:18501'
Write-Host '  Web 后端  :  http://127.0.0.1:8966'
Write-Host '  日志      :  E:\OCR\logs'

# Word 的「公式可编辑」导出依赖 pandoc，缺了只会影响这一个功能
$pandoc = 'E:\OCR\sources\pandoc\pandoc-3.13\pandoc.exe'
if (Test-Path $pandoc) {
  Write-Host "  Pandoc    :  $pandoc  (Word 公式可编辑导出)"
} else {
  Write-Warning "没找到 pandoc，Word 的「公式可编辑」导出会失败（其余功能正常）: $pandoc"
}
