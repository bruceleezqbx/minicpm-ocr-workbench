# 读判工作台 · 全链路自检
#
# 一条命令把整条链路的健康状况跑一遍：
#   静态检查（不依赖服务）：文件就位、依赖、许可、前端产物
#   动态检查（需要服务在跑）：四个服务、显存、Jev 是否在 CPU、
#                            官方三例分数口径、Word 导出、前端静态托管
#
# 用法:
#   pwsh -File E:\OCR\scripts\health_check.ps1
#   pwsh -File E:\OCR\scripts\health_check.ps1 -Start    # 先把服务拉起来再查
#
# 退出码: 0 = 全过（动态项可跳过）；1 = 有失败项
param(
  [switch] $Start
)
$ErrorActionPreference = 'Continue'
$root = 'E:\OCR'
$pass = 0; $fail = 0; $skip = 0
$results = New-Object System.Collections.Generic.List[string]

function Ok($name, $detail) {
  $script:pass++
  $script:results.Add(("  [通过] {0,-44} {1}" -f $name, $detail))
}
function Bad($name, $detail) {
  $script:fail++
  $script:results.Add(("  [失败] {0,-44} {1}" -f $name, $detail))
}
function Skip($name, $detail) {
  $script:skip++
  $script:results.Add(("  [跳过] {0,-44} {1}" -f $name, $detail))
}
function Section($t) { $script:results.Add(""); $script:results.Add("== $t ==") }

function Http($url, $method = 'GET', $body = $null) {
  try {
    if ($body) {
      $r = Invoke-WebRequest -Uri $url -Method $method -Body $body -ContentType 'application/json' -TimeoutSec 20 -UseBasicParsing
    } else {
      $r = Invoke-WebRequest -Uri $url -Method $method -TimeoutSec 20 -UseBasicParsing
    }
    return @{ Code = $r.StatusCode; Body = $r.Content; Raw = $r }
  } catch {
    $code = 0
    if ($_.Exception.Response) { $code = [int]$_.Exception.Response.StatusCode }
    return @{ Code = $code; Body = ''; Raw = $null }
  }
}

$results.Add("MiniCPM-OCR 读判工作台 · 全链路自检")
$results.Add("生成时间: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')")

# ─────────────────────────────────────────────────────────────
Section "一、静态检查（不依赖服务）"

$must = @(
  @{p = "$root\models\MiniCPM-OCR-1.0-gguf\MiniCPM-OCR-1_0-Q8_0.gguf"; n = '1.0 主模型 GGUF'},
  @{p = "$root\models\MiniCPM-OCR-1.0-gguf\mmproj-model-f16-4x.gguf"; n = '1.0 视觉投影 GGUF'},
  @{p = "$root\models\MiniCPM-OCR-Jev-gguf\MiniCPM-OCR-Jev-Q4_K_M.gguf"; n = 'Jev 权重 GGUF'},
  @{p = "$root\models\MiniCPM-OCR-Jev-gguf\mmproj-model-f16.gguf"; n = 'Jev 视觉投影 GGUF'},
  @{p = "$root\sources\ollama-0.40.12\ollama.exe"; n = 'Ollama 可执行文件'},
  @{p = "$root\sources\llama-b12032\llama-server.exe"; n = 'llama.cpp 引擎'},
  @{p = "$root\sources\pandoc\pandoc-3.13\pandoc.exe"; n = 'Pandoc（Word 导出）'},
  @{p = "$root\.minicpm-ocr\Scripts\python.exe"; n = '1.0 SDK venv'},
  @{p = "$root\.jev-score\Scripts\python.exe"; n = 'Jev 打分 venv'},
  @{p = "$root\.jev-render\Scripts\python.exe"; n = 'Jev 渲染 venv'},
  @{p = "$root\.desktop\Scripts\python.exe"; n = '桌面壳 venv'},
  @{p = "$root\sources\MiniCPM-OCR-main\webdemo\frontend\dist\index.html"; n = '前端生产构建产物'},
  @{p = "$root\sources\MiniCPM-OCR-main\LICENSE"; n = '上游 LICENSE'},
  @{p = "$root\LICENSE"; n = '本仓 LICENSE'},
  @{p = "$root\NOTICE"; n = '本仓 NOTICE'},
  @{p = "$root\CHANGES.md"; n = '改造清单 CHANGES.md'},
  @{p = "$root\upstream-local.patch"; n = '可回溯补丁'},
  @{p = "$root\start_desktop.bat"; n = '桌面版入口'}
)
foreach ($m in $must) {
  if (Test-Path $m.p) { Ok $m.n ((Get-Item $m.p).Length.ToString() + ' B') }
  else { Bad $m.n "缺失: $($m.p)" }
}

