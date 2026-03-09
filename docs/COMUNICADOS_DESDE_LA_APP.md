# Cómo se envían los comunicados desde la aplicación

Guía de **cómo van a mandar** los comunicados por WhatsApp desde esta aplicación: flujo para el usuario (RRHH/admin) y qué hay que tener implementado en el backend.

> **Proveedor de WhatsApp:** Esta app puede usar **Twilio** para enviar los mensajes (recomendado). Ver **[TWILIO_WHATSAPP.md](TWILIO_WHATSAPP.md)** para configuración (Account SID, Auth Token, número) y el módulo `twilio_whatsapp.py`.

---

## 1. Flujo para el usuario (desde la app)

La idea es que alguien con permiso (RRHH o admin) pueda **disparar un comunicado** desde la misma app donde está el chat y el panel de atención.

### Pantalla “Comunicados” (a implementar)

- **Dónde:** Un nuevo ítem en el menú, por ejemplo **“Comunicados”**, al mismo nivel que “Panel de atención”, “Configuración”, “Estadísticas”, “Historial”.
- **Quién entra:** Usuarios con permiso (ej. mismo rol que panel RRHH o un permiso tipo “Enviar comunicados”).

En esa pantalla el usuario:

1. **Elige la empresa** (ej. Bacar).  
   - La app usa el número de WhatsApp configurado para esa empresa (con Twilio: campo `twilio_whatsapp_from`, ej. `whatsapp:+54911...`).

2. **Carga o pega los destinatarios**  
   - **Opción A:** Pegar una lista de números (uno por línea o separados por coma).  
   - **Opción B:** Subir un archivo (CSV o Excel) con una columna “teléfono” o “número”.  
   - Los números se normalizan a formato internacional (ej. 54911 12345678).

3. **Elige el mensaje**  
   - **Opción A – Plantilla aprobada (recomendado para masivos):** Elige una plantilla (ej. `comunicado_rrhh`) y completa los parámetros (nombre del colaborador, texto del comunicado, etc.).  
   - **Opción B – Texto libre:** Solo si la app envía dentro de la ventana de 24 h (menos común para comunicados masivos).

4. **Revisa y envía**  
   - Ve un resumen: “Se enviará a X contactos con la plantilla Y para la empresa Z.”  
   - Clic en **“Enviar comunicado”**.  
   - La app envía en **lotes con pausa** (throttling) para no ser bloqueada por WhatsApp.

5. **Resultado**  
   - Se muestra progreso o resultado: “Enviados: 650. Fallidos: 2. Total: 652.” (o se guarda en historial de comunicados para consultar después).

### Resumen del flujo

```
Menú → Comunicados → Elegir empresa → Cargar destinatarios → Elegir plantilla (o texto) → Revisar → Enviar
                                                                                              ↓
                                              Backend: obtiene phone_number_id de la empresa, llama a broadcast en lotes
```

---

## 2. Qué hace el backend (tu aplicación)

### Paso 1 – API para enviar el comunicado

Se necesita un **endpoint** (ej. `POST /api/comunicados/enviar`) que reciba:

- **company_id** (obligatorio): para saber qué empresa es y qué número usar.
- **destinatarios**: lista de números de teléfono (o archivo que se procesa y se convierte en lista).
- **template_name** (recomendado): nombre de la plantilla aprobada en Meta (ej. `comunicado_rrhh`).
- **template_params**: lista de parámetros en orden (ej. `["Nombre del colaborador", "Texto del comunicado"]`).
- Opcional: **body_text** si en el futuro se permite texto libre dentro de ventana 24 h.

El backend:

1. Verifica que el usuario tenga permiso para enviar comunicados (y opcionalmente para esa empresa).
2. Obtiene la empresa por `company_id` (Firestore `chatbot_empresas` o equivalente).
3. Lee de esa empresa el **`whatsapp_phone_number_id`** (y si usás token por empresa, el token).
4. Normaliza la lista de teléfonos a formato internacional.
5. Llama al módulo de envío en lotes (`whatsapp_broadcast.broadcast_messages`) pasando:
   - `phone_list`,
   - `template_name` y `template_params` (o `body_text`),
   - y el **phone_number_id** (y token) para que cada mensaje se envíe desde el número correcto.
6. Devuelve el resultado (enviados, fallidos, total).

### Paso 2 – Conectar con Twilio (recomendado) o Meta

**Opción A – Twilio (recomendado):**

