# Configurar el envío de email (recuperar contraseña)

Para que cuando alguien pida recuperar contraseña **le llegue el correo** con el enlace, tenés que configurar SMTP. Pasos:

---

## Paso 1: Instalar la dependencia que lee el archivo .env

En la carpeta del proyecto, en la terminal:

```bash
pip install python-dotenv
```

(O instalar todo: `pip install -r requirements.txt`)

---

## Paso 2: Crear el archivo .env

En la **raíz del proyecto** (donde está `web_chat.py`):

1. Copiá el archivo de ejemplo:
   - **Windows (PowerShell):** `Copy-Item .env.example .env`
   - **Windows (CMD):** `copy .env.example .env`
   - **Mac/Linux:** `cp .env.example .env`

2. Abrí el archivo `.env` con el editor de texto.

---

## Paso 3: Completar las variables SMTP en .env

En `.env` vas a ver algo como esto. Reemplazá los valores por los de **tu servidor de correo**:

```env
SMTP_HOST=smtp.ejemplo.com
SMTP_PORT=587
SMTP_USER=no-reply@tudominio.com
SMTP_PASSWORD=tu-clave-smtp
SMTP_FROM=no-reply@tudominio.com
SMTP_USE_TLS=true
```

- **SMTP_HOST:** servidor SMTP del proveedor (ver ejemplos abajo).
- **SMTP_PORT:** casi siempre `587` (con TLS).
- **SMTP_USER:** usuario o email con el que te logueás en el servidor.
- **SMTP_PASSWORD:** contraseña (en Gmail no es tu contraseña normal; ver abajo).
- **SMTP_FROM:** dirección que aparece como “quien envía” (puede ser la misma que SMTP_USER).
- **SMTP_USE_TLS:** dejalo en `true`.

**No subas el archivo `.env` a Git** (ya debería estar en `.gitignore`); tiene datos sensibles.

---

## Paso 4: Ejemplos por proveedor

### Gmail

1. Activá [verificación en 2 pasos](https://myaccount.google.com/security) en tu cuenta de Google.
2. Creá una [Contraseña de aplicación](https://myaccount.google.com/apppasswords) para “Correo” y “Otro dispositivo”.
3. En `.env` usá:
   ```env
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USER=tu-email@gmail.com
   SMTP_PASSWORD=la-contraseña-de-16-caracteres-que-te-dio-google
   SMTP_FROM=tu-email@gmail.com
   SMTP_USE_TLS=true
   ```

### Outlook / Microsoft 365

```env
SMTP_HOST=smtp.office365.com
SMTP_PORT=587
SMTP_USER=tu-email@tuempresa.com
SMTP_PASSWORD=tu-contraseña
SMTP_FROM=tu-email@tuempresa.com
SMTP_USE_TLS=true
```

### SendGrid (servicio de envío)

1. Creá una API Key en SendGrid.
2. En `.env`:
   ```env
   SMTP_HOST=smtp.sendgrid.net
   SMTP_PORT=587
   SMTP_USER=apikey
   SMTP_PASSWORD=tu-api-key-de-sendgrid
   SMTP_FROM=no-reply@tudominio.com
   SMTP_USE_TLS=true
   ```

---

## Paso 5: Reiniciar la aplicación

Guardá el `.env`, cerrá la aplicación si estaba corriendo y volvé a iniciarla:

```bash
python web_chat.py
```

(O el comando que uses para levantar el servidor.)

---

## Paso 6: Probar

1. Entrá a **Recuperar contraseña** (desde el login: “Restablecela por email”).
2. Ingresá **usuario** y **email** de un usuario que exista en el sistema (el email debe coincidir con el del usuario).
3. Enviar.

Si todo está bien configurado:
- La página debería decir algo como “Si los datos coinciden, enviamos un enlace…”
- El correo debe llegar a la casilla del usuario con el enlace para restablecer la contraseña.

Si ves “El envío por email no está configurado” o el enlace solo en pantalla, revisá que:
- El archivo se llame exactamente `.env` y esté en la raíz del proyecto.
- No haya espacios alrededor del `=` en las variables (ej. `SMTP_HOST=smtp.gmail.com`).
- Hayas reiniciado la app después de cambiar `.env`.

---

## Resumen rápido

| Paso | Qué hacer |
|------|-----------|
| 1 | `pip install python-dotenv` |
| 2 | Copiar `.env.example` a `.env` |
| 3 | Editar `.env` y poner tu SMTP_HOST, SMTP_USER, SMTP_PASSWORD, etc. |
| 4 | Usar los ejemplos (Gmail, Outlook, SendGrid) si no sabés qué poner |
| 5 | Reiniciar la aplicación |
| 6 | Probar desde “Recuperar contraseña” |