# 许可一致性：本仓 LICENSE 应与上游一致
$up = Get-Content "$root\sources\MiniCPM-OCR-main\LICENSE" -Raw
$me = Get-Content "$root\LICENSE" -Raw
if ($up.Trim() -eq $me.Trim()) { Ok '本仓 LICENSE 与上游一致' 'Apache-2.0 全文' }
else { Bad '本仓 LICENSE 与上游一致' '内容不一致' }

# Apache-2.0 §4(b)：被改过的上游文件要有改动声明
$repo = "$root\sources\MiniCPM-OCR-main"
$marked = (Get-ChildItem $repo -Recurse -File -Include *.py, *.ts, *.tsx -ErrorAction SilentlyContinue |
  Where-Object { $_.FullName -notmatch '\\(node_modules|dist)\\' } |
  Select-String -Pattern 'Apache-2\.0 §4\(b\)' -List).Count
if ($marked -ge 20) { Ok 'Apache-2.0 §4(b) 改动声明' "$marked 个文件已声明" }
else { Bad 'Apache-2.0 §4(b) 改动声明' "只有 $marked 个文件声明（应 ≥20）" }

# 前端产物完整性
foreach ($d in @('assets', 'pdfjs\cmaps', 'pdfjs\standard_fonts')) {
  $p = "$repo\webdemo\frontend\dist\$d"
  if (Test-Path $p) { Ok "前端产物 $d" '在位' } else { Bad "前端产物 $d" "缺失: $p" }
}

# 桌面壳依赖
$dv = & "$root\.desktop\Scripts\python.exe" -c "import importlib.metadata as m; print(m.version('pywebview'))" 2>&1
if ($LASTEXITCODE -eq 0) { Ok 'pywebview 已安装' "v$dv" } else { Bad 'pywebview 已安装' '未安装' }

# ─────────────────────────────────────────────────────────────
Section "二、动态检查（需要服务在跑）"

if ($Start) {
  $results.Add("  正在拉起服务 ...")
  Start-Process -FilePath 'pwsh' -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "$root\scripts\desktop_app.py", '--serve-only') -WindowStyle Hidden | Out-Null
  foreach ($p in @(18499, 18498, 18501, 8966)) {
    $ok = $false
    for ($i = 0; $i -lt 60; $i++) {
      Start-Sleep -Seconds 2
      if ((Http "http://127.0.0.1:$p/health").Code -eq 200 -or (Http "http://127.0.0.1:$p/api/version").Code -eq 200 -or (Http "http://127.0.0.1:$p/healthz").Code -eq 200) { $ok = $true; break }
    }
    if (-not $ok) { $results.Add("  服务 $p 启动超时") }
  }
  $results.Add("  服务已就绪")
}

# 2.1 四个服务
$svc = @(
  @{p = 18499; u = '/api/version'; n = '1.0 识别服务 (Ollama)'},
  @{p = 18498; u = '/health';    n = 'Jev 判别引擎'},
  @{p = 18501; u = '/healthz';   n = 'Jev 打分服务'},
  @{p = 8966;  u = '/health';    n = 'Web 后端'}
)
$up = 0
foreach ($s in $svc) {
  $r = Http "http://127.0.0.1:$($s.p)$($s.u)"
  if ($r.Code -eq 200) { Ok $s.n "http://127.0.0.1:$($s.p)$($s.u)" ; $up++ }
  else { Skip $s.n "服务未启动（HTTP $($r.Code)）" }
}

