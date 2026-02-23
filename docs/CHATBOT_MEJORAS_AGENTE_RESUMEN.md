# Todo lo del agente "Chatbot mejoras" – Resumen

Este documento concentra todo lo que se hizo y se indicó en el chat del agente "Chatbot mejoras" (transcript `7fd7e7c4-e2e8-402b-9e72-1801a9f7fc15`).

---

## Situación que se trabajó

- **Rama:** `cursor/chatbot-mejoras-e2c5`
- **Objetivo:** Traer los cambios hechos en Mac desde GitHub y levantar el chatbot en Windows en localhost.
- **Problema detectado:** Git en Windows sin credenciales para GitHub.

---

## 1. Traer cambios de GitHub

```powershell
cd c:\Users\Usr\Desktop\ChatBotRRHH
git pull origin cursor/chatbot-mejoras-e2c5
```

Si falla por credenciales:

- **Opción A:** Instalar [GitHub CLI](https://cli.github.com/) y ejecutar `gh auth login` antes del `git pull`.
- **Opción B:** Administrador de credenciales de Windows → Credenciales de Windows → borrar entradas antiguas de `github.com` y volver a intentar.

---

## 2. Levantar el proyecto en localhost

**Con script:**

```powershell
cd c:\Users\Usr\Desktop\ChatBotRRHH
.\levantar_local.ps1
```

**Manual:**

```powershell
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt -r requirements-full.txt
python web_chat.py
```

Abrir **http://localhost:5000**.

---

## 3. Firebase

- **Proyecto:** "Chatbot" (ID: `it-analyzr`)
- **Firestore:** `chat_historial`, `faq_rrhh`, `Feedback_respuestas`, `rrhh_handoffs`, etc.
- **Hosting:** `t-anal-yapp.web.app`
- **Credenciales en el proyecto:** `claves.json`, `claves-vieja.json`, `clavesbackup.json`

`claves.json` debe ser la **Service Account Key** del proyecto "Chatbot". Si se usa otro archivo:

```powershell
$env:FIREBASE_CREDENTIALS = "claves.json"
```

En `/estadisticas` debería verse el proyecto Firebase conectado (`it-analyzr`) y no `modo_local_sin_firestore`.

---

## 4. Panel RRHH – Usuario y contraseña

- **Variables de entorno:** `RRHH_ADMIN_USER` y `RRHH_ADMIN_PASSWORD`. Ejemplo: usuario **admin**, contraseña la que definas.
- **Archivo `rrhh_users.json`:** Credenciales definidas ahí. En `rrhh_users.example.json`: usuario **laura**, contraseña **cambiar-esta-clave**.
- **Desarrollo típico:** Usuario **admin**, contraseña **admin123**.

Para usar variables de entorno antes de levantar:

```powershell
$env:RRHH_AUTH_ENABLED = "true"
$env:RRHH_ADMIN_USER = "admin"
$env:RRHH_ADMIN_PASSWORD = "admin123"
python web_chat.py
```

Login en **http://localhost:5000/login** con `admin` / `admin123`.

**Regenerar hash de contraseña:**

```powershell
python auth_rrhh.py --hash "nueva-contraseña"
```

El hash se copia en `rrhh_users.json` en el campo `password_hash` del usuario.

---

## Archivos creados por / para este agente

| Archivo | Descripción |
|---------|-------------|
| `levantar_local.ps1` | Script para activar venv, instalar dependencias y ejecutar `web_chat.py`. |
| `SETUP_WINDOWS.md` | Instrucciones de setup en Windows (Git, levantar app, Firebase, RRHH). |
| `docs/CHATBOT_MEJORAS_AGENTE_RESUMEN.md` | Este resumen con todo lo del agente "Chatbot mejoras". |

---

*Resumen generado a partir del transcript del agente "Chatbot mejoras".*
