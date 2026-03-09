# Comunicados masivos por WhatsApp: evitar bloqueos

Cuando RRHH envía comunicados a muchas personas (ej. 700) por WhatsApp, la plataforma puede marcar el envío como spam y bloquear el número o la cuenta. Acá se resume **por qué pasa** y **cómo evitarlo** al conectar el chatbot con WhatsApp.

---

## Por qué WhatsApp bloquea

- **Volumen en poco tiempo:** muchos mensajes seguidos parecen spam.
- **Uso de apps no oficiales:** si usan WhatsApp Web/API no oficial o automatización con número personal, Meta aplica bloqueos fuertes.
- **Sin opt-in:** enviar a personas que no dieron consentimiento empeora la reputación del número.
- **Contenido repetido:** el mismo texto a cientos de contactos dispara filtros anti-spam.

---

## Solución recomendada: WhatsApp Business API (Cloud API)

Para comunicados masivos hay que usar la **API oficial** de WhatsApp (Cloud API o Business API), no números personales ni clientes no oficiales.

### Ventajas

- Límites claros y documentados (tiers y throughput).
- Menos riesgo de bloqueo si se respetan las reglas.
- Soporte para plantillas aprobadas para mensajes proactivos.
- Escalable según el tier de la cuenta.

### Límites importantes (referencia 2024–2025)

| Concepto | Detalle |
|--------|---------|
| **Throughput** | Por defecto ~80 mensajes por segundo; puede subir según tier y calidad. |
| **Tier diario** | Límite de **contactos únicos por 24 h** (ej. Sandbox 250, Tier 1: 1.000, Tier 2: 10.000, etc.). |
| **Ventana 24 h** | Fuera de las 24 h desde el último mensaje del usuario, solo se pueden enviar **mensajes plantilla** aprobados por Meta. |
| **Plantillas** | Para iniciar conversación o comunicados proactivos hay que usar **template messages** aprobados. |
| **Calidad** | Mantener buen “quality score” (verde/amarillo) ayuda a no sufrir límites ni bloqueos. |

Para **700 personas** en un mismo día suele ser viable con Tier 2 (10.000 únicos/día), pero hay que **repartir el envío en el tiempo** (ver más abajo).

---

## Cómo hacer que no pase cuando lo conecten

### 1. Usar solo WhatsApp Business API oficial

- Darse de alta en [Meta for Developers](https://developers.facebook.com/docs/whatsapp) y usar Cloud API o un proveedor (Twilio, 360dialog, etc.) que use la API oficial.
- No usar automatización sobre WhatsApp Web ni números personales para masivos.

### 2. Enviar en lotes con pausa (throttling)

Aunque el throughput permita muchos mensajes por segundo, para comunicados internos (ej. 700 colaboradores) conviene **no saturar**:

- Enviar en **lotes** (ej. 30–80 destinatarios por lote).
- Dejar una **pausa entre lotes** (ej. 2–5 segundos, o 1 mensaje cada 1–2 segundos si quieren ser más conservadores).
- Así se evita un pico de cientos de mensajes en pocos segundos y se reduce el riesgo de que lo marquen como spam.

En este proyecto, cuando integren el envío a WhatsApp, pueden usar el módulo **`whatsapp_broadcast.py`** (ver más abajo), que ya implementa envío en cola con lotes y pausa configurable.

### 3. Usar plantillas aprobadas para comunicados

- Para comunicados iniciados por la empresa (fuera de la ventana 24 h), usar **solo mensajes plantilla** aprobados por Meta.
- Crear plantillas con nombre claro (ej. “comunicado_rrhh”) y texto que cumpla las [políticas de WhatsApp](https://developers.facebook.com/docs/whatsapp/message-templates/guidelines).
- En el código, enviar siempre ese template con los parámetros (nombre, texto del comunicado, etc.) en lugar de texto libre en envíos masivos.

### 4. Consentimiento (opt-in)

- Que los colaboradores acepten recibir comunicados por WhatsApp (registro, formulario o doble opt-in).
- Guardar ese consentimiento en base de datos y enviar solo a quienes estén dados de alta.
- Eso mejora la reputación del número y reduce reportes y bloqueos.

### 5. Respetar el tier y la calidad

- Revisar en el panel de Meta el **tier** de la cuenta y el **límite de contactos únicos por 24 h**.
- Si hoy tienen límite bajo (ej. 1.000/día), planear los 700 envíos en un día donde no superen ese tope, o subir de tier con buen uso.
- Evitar mensajes repetidos idénticos sin personalización; usar variables en la plantilla (nombre, área, etc.) cuando sea posible.

---

## Módulo de envío en cola (para cuando conecten WhatsApp)

En el repo hay un módulo **`whatsapp_broadcast.py`** que:

- Recibe una lista de destinatarios (teléfonos) y el contenido del comunicado (o nombre de plantilla + parámetros).
- Envía en **lotes** de tamaño configurable (`BROADCAST_BATCH_SIZE`, ej. 50).
- Aplica una **pausa en segundos** entre lotes (`BROADCAST_DELAY_BETWEEN_BATCHES`, ej. 3).
- Permite encolar varios comunicados y procesarlos uno tras otro.

Cuando integren la API real de WhatsApp (Meta Cloud API o proveedor), solo tienen que implementar la función que envía **un** mensaje (o una plantilla) a un número; el módulo se encarga del ritmo y de no mandar todo de golpe.

Configuración sugerida en `.env` o en Configuración:

- `WHATSAPP_BROADCAST_BATCH_SIZE=50` — cantidad de mensajes por lote.
- `WHATSAPP_BROADCAST_DELAY_SECONDS=3` — segundos de espera entre lotes.

Para 700 personas con batch 50 y 3 s de pausa: 14 lotes × 3 s ≈ 42 segundos extra además del tiempo de envío real, lo que evita picos y ayuda a no disparar anti-spam.

---

## Resumen

| Acción | Para qué |
|--------|----------|
| Usar **WhatsApp Business API oficial** | Evitar bloqueos por uso no permitido. |
| **Envío en lotes con pausa** | No saturar en pocos segundos; menos riesgo de spam. |
| **Plantillas aprobadas** | Cumplir reglas para mensajes proactivos. |
| **Opt-in** | Mejor reputación y menos reportes. |
| **Respetar tier y límites** | No superar contactos únicos/día ni throughput sin planearlo. |

Cuando conecten WhatsApp al sistema, usando la API oficial y el envío throttled (p. ej. con `whatsapp_broadcast.py`), podrán mandar comunicados a 700 u otros tantos destinatarios minimizando el riesgo de que WhatsApp lo bloquee.

**Desde la aplicación:** Cómo va a usar RRHH la app para enviar esos comunicados (pantalla, API, flujo): **[COMUNICADOS_DESDE_LA_APP.md](COMUNICADOS_DESDE_LA_APP.md)**.
