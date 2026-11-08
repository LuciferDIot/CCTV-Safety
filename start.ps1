# ==============================================================================
# AURA-Traffic CCTV Analyzer - Local Dual Server Runner
# Starts both FastAPI Backend (:8000) and Next.js Dashboard (:3000) simultaneously
# ==============================================================================

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  Starting AURA-Traffic Safety Analyzer (Full Stack)     " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

$env:PYTHONPATH = "backend"
$frontendDir = Join-Path $PSScriptRoot "frontend"

# Locate Python Executable (.venv, venv, or system Python)
$pythonExe = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    $altVenv = Join-Path $PSScriptRoot "venv\Scripts\python.exe"
    if (Test-Path $altVenv) {
        $pythonExe = $altVenv
    } else {
        $sysPython = (Get-Command python.exe -ErrorAction SilentlyContinue).Source
        if ($sysPython) {
            Write-Host "Notice: Virtual environment (.venv) not found. Using system Python: $sysPython" -ForegroundColor Yellow
            $pythonExe = $sysPython
        } else {
            Write-Error "Python executable not found. Please install Python 3.10+ or create a virtual environment: python -m venv .venv"
            exit 1
        }
    }
}

# 1. Start FastAPI Backend
Write-Host "[1/2] Starting FastAPI Backend on http://localhost:8000..." -ForegroundColor Green
$backendProc = Start-Process -FilePath $pythonExe -ArgumentList "-m uvicorn main:app --app-dir backend --host 0.0.0.0 --port 8000 --reload --reload-dir backend --reload-exclude data --reload-exclude frontend" -PassThru

# 2. Wait for Backend Health
Start-Sleep -Seconds 2
try {
    $health = Invoke-RestMethod -Uri "http://localhost:8000/api/health" -TimeoutSec 5 -ErrorAction Stop
    Write-Host "      Backend is ONLINE (Status: $($health.status), Device: $($health.device))" -ForegroundColor Green
} catch {
    Write-Host "      Backend is initializing..." -ForegroundColor Yellow
}

# 3. Resolve Frontend Package Manager and Dependencies
$pnpmCmd = (Get-Command pnpm.cmd -ErrorAction SilentlyContinue).Source
if (-not $pnpmCmd) {
    $pnpmCmd = (Get-Command pnpm -ErrorAction SilentlyContinue).Source
}
if (-not $pnpmCmd) {
    $pnpmCmd = "npx"
    $frontArgs = "next dev -p 3000"
} else {
    $frontArgs = "dev"
}

# First-time setup: install frontend node_modules if missing
if (-not (Test-Path (Join-Path $frontendDir "node_modules"))) {
    Write-Host "      First-time setup: Installing frontend dependencies..." -ForegroundColor Yellow
    if ($pnpmCmd -ne "npx") {
        Start-Process -FilePath $pnpmCmd -ArgumentList "install" -WorkingDirectory $frontendDir -Wait -NoNewWindow
    } else {
        Start-Process -FilePath "npm" -ArgumentList "install" -WorkingDirectory $frontendDir -Wait -NoNewWindow
    }
}

# 4. Start Next.js Frontend
Write-Host "[2/2] Starting Next.js Frontend on http://localhost:3000..." -ForegroundColor Green
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
