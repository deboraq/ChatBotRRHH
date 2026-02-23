# Levantar ChatBot RRHH en localhost (Windows)
# Uso: .\levantar_local.ps1

$ErrorActionPreference = "Stop"
$projectRoot = $PSScriptRoot

Set-Location $projectRoot

# Activar entorno virtual
if (Test-Path ".\venv\Scripts\Activate.ps1") {
    Write-Host "Activando venv..." -ForegroundColor Cyan
    .\venv\Scripts\Activate.ps1
} else {
    Write-Host "No se encontró venv. Crear con: python -m venv venv" -ForegroundColor Yellow
    exit 1
}

# Instalar dependencias
Write-Host "Instalando dependencias..." -ForegroundColor Cyan
if (Test-Path "requirements-full.txt") {
    pip install -r requirements.txt -r requirements-full.txt --quiet
} else {
    pip install -r requirements.txt --quiet
}

# Levantar servidor
Write-Host "Levantando servidor en http://localhost:5000" -ForegroundColor Green
python web_chat.py
