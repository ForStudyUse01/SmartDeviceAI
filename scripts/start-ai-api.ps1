# Start local YOLO + VLM inference API (backend/app.py) on port 5000 using backend/.venv.
# Run from repo root:  powershell -ExecutionPolicy Bypass -File ./scripts/start-ai-api.ps1

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$backendDir = Join-Path $repoRoot "backend"
$requirements = Join-Path $backendDir "requirements.txt"

function Write-Log([string]$msg) { Write-Host "[start-ai-api] $msg" }

if (-not (Test-Path $backendDir)) {
    Write-Log "ERROR: backend folder not found at $backendDir"
    exit 1
}

$py = Join-Path $backendDir ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    Write-Log "Creating venv and installing dependencies (first run may take several minutes)..."
    Push-Location $backendDir
    try {
        python -m venv .venv
        & (Join-Path $backendDir ".venv\Scripts\pip.exe") install --upgrade pip | Out-Null
        & (Join-Path $backendDir ".venv\Scripts\pip.exe") install -r $requirements
        $py = Join-Path $backendDir ".venv\Scripts\python.exe"
    } finally {
        Pop-Location
    }
}

Write-Log "Verifying app.py syntax via py_compile..."
Push-Location $backendDir
try {
    & $py -m py_compile app.py 2>&1 | Out-Host
} catch {
    Write-Log "ERROR: app.py failed py_compile. Fix errors above."
    exit 1
} finally {
    Pop-Location
}

$port = if ($env:PORT) { [int]$env:PORT } else { 5000 }
Write-Log "Starting AI inference API on port $port in a new window. First BLIP-2 download/load can take several minutes."
# Pass PORT into the child shell without expanding $env in this script.
# Expand paths in this shell; child must receive literal $env:PORT assignment.
$inner = "`$env:PORT='$port'; `$env:PRELOAD_AI_PIPELINE='1'; `$env:ANALYSIS_TIMEOUT_SECONDS='300'; Set-Location '$($backendDir)'; & '$($py)' app.py"
Start-Process powershell -ArgumentList @("-NoExit", "-Command", $inner) | Out-Null

$url = "http://127.0.0.1:$port/health"
Write-Log "Waiting for GET $url ..."
for ($i = 0; $i -lt 120; $i++) {
    try {
        $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 5
        if ($r.StatusCode -eq 200) {
            Write-Log "AI API health OK: $url"
            exit 0
        }
    } catch {
        Start-Sleep -Seconds 2
    }
}
Write-Log "WARN: /health did not respond in time. Check the AI window; model download may still be running."
exit 0
