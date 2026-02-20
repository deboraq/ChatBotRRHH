param(
    [string]$ProjectId = "it-analyzer",
    [string]$Region = "southamerica-east1",
    [string]$ServiceName = "chatbot-rrhh",
    [string]$ServiceAccountName = "chatbot-rrhh-run",
    [string]$AdminUser = "admin",
    [string]$AdminPassword = "admin123",
    [string]$WebSecret = "cambiar-por-secreto-largo",
    [switch]$UseHosting = $false,
    [switch]$UseDefaultServiceAccount = $false
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Require-Command([string]$CommandName) {
    if (-not (Get-Command $CommandName -ErrorAction SilentlyContinue)) {
        throw "No se encontro '$CommandName'. Instalala y reintenta."
    }
}

function Assert-LastExit([string]$Step) {
    if ($LASTEXITCODE -ne 0) {
        throw "Fallo en: $Step (exit code $LASTEXITCODE). Revisa errores de permisos/IAM en la salida."
    }
}

Require-Command "gcloud"
if ($UseHosting) {
    Require-Command "firebase"
}

$serviceAccountEmail = "$ServiceAccountName@$ProjectId.iam.gserviceaccount.com"

Write-Host "Configurando proyecto: $ProjectId" -ForegroundColor Cyan
gcloud config set project $ProjectId | Out-Null
Assert-LastExit "gcloud config set project"

Write-Host "Habilitando APIs necesarias..." -ForegroundColor Cyan
gcloud services enable `
    run.googleapis.com `
    cloudbuild.googleapis.com `
    artifactregistry.googleapis.com `
    firestore.googleapis.com `
    iam.googleapis.com | Out-Null
Assert-LastExit "gcloud services enable"

if (-not $UseDefaultServiceAccount) {
    Write-Host "Verificando service account de Cloud Run..." -ForegroundColor Cyan
    $sa = gcloud iam service-accounts list `
        --filter="email:$serviceAccountEmail" `
        --format="value(email)"
    Assert-LastExit "gcloud iam service-accounts list"

    if (-not $sa) {
        gcloud iam service-accounts create $ServiceAccountName `
            --display-name "Cloud Run Chatbot RRHH" | Out-Null
        Assert-LastExit "gcloud iam service-accounts create"
    }

    Write-Host "Asignando permisos a service account..." -ForegroundColor Cyan
    gcloud projects add-iam-policy-binding $ProjectId `
        --member="serviceAccount:$serviceAccountEmail" `
        --role="roles/datastore.user" `
        --quiet | Out-Null
    Assert-LastExit "gcloud projects add-iam-policy-binding"
}
else {
    Write-Host "Modo UseDefaultServiceAccount activo: se omite creacion/configuracion de service account." -ForegroundColor Yellow
}

Write-Host "Desplegando servicio en Cloud Run..." -ForegroundColor Cyan
$envVars = "CHATBOT_WEB_SECRET=$WebSecret,RRHH_AUTH_ENABLED=true,RRHH_ADMIN_USER=$AdminUser,RRHH_ADMIN_PASSWORD=$AdminPassword"
if ($UseDefaultServiceAccount) {
    gcloud run deploy $ServiceName `
        --source . `
        --region $Region `
        --platform managed `
        --allow-unauthenticated `
        --set-env-vars $envVars | Out-Null
}
else {
    gcloud run deploy $ServiceName `
        --source . `
        --region $Region `
        --platform managed `
        --allow-unauthenticated `
        --service-account $serviceAccountEmail `
        --set-env-vars $envVars | Out-Null
}
Assert-LastExit "gcloud run deploy"

# Intenta dejar el servicio publico para evitar 403 en navegador.
Write-Host "Intentando habilitar acceso publico (allUsers:roles/run.invoker)..." -ForegroundColor Cyan
gcloud run services add-iam-policy-binding $ServiceName `
    --region $Region `
    --member="allUsers" `
    --role="roles/run.invoker" `
    --quiet | Out-Null

if ($LASTEXITCODE -ne 0) {
    Write-Warning "No se pudo habilitar acceso publico automaticamente."
    Write-Warning "Tu usuario no tiene permisos IAM o hay una politica de organizacion que lo bloquea."
    Write-Host "Comando para ejecutar con un usuario owner/admin:" -ForegroundColor Yellow
    Write-Host "gcloud run services add-iam-policy-binding $ServiceName --region $Region --member=`"allUsers`" --role=`"roles/run.invoker`" --project $ProjectId" -ForegroundColor Yellow
}
else {
    Write-Host "Acceso publico habilitado correctamente." -ForegroundColor Green
}

$url = gcloud run services describe $ServiceName `
    --region $Region `
    --format="value(status.url)"
Assert-LastExit "gcloud run services describe"

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
    Assert-LastExit "firebase use"
    firebase deploy --only hosting
    Assert-LastExit "firebase deploy --only hosting"
    Write-Host "Firebase Hosting desplegado para proyecto $ProjectId." -ForegroundColor Green
}

Write-Host ""
Write-Host "Deploy finalizado." -ForegroundColor Green
Write-Host "URL backend (Cloud Run): $url" -ForegroundColor Green
