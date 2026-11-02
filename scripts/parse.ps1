# 一键整页解析：PDF/图片 -> Markdown
# 用法:
#   pwsh -File E:\OCR\scripts\parse.ps1 -Input E:\OCR\work\sample_doc.png
#   pwsh -File E:\OCR\scripts\parse.ps1 -Input D:\docs\scan.pdf -Output D:\docs\scan.md
param(
  [Parameter(Mandatory = $true)][Alias('Input')][string] $Doc,
  [string] $Output = '',
  [string] $Backend = 'ollama',
  [string] $ServerUrl = 'http://127.0.0.1:18499',
  [string] $Model = 'minicpm-ocr',
  [int] $Ctx = 2048,          # 4GB 显存上限，勿轻易调大（8192 会 OOM）
  [int] $Workers = 1,        # Ollama 单并发槽位，保持 1
  [int] $Threads = 4,        # Paddle 版面检测线程数（机器内存紧张时别调大）
  [switch] $Full,            # 解析全部页（默认限 1 页做冒烟验证）
  [switch] $KeepModel        # 保留已加载的模型（内存充足时可加快连续批处理）
)
$ErrorActionPreference = 'Continue'
$root = 'E:\OCR'
$exe = "$root\.minicpm-ocr\Scripts\minicpmvocr.exe"
$layoutModel = "$env:USERPROFILE\.paddlex\official_models\PP-DocLayoutV3"

if (-not (Test-Path $exe)) { Write-Output "SDK 未安装: $exe"; exit 1 }
if (-not (Test-Path $layoutModel)) {
  Write-Output "版面模型缺失: $layoutModel"
  Write-Output "请先运行: $root\.minicpm-ocr\Scripts\python.exe -c ""from paddlex import create_model; create_model('PP-DocLayoutV3')"""
  exit 1
}
if (-not $Output) {
  $base = [System.IO.Path]::GetFileNameWithoutExtension($Doc)
  $Output = "$root\work\$base.md"
}

# paddle 3.3.1 的 oneDNN(PIR) 路径与 PP-DocLayoutV3 不兼容，必须关掉 mkldnn
$env:PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK = 'True'
$env:FLAGS_use_mkldnn = '0'
$env:OMP_NUM_THREADS = "$Threads"
$env:MKL_NUM_THREADS = "$Threads"
$env:PYTHONIOENCODING = 'utf-8'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$setArgs = @("--set", "engine.num_ctx=$Ctx", "--set", "engine.max_model_len=$Ctx")
if (-not $Full) { $setArgs += @("--set", "input.limit=1") }

# 版面检测(PaddleX)与识别(Ollama)会同时占用内存。本机 16GB 常被其他程序占满，
# 因此默认先把 Ollama 模型卸载，给 Paddle 让出 ~2.4GB，识别时再自动加载一次。
if (-not $KeepModel) {
  $ollama = "$root\sources\ollama-0.40.12\ollama.exe"
  if (Test-Path $ollama) {
    $env:OLLAMA_HOST = '127.0.0.1:18499'
    & $ollama stop $Model 2>&1 | Out-Null
    Start-Sleep -Seconds 2
    $os = Get-CimInstance Win32_OperatingSystem
    Write-Output ("已卸载模型，可用内存 {0:n2} GB" -f ($os.FreePhysicalMemory / 1MB))
  }
}

$sw = [Diagnostics.Stopwatch]::StartNew()
& $exe parse --backend $Backend --server-url $ServerUrl --model $Model `
  --device cpu --workers $Workers --layout-model $layoutModel `
  @setArgs --input $Doc --output $Output
$code = $LASTEXITCODE
$sw.Stop()
Write-Output ("解析耗时 {0:n1}s -> {1} (exit {2})" -f $sw.Elapsed.TotalSeconds, $Output, $code)
exit $code

