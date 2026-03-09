# Cómo conectar WhatsApp Business API

Guía paso a paso para registrar y conectar la API oficial de WhatsApp (Cloud API) y poder enviar y recibir mensajes desde el chatbot.

> **Guía completa (facturación + número + muchos contactos):** Si necesitás el flujo entero en orden —crear todo, configurar pago, usar un número específico y enviar a muchos contactos— usá **[WHATSAPP_PASO_A_PASO_COMPLETO.md](WHATSAPP_PASO_A_PASO_COMPLETO.md)**.  
> **Varios números (varias empresas/áreas):** Cómo gestionar múltiples números y qué hacer al agregar cada uno: **[WHATSAPP_MULTIPLES_NUMEROS.md](WHATSAPP_MULTIPLES_NUMEROS.md)**.

---

## Paso a paso: dónde ingresar (pantalla por pantalla)

### Parte A – Iniciar sesión y llegar a “Mis aplicaciones”

| Paso | Dónde ingresar | Qué hacer |
|------|----------------|-----------|
| **A1** | Abrí el navegador y escribí: **https://developers.facebook.com** | Entrá a la página. Vas a ver “Tecnologías sociales” y la sección “Primeros pasos”. |
| **A2** | Arriba a la **derecha** de la misma página | Clic en **“Login”** (Iniciar sesión). |
| **A3** | Te puede llevar a **business.facebook.com** (“Empieza a usar las herramientas empresariales de Meta”) | Clic en **“Iniciar sesión con Facebook”** (botón azul). Ingresá tu usuario y contraseña de Facebook si te lo pide. |
| **A4** | Volvés a **developers.facebook.com** ya logueado | En la barra superior (o menú), buscá y hacé clic en **“Mis aplicaciones”** o **“My Apps”**. |

Si en el paso A2 no ves “Login” y ya estás logueado, saltá directo al paso A4.

---

### Parte B – Crear la app y agregar WhatsApp

| Paso | Dónde ingresar | Qué hacer |
|------|----------------|-----------|
| **B1** | En la página **“Mis aplicaciones”** | Clic en el botón **“Crear aplicación”** o **“Create App”**. |
| **B2** | Pantalla de tipo de app | Elegí **“Empresa”** (Business). Si no aparece, elegí **“Otra”** → **“Siguiente”**. |
| **B3** | Formulario de la app | Completá **nombre de la app** (ej. “ChatBot RRHH”), **correo de contacto** y, si te pide, la **Cuenta de negocio de Meta**. Clic en **“Crear aplicación”** / **“Create app”**. |
| **B4** | Panel de tu app (menú a la izquierda) | En la columna izquierda buscá **“Agregar productos”** / **“Add products”** o la sección **“Productos”**. |
| **B5** | Lista de productos | Buscá la tarjeta **“WhatsApp”** y hacé clic en **“Configurar”** o **“Set up”**. |
| **B6** | Si aparece “Portafolio comercial” / “App portfolio” | Creá uno nuevo o elegí uno existente de tu negocio y continuá. |
| **B7** | Después de configurar WhatsApp | Meta crea una cuenta de prueba. En el menú izquierdo de la app deberías ver **“WhatsApp”** con subopciones. |

---

### Parte C – Ver el número de prueba y el token (API Setup)

| Paso | Dónde ingresar | Qué hacer |
|------|----------------|-----------|
| **C1** | Menú izquierdo dentro de tu app | Clic en **“WhatsApp”** y después en **“Configuración de la API”** o **“API Setup”** (a veces está como “Getting started” / “Empezar”). |
| **C2** | Pantalla “Configuración de la API” / “API Setup” | Ahí vas a ver: **“ID de número de teléfono”** (Phone number ID) y **“Token de acceso temporal”** (Temporary access token). Copiá y guardá ambos en un lugar seguro (el token lo usás en tu código). |
| **C3** | En la misma pantalla | Para probar, agregá hasta **5 números de teléfono** en la sección “To” / “Para” (números a los que podés enviar con el número de prueba). |

Con eso ya podés hacer pruebas de envío. Para producción seguí con la Parte D.

---

### Parte D – Agregar tu número real (producción)

