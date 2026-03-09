# Múltiples números de WhatsApp (escalable por empresa o área)

Cuando empieces a tener **más de un número** de WhatsApp (una empresa, un área, otra sucursal, etc.), acá se explica **cómo se gestiona** del lado de Meta y del lado de esta aplicación, y **qué tenés que hacer** al agregar cada número nuevo.

---

## 1. Cómo funciona en Meta (WhatsApp Business API)

### Una cuenta, varios números

- Podés tener **varios números de teléfono** en la **misma** cuenta de WhatsApp Business (WABA) y en la misma app de Meta for Developers.
- Cada número tiene su propio **Phone number ID** (y opcionalmente su propio token si Meta lo permite; en la práctica suele usarse un **mismo token** de la app para todos los números).
- La **facturación** suele ser por cuenta (WABA), no por número: todos los números comparten el mismo método de pago y límites de tier.
- Cada número se **verifica por separado** (SMS o llamada) cuando lo agregás.

### Qué implica para vos

- **Un solo** Business Manager, **una** app en Developers, **una** facturación.
- **Varios** números vinculados a esa app, cada uno con su **Phone number ID**.
- Al enviar un mensaje, en la API indicás **desde qué número** enviar usando ese número’s **Phone number ID**.

---

## 2. Dónde y cómo agregar un número nuevo (Meta)

### Opción A – Desde Meta for Developers (recomendado)

1. Entrá a **https://developers.facebook.com** → **Mis aplicaciones** → tu app.
2. Menú izquierdo: **WhatsApp** → **Configuración de la API** / **API Setup**.
3. En la misma pantalla donde está tu número actual, buscá **“Agregar número de teléfono”** / **“Add phone number”**.
4. Elegí **código de país** y **número** (que **no** esté ya en WhatsApp).
5. Verificá con el **código por SMS o llamada**.
6. Una vez verificado, en API Setup vas a ver **varios números**. Cada uno tiene su propio **Phone number ID**. **Copiá y guardá** el **Phone number ID** del número nuevo (lo vas a usar en la app).

El **token de acceso** suele ser **el mismo** para todos los números de esa app; no hace falta un token distinto por número.

### Opción B – Desde Business Manager (WhatsApp Manager)

1. Entrá a **https://business.facebook.com** → **Configuración del negocio**.
2. En el menú: **Cuentas** → **Cuentas de WhatsApp** → elegí tu cuenta (WABA).
3. Buscá la sección **“Números de teléfono”** / **“Phone numbers”**.
4. **“Agregar número de teléfono”** → completá y verificá con SMS/llamada.
5. Después, el **Phone number ID** de ese número lo podés ver en **developers.facebook.com** → tu app → **WhatsApp** → **API Setup** (ahí aparecen todos los números con su ID).

---

## 3. Cómo gestionarlo en esta aplicación

El sistema ya es **multi-empresa** (empresas en Firestore, panel por empresa, etc.). La idea es que **cada empresa (o cada “canal”) pueda tener su propio número de WhatsApp**.

### Opción recomendada: un número por empresa

- En la **configuración de cada empresa** (en Firestore o en la pantalla de Configuración cuando se implemente) se guarda:
  - **WhatsApp Phone number ID** del número que usa esa empresa.
- El **token** puede ser:
  - **Uno solo para toda la app** (variable de entorno `WHATSAPP_ACCESS_TOKEN`), o
  - Uno por empresa si en el futuro querés tokens distintos (ej. por seguridad o por usar varias cuentas Meta).

Cuando enviás un comunicado o un mensaje para la **empresa X**:

1. La app busca la empresa X (por `company_id`).
2. Lee el **Phone number ID** configurado para esa empresa (ej. `whatsapp_phone_number_id`).
3. Llama a la API de WhatsApp usando ese **Phone number ID** y el token (común o el de esa empresa).

Así, cada empresa (o área, si más adelante lo mapeás por área) usa **su** número sin mezclar conversaciones.

### Dónde guardar el Phone number ID por empresa

**En Firestore (colección `chatbot_empresas`):**

- Cada documento de empresa puede tener campos opcionales, por ejemplo:
  - **`whatsapp_phone_number_id`**: string con el Phone number ID que usa esa empresa.
  - **`whatsapp_access_token`**: (opcional) si en el futuro usás un token distinto por empresa; si no, se usa el token global.

**En la UI de Configuración (futuro):**

- En la pantalla **Configuración** → **Empresas** → al editar/agregar una empresa, agregar campos:
  - **“Número de WhatsApp (ID)”** o **“WhatsApp Phone number ID”**: donde el admin pega el ID del número que corresponde a esa empresa.
- Opcional: **“Token de WhatsApp”** por empresa si no usás un token único global.

Mientras no exista esa pantalla, se puede editar el documento de la empresa en Firestore a mano y agregar `whatsapp_phone_number_id` (y opcionalmente `whatsapp_access_token`).

### Si querés un número por “área” o por “canal”

- Podés definir una entidad **“Canal WhatsApp”** o **“Número WhatsApp”** (ej. en una colección `whatsapp_canales` o en un archivo de config):
  - `id`, `label` (ej. “Bacar RRHH”, “Ventas”), `phone_number_id`, `token` (opcional).
- Luego cada **empresa** (o cada área) tiene un campo que referencia ese canal, ej. `whatsapp_canal_id` o `whatsapp_phone_number_id`.
- El envío siempre se resuelve a **un** Phone number ID (y un token); la diferencia es solo si ese ID está guardado en la empresa o en un canal que la empresa referencia.

