# WhatsApp con Twilio – Paso a paso (con tus datos)

Guía con los pasos concretos para que el colaborador escriba por WhatsApp al número de Bacar y reciba respuestas del bot y del agente.

---

## Lo que ya tenés

- **Cuenta Twilio:** BacarIT  
- **Credenciales en `.env`:**
  - `TWILIO_ACCOUNT_SID=<tu_account_sid>`
  - `TWILIO_AUTH_TOKEN=...` (está en tu `.env`)
  - `TWILIO_WHATSAPP_FROM=whatsapp:+14155238886` (número del sandbox)
- **App desplegada en:** https://debo-chat.web.app

---

## Paso 1 – Unirte al sandbox desde tu WhatsApp

Solo los números que “se unen” al sandbox pueden enviar y recibir mensajes en modo prueba.

1. Abrí **WhatsApp** en tu celular.
2. Creá un **nuevo chat** con este número: **+1 415 523 8886**
3. Enviá **exactamente** este mensaje:  
   **`join stand-prevent`**
4. Twilio suele responder algo como “You are all set!”. A partir de ahí ese número ya puede chatear con el bot.

Si querés que **otro colaborador** pruebe, esa persona debe repetir el mismo paso (nuevo chat a +1 415 523 8886 y mensaje “join stand-prevent”).

---

## Paso 2 – Configurar el webhook en Twilio

El webhook es la URL a la que Twilio envía cada mensaje que recibe en tu número de WhatsApp.

1. Entrá a **https://www.twilio.com/console**
2. Elegí la cuenta **BacarIT** si te lo pide.
3. En el menú izquierdo: **Messaging** → **Try it out** → **Send a WhatsApp message** (o el enlace al sandbox de WhatsApp).
4. Buscá la sección donde se configura el **webhook** para mensajes entrantes (a veces dice “When a message comes in” o “URL for incoming messages”).
5. En la URL poné **exactamente**:
   ```text
   https://debo-chat.web.app/webhook/twilio/whatsapp
   ```
6. Método: **POST** (si Twilio lo pide).
7. Guardá los cambios.

Si tu app corre en otra URL (por ejemplo otra región o dominio), usá esa base y agregá `/webhook/twilio/whatsapp`. Ejemplo:  
`https://TU-DOMINIO.com/webhook/twilio/whatsapp`.

---

## Paso 3 – Tener la app desplegada con el webhook

La URL del paso 2 solo funciona si la app está publicada y el endpoint existe.

- Si ya desplegás en **debo-chat.web.app** (Firebase Hosting + Cloud Run), solo hace falta que el código con el webhook esté en la versión desplegada.
- Desplegá como siempre, por ejemplo:
  ```bash
  firebase deploy --only hosting:debo-chat
  ```
  (y lo que uses para subir el backend a Cloud Run).

---

## Paso 4 – Probar el flujo

1. En tu celular, abrí el chat de WhatsApp con **+1 415 523 8886** (el mismo donde enviaste “join stand-prevent”).
2. Escribí por ejemplo: **Bacar** (o el nombre de tu empresa).
3. El bot debería responder pidiendo sucursal o área, según cómo tengas configuradas las empresas.
4. Seguí el diálogo (sucursal, área, tema o “quiero hablar con rrhh”).
5. Si pedís hablar con un agente:
   - En el **Panel de atención** (https://debo-chat.web.app, entrando como RRHH) debería aparecer la conversación.
   - Lo que el agente escriba en el panel le llega al colaborador por **WhatsApp**.

Si no responde:

- Revisá que la URL del webhook en Twilio sea **exactamente**  
  `https://debo-chat.web.app/webhook/twilio/whatsapp`  
  y que esté en **POST**.
- Revisá que el último deploy incluya el endpoint `/webhook/twilio/whatsapp`.
- Revisá los logs del backend (Cloud Run o donde esté) por errores cuando Twilio llama al webhook.

---

## Paso 5 – Probar envío de comunicado (opcional)

Para probar que **vos** (o RRHH) podés enviar un mensaje a un número por WhatsApp:

1. En la carpeta del proyecto, en una terminal:
   ```bash
   python test_twilio_envio.py +54XXXXXXXXXX "Hola, mensaje de prueba"
   ```
   Reemplazá `+54XXXXXXXXXX` por un número que ya haya unido el sandbox (con “join stand-prevent”), en formato internacional.
2. Ese número debería recibir el mensaje en WhatsApp.

---

## Resumen rápido

| Paso | Qué hacer |
|------|-----------|
| 1 | En WhatsApp: nuevo chat a **+1 415 523 8886** y mensaje **join stand-prevent**. |
| 2 | En Twilio: Messaging → WhatsApp sandbox → URL de webhook = **https://debo-chat.web.app/webhook/twilio/whatsapp** (POST). |
| 3 | App desplegada (Firebase/Cloud Run) con el código del webhook. |
| 4 | Escribir al +1 415 523 8886 desde el mismo WhatsApp que unió el sandbox y probar empresa/sucursal/área y “hablar con rrhh”. |
| 5 | (Opcional) Probar envío con `test_twilio_envio.py` a un número que haya unido el sandbox. |

Con esto, el colaborador escribe desde su número de WhatsApp al número configurado (en sandbox: +1 415 523 8886) y vos seguís atendiendo desde el panel en debo-chat.web.app; las respuestas del agente le llegan por WhatsApp.
