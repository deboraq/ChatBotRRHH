param(
    [string]$ProjectId = "it-analyzer",
    [string]$Region = "southamerica-east1",
    [string]$ServiceName = "chatbot-rrhh",
    [string]$ServiceAccountName = "chatbot-rrhh-run",
    [string]$AdminUser = "admin",
    [string]$AdminPassword = "admin123",
    [string]$WebSecret = "cambiar-por-secreto-largo",
    [switch]$UseHosting = $false
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Require-Command([string]$CommandName) {
    if (-not (Get-Command $CommandName -ErrorAction SilentlyContinue)) {
        throw "No se encontro '$CommandName'. Instalala y reintenta."
    }
}

Require-Command "gcloud"
if ($UseHosting) {
    Require-Command "firebase"
}

$serviceAccountEmail = "$ServiceAccountName@$ProjectId.iam.gserviceaccount.com"

Write-Host "Configurando proyecto: $ProjectId" -ForegroundColor Cyan
gcloud config set project $ProjectId | Out-Null

Write-Host "Habilitando APIs necesarias..." -ForegroundColor Cyan
gcloud services enable `
    run.googleapis.com `
    cloudbuild.googleapis.com `
    artifactregistry.googleapis.com `
    firestore.googleapis.com `
    iam.googleapis.com | Out-Null

Write-Host "Verificando service account de Cloud Run..." -ForegroundColor Cyan
$sa = gcloud iam service-accounts list `
    --filter="email:$serviceAccountEmail" `
    --format="value(email)"

if (-not $sa) {
    gcloud iam service-accounts create $ServiceAccountName `
        --display-name "Cloud Run Chatbot RRHH" | Out-Null
}

Write-Host "Asignando permisos a service account..." -ForegroundColor Cyan
gcloud projects add-iam-policy-binding $ProjectId `
    --member="serviceAccount:$serviceAccountEmail" `
    --role="roles/datastore.user" `
    --quiet | Out-Null

Write-Host "Desplegando servicio en Cloud Run..." -ForegroundColor Cyan
$envVars = "CHATBOT_WEB_SECRET=$WebSecret,RRHH_AUTH_ENABLED=true,RRHH_ADMIN_USER=$AdminUser,RRHH_ADMIN_PASSWORD=$AdminPassword"
gcloud run deploy $ServiceName `
    --source . `
    --region $Region `
    --platform managed `
    --allow-unauthenticated `
    --service-account $serviceAccountEmail `
    --set-env-vars $envVars | Out-Null

$url = gcloud run services describe $ServiceName `
    --region $Region `
    --format="value(status.url)"

Write-Host "Cloud Run desplegado: $url" -ForegroundColor Green

if ($UseHosting) {
    Write-Host "Configurando Firebase Hosting con rewrite a Cloud Run..." -ForegroundColor Cyan

    if (-not (Test-Path "hosting")) {
        New-Item -ItemType Directory -Path "hosting" | Out-Null
    }
    if (-not (Test-Path "hosting\index.html")) {
        Set-Content -Path "hosting\index.html" -Value "<!doctype html><meta charset='utf-8'><title>Chatbot RRHH</title>"
    }

    if (-not (Test-Path "firebase.json")) {
        $firebaseJson = @"
{
  "hosting": {
    "public": "hosting",
    "ignore": ["firebase.json", "**/.*", "**/node_modules/**"],
    "rewrites": [
      {
        "source": "**",
        "run": {
          "serviceId": "$ServiceName",
          "region": "$Region"
        }
      }
    ]
  }
}
"@
        Set-Content -Path "firebase.json" -Value $firebaseJson
    }

    firebase use $ProjectId
    firebase deploy --only hosting
    Write-Host "Firebase Hosting desplegado para proyecto $ProjectId." -ForegroundColor Green
}

Write-Host ""
Write-Host "Deploy finalizado." -ForegroundColor Green
Write-Host "URL backend (Cloud Run): $url" -ForegroundColor Green
