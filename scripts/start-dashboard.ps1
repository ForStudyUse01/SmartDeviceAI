# Auto-detect backend, pick a free port (8000..8010), sync frontend/.env, start uvicorn, verify health + OpenAPI.
# Run from repo root:  powershell -ExecutionPolicy Bypass -File ./scripts/start-dashboard.ps1
# Or:  npm run start:dashboard

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$backendDir = Join-Path $repoRoot "backend"
$frontendEnv = Join-Path $repoRoot "frontend\.env"
$requirements = Join-Path $backendDir "requirements.txt"

function Write-Log([string]$msg) {
    Write-Host "[start-dashboard] $msg"
}

function Test-PortListening([int]$port) {
    try {
        $c = New-Object System.Net.Sockets.TcpClient
        $iar = $c.BeginConnect("127.0.0.1", $port, $null, $null)
        if (-not $iar.AsyncWaitHandle.WaitOne(400, $false)) {
            $c.Close()
            return $false
        }
        try { $c.EndConnect($iar) } catch { $c.Close(); return $false }
        $c.Close()
        return $true
    } catch {
        return $false
    }
}

function Get-FirstFreePort([int]$from = 8000, [int]$to = 8010) {
    foreach ($p in $from..$to) {
        if (-not (Test-PortListening $p)) { return $p }
    }
    throw "No free TCP port in range $from..$to for the dashboard API."
}

function Set-FrontendApiUrl([int]$port) {
    $line = "VITE_API_URL=http://127.0.0.1:$port"
    $text = ""
    if (Test-Path $frontendEnv) { $text = Get-Content -Path $frontendEnv -Raw -Encoding UTF8 }
    if ($text -match "(?m)^VITE_API_URL=") {
        $text = $text -replace "(?m)^VITE_API_URL=.*$", $line
    } else {
        if ($text.Trim().Length -gt 0) { $text = $text.TrimEnd() + "`n" + $line + "`n" }
        else { $text = $line + "`n" }
    }
    Set-Content -Path $frontendEnv -Value $text -Encoding UTF8
    Write-Log "Updated frontend/.env -> $line"
}

function Wait-Health([int]$port, [int]$maxAttempts = 40, [int]$delaySec = 2) {
    $url = "http://127.0.0.1:$port/health"
    for ($i = 0; $i -lt $maxAttempts; $i++) {
        try {
            $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 5
            if ($r.StatusCode -eq 200) { return $true }
        } catch {
            Start-Sleep -Seconds $delaySec
        }
    }
    return $false
}

function Test-Docs([int]$port) {
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:$port/docs" -UseBasicParsing -TimeoutSec 8
        return ($r.StatusCode -eq 200)
    } catch {
        return $false
    }
}

function Test-OpenApiHasScan([int]$port) {
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:$port/openapi.json" -UseBasicParsing -TimeoutSec 10
        return $r.Content -match "ai-device-scan"
    } catch {
        return $false
    }
}

if (-not (Test-Path $backendDir)) {
    Write-Log "ERROR: backend folder not found at $backendDir"
    exit 1
}

$py = Join-Path $backendDir ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    Write-Log "Creating venv and installing dependencies (first run may take a few minutes)..."
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

Write-Log "Ensuring core packages (fastapi, uvicorn, python-multipart)..."
& (Join-Path $backendDir ".venv\Scripts\pip.exe") install -q "fastapi" "uvicorn[standard]" "python-multipart" 2>$null

Write-Log "Verifying import app.main:app ..."
Push-Location $backendDir
try {
    & $py -c "from app.main import app; print('import_ok')" 2>&1 | Out-Host
} catch {
    Write-Log "ERROR: Cannot import app.main. Install backend/requirements.txt and fix errors above."
    exit 1
} finally {
    Pop-Location
}

$port = Get-FirstFreePort
if ($port -ne 8000) {
    Write-Log "Port 8000 is in use; using $port instead."
}
Set-FrontendApiUrl -port $port

Write-Log "Starting: $py -m uvicorn app.main:app --host 0.0.0.0 --port $port --reload"
$inner = "Set-Location '$backendDir'; & '$py' -m uvicorn app.main:app --host 0.0.0.0 --port $port --reload"
Start-Process powershell -ArgumentList @("-NoExit", "-Command", $inner) | Out-Null
Write-Log "Uvicorn launched in a new window. Waiting for /health ..."

if (-not (Wait-Health -port $port)) {
    Write-Log "ERROR: /health did not return 200. Is MongoDB running (mongodb://127.0.0.1:27017)? Check the uvicorn window for tracebacks."
    exit 1
}
Write-Log "Health check OK: http://127.0.0.1:$port/health"

if (-not (Test-Docs -port $port)) {
    Write-Log "WARN: GET /docs did not return 200 (unexpected)."
} else {
    Write-Log "Docs OK: http://127.0.0.1:$port/docs"
}

if (-not (Test-OpenApiHasScan -port $port)) {
    Write-Log "ERROR: OpenAPI does not list ai-device-scan — route registration issue."
    exit 1
}
Write-Log "OpenAPI lists POST /ai-device-scan — route OK."

Write-Log "Backend connected successfully on port $port (restart npm run dev if Vite was already running to pick up .env)."
