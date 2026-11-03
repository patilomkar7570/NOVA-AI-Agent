$ErrorActionPreference = "Stop"

# Persist Ollama server settings for the current Windows user.
[Environment]::SetEnvironmentVariable("OLLAMA_MAX_LOADED_MODELS", "2", "User")
[Environment]::SetEnvironmentVariable("OLLAMA_NUM_PARALLEL", "1", "User")

Write-Host "Ollama settings saved for this Windows user:" -ForegroundColor Green
Write-Host "  OLLAMA_MAX_LOADED_MODELS = 2"
Write-Host "  OLLAMA_NUM_PARALLEL      = 1"
Write-Host ""
Write-Host "Next: fully quit Ollama from its system-tray icon, then reopen Ollama."
Write-Host "These settings apply to the Ollama server process, not just this PowerShell window."
Write-Host "After Ollama restarts, run scripts\\preload_nova_models.ps1."