| Paso | Dónde ingresar | Qué hacer |
|------|----------------|-----------|
| **D1** | Siempre en **developers.facebook.com** → **Mis aplicaciones** → tu app → **WhatsApp** | Entrá de nuevo a **“Configuración de la API”** / **“API Setup”**. |
| **D2** | En esa pantalla | Buscá el enlace o botón **“Agregar número de teléfono”** / **“Add phone number”** (suele estar cerca del número de prueba). |
| **D3** | Formulario de número | Elegí **código de país** (ej. +54) y escribí **tu número** (sin el 0 inicial, ej. 9 11 1234-5678 → 91112345678). |
| **D4** | Verificación | Elegí recibir el código por **SMS** o **llamada de voz**. Ingresá el código en la pantalla. Listo: ese número queda vinculado a tu WhatsApp Business API. |

Si ese número **ya tiene WhatsApp** instalado, antes hay que migrarlo (Meta te guía en pantalla) o usar otro número que no esté en WhatsApp.

---

### Parte E – Herramientas de negocio y verificación (opcional)

| Paso | Dónde ingresar | Qué hacer |
|------|----------------|-----------|
| **E1** | Abrí: **https://business.facebook.com** | Vas a ver “Empieza a usar las herramientas empresariales de Meta”. |
| **E2** | Lado derecho de la página | Clic en **“Iniciar sesión con Facebook”** (o con Instagram si usás esa cuenta para el negocio). |
| **E3** | Una vez dentro | En el menú o configuración buscá **“Configuración del negocio”** / **“Business settings”** → **“Verificación del negocio”** / **“Business verification”** para subir documentos y subir de tier (más destinatarios por día). |

---

## Resumen de sitios

