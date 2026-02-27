# Preguntas frecuentes y reglas escalables (multi-empresa y multi-área)

## Situación actual

- **FAQs**: Una sola colección en Firestore (`faq_rrhh`) con temas y respuestas. No hay separación por empresa ni por área.
- **Empresas**: La app ya tiene multi-empresa (sesión, Panel RRHH, Configuración). El mensaje de bienvenida y contacto se arman con el nombre de la empresa activa.
- **Reglas**: No hay un concepto explícito de “reglas” por empresa/área (qué temas mostrar, quién puede hablar con el bot, horarios, etc.).

Para escalar a **otras áreas de Bacar** y **otras empresas**, con **reglas y FAQs distintas**, conviene definir un modelo claro.

---

## Objetivos

1. **Por empresa**: Cada empresa puede tener su propio set de FAQs y sus propias reglas.
2. **Por área** (opcional): Dentro de una empresa (ej. Bacar), poder tener “RRHH”, “IT”, “Beneficios”, etc., cada uno con sus temas y respuestas.
3. **Reglas configurables**: No todos con las mismas reglas; poder definir por empresa/área cosas como:
   - Qué temas están habilitados.
   - Si está permitido “Hablar con RRHH” (o con el área correspondiente).
   - Restricciones por sucursal, horario, etc. (fase posterior).

---

## Propuesta de modelo

### 1. Alcance de FAQs por empresa (y opcionalmente por área)

Dos enfoques posibles:

#### Opción A: Una colección por empresa (y por área)

- **Estructura en Firestore**:
  - Colección `faq_{company_id}` (ej. `faq_bacar`) para temas globales de esa empresa.
  - O bien `faq_{company_id}_{area}` (ej. `faq_bacar_rrhh`, `faq_bacar_it`) si querés separar por área.
- **Ventaja**: Datos muy aislados por cliente; fácil de exportar o migrar por empresa.
- **Desventaja**: Más colecciones; scripts de carga y migración deben conocer el nombre.

#### Opción B: Una sola colección con “scope” en el documento

- **Estructura**: Una colección, por ejemplo `faqs`, con documentos que llevan `company_id` y opcionalmente `area`.
  - Ejemplo: `{ company_id: "bacar", area: "rrhh", tema: "vacaciones", respuesta: "..." }`.
  - Para temas globales de la empresa: `area: ""` o sin campo `area`.
- **Consultas**: Al cargar temas/respuestas se filtra por `company_id` (y `area` si existe).
- **Ventaja**: Una sola colección; fácil agregar empresas/áreas sin tocar nombres de colecciones.
- **Desventaja**: Índices y reglas de seguridad Firestore deben filtrar bien por `company_id` (y `area`).

**Recomendación**: Para escalar a muchas empresas y áreas, la **Opción B** suele ser más manejable (una colección `faqs` con `company_id` y `area`).

### 2. Dónde guardar las “reglas”

Las reglas (qué puede hacer el usuario con el chatbot) se pueden guardar:

- **En la empresa (Configuración actual)**: En el documento o payload de “empresa” en tu backend (Firestore o lo que uses para `general_settings` / empresas) agregar algo como:
  - `chat_rules` o `faq_config`:
    - `areas_habilitadas`: lista de áreas para esa empresa (ej. `["rrhh", "it"]`). Si está vacío o no existe, se asume un solo “área” por defecto (ej. RRHH).
    - `temas_obligatorios`: temas que siempre se muestran (opcional).
    - `permitir_hablar_con_humano`: boolean (ej. “Hablar con RRHH”).
    - Más adelante: `sucursales_permitidas`, `horario_activo`, etc.

Así cada empresa (y luego cada área) puede tener reglas distintas sin cambiar código por cliente.

### 3. Cómo se elige “área” en el chat

- **Por URL o parámetro**: Ej. `/?empresa=bacar&area=rrhh`. La sesión ya tiene `company_id`; se puede agregar `area` en sesión (por defecto `"rrhh"` para no romper lo actual).
- **Por subdominio o path**: Si más adelante tenés rutas por área (ej. `/rrhh`, `/it`), el área puede venir de ahí.
- **Un solo asistente por empresa**: Si por ahora cada empresa tiene un solo “asistente” (solo RRHH), podés dejar `area` fijo `"rrhh"` y solo escalar por `company_id`; el área se usa cuando agregues más.

---

## Pasos de implementación sugeridos

### Fase 1: FAQs por empresa (sin área aún) — **implementada**

