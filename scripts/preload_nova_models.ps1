$ErrorActionPreference = "Stop"
$ollamaBase = "http://127.0.0.1:11434"
$models = @("qwen3:8b", "qwen3:1.7b")

try {
    Invoke-RestMethod -Uri "$ollamaBase/api/version" -TimeoutSec 5 | Out-Null
} catch {
    Write-Error "Ollama is not reachable at $ollamaBase. Start Ollama and try again."
    exit 1
}

# Check that both models are present before trying to pin them in memory.
$tags = Invoke-RestMethod -Uri "$ollamaBase/api/tags" -TimeoutSec 10
$installed = @($tags.models | ForEach-Object { [string]$_.name })
foreach ($model in $models) {
    if ($installed -notcontains $model -and $installed -notcontains "$model`:latest") {
        Write-Error "Model '$model' is not installed. Run: ollama pull $model"
        exit 2
    }
}

foreach ($model in $models) {
    Write-Host "Loading $model and asking Ollama to keep it resident..." -ForegroundColor Cyan
    $payload = @{
        model = $model
        prompt = ""
        stream = $false
        keep_alive = -1
        options = @{
            num_predict = 1
            num_ctx = 2048
        }
    } | ConvertTo-Json -Depth 5 -Compress

    Invoke-RestMethod -Uri "$ollamaBase/api/generate" -Method Post `
        -ContentType "application/json" -Body $payload -TimeoutSec 300 | Out-Null
}

Write-Host "Both model warm-up requests completed. Current Ollama residency:" -ForegroundColor Green
& ollama ps
Write-Host ""
Write-Host "Confirm that both qwen3:8b and qwen3:1.7b appear above."
Write-Host "If only one appears, the machine/runtime may not have enough available memory or the server did not accept the two-model limit."
