# 下载 MiniCPM-OCR 1.0 的三个 GGUF 文件（主模型 / 视觉投影 / DSpark draft）
# 优先 ModelScope（国内线路），失败回退 HF 镜像，并按预期大小校验完整性。
$ErrorActionPreference = 'Continue'
$dst = 'E:\OCR\models\MiniCPM-OCR-1.0-gguf'
New-Item -ItemType Directory -Force -Path $dst | Out-Null

$py = 'E:\OCR\.minicpm-ocr\Scripts\python.exe'
$files = @(
  @{ repo='OpenBMB/MiniCPM-OCR-1.0-gguf';      name='MiniCPM-OCR-1_0-Q8_0.gguf';        size=811598432 },
  @{ repo='OpenBMB/MiniCPM-OCR-1.0-gguf';      name='mmproj-model-f16-4x.gguf';         size=901017536 },
  @{ repo='OpenBMB/MiniCPM-OCR-1.0-DSpark-gguf'; name='dspark-MiniCPM-OCR-1_0-Q8_0.gguf'; size=327293024 }
)
$hfBase = 'https://hf-cdn.sufy.com/openbmb'

function Log($m) { Write-Output ("[{0}] {1}" -f (Get-Date -Format 'HH:mm:ss'), $m) }

foreach ($f in $files) {
  $out = Join-Path $dst $f.name
  $done = (Test-Path $out) -and ((Get-Item $out).Length -eq $f.size)
  if ($done) { Log "skip (already complete): $($f.name)"; continue }

  $ok = $false
  for ($try = 1; $try -le 8 -and -not $ok; $try++) {
    Log "downloading $($f.name) via ModelScope (try $try)"
    & $py -m modelscope download --model $f.repo $f.name --local_dir $dst 2>&1 |
      Select-Object -Last 2 | ForEach-Object { Log "  $_" }
    if ((Test-Path $out) -and ((Get-Item $out).Length -eq $f.size)) { $ok = $true; break }

    $hfUrl = if ($f.repo -like '*DSpark*') {
      "$hfBase/MiniCPM-OCR-1.0-DSpark-gguf/resolve/main/$($f.name)"
    } else {
      "$hfBase/MiniCPM-OCR-1.0-gguf/resolve/main/$($f.name)"
    }
    Log "  fallback to HF mirror: $hfUrl"
    curl.exe -sSL --retry 5 --retry-delay 5 --retry-all-errors -C - -o $out $hfUrl
    if ((Test-Path $out) -and ((Get-Item $out).Length -eq $f.size)) { $ok = $true; break }
    Log "  incomplete ($((Get-Item $out -ErrorAction SilentlyContinue).Length) / $($f.size)), retry later"
    Start-Sleep -Seconds 10
  }
  if ($ok) { Log "OK: $($f.name)" } else { Log "FAILED: $($f.name)" }
}

Get-ChildItem $dst -File | Select-Object Name, @{n='MB';e={[math]::Round($_.Length/1MB,1)}} | Format-Table -AutoSize | Out-String
