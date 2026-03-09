# Conectar WhatsApp con Twilio

Esta aplicación puede usar **Twilio** para enviar mensajes por WhatsApp (comunicados, respuestas, etc.). Twilio actúa como proveedor oficial frente a Meta; vos te conectás a la API de Twilio y Twilio se encarga del enlace con WhatsApp.

---

## 1. Qué necesitás en Twilio

- **Cuenta Twilio** (ya tenés una, ej. "BacarlT").
- **Account SID** y **Auth Token**: en la [consola de Twilio](https://www.twilio.com/console) → resumen del proyecto o "Account" → Account SID y Auth Token (no los compartas ni los subas al repo).
- **Número de WhatsApp** configurado en Twilio:
  - **Sandbox (pruebas):** En la consola → **Messaging** → **Try it out** → **Send a WhatsApp message** → te dan un número de prueba y un código para unirte al sandbox desde tu WhatsApp. Solo podés enviar a números que se hayan unido al sandbox.
  - **Producción:** En **Messaging** → **WhatsApp** → **Senders** podés solicitar o conectar tu propio número; Twilio te guía con la aprobación de Meta.

---

## 2. Dónde encontrar SID y Auth Token

1. Entrá a **https://www.twilio.com/console**.
2. Si te pide, elegí la cuenta (ej. "BacarlT").
3. En la página de inicio del proyecto (o en **Account** → **Keys & credentials**) vas a ver:
   - **Account SID** (empieza con `AC...`).
   - **Auth Token** (clic en "Show" para verlo).
4. Guardalos en **variables de entorno** en el servidor donde corre la app, por ejemplo:
   - `TWILIO_ACCOUNT_SID=AC...`
   - `TWILIO_AUTH_TOKEN=...`

**No** pongas el Auth Token en el código ni en el repositorio.

---

## 3. Configurar el número "desde" (por empresa)

Para cada empresa que envíe comunicados necesitás un número "desde" en formato que Twilio acepte:

- En **sandbox:** el número te lo da Twilio (ej. `whatsapp:+14155238886`).
- En **producción:** es el número que hayas dado de alta en Twilio para WhatsApp (ej. `whatsapp:+5491123456789`).

En esta app, por empresa se guarda ese número "desde" (ej. en Firestore, en el documento de la empresa):

- Campo sugerido: **`twilio_whatsapp_from`** con valor tipo `whatsapp:+14155238886` (con prefijo `whatsapp:`).

Si solo tenés un número por ahora, podés usar una sola variable de entorno `TWILIO_WHATSAPP_FROM=whatsapp:+14155238886` y usarla para todas las empresas hasta que definas uno por empresa.

---

## 4. Enviar un mensaje desde Python (Twilio)

Instalá el cliente de Twilio:

```bash
pip install twilio
```

Ejemplo mínimo:

```python
from twilio.rest import Client
import os

client = Client(
    os.environ["TWILIO_ACCOUNT_SID"],
    os.environ["TWILIO_AUTH_TOKEN"],
)
message = client.messages.create(
    body="Hola, este es un comunicado de RRHH.",
    from_="whatsapp:+14155238886",   # tu número Twilio WhatsApp
    to="whatsapp:+5491112345678",    # destinatario en formato E.164
)
```

Para **comunicados masivos** seguís usando el módulo **`whatsapp_broadcast`** de este proyecto: solo hay que conectar una función que envíe un mensaje por vez usando Twilio (ver más abajo).

---

## 5. Activar el envío con Twilio en la app

En el arranque de la aplicación (por ejemplo en `web_chat.py` o donde inicialices el backend), antes de enviar cualquier comunicado, ejecutá:

```python
from twilio_whatsapp import register_twilio_sender
register_twilio_sender()
```

Así el módulo `whatsapp_broadcast` usará Twilio para cada envío. Necesitás tener instalado `twilio` (está en `requirements-full.txt`).

---

## 6. Cómo se integra con esta aplicación

En el proyecto hay un módulo **`whatsapp_broadcast.py`** que envía en **lotes con pausa** (throttling) para no saturar y reducir riesgo de bloqueo. La idea es que la función que “envía un mensaje” use Twilio en lugar de llamar directo a Meta.

- Opción **A – Módulo listo:** Usar **`twilio_whatsapp.py`** (en la raíz del proyecto). Ese módulo:
  - Lee `TWILIO_ACCOUNT_SID` y `TWILIO_AUTH_TOKEN`.
  - Expone una función que recibe número destino, texto (o plantilla) y el número “desde” (por empresa).
  - Esa función se registra en `whatsapp_broadcast` con `set_send_function(...)`.
- Opción **B – Propia:** Implementar vos una función que, con los mismos parámetros, llame a `client.messages.create(...)` y registrarla con `set_send_function`.

El flujo de la app (pantalla Comunicados, empresa, lista de destinatarios, plantilla, etc.) sigue igual; solo cambia que “quien envía” es Twilio. Los comunicados se siguen enviando en lotes con pausa.

---

## 7. Límites y buenas prácticas con Twilio

- **Sandbox:** Solo podés enviar a números que se hayan unido al sandbox (código que muestra Twilio en la consola).
- **Producción:** Cuando des de alta tu número, aplican los límites de WhatsApp/Meta (por ejemplo, mensajes plantilla para iniciar conversación).
- **Throttling:** Sigue siendo importante no mandar cientos de mensajes en segundos. El módulo `whatsapp_broadcast` ya aplica lotes y pausas; usalo también con Twilio.
- **Costos:** Twilio cobra por mensaje; revisá la [página de precios de Twilio para WhatsApp](https://www.twilio.com/whatsapp/pricing).

---

## 8. Resumen

| Qué | Dónde / Cómo |
|-----|----------------|
| Cuenta | Ya tenés (ej. BacarlT) en twilio.com/console. |
| Account SID y Auth Token | Consola → Account / Keys → variables de entorno. |
| Número “desde” | Sandbox o Senders en Messaging → WhatsApp; guardar en `twilio_whatsapp_from` por empresa o en env. |
| Envío desde la app | Usar `twilio_whatsapp.py` + `whatsapp_broadcast` (o tu función con `set_send_function`). |
| Comunicados masivos | Mismo flujo que en COMUNICADOS_DESDE_LA_APP; el backend usa Twilio en lugar de Meta directo. |

Si antes tenías pensado usar la API de Meta (WhatsApp Cloud API), con Twilio **no** necesitás configurar Meta for Developers ni el token de WhatsApp Cloud para el envío: solo Account SID, Auth Token y el número WhatsApp en Twilio.