1. Configurá **TWILIO_ACCOUNT_SID** y **TWILIO_AUTH_TOKEN** en el entorno (desde la [consola Twilio](https://www.twilio.com/console)).
2. Configurá el número "desde" por empresa (ej. `twilio_whatsapp_from` = `whatsapp:+54911...`) o **TWILIO_WHATSAPP_FROM** en el entorno.
3. En el arranque de la app (o antes de enviar):  
   `from twilio_whatsapp import register_twilio_sender; register_twilio_sender()`
4. El módulo **`twilio_whatsapp.py`** ya implementa el envío de un mensaje y se registra en `whatsapp_broadcast`. Solo falta el endpoint y la pantalla Comunicados (paso 1 y 5). Ver **[TWILIO_WHATSAPP.md](TWILIO_WHATSAPP.md)**.

**Opción B – Meta (WhatsApp Cloud API) directo:**

1. Implementar la función que envía **un** mensaje con la API de WhatsApp Cloud (Meta) y **registrarla** con `whatsapp_broadcast.set_send_function(mi_funcion)`.
2. Esa función debe recibir número, texto o plantilla, **phone_number_id** y token, y llamar a `POST https://graph.facebook.com/v18.0/{phone_number_id}/messages`.
3. `broadcast_messages` ya recibe **phone_number_id** y **access_token** y se los pasa a la función de envío.

### Paso 3 – Número por empresa

- En la **configuración de cada empresa** (Firestore o pantalla Configuración → Empresas) debe estar guardado el **WhatsApp Phone number ID** de ese número (ver `docs/WHATSAPP_MULTIPLES_NUMEROS.md`).
- Al enviar un comunicado para “Bacar”, el backend usa el `whatsapp_phone_number_id` de Bacar; para otra empresa, el de esa empresa.

---

## 3. Esquema técnico resumido

```
[Usuario en pantalla Comunicados]
  → Elige empresa "Bacar", pega 700 números, elige plantilla "comunicado_rrhh" con params
  → Clic "Enviar"

[Frontend]
  → POST /api/comunicados/enviar
  → Body: { company_id: "bacar", destinatarios: ["54911...", ...], template_name: "comunicado_rrhh", template_params: ["Hola", "Texto del comunicado"] }

[Backend web_chat.py o módulo comunicados]
  1. Verifica permiso.
  2. Obtiene empresa "bacar" → whatsapp_phone_number_id = "123456789..."
  3. Token: variable de entorno WHATSAPP_ACCESS_TOKEN o token de la empresa.
  4. Llama: broadcast_messages(phone_list=destinatarios, template_name=..., template_params=..., phone_number_id=..., access_token=...)

[whatsapp_broadcast.py]
  → Envía en lotes de 50 con pausa de 3 s.
  → Por cada número llama a send_single_message(phone, template_name=..., template_params=..., phone_number_id=..., access_token=...)

[send_single_message implementada con Meta]
  → POST a graph.facebook.com/v18.0/{phone_number_id}/messages con el token y el cuerpo del mensaje (plantilla).
```

---

## 4. Qué hay hoy y qué falta

| Qué | Estado |
|-----|--------|
| Módulo de envío en lotes con pausa | **Hecho** (`whatsapp_broadcast.py`). Falta que acepte `phone_number_id` (y token) y que se los pase a `send_single_message`. |
| Función que envía un mensaje a Meta | **Falta**: implementar la llamada a WhatsApp Cloud API y registrar esa función con `set_send_function`. |
| Configuración por empresa (phone_number_id) | **Falta**: campo en empresa (Firestore/config) y que el backend lo lea. |
| API POST /api/comunicados/enviar | **Falta**: crear el endpoint que reciba company_id, destinatarios, plantilla y llame al broadcast. |
| Pantalla “Comunicados” en la app | **Falta**: página en el menú con formulario (empresa, destinatarios, plantilla, botón Enviar). |
| Permiso “Enviar comunicados” | **Falta** (opcional): restringir quién ve el menú y puede llamar al API. |

---

## 5. Orden sugerido para implementar

1. **Backend – Envío real a Meta:** Implementar la función que, dado `phone_number_id`, token, número y plantilla (o texto), llama a la API de WhatsApp Cloud. Registrar esa función en `whatsapp_broadcast.set_send_function`.  
2. **Backend – phone_number_id en broadcast:** Extender `broadcast_messages` para que reciba `phone_number_id` (y opcionalmente `access_token`) y se los pase a `send_single_message`.  
3. **Backend – Empresa con número:** Poder guardar y leer `whatsapp_phone_number_id` por empresa (Firestore o Configuración).  
4. **Backend – API de comunicados:** Crear `POST /api/comunicados/enviar` que reciba company_id, destinatarios, plantilla/params, obtenga el phone_number_id de la empresa y llame a `broadcast_messages`.  
5. **Frontend – Pantalla Comunicados:** Página con selector de empresa, carga de destinatarios (pegado o archivo), selector de plantilla y parámetros, y botón que llame al API.  
6. **(Opcional)** Permiso y historial de comunicados enviados.

Con eso, **desde la aplicación** van a poder mandar esos comunicados eligiendo empresa, cargando los contactos y la plantilla, y el sistema enviará en lotes con el número correcto de cada empresa.
