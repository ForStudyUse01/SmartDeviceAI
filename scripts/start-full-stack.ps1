# Start AI inference (port 5000) then dashboard API + sync frontend/.env (port 8000+).
# Run from repo root:  powershell -ExecutionPolicy Bypass -File ./scripts/start-full-stack.ps1

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$frontendEnv = Join-Path $repoRoot "frontend\.env"

function Write-Log([string]$msg) { Write-Host "[start-full-stack] $msg" }

function Set-FrontendAiUrl([string]$url) {
    $line = "VITE_AI_ANALYZE_URL=$url"
    $text = ""
    if (Test-Path $frontendEnv) { $text = Get-Content -Path $frontendEnv -Raw -Encoding UTF8 }
    if ($text -match "(?m)^VITE_AI_ANALYZE_URL=") {
        $text = $text -replace "(?m)^VITE_AI_ANALYZE_URL=.*$", $line
    } else {
        if ($text.Trim().Length -gt 0) { $text = $text.TrimEnd() + "`n" + $line + "`n" }
        else { $text = $line + "`n" }
    }
    Set-Content -Path $frontendEnv -Value $text -Encoding UTF8
    Write-Log "Updated frontend/.env -> $line"
}

Write-Log "Step 1/2: AI inference API (YOLO + VLM)..."
& (Join-Path $repoRoot "scripts\start-ai-api.ps1")
if ($LASTEXITCODE -ne 0) {
    Write-Log "WARN: start-ai-api.ps1 returned non-zero; continuing anyway."
}

Set-FrontendAiUrl "http://127.0.0.1:5000"

Write-Log "Step 2/2: Dashboard API (uvicorn app.main:app)..."
& (Join-Path $repoRoot "scripts\start-dashboard.ps1")
exit $LASTEXITCODE
