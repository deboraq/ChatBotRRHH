# Setup ChatBot RRHH en Windows

Guía para traer los cambios de GitHub y levantar el proyecto en localhost (según agente "Chatbot mejoras").

---

## 1. Traer los cambios de GitHub

En **PowerShell** o **Terminal**:

```powershell
cd c:\Users\Usr\Desktop\ChatBotRRHH
git pull origin cursor/chatbot-mejoras-e2c5
```

Si aparece error de credenciales:

- **Opción A:** Instalá [GitHub CLI](https://cli.github.com/) y ejecutá `gh auth login` antes del `git pull`.
- **Opción B:** Abrí **Administrador de credenciales de Windows** → Credenciales de Windows → eliminá entradas viejas de `github.com` y volvé a intentar el `git pull`.

---

## 2. Levantar el proyecto en localhost

### Con el script (recomendado)

```powershell
cd c:\Users\Usr\Desktop\ChatBotRRHH
.\levantar_local.ps1
```

### Manual

```powershell
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt -r requirements-full.txt
python web_chat.py
```

Luego abrí **http://localhost:5000** en el navegador.

---

## 3. Firebase (opcional)

Si usás Firebase, copiá tu archivo de credenciales (por ejemplo `claves.json` o `claves-bacar.json`) al proyecto y configurá:

```powershell
$env:FIREBASE_CREDENTIALS = "claves.json"
```

**Setup actual de referencia:**

| Componente        | Valor                    |
|-------------------|--------------------------|
| Proyecto Firebase | "Chatbot" (ID: `it-analyzr`) |
| Firestore         | `chat_historial`, `faq_rrhh`, `Feedback_respuestas`, `rrhh_handoffs`, etc. |
| Hosting           | `t-anal-yapp.web.app`    |
| Credenciales      | `claves.json` en la raíz (Service Account Key del proyecto Chatbot) |

Para obtener la clave: Firebase Console → Configuración del proyecto → Cuentas de servicio → Crear clave privada → descargar JSON → guardar como `claves.json`.

---

## 4. Panel RRHH – Usuario y contraseña

### Variables de entorno

```powershell
$env:RRHH_AUTH_ENABLED = "true"
$env:RRHH_ADMIN_USER = "admin"
$env:RRHH_ADMIN_PASSWORD = "admin123"
python web_chat.py
```

Luego entrá a **http://localhost:5000/login** con `admin` / `admin123`.

### Archivo `rrhh_users.json`

Si existe `rrhh_users.json`, las credenciales son las definidas ahí. Ejemplo en `rrhh_users.example.json`: usuario **laura**, contraseña **cambiar-esta-clave**.

### Cambiar contraseña (generar hash)

```powershell
python auth_rrhh.py --hash "nueva-contraseña"
```

Copiá el hash en `rrhh_users.json` en el campo `password_hash` del usuario.

---

## Resumen rápido

1. `git pull origin cursor/chatbot-mejoras-e2c5`
2. `.\levantar_local.ps1`
3. Opcional: `$env:FIREBASE_CREDENTIALS = "claves.json"`
4. Navegador: http://localhost:5000 (login: admin / admin123 si usás variables de entorno)
