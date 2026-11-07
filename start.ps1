# ==============================================================================
# AURA-Traffic CCTV Analyzer - Local Dual Server Runner
# Starts both FastAPI Backend (:8000) and Next.js Dashboard (:3000) simultaneously
# ==============================================================================

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  Starting AURA-Traffic Safety Analyzer (Full Stack)     " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

$env:PYTHONPATH = "backend"
$pythonExe = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
$frontendDir = Join-Path $PSScriptRoot "frontend"

# 1. Start FastAPI Backend
Write-Host "[1/2] Starting FastAPI Backend on http://localhost:8000..." -ForegroundColor Green
$backendProc = Start-Process -FilePath $pythonExe -ArgumentList "-m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload" -PassThru

# 2. Wait for Backend Health
Start-Sleep -Seconds 2
try {
    $health = Invoke-RestMethod -Uri "http://localhost:8000/api/health" -TimeoutSec 5 -ErrorAction Stop
    Write-Host "      Backend is ONLINE (Status: $($health.status), Device: $($health.device))" -ForegroundColor Green
} catch {
    Write-Host "      Backend is initializing..." -ForegroundColor Yellow
}

# 3. Start Next.js Frontend
Write-Host "[2/2] Starting Next.js Frontend on http://localhost:3000..." -ForegroundColor Green
$pnpmCmd = (Get-Command pnpm.cmd -ErrorAction SilentlyContinue).Source
if (-not $pnpmCmd) {
    $pnpmCmd = "npx"
    $frontArgs = "next dev -p 3000"
} else {
    $frontArgs = "dev"
}

$frontendProc = Start-Process -FilePath $pnpmCmd -ArgumentList $frontArgs -WorkingDirectory $frontendDir -PassThru

Write-Host ""
Write-Host "----------------------------------------------------------" -ForegroundColor Cyan
Write-Host "  Dashboard UI:   http://localhost:3000                   " -ForegroundColor Green
Write-Host "  Backend API:    http://localhost:8000                   " -ForegroundColor Green
Write-Host "  Swagger Docs:   http://localhost:8000/docs              " -ForegroundColor Green
Write-Host "----------------------------------------------------------" -ForegroundColor Cyan
Write-Host "Press [Ctrl+C] or Enter to stop both servers..." -ForegroundColor Magenta

# Open browser
Start-Sleep -Seconds 2
Start-Process "http://localhost:3000"

try {
    [Console]::ReadLine()
} finally {
    Write-Host "Stopping servers..." -ForegroundColor Yellow
    if ($backendProc -and -not $backendProc.HasExited) { Stop-Process -Id $backendProc.Id -Force -ErrorAction SilentlyContinue }
    if ($frontendProc -and -not $frontendProc.HasExited) { Stop-Process -Id $frontendProc.Id -Force -ErrorAction SilentlyContinue }
    Write-Host "Servers stopped." -ForegroundColor Gray
}

