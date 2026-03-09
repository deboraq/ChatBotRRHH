# WhatsApp Business API: paso a paso detallado (todo)

Guía **paso a paso detallada** para crear la cuenta de negocio, la app, WhatsApp, facturación, tu número y verificación para muchos contactos. Cada acción está numerada; seguí el orden.

---

## Índice

1. [Paso 1 – Cuenta de negocio (Meta Business)](#paso-1--cuenta-de-negocio-meta-business)  
2. [Paso 2 – Crear la app y agregar WhatsApp](#paso-2--crear-la-app-y-agregar-whatsapp)  
3. [Paso 3 – Configurar facturación](#paso-3--configurar-facturación)  
4. [Paso 4 – Agregar tu número específico](#paso-4--agregar-tu-número-específico)  
5. [Paso 5 – Verificación del negocio (muchos contactos)](#paso-5--verificación-del-negocio-muchos-contactos)  
6. [Paso 6 – Plantillas de mensaje (comunicados)](#paso-6--plantillas-de-mensaje-comunicados)  

---

## Paso 1 – Cuenta de negocio (Meta Business)

**Objetivo:** Tener una “Cuenta de negocio de Meta” para facturación y verificación. Si ya tenés una, pasá al Paso 2.

---

### 1.1 – Abrir la página de Business

- Abrí el navegador (Chrome, Edge, Firefox, etc.).
- En la barra de direcciones escribí: **`https://business.facebook.com`**
- Pulsá **Enter**.

**Verás:** Una página con el título tipo “Empieza a usar las herramientas empresariales de Meta” o “Meta Business Suite”. A la derecha hay botones para iniciar sesión.

---

### 1.2 – Iniciar sesión

- Clic en el botón azul **“Iniciar sesión con Facebook”**.
- Si te pide, ingresá tu **correo o teléfono** y **contraseña** de Facebook.
- Clic en **“Iniciar sesión”**.

**Si no tenés cuenta de Facebook:** Creá una primero en facebook.com y después volvé a business.facebook.com.

---

### 1.3 – ¿Tenés ya una cuenta de negocio?

**Si entraste y ves un panel** (menú a la izquierda, anuncios, etc.): ya tenés cuenta de negocio. **Anotá** que vas a usar esta misma cuenta para facturación y verificación. Pasá al **Paso 2**.

**Si te muestra “Crear cuenta” o te pide crear una cuenta de negocio:** seguí con 1.4.

---

### 1.4 – Crear la cuenta de negocio (solo si no tenés)

- En la pantalla que te pide datos del negocio, en **“Nombre de la empresa”** o “Business name” escribí el **nombre legal o comercial** (ej. “Bacar S.A.” o “Mi Empresa RRHH”).
- En **“Tu nombre”** o “Your name” escribí **tu nombre y apellido**.
- En **“Correo electrónico de la empresa”** escribí un **email que revises** (ej. administracion@empresa.com).
- Clic en **“Enviar”** o “Submit” / “Siguiente”.

**Verás:** Pantallas adicionales (ej. dirección, tipo de negocio). Completá lo que pida con datos reales.

- Cuando termine el flujo, vas a quedar en el **panel principal** de Business Manager (o Meta Business Suite). No cierres sesión.

---

## Paso 2 – Crear la app y agregar WhatsApp

**Objetivo:** Tener una “aplicación” en Meta for Developers con el producto WhatsApp activado (y el número de prueba).

---

### 2.1 – Abrir Meta for Developers

- En el navegador, en la barra de direcciones escribí: **`https://developers.facebook.com`**
- Pulsá **Enter**.

**Verás:** La página “Tecnologías sociales” o similar, con opciones como “Explorar todos los productos”, “Documentos”, etc.

---

### 2.2 – Iniciar sesión en Developers

- Arriba a la **derecha** de la página buscá **“Login”** o “Iniciar sesión”.
- Clic en **“Login”**.

**Si te redirige a business.facebook.com:**  
- Vas a ver “Iniciar sesión en las herramientas empresariales de Meta”.
- Clic en **“Iniciar sesión con Facebook”** e ingresá usuario y contraseña si te lo pide.
- Después de iniciar sesión, volvé manualmente a **`https://developers.facebook.com`**.

---

### 2.3 – Ir a “Mis aplicaciones”

- En la barra superior de developers.facebook.com buscá **“Mis aplicaciones”** (o “My Apps” si está en inglés).
- Clic en **“Mis aplicaciones”**.

**Verás:** Una lista de aplicaciones (puede estar vacía) y un botón para crear una nueva.

---

### 2.4 – Crear una nueva aplicación

- Clic en el botón **“Crear aplicación”** o “Create App”.

**Verás:** Una pantalla que pregunta **qué tipo de aplicación** querés crear.

---

### 2.5 – Elegir tipo “Empresa”

- Buscá la tarjeta u opción **“Empresa”** (o “Business”).
- Clic en **“Empresa”** (o “Siguiente” si primero elegiste “Empresa”).

**Si no ves “Empresa”:**  
- Elegí **“Otra”** (Other) y clic en **“Siguiente”** (Next). En la siguiente pantalla podés seguir.

---

### 2.6 – Completar datos de la aplicación

En el formulario que aparece:

- **Nombre de la aplicación:** Escribí por ejemplo **“ChatBot RRHH”** o **“Comunicados Empresa”** (el que prefieras).
- **Correo de contacto:** Escribí un **email válido** donde Meta pueda contactarte (ej. it@empresa.com).
- **Cuenta de negocio de Meta:** En el desplegable elegí la **cuenta de negocio** que creaste o que ya tenés (Paso 1). Si solo tenés una, esa será la que aparezca.

**Opcional** (si aparece):  
- Podés completar “Página de negocio” si tenés una página de Facebook vinculada. No es obligatorio para WhatsApp.

- Clic en **“Crear aplicación”** (o “Create app”).

**Verás:** Puede pedirte confirmar con contraseña de Facebook. Ingresala si te lo pide y confirmá.

---

### 2.7 – Llegar al panel de la app

- Después de crear la app, vas a entrar al **panel** de esa aplicación.
- A la **izquierda** hay un menú con opciones como “Panel”, “Configuración”, “Productos” o “Agregar productos”.

**Verás:** En el centro puede decir “Agregar productos a tu aplicación” o mostrar una lista de productos (WhatsApp, Facebook Login, etc.).

---

### 2.8 – Buscar el producto WhatsApp

- En la misma página, buscá la tarjeta o bloque que diga **“WhatsApp”** (a veces tiene el ícono de WhatsApp).
- Debajo o al lado del nombre debería decir algo como “Enviar y recibir mensajes”, “Messaging”, etc.
- Clic en el botón **“Configurar”** o “Set up” de esa tarjeta.

**Verás:** Una pantalla o ventana que puede hablar del “Portafolio comercial” (App portfolio) o de la cuenta de WhatsApp Business.

---

### 2.9 – Portafolio comercial (si lo pide)

- Si te pide **“Crear portafolio comercial”** o “Create app portfolio”:  
  - Clic en **“Crear nuevo”** o “Create new”.  
  - Dale un nombre (ej. “Portafolio ChatBot”) y confirmá.
- Si te pide **elegir un portafolio existente**: elegí el que corresponda a tu negocio y continuá.

**Verás:** Luego de confirmar, la app queda con WhatsApp agregado. Puede mostrarte un mensaje de éxito o llevarte directo al menú de WhatsApp.

---

### 2.10 – Confirmar que WhatsApp está activo

- En el **menú izquierdo** de la aplicación buscá la entrada **“WhatsApp”** (puede tener un ícono verde).
- Clic en **“WhatsApp”**.

**Verás:** Se despliega un submenú con opciones como “Empezar” / “Getting started”, “Configuración de la API” / “API Setup”, “Plantillas de mensaje”, etc. Meta ya creó un **número de prueba** (solo para 5 destinatarios). Pasá al **Paso 3** (facturación) antes de agregar tu número real.

---

## Paso 3 – Configurar facturación

**Objetivo:** Tener al menos un método de pago (tarjeta o PayPal) asociado a tu cuenta de negocio. Sin esto **no** podés usar tu número real ni enviar a más de 5 contactos.

---

### 3.1 – Abrir Business Manager

- En el navegador, en la barra de direcciones escribí: **`https://business.facebook.com`**
- Pulsá **Enter**.
- Si te pide, **iniciá sesión con Facebook** (la misma cuenta que usaste en Developers).

**Verás:** El panel principal de Meta Business Suite o Business Manager (menú, resumen, etc.).

---

### 3.2 – Abrir Configuración del negocio

- En la esquina **superior izquierda** (o en el menú lateral) buscá el ícono de **engranaje** (⚙️) o el texto **“Configuración”** / “Configuración del negocio” / “Business settings”.
- Clic en **Configuración** (o en el engranaje y después en “Configuración del negocio” si aparece).

**Verás:** Una pantalla con un **menú a la izquierda** con muchas opciones (Cuentas, Usuarios, Seguridad, Facturación, etc.).

---

### 3.3 – Buscar Facturación o Cuentas

- En el **menú izquierdo** de Configuración, buscá una de estas opciones:
  - **“Facturación”** o “Billing”
  - **“Cuentas”** (Accounts)

**Si ves “Facturación”:**  
- Clic en **“Facturación”**. Seguí al paso 3.4a.

**Si ves “Cuentas” y no “Facturación”:**  
- Clic en **“Cuentas”**.  
- Buscá **“Cuentas de WhatsApp”** o “WhatsApp accounts” y clic ahí.  
- Si te muestra una lista de cuentas de WhatsApp, seleccioná la que corresponde a tu app (puede haber solo una).  
- Dentro de esa cuenta buscá **“Configuración de pago”** o “Payment settings” o “Métodos de pago”. Clic ahí. Seguí al paso 3.5.

---

### 3.4a – Dentro de Facturación (si entraste por “Facturación”)

- En la zona central de la pantalla buscá **“Configuración de pago”** / “Payment settings” o **“Métodos de pago”** / “Payment methods”.
- Clic en **“Configuración de pago”** o en **“Agregar método de pago”** si es lo único que ves.

**Verás:** Una lista de métodos de pago (puede estar vacía) y un botón para agregar uno nuevo.

---

### 3.5 – Agregar método de pago

- Clic en el botón **“Agregar método de pago”** o “Add payment method” / “Agregar tarjeta”, etc.

**Verás:** Un formulario o un selector de tipo de pago (Tarjeta, PayPal, etc.).

---

### 3.6 – Elegir tipo de pago

- Elegí **“Tarjeta de crédito o débito”** (o “PayPal” si preferís).
- Clic en **“Siguiente”** o “Continuar” según lo que diga.

---

### 3.7 – Completar datos de la tarjeta (si elegiste tarjeta)

- **Número de tarjeta:** Los 16 dígitos de la tarjeta (sin espacios o con espacios, según acepte el formulario).
- **Fecha de vencimiento:** Mes y año (ej. 12/28).
- **CVV:** Los 3 dígitos del dorso (o 4 si es American Express).
- **Nombre del titular:** Exactamente como figura en la tarjeta.
- **País / Dirección de facturación:** Completá lo que pida (calle, ciudad, código postal, país).

Revisá que todo esté bien y clic en **“Guardar”** o “Listo” o “Confirmar”.

---

### 3.8 – Si elegiste PayPal

- Te va a redirigir a PayPal para autorizar. Iniciá sesión en PayPal y aceptá la vinculación con Meta.
- Volvé a business.facebook.com y verificá que el método de pago figure en la lista.

---

### 3.9 – Verificar que el método quedó guardado

- En la pantalla de Facturación o Configuración de pago deberías ver tu **tarjeta** o **PayPal** listado (a veces con los últimos 4 dígitos o el nombre).
- Si ves eso, **facturación está lista**. Podés pasar al **Paso 4** (agregar tu número).

**Alternativa:** Si en developers.facebook.com, en **tu app**, en el menú izquierdo ves **“Configuración”** (Settings) y dentro **“Facturación”** (Billing), podés agregar el método de pago desde ahí si Business Manager no te mostró la opción.

---

## Paso 4 – Agregar tu número específico

**Objetivo:** Vincular **el número que vas a usar** para RRHH/comunicados a tu WhatsApp Business API y obtener el Phone number ID y el Token.

**Importante:** Ese número **no** debe estar ya registrado en WhatsApp (app normal o Business app). Si está, hay que migrarlo (Meta te guía) o usar otro número.

---

### 4.1 – Ir a la configuración de la API de WhatsApp

- Abrí **`https://developers.facebook.com`** y, si hace falta, iniciá sesión.
- Clic en **“Mis aplicaciones”** y elegí **tu aplicación** (la que creaste en el Paso 2).
- En el **menú izquierdo** clic en **“WhatsApp”**.
- En el submenú clic en **“Configuración de la API”** o “API Setup” (a veces se llama “Empezar” / “Getting started”).

**Verás:** Una pantalla con el “número de prueba”, un “ID de número de teléfono” (Phone number ID), un “Token de acceso temporal” y una sección para agregar números de prueba (hasta 5).

---

### 4.2 – Buscar la opción para agregar número real

- En esa misma pantalla (API Setup) buscá un enlace o botón que diga **“Agregar número de teléfono”** / “Add phone number” o “Registrar número” (suele estar arriba a la derecha o debajo del número de prueba).
- Clic en **“Agregar número de teléfono”**.

**Verás:** Un formulario o pantalla para ingresar el número que querés usar.

---

### 4.3 – Ingresar el número

- **Código de país:** En el desplegable elegí tu país (ej. Argentina +54, México +52, España +34).
- **Número:** Escribí el número **sin** el 0 inicial y **sin** el código de país (ya lo elegiste).  
  Ejemplo Argentina: si el número es 011 15 1234-5678, ingresá **91112345678**.  
  Ejemplo México: 55 1234 5678 → **5512345678**.

- Clic en **“Siguiente”** o “Enviar código” / “Next”.

**Verás:** Opciones para recibir el código de verificación (SMS o llamada de voz).

---

### 4.4 – Pedir el código de verificación

- Elegí **“Enviar código por SMS”** o **“Llamada de voz”** (la que prefieras).
- Clic en **“Enviar código”** o “Send code”.

**Verás:** Un mensaje que dice que se envió el código. En unos segundos o minutos recibís el SMS o la llamada con un código de **6 dígitos** (o similar).

---

### 4.5 – Ingresar el código

- En la casilla que te pide el código, escribí los **6 dígitos** que recibiste (sin espacios).
- Clic en **“Verificar”** o “Submit” / “Confirmar”.

**Verás:** Un mensaje de éxito. Ese número queda **vinculado** a tu cuenta de WhatsApp Business API.

**Si el número ya tiene WhatsApp:** Meta puede mostrarte la opción **“Migrar a WhatsApp Business API”**. Si querés usar ese mismo número, seguí las instrucciones en pantalla (incluyen pasos en la app de WhatsApp del celular). Si no, usá otro número que no esté en WhatsApp.

---

### 4.6 – Obtener Phone number ID y Token de tu número

- Volvé a la pantalla **“Configuración de la API”** / “API Setup” (menú WhatsApp → Configuración de la API).
- Ahora deberías ver **dos** números: el de **prueba** y **tu número**.
- Seleccioná o hacé clic en **tu número** (el que acabas de verificar).
- En la misma pantalla vas a ver:
  - **“ID de número de teléfono”** o “Phone number ID”: un número largo (ej. 123456789012345). **Copialo** y guardalo en un archivo o gestor de claves.
  - **“Token de acceso temporal”** o “Temporary access token”: una cadena larga. **Copiala** y guardala en el mismo lugar. Esta la vas a usar en tu backend (variable de entorno `WHATSAPP_ACCESS_TOKEN`; no la subas a repositorios públicos).

**Listo:** Con el Phone number ID y el Token ya podés enviar mensajes desde tu código usando ese número. Para **muchos contactos**, seguí con el **Paso 5** (verificación del negocio).

---

## Paso 5 – Verificación del negocio (muchos contactos)

**Objetivo:** Completar la **verificación del negocio** en Meta para que te suban el límite de contactos únicos por día (tier) y puedas enviar a cientos o miles de personas.

---

### 5.1 – Abrir Configuración del negocio

- Abrí **`https://business.facebook.com`** e iniciá sesión.
- Clic en el **engranaje** (Configuración) o en **“Configuración del negocio”** / “Business settings” como en el Paso 3.

---

### 5.2 – Ir a Verificación del negocio

- En el **menú izquierdo** buscá **“Verificación del negocio”** / “Business verification” o **“Seguridad central”** / “Security Centre”.
- Clic en **“Verificación del negocio”** (o dentro de Seguridad central, la opción de verificación).

**Verás:** Una pantalla que indica el estado de verificación (no iniciada, en revisión, aprobada) y un botón para iniciar.

---

### 5.3 – Iniciar la verificación

- Si el estado es “No verificada” o similar, clic en **“Iniciar verificación”** / “Start verification” o “Completar verificación”.

**Verás:** Un formulario o flujo guiado para los datos del negocio.

---

### 5.4 – Completar datos del negocio

- **Nombre legal de la empresa:** El que figura en documentos oficiales (ej. razón social, nombre fiscal).
- **Dirección del negocio:** Dirección fiscal o legal (calle, número, ciudad, código postal, país).
- **Sitio web:** URL del sitio oficial de la empresa (recomendado; si no tenés, a veces se puede dejar en blanco o poner un perfil de red social según lo que permita Meta).
- Completá cualquier otro campo obligatorio que aparezca.
- Clic en **“Siguiente”** o “Continuar”.

---

### 5.5 – Subir documentos

Meta suele pedir **dos tipos** de documentos:

1. **Prueba del nombre legal del negocio**  
   Ejemplos: certificado de incorporación, alta en AFIP/IVA, inscripción en cámara, estatuto, etc. Subí un **PDF o imagen** (foto escaneada) legible.

2. **Prueba de dirección o del negocio**  
   Ejemplos: factura de servicio (luz, gas, teléfono) a nombre de la empresa, contrato de alquiler, licencia comercial, etc. Subí **PDF o imagen** legible.

- En cada sección clic en **“Subir archivo”** o “Upload” y elegí el archivo desde tu computadora.
- Asegurate de que el archivo no esté vencido y que el nombre/dirección coincida con lo que pusiste en el formulario.
- Clic en **“Siguiente”** o “Continuar” cuando hayas subido lo que pida.

---

### 5.6 – Enviar para revisión

- Revisá que todo esté completo.
- Clic en **“Enviar”** / “Submit” o “Enviar para revisión”.

**Verás:** Un mensaje de que la solicitud fue enviada. La revisión de Meta puede tardar **varios días** (a veces 1–2 semanas). Te notifican por **correo** y en Business Manager cuando el resultado esté listo.

---

### 5.7 – Después de la aprobación

- Cuando Meta **apruebe** la verificación, el **tier** (límite de contactos únicos por día) suele aumentar (ej. a 10.000 o más según la política actual).
- Podés revisar el límite en la pantalla de API Setup de WhatsApp o en la sección de la cuenta de WhatsApp en Business Manager.

Mientras tanto podés seguir usando tu número con el límite actual. Para **700 destinatarios en un día** suele alcanzar con Tier 2 (10.000/día), que muchas veces se habilita tras la verificación.

---

## Paso 6 – Plantillas de mensaje (comunicados)

**Objetivo:** Crear una **plantilla de mensaje** aprobada por Meta para enviar comunicados a muchos contactos (fuera de la ventana de 24 h).

---

### 6.1 – Ir a Plantillas de mensaje

- En **`https://developers.facebook.com`** → **Mis aplicaciones** → tu app.
- En el menú izquierdo: **WhatsApp** → **“Plantillas de mensaje”** / “Message templates”.

**Verás:** Una lista de plantillas (puede estar vacía) y un botón para crear una nueva.

---

### 6.2 – Crear plantilla

- Clic en **“Crear plantilla”** / “Create template” o “Nueva plantilla”.

**Verás:** Un formulario con varios campos.

---

### 6.3 – Completar la plantilla

- **Nombre:** Un nombre interno en inglés, sin espacios (ej. `comunicado_rrhh` o `hr_announcement`). Este nombre lo usás en el código para enviar.
- **Idioma:** Elegí el idioma (ej. Español).
- **Categoría:** Para comunicados de RRHH suele servir **“Marketing”** o **“Utilidad”** (Utility). Elegí la que mejor describa el uso.
- **Cuerpo (Body):** El texto del mensaje. Podés usar variables con `{{1}}`, `{{2}}`, etc. para personalizar (ej. “Hola {{1}}, te informamos que …”). Revisá las [políticas de plantillas de Meta](https://developers.facebook.com/docs/whatsapp/message-templates/guidelines) para que no rechacen el texto.
- **Encabezado (Header) y Pie (Footer):** Opcionales; completalos solo si los querés.
- Clic en **“Enviar”** / “Submit” para enviar a **revisión**.

**Verás:** El estado de la plantilla pasa a “En revisión” (Pending). La aprobación puede tardar **horas o días**.

---

### 6.4 – Usar la plantilla aprobada

- Cuando el estado sea **“Aprobada”** (Approved), en tu código podés enviar mensajes usando ese **nombre de plantilla** y los parámetros en orden (ej. `["Juan", "texto del comunicado"]`).
- En este proyecto podés usar el módulo `whatsapp_broadcast.py` y el doc `docs/WHATSAPP_COMUNICADOS_MASIVOS.md` para el envío en lotes con pausa.

---

## Resumen de datos para tu código

| Dato | Dónde se obtiene |
|------|-------------------|
| **WHATSAPP_ACCESS_TOKEN** | developers.facebook.com → tu app → WhatsApp → API Setup → Token (de tu número). |
| **WHATSAPP_PHONE_NUMBER_ID** | developers.facebook.com → tu app → WhatsApp → API Setup → Phone number ID (de tu número). |

Guardalos en variables de entorno o en un archivo de configuración que no se suba a repositorios públicos.

---

## Checklist final

- [ ] Cuenta de negocio en business.facebook.com (Paso 1).  
- [ ] App creada en developers.facebook.com con producto WhatsApp (Paso 2).  
- [ ] Facturación: método de pago agregado en Business Manager (Paso 3).  
- [ ] Número específico agregado y verificado en WhatsApp → API Setup (Paso 4).  
- [ ] Phone number ID y Token copiados y guardados (Paso 4.6).  
- [ ] Verificación del negocio iniciada y, si es posible, aprobada (Paso 5).  
- [ ] (Opcional) Plantilla de mensaje creada y aprobada (Paso 6).  

Para no ser bloqueado al enviar a muchos contactos, usá **envío en lotes con pausa** como en `whatsapp_broadcast.py` y en `docs/WHATSAPP_COMUNICADOS_MASIVOS.md`.
