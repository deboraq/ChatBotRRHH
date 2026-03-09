# Cloud Run – Paso a paso: variables de Twilio

Para que el chat por WhatsApp y el webhook funcionen en **https://debo-chat.web.app**, tenés que cargar las variables de Twilio en el servicio de Cloud Run.

---

## Paso 1 – Entrar a Cloud Run

1. Abrí **https://console.cloud.google.com**
2. Arriba, elegí el proyecto **it-analyzer** (selector de proyecto).
3. En el menú de la izquierda (o en la búsqueda): **Cloud Run**.
4. En la lista de servicios, hacé clic en **chatbot-rrhh**.

---

## Paso 2 – Editar el servicio

1. Arriba de la página del servicio, hacé clic en **EDITAR NUEVA REVISIÓN** (o **Edit new revision**).
2. Esperá a que cargue la configuración (imagen, región, etc.).

---

## Paso 3 – Variables y secretos

1. Desplegá la sección **Variables y secretos** (o **Variables & Secrets**).
2. En **Variables de entorno** vas a ver las que ya tiene (por ejemplo `CHATBOT_WEB_SECRET`, `RRHH_AUTH_ENABLED`, etc.).
3. Clic en **+ AÑADIR VARIABLE** (o **+ Add variable**) y agregá **una por una**:

   | Nombre                     | Valor                          |
   |----------------------------|--------------------------------|
   | `TWILIO_ACCOUNT_SID`       | *(Account SID de Twilio)*      |
   | `TWILIO_AUTH_TOKEN`        | *(el token que tenés en tu .env)* |
   | `TWILIO_WHATSAPP_FROM`     | `whatsapp:+14155238886`        |
   | `FIREBASE_STORAGE_BUCKET`  | `it-analyzer.firebasestorage.app` |

4. **FIREBASE_STORAGE_BUCKET** es necesario para que desde el panel puedas **subir fotos o archivos** (adjuntos) y no aparezca "Storage no configurado".
5. El **Auth Token** lo copiás de tu archivo `.env` (línea `TWILIO_AUTH_TOKEN=...`) o de la consola de Twilio (Account → Auth Token → Show / Copiar).
6. No dejes espacios antes o después del valor.

---

## Paso 4 – Desplegar

1. Bajá hasta el final de la página.
2. Clic en **DESPLEGAR** (o **Deploy**).
3. Esperá a que termine (1–2 minutos). Cuando diga “Revisión lista” o “Revision ready”, ya está.

---

## Paso 5 – Probar

1. Desde WhatsApp, enviá un mensaje al número del sandbox (**+1 415 523 8886**), por ejemplo: **Bacar**.
2. El bot debería responder. Si no responde, revisá en Cloud Run → **Registros** (Logs) si llegan requests al webhook y si hay errores.

---

## Resumen

| Dónde              | Qué hacer |
|--------------------|-----------|
| Consola            | Google Cloud → proyecto **it-analyzer** → **Cloud Run** → **chatbot-rrhh** |
| Editar             | **Editar nueva revisión** |
| Variables          | **Variables y secretos** → **Añadir variable** → `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_FROM`, `FIREBASE_STORAGE_BUCKET` |
| Valores            | Los mismos que en tu `.env`; para Storage: `it-analyzer.firebasestorage.app` |
| Guardar            | **Desplegar** y esperar a que termine |

Cuando la nueva revisión esté activa, **debo-chat.web.app** usará esas variables y el webhook de Twilio funcionará en producción.