| Para qué | URL | Dónde hacer clic después |
|----------|-----|---------------------------|
| Crear app y WhatsApp API | **https://developers.facebook.com** | Login → Mis aplicaciones → Crear aplicación → Agregar producto WhatsApp → API Setup |
| Gestionar negocio / verificación | **https://business.facebook.com** | Iniciar sesión con Facebook → Configuración del negocio → Verificación del negocio |
| Documentación WhatsApp (español) | [Empezar - Cloud API](https://developers.facebook.com/docs/whatsapp/cloud-api/get-started?locale=es_LA) | Para consultar detalles de la API |

---

## ¿Dónde está el pago / facturación?

Para usar tu **número real** y enviar a más de los 5 contactos de prueba, tenés que tener **método de pago** asociado a tu cuenta de negocio. Sin eso, Meta no te deja enviar a usuarios reales.

### Dónde agregar el método de pago

| Paso | Dónde ingresar | Qué hacer |
|------|----------------|-----------|
| **F1** | **https://business.facebook.com** | Iniciá sesión (con Facebook o Instagram). |
| **F2** | Menú (ícono de engranaje o “Configuración”) | Clic en **“Configuración del negocio”** o **“Business settings”**. |
| **F3** | En el menú izquierdo de Configuración | Buscá **“Facturación”** / **“Billing”** o **“Cuentas”** → **“Cuentas de WhatsApp”**. |
| **F4** | Si ves “Cuentas de WhatsApp” | Seleccioná tu **cuenta de WhatsApp Business** (WABA) y buscá **“Configuración de pago”** / **“Payment settings”** o **“Métodos de pago”**. |
| **F5** | Si ves “Facturación” directo | Ahí suele estar **“Configuración de pago”** o **“Agregar método de pago”**. Agregá tarjeta de crédito/débito o PayPal según lo que ofrezca tu país. |

**Alternativa:** A veces la facturación de la **app** está en **developers.facebook.com** → **Mis aplicaciones** → tu app → **Configuración** (o “Settings”) → **Facturación** / **Billing**. Revisá el menú izquierdo de tu app por “Facturación” o “Configuración de pago”.

### Cómo te cobran (referencia)

- **Prueba (número de prueba):** Envío gratis solo a los 5 números que agregaste en API Setup.
- **Producción (tu número):** Meta cobra por uso. Desde **julio 2025** el modelo pasó a ser por **mensaje/plantilla entregado**, según categoría (Marketing, Utilidad, Autenticación, Servicio) y **país del destinatario**. Las respuestas **dentro de la ventana de 24 h** (cuando el usuario te escribió primero) suelen ser de categoría Servicio y en muchos casos no se cobran o son más baratas.
- **Precios oficiales:** [Precios de WhatsApp (Meta)](https://developers.facebook.com/docs/whatsapp/pricing?locale=es_LA) y [business.whatsapp.com - Precios](https://business.whatsapp.com/products/platform-pricing?lang=es). Ahí podés ver tarifas por país y categoría.

Resumen: el **pago se configura en Business Manager** (business.facebook.com) en **Configuración del negocio → Facturación / Cuentas de WhatsApp → Configuración de pago**, o a veces en la app en developers.facebook.com en **Configuración → Facturación**.

---

## ¿Dónde se hace? (referencia rápida)

Todo el registro y la configuración se hacen en la plataforma de Meta (Facebook):

| Qué | Dónde |
|-----|--------|
| Crear app y activar WhatsApp | **Meta for Developers** → [developers.facebook.com](https://developers.facebook.com) |
| Gestionar negocio y verificación | **Meta Business Suite** → [business.facebook.com](https://business.facebook.com) |
| Documentación oficial (español) | [WhatsApp Cloud API - Empezar](https://developers.facebook.com/docs/whatsapp/cloud-api/get-started?locale=es_LA) |

---

## Qué necesitás antes de empezar

1. **Cuenta de Facebook** (personal) para acceder.
2. **Cuenta de Meta Business** (negocio). Si no tenés:
   - Entrá a [business.facebook.com](https://business.facebook.com) y creá una cuenta de negocio (nombre de la empresa, etc.).
3. **Número de teléfono para WhatsApp Business**:
   - Tiene que poder recibir **SMS o llamada de voz** (para el código de verificación).
   - **No** puede estar ya registrado en WhatsApp (ni personal ni en la app de WhatsApp Business normal).
   - Si hoy ese número tiene WhatsApp, hay que migrarlo o usar otro número nuevo.
4. **Sitio web de la empresa** (recomendado para verificación): una web en vivo con nombre legal, contacto y actividad del negocio.
5. **Documentos del negocio** (para verificación de negocio de Meta, si te la piden):
   - Prueba del nombre legal (ej. inscripción en AFIP, cámara, etc.).
   - Prueba de dirección o del teléfono (factura de servicio, etc.).

---

## Pasos para conectar WhatsApp Business API (Cloud API)

### 1. Entrar a Meta for Developers

1. Andá a **[developers.facebook.com](https://developers.facebook.com)** e iniciá sesión con tu cuenta de Facebook.
2. En el menú, entrá a **“Mis aplicaciones”** (o “My Apps”).

### 2. Crear una aplicación (o usar una existente)

1. Clic en **“Crear aplicación”**.
2. Elegí tipo **“Empresa”** (Business). Si no ves “Empresa”, podés elegir **“Otra”** y después **“Siguiente”**.
3. Completá nombre de la app, contacto del desarrollador y elegí la **Cuenta de negocio de Meta** (Meta Business Account) a la que la vas a asociar.
4. Creá la app.

### 3. Agregar el producto WhatsApp

1. En el panel de tu app, buscá la sección **“Agregar productos”** o **“Productos”**.
2. Buscá **WhatsApp** y hacé clic en **“Configurar”** o **“Set up”**.
3. Si te pide un **“Portafolio comercial”** (App portfolio), podés crear uno desde ahí o vincular uno existente de tu negocio.
4. Al agregar WhatsApp, Meta te crea:
   - Una **cuenta de WhatsApp Business** (WABA) de prueba.
   - Un **número de prueba** para enviar mensajes a hasta **5 números** que vos agregues (ideal para probar sin verificación completa).

### 4. Ver la configuración de WhatsApp (API Setup)

1. En el menú de la app, entrá a **WhatsApp** → **“Configuración de la API”** o **“API Setup”**.
2. Ahí vas a ver:
   - **ID de número de teléfono** (Phone number ID).
   - **Token de acceso temporal** (Access token).  
   Estos los vas a usar en tu backend para enviar mensajes.

### 5. Token de acceso (para que tu servidor hable con la API)

- En **API Setup** hay un **token temporal** que sirve para pruebas.
- Para **producción** tenés que generar un **token permanente**:
  1. En la app de Meta, andá a **Configuración** → **Básica**.
  2. Mostrá el **Secreto de la aplicación** (App Secret) y guardalo en un lugar seguro.
  3. Para tokens de larga duración se usa **Login de Facebook** o **Sistema de usuarios**; la opción más común en servidor es usar un **token de acceso del sistema** (System User token) desde **Business Manager** → **Configuración del negocio** → **Usuarios** → **Usuarios del sistema** → generar token con permisos `whatsapp_business_messaging` y `whatsapp_business_management`.

Guardá el token en variables de entorno (ej. `WHATSAPP_ACCESS_TOKEN`) y **nunca** lo subas al código ni a repos públicos.

### 6. Agregar tu número de teléfono real (producción)

Para usar **tu** número (el que va a atender a los 700+ contactos):

1. En **WhatsApp** → **Configuración de la API** (o **API Setup**), buscá la opción para **agregar número de teléfono**.
2. Elegí código de país (ej. +54 Argentina) y cargá el número.
3. Meta envía un **código por SMS o por llamada de voz** al número.
4. Ingresá el código en la pantalla para verificar.
5. Si ese número **ya tiene WhatsApp** (app normal o Business app), primero hay que **migrarlo** desde la app de WhatsApp en el celular (opción “Migrar a WhatsApp Business API” según el flujo que muestre Meta). Si no, usá un número que no esté en WhatsApp.

Después de verificar, ese número queda asociado a tu cuenta de WhatsApp Business API y podés usarlo para enviar y recibir.

### 7. Verificación del negocio (Meta Business Verification)

Para **límites altos** (muchos destinatarios por día) y para que no te limiten, Meta suele pedir **verificación del negocio**:

1. Entrá a **[business.facebook.com](https://business.facebook.com)** → **Configuración del negocio** (o Business Settings).
2. Buscá **“Verificación del negocio”** o **“Business verification”**.
3. Completá datos legales del negocio y subí los documentos que pidan (nombre legal, dirección, etc.).
4. Esperá la revisión (puede tardar unos días).

Mientras no esté verificada la cuenta, podés seguir usando el **número de prueba** y el tier de prueba (ej. 250 o 1.000 contactos/día según lo que muestre tu cuenta).

---

## Resumen de datos que vas a necesitar en tu código

Cuando integres la API en este proyecto, vas a usar:

| Variable | Dónde se obtiene |
|----------|-------------------|
| `WHATSAPP_ACCESS_TOKEN` | WhatsApp → API Setup (token temporal) o token del System User (producción). |
| `WHATSAPP_PHONE_NUMBER_ID` | WhatsApp → API Setup → “Phone number ID” del número que agregaste. |
| `WHATSAPP_BUSINESS_ACCOUNT_ID` (opcional) | A veces se usa en algunas llamadas; está en la misma pantalla o en Business Manager. |

La **URL base** de la API Cloud es:

```text
https://graph.facebook.com/v18.0/{phone_number_id}/messages
```

(Revisá en la [documentación oficial](https://developers.facebook.com/docs/whatsapp/cloud-api/reference/messages) la versión actual de la API, ej. v21.0.)

---

## Alternativa: usar un proveedor (BSP)

Si preferís no gestionar tokens ni verificación directamente con Meta:

- Podés usar un **proveedor oficial** (BSP) que ya tiene la conexión con WhatsApp Cloud API y te da un dashboard y API más simple:
  - **Twilio** – [twilio.com/whatsapp](https://www.twilio.com/whatsapp)
  - **360dialog** – [360dialog.com](https://www.360dialog.com)
  - **MessageBird**, **Infobip**, etc.

En ese caso:
- Te registrás en la página del proveedor.
- Conectás tu cuenta de Meta Business / WhatsApp Business con ellos (ellos te guían).
- Usás la API o SDK del proveedor para enviar mensajes; ellos se encargan del token y de la comunicación con Meta.

El flujo de **envío en lotes con pausa** que tenés en `whatsapp_broadcast.py` sigue siendo válido: solo cambiás la implementación de “enviar un mensaje” para que llame a la API del proveedor en lugar de a Meta directo.

---

## Orden sugerido

1. Entrar a [developers.facebook.com](https://developers.facebook.com) y crear app tipo Empresa.
2. Agregar producto **WhatsApp** y usar el **número de prueba** para probar envío a 5 números.
3. Obtener **Phone number ID** y **Access token** y probar un envío desde tu backend (o Postman).
4. Agregar **tu número real** (que no esté en WhatsApp) y verificar por SMS/llamada.
5. Si vas a enviar a muchos (ej. 700), iniciar **verificación del negocio** en [business.facebook.com](https://business.facebook.com).
6. Crear **plantillas de mensaje** para comunicados (en WhatsApp → Plantillas de mensaje) y aprobarlas.
7. Integrar en este proyecto usando `whatsapp_broadcast.py` y enviando en lotes con pausa (ver `docs/WHATSAPP_COMUNICADOS_MASIVOS.md`).

Si querés, en el siguiente paso podemos bajar esto a “qué endpoint llamar desde Python” y cómo conectar eso con `whatsapp_broadcast.py`.
