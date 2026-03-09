# WhatsApp por Twilio: no responde / no llega a la plataforma

Si enviás un mensaje por WhatsApp al número de Bacar y **no te contesta el chatbot** ni **aparece en el panel RRHH**, revisá estos puntos en orden.

---

## 1. URL del webhook en Twilio (lo más frecuente)

Twilio tiene que llamar a tu backend cada vez que alguien escribe al número de WhatsApp. Si la URL no está configurada o está mal, el mensaje nunca llega.

**URL que debe tener Twilio (copiá tal cual, sin espacios ni barra final):**

```
https://chatbot-rrhh-528225147242.southamerica-east1.run.app/webhook/twilio/whatsapp
```

**Errores frecuentes:** `52022514/242` → tiene que ser **528225147242** (sin barra). `eastt` → tiene que ser **east1** (con uno).

**Dónde configurarla:**

1. Entrá a **[Twilio Console](https://console.twilio.com)**.
2. Menú **Messaging** → **Try it out** → **Send a WhatsApp message**  
   **o** **Explore** → **Messaging** → **Settings** → **WhatsApp senders** (o el número/canal que uses).
3. En el número/canal de WhatsApp que recibe los mensajes, buscá **"When a message comes in"** (Cuando llega un mensaje).
4. Pegá la URL de arriba.
5. Método: **HTTP POST** (si Twilio ofrece GET también, puede quedar en POST).
6. Guardá.

**Importante:** La URL debe ser **HTTPS** y exactamente esa ruta. No debe terminar en `/`.

---

## 2. Variables de Twilio en Cloud Run

Si el webhook no tiene credenciales en el servidor, no puede enviar la respuesta por WhatsApp (y puede fallar algo interno).

En **Google Cloud Console** → **Cloud Run** → **chatbot-rrhh** → **Editar nueva revisión** → **Variables y secretos**, tené que tener:

| Variable | Ejemplo |
|----------|---------|
| `TWILIO_ACCOUNT_SID` | `AC...` (de Twilio) |
| `TWILIO_AUTH_TOKEN` | token secreto |
| `TWILIO_WHATSAPP_FROM` | `whatsapp:+14155238886` (tu número de Twilio para WhatsApp) |

Detalle: [CLOUD_RUN_VARIABLES_TWILIO.md](CLOUD_RUN_VARIABLES_TWILIO.md).

---

## 3. Ver si Twilio está llamando al webhook (logs)

En **Cloud Run** → **chatbot-rrhh** → pestaña **Registros** (Logs), buscá líneas que digan:

- **`Webhook Twilio WhatsApp: From=...`**  
  → Twilio **sí** está llamando. Si después no contestás, el fallo puede ser de sesión, empresa/sucursal/área o handoff.
- Si **nunca** aparece esa línea cuando mandás un mensaje por WhatsApp, Twilio **no** está llamando a esa URL: revisá el punto 1 (URL y método POST).

También podés buscar errores: **`Webhook Twilio: error en _process_chat_turn`** o **`no se pudo enviar respuesta por WhatsApp`**.

---

## 4. Número de WhatsApp (sandbox vs producción)

- **Sandbox de Twilio:** Solo recibe mensajes de números que **antes** enviaron el código de unión al sandbox (ej. "join xxx-xxx"). Si no hiciste "join", Twilio puede no entregar o no disparar el webhook.
- **Producción:** El número verificado recibe de cualquier usuario; el webhook es el mismo.

---

## 5. Resumen de comprobaciones

| Revisar | Dónde |
|--------|--------|
| URL del webhook | Twilio Console → Messaging / WhatsApp senders → "When a message comes in" |
| Método POST | Mismo lugar, método **HTTP POST** |
| Variables Twilio | Cloud Run → chatbot-rrhh → Variables y secretos |
| Si llegan requests | Cloud Run → chatbot-rrhh → Registros → buscar "Webhook Twilio WhatsApp" |

Cuando la URL esté bien y las variables cargadas en Cloud Run, volvé a desplegar si hiciste cambios, enviá un mensaje por WhatsApp y revisá los logs para confirmar que aparece la línea del webhook.
