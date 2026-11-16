# Запуск «Спільної каси» локально: бекенд (порт 8000) і фронтенд (порт 5173).
# Використання:  .\dev.ps1            — звичайний запуск
#                .\dev.ps1 -Reset     — перед запуском заново створити демо-дані
param([switch]$Reset)

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$backend = Join-Path $root "backend"
$frontend = Join-Path $root "frontend"
$python = Join-Path $backend ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    Write-Host "Створюю віртуальне середовище Python..." -ForegroundColor Magenta
    python -m venv (Join-Path $backend ".venv")
    & $python -m pip install -r (Join-Path $backend "requirements.txt")
    $Reset = $true
}
if (-not (Test-Path (Join-Path $frontend "node_modules"))) {
    Write-Host "Встановлюю залежності фронтенду..." -ForegroundColor Magenta
    Push-Location $frontend; npm install; Pop-Location
}
if ($Reset -or -not (Test-Path (Join-Path $backend "kasa.db"))) {
    Push-Location $backend; & $python -m app.seed; Pop-Location
}

Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$backend'; & '$python' -m uvicorn app.main:app --port 8000 --reload --reload-dir app"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$frontend'; npm run dev"

Write-Host ""
Write-Host "Застосунок:  http://localhost:5173" -ForegroundColor Magenta
Write-Host "Swagger API: http://localhost:8000/docs" -ForegroundColor Magenta
