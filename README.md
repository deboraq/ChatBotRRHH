# Asistente Virtual de RRHH - Bacar SA

Plataforma integral de atención a colaboradores vía web y WhatsApp, con panel de gestión RRHH, base de conocimiento inteligente y automatizaciones via N8N.

**Producción:** [debo-chat.web.app](https://debo-chat.web.app)

---

## Funcionalidades

### Chat con colaboradores
- Chat web en tiempo real con motor de IA (fuzzy matching + NLP)
- Canal WhatsApp via Twilio (mismo bot, misma base de conocimiento)
- Detección automática de empresa, sucursal y área del colaborador
- Menú interactivo con temas habilitados por empresa
- Análisis de sentimiento en consultas no resueltas (TextBlob)
- Botón "hablar con RRHH" disponible en cualquier momento

### Panel de atención RRHH (`/rrhh`)
- Bandeja de conversaciones derivadas (pendientes, en atención, cerradas)
- Buscador por nombre o número de teléfono
- Asignación automática de chats entre agentes activos
- Reasignación manual entre agentes
- Respuesta en tiempo real al colaborador (web y WhatsApp)
- Reabrir conversaciones cerradas
- Iniciar conversación proactiva hacia un colaborador
- Notificación por email al llegar un nuevo handoff (SMTP directo)
- Notificaciones push en el navegador (Web Push)
- Resumen automático de la conversación al derivar (Gemini AI)

### Comunicados masivos (`/comunicados`)
- Envío de mensajes por WhatsApp a lista de destinatarios
- Selección de contactos guardados por empresa
- Adjuntos: imagen, PDF o URL de archivo
- Envío con progreso en tiempo real (Server-Sent Events)
- **Comunicados programados**: programar envío para fecha/hora futura
  - N8N ejecuta cada 5 minutos y dispara los pendientes automáticamente

### Base de conocimiento (`/configuracion`)
- FAQs por empresa, sucursal y área
- Carga desde archivo CSV, PDF o texto plano
- Generación automática de FAQs desde documentos PDF via Gemini AI
- **Auto-sync desde Google Drive**: N8N detecta cambios en la carpeta configurada y actualiza la KB automáticamente
- Gestión de temas habilitados por empresa

### Configuración (`/configuracion`)
- Múltiples empresas con branding propio (nombre, logo, contacto)
- Sucursales y áreas por empresa
- Múltiples números de WhatsApp por empresa/área
- Email de notificación por número/área para derivaciones

### Historial (`/historial`)
- Registro completo de todos los mensajes (colaborador, bot, RRHH, sistema)
- Filtros por canal, empresa, colaborador, texto libre, fecha
- Descarga y exportación

### Estadísticas (`/estadisticas`)
- Dashboard en tiempo real conectado a Firestore
- Tasa de satisfacción, votos, temas más consultados
- Estado de derivaciones RRHH (abiertas / en atención / cerradas)
- Evolución de feedback (últimos 7 días)
- Pendientes por sentimiento
- Auto-refresco cada 1 minuto

### Legajos digitales
- Upload de archivos por colaborador (PDF, imágenes)
- Almacenamiento en Firebase Storage

### Usuarios y roles
- Autenticación con login para todos los módulos internos
- Roles: `admin` (todos los permisos), `rrhh` (conversaciones + historial)
- Roles personalizados desde el panel
- Permisos granulares: `conversaciones_ver`, `conversaciones_gestionar`, `historial_ver`, `usuarios_gestionar`, `roles_gestionar`, `comunicados_enviar`
- Restablecimiento de contraseña por email

---

## Tecnologías

| Capa | Tecnología |
|---|---|
| Backend | Python 3.12, Flask, Gunicorn |
| Base de datos | Firebase Firestore |
| Archivos | Firebase Storage |
| Hosting | Firebase Hosting → Cloud Run (`southamerica-east1`) |
| WhatsApp | Twilio WhatsApp API |
| IA / NLP | Gemini AI (FAQs), TheFuzz (fuzzy matching), TextBlob (sentimiento) |
| Automatizaciones | N8N (self-hosted) |
| Email | SMTP (Gmail App Password u otro) |
| Push | Web Push (VAPID) |

---

## Estructura del proyecto

```
# Backend
web_chat.py           # App Flask principal (rutas, lógica de negocio)
app.py                # Motor del chatbot (IA, respuestas, KB)
auth_rrhh.py          # Autenticación y roles RRHH
twilio_whatsapp.py    # Integración WhatsApp via Twilio
whatsapp_broadcast.py # Envío masivo por WhatsApp
stats_service.py      # Métricas y estadísticas
legajos_service.py    # Gestión de legajos digitales
firebase_config.py    # Configuración Firebase

# Frontend
templates/            # Jinja2: index, rrhh, historial, configuracion, comunicados, etc.
static/               # CSS, JS, íconos

# Infraestructura
Dockerfile            # Imagen para Cloud Run
firebase.json         # Firebase Hosting + rewrites
firestore.rules       # Reglas de seguridad Firestore
storage.rules         # Reglas de seguridad Storage

# Automatizaciones N8N
n8n/                  # Workflows exportados (importar en N8N para activar)

# Scripts de desarrollo y deploy (Windows)
scripts/              # PS1: iniciar local, deploy a Cloud Run + Firebase

# Documentación y tests
docs/                 # Guías técnicas de configuración e integración
tests/                # Tests unitarios e integración
```

---

## N8N — Automatizaciones activas

| Workflow | Trigger | Función |
|---|---|---|
| ChatBot Comunicados - Procesar Programados | Cada 5 min | Envía comunicados guardados con fecha/hora futura |
| ChatBot RRHH - Reporte Semanal | Lunes 8am | Envía reporte por empresa a cada email configurado |
| ChatBot KB - Auto-Sync desde Drive | Según Drive | Sincroniza la base de conocimiento desde Google Drive |

---

## Variables de entorno

Copiá `.env.example` a `.env` y completá:

```bash
# Auth panel interno
CHATBOT_WEB_SECRET=clave-larga-segura
RRHH_AUTH_ENABLED=true
RRHH_ADMIN_USER=admin
RRHH_ADMIN_PASSWORD=clave-segura

# Firebase
FIREBASE_CREDENTIALS=claves.json        # o dejar vacío en Cloud Run con SA
FIREBASE_STORAGE_BUCKET=it-analyzer.firebasestorage.app

# Twilio WhatsApp
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_WHATSAPP_FROM=whatsapp:+54911...

# SMTP (emails: notificaciones de handoff, reset de contraseña, reporte semanal)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=no-reply@tudominio.com
SMTP_PASSWORD=app-password-de-gmail
SMTP_FROM=no-reply@tudominio.com
SMTP_USE_TLS=true

# Gemini AI (generación de FAQs desde PDF)
GEMINI_API_KEY=

# N8N Webhook secret (para sync Drive y otros webhooks)
N8N_WEBHOOK_SECRET=
```

---

## Deploy (producción)

El deploy usa **Cloud Run** en `southamerica-east1` con **Firebase Hosting** como frontend en `debo-chat.web.app`.

```bash
# 1. Build imagen
gcloud builds submit --tag gcr.io/it-analyzer/chatbot-rrhh --project it-analyzer

# 2. Deploy a Cloud Run
gcloud run deploy chatbot-rrhh \
  --image gcr.io/it-analyzer/chatbot-rrhh \
  --project it-analyzer \
  --region southamerica-east1

# 3. Deploy Firebase Hosting
firebase deploy --only hosting:debo-chat
```

O desde Windows con un solo comando:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\deploy_firebase_cloudrun.ps1 -ProjectId "it-analyzer" -UseHosting -HostingSite "debo-chat"
```

> Siempre usar `--only hosting:debo-chat`. No usar `firebase deploy --only hosting` (despliega todos los sitios).

URLs:
- **Producción (Firebase Hosting):** https://debo-chat.web.app
- **Cloud Run directo:** https://chatbot-rrhh-528225147242.southamerica-east1.run.app
- GCP Project: `it-analyzer`

---

## Desarrollo local (Windows)

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\iniciar_windows_it_analyzer.ps1
```

O manualmente:

```bash
pip install -r requirements.txt
python web_chat.py
```

Abrí en `http://localhost:5000`.

### Deploy rápido desde Windows

```powershell
.\deploy_firebase_cloudrun.ps1 -ProjectId "it-analyzer" -UseHosting -HostingSite "debo-chat"
```

---

## Módulos internos

| URL | Descripción |
|---|---|
| `/` | Chat web con colaboradores |
| `/rrhh` | Panel de atención RRHH |
| `/historial` | Historial completo de conversaciones |
| `/estadisticas` | Dashboard de métricas |
| `/comunicados` | Envío masivo y programado por WhatsApp |
| `/configuracion` | Empresas, usuarios, roles, KB |
| `/login` | Autenticación |

---

## Documentación adicional

Ver carpeta `docs/`:

- `TWILIO_WHATSAPP.md` — Configuración WhatsApp Business API
- `WHATSAPP_COMUNICADOS_MASIVOS.md` — Envío masivo
- `DOCUMENT_AI_BASE_CONOCIMIENTO.md` — Base de conocimiento con Document AI
- `CONFIGURAR_EMAIL.md` — Configuración SMTP
- `ALMACENAMIENTO_Y_COSTO.md` — Firebase Storage
- `WHATSAPP_MULTIPLES_NUMEROS.md` — Multi-número por empresa
