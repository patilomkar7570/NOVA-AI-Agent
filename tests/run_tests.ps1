$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $ProjectRoot

# Avoid creating or rewriting __pycache__ files during this test run.
$env:PYTHONDONTWRITEBYTECODE = "1"

Write-Host "`n=== NOVA Python regression tests ===" -ForegroundColor Cyan
& python -B -m unittest discover -s tests/python -p "test_*.py" -v
if ($LASTEXITCODE -ne 0) {
    Write-Error "Python test suite failed (exit code $LASTEXITCODE)."
    exit $LASTEXITCODE
}

Write-Host "`n=== NOVA frontend voice tests ===" -ForegroundColor Cyan
$FrontendTests = @(
    Get-ChildItem -Path (Join-Path $PSScriptRoot "frontend") -Filter "*.test.mjs" |
        Sort-Object Name |
        ForEach-Object { $_.FullName }
)

if ($FrontendTests.Count -eq 0) {
    Write-Error "No frontend .test.mjs files were found."
    exit 1
}

& node --test $FrontendTests
if ($LASTEXITCODE -ne 0) {
    Write-Error "Frontend test suite failed (exit code $LASTEXITCODE)."
    exit $LASTEXITCODE
}

Write-Host "`nAll automated NOVA tests passed." -ForegroundColor Green
