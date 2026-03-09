# Chat por WhatsApp (colaborador escribe al número de Bacar)

El **colaborador** puede escribir desde su WhatsApp al **número configurado como agente de Bacar** (el número de Twilio). La conversación con el bot y la derivación a un agente ocurren por WhatsApp. Los **agentes** siguen atendiendo desde el **Panel de atención** en la web; cuando responden, el mensaje se envía al colaborador por WhatsApp.

---

## Flujo

1. **Colaborador** abre WhatsApp y escribe al número de Bacar (ej. el número del sandbox o el número de producción de Twilio).
2. **Twilio** recibe el mensaje y lo reenvía a esta app (webhook).
3. La app identifica al colaborador por su número de teléfono, mantiene el contexto (empresa, sucursal, área) y genera la respuesta con la misma lógica del chat web (bot o handoff).
4. La respuesta se envía de vuelta por **Twilio** al WhatsApp del colaborador.
5. Si el colaborador pide hablar con un agente, se crea un handoff; el **agente** ve la conversación en el **Panel de atención** (web) y escribe su respuesta ahí.
6. La respuesta del agente se envía automáticamente por **WhatsApp** al número del colaborador.

---

## Qué está implementado

- **Webhook** `POST /webhook/twilio/whatsapp`: recibe los mensajes entrantes de Twilio (From, To, Body).
- **Sesión por teléfono**: el estado del chat (empresa, sucursal, área, handoff) se guarda por número de WhatsApp del colaborador.
- **Misma lógica que el chat web**: selección de empresa/sucursal/área, menú de temas, derivación a RRHH y respuestas del bot.
- **Respuestas del agente por WhatsApp**: cuando un handoff se originó por WhatsApp, los mensajes que el agente escribe en el panel se envían también por WhatsApp al colaborador.

---

## Configuración en Twilio

1. En **Messaging** → **Try it out** → **Send a WhatsApp message** (o en **Settings** del número), configurá la **URL del webhook** para mensajes entrantes:
   - `https://tu-dominio.com/webhook/twilio/whatsapp`
   - Método: **POST**.
2. Twilio enviará un POST con `From` (número del colaborador), `To` (tu número), `Body` (texto del mensaje).
3. La app responde con TwiML vacío (el mensaje al colaborador se envía por API, no en la respuesta del webhook).

---

## Número “desde” por empresa

El número al que el colaborador escribe (y desde el que la app responde) puede ser:
- **Un solo número** (ej. sandbox): variable de entorno `TWILIO_WHATSAPP_FROM`.
- **Por empresa**: en el documento de la empresa (Firestore) el campo `twilio_whatsapp_from` (ej. `whatsapp:+54911...`). Así cada empresa puede tener su propio número de WhatsApp.