Para empezar, **un número por empresa** (campo en la empresa) suele ser suficiente y escalable.

---

## 4. Qué tenés que hacer cuando agregás un número nuevo

### En Meta (WhatsApp)

1. Agregar y verificar el número (Developers → API Setup → “Agregar número de teléfono” o Business Manager → Cuentas de WhatsApp → Números).
2. Copiar el **Phone number ID** de ese número (API Setup en Developers).
3. No hace falta agregar otro método de pago: la facturación sigue siendo de la misma cuenta.

### En esta aplicación

1. **Asignar ese número a una empresa (o canal):**
   - **Si usás Firestore directo:** Editá el documento de la empresa en la colección `chatbot_empresas` y agregá (o actualizá) el campo `whatsapp_phone_number_id` con el ID que copiaste.
   - **Si tenés UI de Configuración:** En Empresas → editar la empresa → completar “WhatsApp Phone number ID” con ese valor y guardar.
2. **Token:** Si usás un solo token para todos, no cambiás nada. Si agregaste token por empresa, guardalo en la config de esa empresa (o en variable de entorno específica si lo preferís así).
3. **Código de envío:** El flujo que envía mensajes (ej. `whatsapp_broadcast` o el que llame a la API) tiene que recibir **para qué empresa** (o canal) es el envío, leer el `whatsapp_phone_number_id` (y token si aplica) de esa empresa y usar ese `phone_number_id` en la llamada a la API de WhatsApp.

Resumen: **cada número nuevo = un Phone number ID nuevo en Meta; en la app = un nuevo valor de `whatsapp_phone_number_id` asociado a una empresa (o canal).**

---

## 5. Límites y facturación con varios números

- **Límites de tier** (contactos únicos por día, etc.) suelen aplicar a la **cuenta (WABA)** en conjunto, no “por número”. Es decir, varios números no duplican el límite; comparten el mismo techo.
- **Facturación:** Un solo método de pago y una sola factura por cuenta; el uso de todos los números se suma para ese cobro.
- **Envío en lotes:** Sigue siendo importante no saturar (evitar bloqueos por spam). Usá el mismo criterio de **lotes con pausa** (`whatsapp_broadcast.py`) **por número**: si enviás por empresa A y por empresa B al mismo tiempo, cada uno con su número, podés correr dos flujos en paralelo o en secuencia, pero cada flujo debería seguir respetando batch size y delay.

---

## 6. Resumen rápido

| Pregunta | Respuesta |
|----------|-----------|
| ¿Varios números en la misma cuenta Meta? | Sí. Misma app, misma WABA, varios números; cada uno con su **Phone number ID**. |
| ¿Dónde agrego un número nuevo? | Developers → WhatsApp → API Setup → “Agregar número de teléfono”, o Business Manager → Cuentas de WhatsApp → Números. |
| ¿Qué guardo por cada número? | El **Phone number ID** (obligatorio). Token puede ser uno solo para todos. |
| ¿Dónde lo guardo en la app? | En la **empresa** (Firestore o Configuración): campo `whatsapp_phone_number_id` (y opcionalmente token por empresa). |
| ¿Qué hago al agregar un número? | 1) En Meta: agregar y verificar número, copiar Phone number ID. 2) En la app: asignar ese ID a la empresa (o canal) correspondiente. |
| ¿Facturación por número? | No; es por cuenta. Todos los números comparten método de pago y límites. |

Con esto podés escalar a **varias empresas o áreas**, cada una con su número, gestionando todo desde la misma cuenta de Meta y desde esta app usando el `company_id` (y opcionalmente área/canal) para elegir el **Phone number ID** correcto en cada envío.

---

## 7. ¿Puedo usar un número al principio y después cambiarlo? (ej. Bacar)

**Sí.** Podés empezar con **un número** para Bacar (o cualquier empresa) y **más adelante usar otro** sin que Meta tenga que “aprobar” el cambio en tu sistema.

### Cómo hacerlo

1. **Al inicio:** Registrás y verificás el **número A** en Meta (API Setup → Agregar número). En la app asignás a Bacar el **Phone number ID** del número A.
2. **Cuando quieras cambiar:** En Meta agregás y verificás el **número B** (mismo flujo: API Setup → Agregar número de teléfono). Copiás el **Phone number ID** del número B.
3. **En la app:** Cambiás la configuración de Bacar para que use el **Phone number ID del número B** en lugar del de A (en Firestore: actualizás `whatsapp_phone_number_id` del documento de Bacar; o en Configuración → Empresas → editar Bacar → nuevo “WhatsApp Phone number ID”).
4. A partir de ahí, los mensajes de Bacar salen por el **número B**. No hace falta avisar ni pedir aprobación a Meta para ese cambio de configuración en tu lado.

**Importante:** En Meta, un número **ya conectado** a la cuenta no suele poder “eliminarse”; queda en la cuenta. Lo que hacés es **dejar de usarlo** para Bacar y usar el nuevo. Es un cambio solo en tu app (qué Phone number ID usás para esa empresa).

### Si querés “migrar” reputación y límites al nuevo número

Meta tiene flujos de **migración** para pasar cosas como calidad (quality score), límites de mensajería o estado verificado del número viejo al nuevo. Eso sí puede tener requisitos (verificación de negocio, mismo ID de empresa, etc.) y es un proceso aparte en Meta. Para **solo cambiar de número** en tu sistema (Bacar pasa del número A al B), no necesitás ese proceso: agregás B, actualizás el ID en la app y listo.
