param(
    [int]$FrontendPort = 5173,
    [int]$DashboardApiPort = 8000,
    [int]$AiApiPort = 5000
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = Join-Path $root "backend"
$frontendDir = Join-Path $root "frontend"

Write-Host "Starting SmartDeviceAI full stack..."

# Dashboard/auth API (backend/app/main.py)
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "Set-Location '$backendDir'; uvicorn app.main:app --host 0.0.0.0 --port $DashboardApiPort"
) | Out-Null

# AI inference API (backend/app.py)
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "Set-Location '$backendDir'; python app.py"
) | Out-Null

# Frontend (Vite)
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "Set-Location '$frontendDir'; npm run dev -- --host 0.0.0.0 --port $FrontendPort"
) | Out-Null

function Wait-ForHttp {
    param(
        [Parameter(Mandatory = $true)][string]$Url,
        [int]$Retries = 25,
        [int]$DelaySeconds = 2
    )

    for ($i = 0; $i -lt $Retries; $i++) {
        try {
            $response = Invoke-WebRequest -Uri $Url -Method GET -TimeoutSec 8
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
                return $true
            }
        } catch {
            Start-Sleep -Seconds $DelaySeconds
        }
    }
    return $false
}

$dashboardReady = Wait-ForHttp -Url "http://localhost:$DashboardApiPort/health"
$aiReady = Wait-ForHttp -Url "http://localhost:$AiApiPort/health/full"
$frontendReady = Wait-ForHttp -Url "http://localhost:$FrontendPort"

Write-Host "Dashboard API ready: $dashboardReady"
Write-Host "AI API ready: $aiReady"
Write-Host "Frontend ready: $frontendReady"

if ($frontendReady) {
    Start-Process "http://localhost:$FrontendPort"
}

