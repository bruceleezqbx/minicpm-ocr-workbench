# 下载并解压 Ollama 0.40.12 便携版（Windows amd64），不动系统服务。
$ErrorActionPreference = 'Continue'
$url = 'https://github.com/ollama/ollama/releases/download/v0.40.12/ollama-windows-amd64.zip'
$zip = 'E:\OCR\sources\ollama-windows-amd64-0.40.12.zip'
$out = 'E:\OCR\sources\ollama-0.40.12'
$expect = 1601458136
New-Item -ItemType Directory -Force -Path 'E:\OCR\sources' | Out-Null
function Log($m) { Write-Output ("[{0}] {1}" -f (Get-Date -Format 'HH:mm:ss'), $m) }

for ($try = 1; $try -le 40; $try++) {
  $have = 0
  if (Test-Path $zip) { $have = (Get-Item $zip).Length }
  if ($have -eq $expect) { break }
  Log "try $try : have $have / $expect bytes"
  # GitHub 线路时快时慢，多源轮询 + 断点续传
  $srcs = @("https://gh-proxy.com/$url",
            "https://gh.ddlc.top/$url",
            $url,
            "https://ghproxy.net/$url")
  foreach ($s in $srcs) {
    curl.exe -sSL --connect-timeout 15 --max-time 900 --retry 3 --retry-delay 3 --retry-all-errors -C - -o $zip $s
    $have = 0; if (Test-Path $zip) { $have = (Get-Item $zip).Length }
    Log "  from $($s.Split('/')[2]) -> $have bytes"
    if ($have -eq $expect) { break }
  }
  if ($have -lt $expect) { Start-Sleep -Seconds 5 }
}

$have = 0; if (Test-Path $zip) { $have = (Get-Item $zip).Length }
if ($have -ne $expect) { Log "INCOMPLETE zip: $have / $expect"; exit 1 }

Log "extracting to $out"
if (Test-Path $out) { Remove-Item -Recurse -Force $out }
Expand-Archive -Path $zip -DestinationPath $out -Force
Log "extracted:"
Get-ChildItem $out -Recurse -Depth 1 | Select-Object -First 20 FullName | Format-Table -AutoSize | Out-String
