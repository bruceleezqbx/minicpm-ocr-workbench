# 启动 1.0 识别服务（Ollama）
# 用法: pwsh -File E:\OCR\scripts\start-ollama.ps1 -Mode gpu|vulkan|cpu
param(
  [ValidateSet('vulkan', 'cpu', 'gpu')] [string] $Mode = 'gpu'
)
$ErrorActionPreference = 'Continue'
$root = 'E:\OCR'
$bin = "$root\sources\ollama-0.40.12\ollama.exe"
if (-not (Test-Path $bin)) { Write-Output "Ollama 未就绪: $bin"; exit 1 }

$env:OLLAMA_HOST = '127.0.0.1:18499'
$env:OLLAMA_MODELS = "$root\models\ollama"
$env:OLLAMA_NUM_PARALLEL = '1'
$env:OLLAMA_MAX_LOADED_MODELS = '1'
$env:OLLAMA_KEEP_ALIVE = '30m'
switch ($Mode) {
  'vulkan' { $env:OLLAMA_VULKAN = '1'; $env:OLLAMA_LLM_LIBRARY = 'vulkan'; $env:GGML_VK_VISIBLE_DEVICES = '0'; $env:CUDA_VISIBLE_DEVICES = '' }
  'gpu'    { $env:OLLAMA_VULKAN = '0'; $env:OLLAMA_LLM_LIBRARY = 'cuda_v12'; $env:CUDA_VISIBLE_DEVICES = '0' }
  'cpu'    { $env:OLLAMA_VULKAN = '0'; $env:CUDA_VISIBLE_DEVICES = '' }
}
New-Item -ItemType Directory -Force -Path $env:OLLAMA_MODELS, "$root\logs" | Out-Null
Write-Output "1.0 识别服务 mode=$Mode -> http://127.0.0.1:18499"
& $bin serve *>> "$root\logs\ollama-$Mode.log"
