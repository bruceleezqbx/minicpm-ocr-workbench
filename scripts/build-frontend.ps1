# 构建工作台前端（生产模式）
#
# 产物: E:\OCR\sources\MiniCPM-OCR-main\webdemo\frontend\dist
# 由 webdemo 后端（:8966）静态托管，桌面壳与浏览器都直接访问 8966，
# 因此不再需要 Vite dev server。
#
# 用法:
#   pwsh -File E:\OCR\scripts\build-frontend.ps1
param(
  [switch] $SkipBuild,
  # 界面默认语言。官方 .env.example 是 en-US；本机做中文界面，所以默认 zh-CN。
  # 不设的话首屏会先按 en-US 渲染、再被浏览器语言探测改一次，闪一下英文。
  [ValidateSet('zh-CN', 'en-US')] [string] $Locale = 'zh-CN'
)
$ErrorActionPreference = 'Stop'
$fe = 'E:\OCR\sources\MiniCPM-OCR-main\webdemo\frontend'
$dist = "$fe\dist"
$pdfjs = "$fe\node_modules\pdfjs-dist"

function Log($msg) { Write-Host "[build-frontend] $msg" }

if (-not (Test-Path "$fe\node_modules")) {
  throw "前端依赖没装。先执行： cd $fe ; corepack pnpm install --registry https://registry.npmmirror.com"
}

if (-not $SkipBuild) {
  Log "跑 pnpm build（tsc --noEmit && vite build），locale=$Locale ..."
  $env:VITE_DEFAULT_LOCALE = $Locale
  Push-Location $fe
  try {
    & corepack pnpm build
    if ($LASTEXITCODE -ne 0) { throw "pnpm build 失败，退出码 $LASTEXITCODE" }
  } finally {
    Pop-Location
  }
}

if (-not (Test-Path "$dist\index.html")) {
  throw "构建产物不对：$dist\index.html 不存在"
}

# pdf.js 的 CJK 字体映射 / 标准字体 / wasm 运行时。
# 前端按同源 /pdfjs/cmaps/ /pdfjs/standard_fonts/ /pdfjs/wasm/ 找它们
# （见 frontend/src/pages/playground/utils/pdfPreview.ts），
# viteStaticCopy 没把它们落进 dist，这里自己补齐。
foreach ($name in 'cmaps', 'standard_fonts', 'wasm') {
  $src = "$pdfjs\$name"
  $dst = "$dist\pdfjs\$name"
  if (-not (Test-Path $src)) {
    Log "警告：找不到 $src，跳过"
    continue
  }
  if (Test-Path $dst) { Remove-Item -Recurse -Force $dst }
  Copy-Item -Recurse $src $dst
  Log "pdfjs/$name -> dist/pdfjs/$name"
}

# 产物自检
$checks = @(
  @{ Path = "$dist\index.html";     Desc = '入口 HTML' },
  @{ Path = "$dist\assets";         Desc = 'JS/CSS 资源' },
  @{ Path = "$dist\pdfjs\cmaps";    Desc = 'PDF CJK 字体映射' },
  @{ Path = "$dist\pdfjs\standard_fonts"; Desc = 'PDF 标准字体' }
)
$missing = @()
foreach ($c in $checks) {
  if (Test-Path $c.Path) {
    Log "OK   $($c.Desc)"
  } else {
    Log "缺少 $($c.Desc)：$($c.Path)"
    $missing += $c.Desc
  }
}
if ($missing.Count -gt 0) { throw "构建产物不完整：$($missing -join ', ')" }

$size = (Get-ChildItem $dist -Recurse -File | Measure-Object -Property Length -Sum).Sum
Log ("完成：{0:N1} MB，{1} 个文件" -f ($size / 1MB), (Get-ChildItem $dist -Recurse -File).Count)
