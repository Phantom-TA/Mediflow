# MediFlow — Windows PowerShell Setup Script
# Run from the mediflow/ root directory.
# Requires: Python 3.11+, pip

param(
    [switch]$SkipVenv,
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"

Write-Host "=== MediFlow Setup ===" -ForegroundColor Cyan

# 1. Check Python version
$pythonVersion = python --version 2>&1
Write-Host "Python: $pythonVersion" -ForegroundColor Green

# 2. Create virtual environment
if (-not $SkipVenv) {
    Write-Host "`nCreating virtual environment..." -ForegroundColor Yellow
    python -m venv backend\.venv
}

# 3. Activate venv
Write-Host "Activating virtual environment..." -ForegroundColor Yellow
& backend\.venv\Scripts\Activate.ps1

# 4. Install dependencies
if (-not $SkipInstall) {
    Write-Host "`nInstalling dependencies..." -ForegroundColor Yellow
    pip install --upgrade pip --quiet
    pip install -r backend\requirements.txt --quiet
    Write-Host "Dependencies installed." -ForegroundColor Green
}

# 5. Check .env exists
if (-not (Test-Path "backend\.env")) {
    if (Test-Path ".env.example") {
        Write-Host "`n[WARNING] No backend\.env found. Copying .env.example..." -ForegroundColor Yellow
        Copy-Item ".env.example" "backend\.env"
        Write-Host "Edit backend\.env and set DATABASE_URL before running tests." -ForegroundColor Red
    }
}

Write-Host "`n=== Setup complete ===" -ForegroundColor Cyan
Write-Host "Next steps:" -ForegroundColor White
Write-Host "  1. Edit backend\.env with your Supabase credentials" -ForegroundColor White
Write-Host "  2. cd backend" -ForegroundColor White
Write-Host "  3. alembic upgrade head   (run migrations)" -ForegroundColor White
Write-Host "  4. pytest ..\tests\       (run Phase 1 tests)" -ForegroundColor White