- **Firestore**: Colección `faqs` con documentos `id = {company_id}_{tema}` y campos `company_id`, `tema`, `respuesta`.
- **app.py**: `obtener_temas_desde_firestore(company_id=None)` y `obtener_respuesta_faq(tema, company_id=None)` leen primero de `faqs` por empresa; si no hay datos, se usa `faq_rrhh` y `FAQ_FALLBACK`.
- **web_chat.py**: `construir_temas_map(company_id=None)` y `responder_chat()` pasan el `company_id` de la sesión al chatbot.
- **Migración**: Script `migrar_faqs_por_empresa.py` copia `faq_rrhh` → `faqs` con un `company_id` (por defecto `bacar`). Uso: `python migrar_faqs_por_empresa.py bacar`.

### Fase 2: Reglas por empresa — **implementada**

- **Modelo de empresa**: Se agregaron `permitir_hablar_con_humano` (bool, default `True`) y `temas_habilitados` (lista de strings, vacía = todos los temas).
- **Chat**: Si `permitir_hablar_con_humano` es `False`, no se muestra el botón "Hablar con RRHH" y si el usuario pide contacto humano se responde que no está disponible. Si `temas_habilitados` tiene elementos, el menú y las respuestas se limitan a esos temas.
- **Preferencias**: En el bloque "Empresa activa y autocierre" se agregó la sección "Reglas del chat para esta empresa": checkbox "Permitir derivación a RRHH" y textarea "Temas habilitados (uno por línea; vacío = todos)". Al cambiar de empresa en el selector se recargan autocierre y reglas de esa empresa.

### Fase 3 en adelante (pendientes)

1. **Firestore**  
   - Crear colección `faqs` con documentos que tengan al menos: `company_id`, `tema` (id normalizado), `respuesta`.  
   - Opcional: mantener `faq_rrhh` como respaldo para la empresa por defecto y leer primero de `faqs` filtrando por `company_id`.

2. **Backend (app.py / web_chat)**  
   - En `obtener_temas_desde_firestore()` (o equivalente): recibir `company_id`, leer de `faqs` donde `company_id == X`.  
   - En `obtener_respuesta_faq(tema)`: recibir `company_id`, buscar en `faqs` por `company_id` + `tema`.  
   - En `web_chat`: al construir el menú y procesar el mensaje, pasar siempre el `company_id` de la sesión (`_current_company()`).

3. **Configuración / carga**  
   - Script o pantalla para “cargar FAQs” por empresa (lista tema + respuesta) y escribir en `faqs` con el `company_id` correspondiente.  
   - Para Bacar RRHH: migrar el contenido actual de `faq_rrhh` a `faqs` con `company_id = "bacar"` (o el id que uses).

### Fase 2: Reglas por empresa (en Configuración)

1. En el modelo de **empresa** (o configuración general por empresa) agregar campos, por ejemplo:
   - `permitir_hablar_con_humano`: bool  
   - `temas_habilitados`: lista (opcional; si está vacía = todos los de la empresa).

2. En el **chat**:
   - Si `permitir_hablar_con_humano` es false, no mostrar el botón “Hablar con RRHH” y tratar el tema como no disponible.
   - Si existe `temas_habilitados`, filtrar el menú y las respuestas solo a esos temas.

### Fase 3: Múltiples áreas por empresa

1. En la **empresa** definir `areas` (ej. `["rrhh", "it"]`) y en cada documento de `faqs` usar `area` además de `company_id`.
2. En la **sesión del chat** guardar `area` (por defecto `"rrhh"`).
3. Cargar temas y respuestas filtrando por `company_id` + `area`.
4. Ajustar mensajes (bienvenida, “Hablar con RRHH”) para que digan el nombre del área cuando corresponda.

---

## Resumen

| Aspecto | Hoy | Escalado |
|--------|-----|----------|
| FAQs | Una colección `faq_rrhh` global | Colección `faqs` con `company_id` (y luego `area`) |
| Empresa | Sesión con `company_id`, solo branding | Mismo + FAQs y reglas por empresa |
| Reglas | Implícitas (todo permitido) | Campos en empresa: permitir humano, temas habilitados, etc. |
| Áreas | No existe | Opcional: `area` en sesión y en `faqs` para Bacar (RRHH, IT, etc.) |

Con esto podés arrancar con RRHH de Bacar como hoy, y después agregar otras áreas de Bacar y otras empresas, cada una con sus propias preguntas frecuentes y reglas sin cambiar la lógica por cliente.

Si querés, el siguiente paso concreto puede ser: definir el esquema exacto de la colección `faqs` (y de los campos de reglas en empresa) y dónde en el código tocar primero (por ejemplo `construir_temas_map()` y `obtener_respuesta_faq` pasando `company_id`).
