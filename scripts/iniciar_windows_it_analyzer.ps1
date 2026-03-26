param(
    [string]$CredPath = "claves.json",
    [string]$Port = "8080",
    [string]$ProjectId = "it-analyzer",
    [string]$AdminUser = "admin",
    [string]$AdminPassword = "ImpBac321"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path $PSScriptRoot -Parent
Set-Location $ProjectRoot

# Soporta ambos nombres de entorno: .venv y venv.
$venvDir = $null
if (Test-Path ".venv\Scripts\Activate.ps1") {
    $venvDir = ".venv"
}
elseif (Test-Path "venv\Scripts\Activate.ps1") {
    $venvDir = "venv"
}
else {
    $venvDir = ".venv"
    Write-Host "No se detecto entorno virtual. Creando $venvDir..." -ForegroundColor Cyan
    py -3 -m venv $venvDir
}

$activate = Join-Path $ProjectRoot "$venvDir\Scripts\Activate.ps1"
if (-not (Test-Path $activate)) {
    throw "No se encontro $venvDir\Scripts\Activate.ps1"
}

. $activate

Write-Host "Actualizando pip e instalando dependencias..." -ForegroundColor Cyan
python -m pip install --upgrade pip
python -m pip install -r requirements.txt -r requirements-full.txt

$env:PORT = $Port
$env:RRHH_AUTH_ENABLED = "true"
$env:RRHH_ADMIN_USER = $AdminUser
$env:RRHH_ADMIN_PASSWORD = $AdminPassword
$env:GOOGLE_CLOUD_PROJECT = $ProjectId
$env:FIREBASE_PROJECT_ID = $ProjectId

$credAbsolutePath = Join-Path $ProjectRoot $CredPath
if (Test-Path $credAbsolutePath) {
    $env:FIREBASE_CREDENTIALS = (Resolve-Path $credAbsolutePath).Path
    Write-Host "Usando FIREBASE_CREDENTIALS=$env:FIREBASE_CREDENTIALS" -ForegroundColor Green
}
else {
    Write-Host "No encontré '$CredPath'. Se intentará conectar por ADC (si existe)." -ForegroundColor Yellow
    Write-Host "Tip: colocá tu Service Account JSON como '$CredPath' en la raíz del proyecto." -ForegroundColor Yellow
}

Write-Host "Iniciando web_chat.py en puerto $Port..." -ForegroundColor Green
python web_chat.py