if ($up -eq 0) {
  Section "三、结论"
  $results.Add("  服务都没起，动态检查已跳过。")
  $results.Add("  启动服务： pwsh -File $root\scripts\desktop_app.py --serve-only")
  $results.Add("  或直接用： $root\start_desktop.bat")
}
else {
  # 2.2 前端静态托管
  $r = Http 'http://127.0.0.1:8966/playground/document-parse'
  if ($r.Code -eq 200 -and $r.Body -match '<div id="root">') { Ok '前端静态托管（SPA 路由）' 'playground/document-parse 返回 index.html' }
  else { Skip '前端静态托管（SPA 路由）' "HTTP $($r.Code)" }

  # 2.3 显存
  $smi = (& nvidia-smi --query-gpu=memory.used,memory.free --format=csv,noheader 2>&1) -join ' '
  if ($smi -match '(\d+)\s*MiB\s*,\s*(\d+)\s*MiB') {
    $used = [int]$Matches[1]; $free = [int]$Matches[2]
    if ($used -lt 3400) { Ok '显存占用' "$used / 4096 MiB（余 $free）" }
    else { Bad '显存占用' "$used / 4096 MiB，太高（Jev 可能又跑上 GPU 了）" }
  } else { Skip '显存占用' "nvidia-smi 输出无法解析: $smi" }

  # 2.4 Jev 是否在 CPU
  $eng = Get-CimInstance Win32_Process -Filter "Name='llama-server.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like '*llama-b12032*' }
  if ($eng) {
    $ngl = if ($eng[0].CommandLine -match '-ngl\s+(\d+)') { $Matches[1] } else { '?' }
    if ($ngl -eq '0') { Ok 'Jev 引擎跑在 CPU' '-ngl 0，不抢显存' }
    else { Bad 'Jev 引擎跑在 CPU' "-ngl $ngl（应为 0，否则会和 1.0 抢 4GB 显存）" }
  } else { Skip 'Jev 引擎跑在 CPU' '引擎没在跑' }

  # 2.5 官方三例分数口径
  if ((Http 'http://127.0.0.1:18498/health').Code -eq 200) {
    $vr = & "$root\.jev-score\Scripts\python.exe" "$root\scripts\verify_jev.py" 2>&1
    $vrTxt = $vr -join "`n"
    if ($vrTxt -match 'ALL PASS|全部通过|PASS') { Ok 'Jev 官方三例分数口径' '全部通过（容差 0.02）' }
    else {
      $fails = ([regex]::Matches($vrTxt, 'FAIL')).Count
      if ($fails -gt 0) { Bad 'Jev 官方三例分数口径' "$fails 项不符" } else { Skip 'Jev 官方三例分数口径' '未能判定' }
    }
  } else { Skip 'Jev 官方三例分数口径' '引擎没在跑' }

  # 2.6 Word 导出（公式是否为原生 OMML）
  # 注意：公式不能包在反引号里，否则 pandoc 当成行内代码，不会转成公式。
  # 这里用单引号 here-string，避免 PowerShell 把 $$ 当变量插值。
  $md = @'
## 自检

公式：

$$E=mc^2$$

| 项目 | 数值 |
|---|---|
| 甲 | 1 |
'@
  $payload = @{ markdown = $md } | ConvertTo-Json
  $out = "$env:TEMP\healthcheck.docx"
  $code = (& curl.exe -sS --noproxy 127.0.0.1 -o $out -w '%{http_code}' -H 'Content-Type: application/json' --data-binary $payload 'http://127.0.0.1:8966/api/export/word' 2>&1) -join ''
  if ($code -eq '200' -and (Test-Path $out)) {
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zip = [System.IO.Compression.ZipFile]::OpenRead($out)
    $en = $zip.Entries | Where-Object { $_.FullName -eq 'word/document.xml' }
    $sr = New-Object System.IO.StreamReader($en.Open()); $xml = $sr.ReadToEnd(); $sr.Close(); $zip.Dispose()
    $oMath = ([regex]::Matches($xml, '<m:oMath[ >]')).Count
    $tex = ([regex]::Matches($xml, '\\frac|\\sum|\\text')).Count
    $tbl = ([regex]::Matches($xml, '<w:tbl[ >]')).Count
    if ($oMath -ge 1 -and $tex -eq 0 -and $tbl -ge 1) {
      Ok 'Word 导出（原生公式）' "oMath=$oMath w:tbl=$tbl 残留LaTeX=$tex"
    } else {
      Bad 'Word 导出（原生公式）' "oMath=$oMath w:tbl=$tbl 残留LaTeX=$tex（期望 oMath>=1、残留=0）"
    }
  } else { Skip 'Word 导出（原生公式）' "HTTP $code" }
}

# ─────────────────────────────────────────────────────────────
Section "结论"
$results.Add("  通过 $pass 项，失败 $fail 项，跳过 $skip 项")
$results.Add("")
foreach ($l in $results) { Write-Host $l }
if ($fail -gt 0) { exit 1 }
exit 0
