# Estadísticas y FAQs desde documentos

## 1. Revisión de estadísticas

### Qué hay hoy

- **Ruta:** `GET /estadisticas` (página) y `GET /api/stats` (datos JSON).
- **Permisos:** La página exige login RRHH y permiso `estadisticas_ver`. La API `/api/stats` ahora también exige el mismo permiso (no se puede obtener el JSON sin estar logueado).
- **Fuentes en Firestore:**
  - **`feedback_respuestas`:** cada documento tiene `tema`, `fue_util`, `fecha`. No guarda `company_id` (se escribe desde `app.py` sin empresa).
  - **`consultas_pendientes`:** `pregunta`, `fecha`, `estado`, `sentimiento`. Tampoco tiene `company_id`.
  - **`rrhh_handoffs`:** derivaciones con `estado`, `company_id`, `company_name`, `area`, `rrhh_agente`, `updated_at`, etc.
- **KPIs mostrados:** Feedback total, Utilidad (%), Votos Sí/No, No útil, Pendientes, Derivaciones abiertas, En atención.
- **Gráficos:** Evolución últimos 7 días, torta por sentimiento, top temas.
- **Detalle (drilldown):** Feedback reciente, no útil, sí útil, pendientes, conversaciones RRHH, etc.

Los nombres de colección en código son **`feedback_respuestas`** y **`consultas_pendientes`** (minúsculas). La app escribe en esas mismas colecciones.

### Qué está bien

- Coincidencia entre donde se escribe (feedback/pendientes) y donde se lee en `stats_service.py`.
- Handoffs sí tienen `company_id` al crearse desde el chat.
- Modo sin Firestore: se devuelve `available: false` y KPIs en 0 (salvo derivaciones si se pasan en memoria).
- Fecha y series de últimos 7 días coherentes.

### Qué se puede agregar o modificar (opcional)

| Mejora | Descripción |
|--------|-------------|
| **Filtro por empresa** | Hoy las estadísticas son globales. Si en el futuro guardás `company_id` al registrar feedback y pendientes (en `app.py` / flujo del chat), se puede filtrar en `obtener_estadisticas` por empresa y mostrar un selector en la página de estadísticas. Los handoffs ya tienen `company_id`, así que ese filtro ya se podría aplicar solo a derivaciones. |
| **Rango de fechas** | Siempre “últimos 7 días”. Se podría agregar parámetro `days` en la API (7, 30, 90) y un selector en la UI. |
| **Exportar** | Botón para exportar los mismos datos a CSV/Excel. |

### Cambios realizados

- **API `/api/stats`:** Ahora requiere autenticación RRHH y permiso `estadisticas_ver`, igual que la página. Acepta filtros opcionales: `company_id`, `branches`, `areas`. Cuando se pasa empresa (y opcionalmente sucursales/áreas), las métricas de **derivaciones** (abiertas, en atención, etc.) se calculan solo sobre esas conversaciones; feedback y pendientes siguen siendo globales (no tienen `company_id` en Firestore aún).
- **Página Estadísticas:** Selectores **Empresa**, **Sucursal** y **Área**. Al elegir empresa se cargan sus sucursales y áreas; al cambiar filtros se recargan las estadísticas. Se usa el endpoint `/api/filtros/contexto` para obtener la lista de empresas con sus branches y areas.
- **Página Historial:** Mismos selectores **Empresa**, **Sucursal** y **Área**. El listado de mensajes se filtra por empresa (según `metadata.company_id` en el historial o por `conversation_id` perteneciente a handoffs de esa empresa/sucursal/área).
- **API `/api/filtros/contexto`:** Devuelve las empresas disponibles para el usuario con sus sucursales y áreas, para rellenar los filtros en Estadísticas e Historial.

---

## 2. Subir documentos y que las FAQs se basen en eso (sugerencias)

Objetivo: **subir un documento por empresa → que se lea y analice → que el chatbot use esas preguntas/respuestas para contestar** (y opcionalmente leer un archivo de Drive que se va modificando).

### Opción A: Subir documento en la app + IA para extraer FAQs (ej. AI Studio / Vertex)

**Flujo:**

1. En **Configuración** (por empresa) el usuario sube un PDF o Word.
2. El backend convierte el archivo a texto (por ejemplo con PyPDF2, python-docx).
3. Se envía el texto a un modelo de **Google (AI Studio / Gemini o Vertex AI)** con un prompt del tipo:  
   *“A partir del siguiente texto, generá una lista de preguntas frecuentes con sus respuestas. Devolvé JSON: [{ \"tema\": \"nombre_corto\", \"pregunta\": \"...\", \"respuesta\": \"...\" }]”*
4. La app recibe el JSON, muestra un borrador al usuario para editar/aceptar y al guardar escribe en Firestore en la colección **`faqs`** con el `company_id` de la empresa (mismo esquema actual: `company_id`, `tema`, `respuesta`).
5. El chat ya lee de `faqs` por empresa, así que las nuevas preguntas y respuestas se usan solas.

**Requisitos:** Cuenta en Google AI Studio (o Vertex), API de Gemini habilitada, API key o credenciales en el backend.

### Opción B: Archivo en Drive que se va modificando

**Flujo:**

- Un archivo en **Google Drive** (Doc o Sheet) es la fuente de verdad de las FAQs de una empresa.
- Periódicamente (cron o botón “Sincronizar desde Drive”) la app lee ese archivo con la **Google Drive API**, parsea el contenido (por ejemplo: hoja con columnas “tema” y “respuesta”) y actualiza la colección **`faqs`** en Firestore para ese `company_id`.

**Ventaja:** Las personas editan un Doc/Sheet conocido y las FAQs se actualizan sin volver a subir en la app.

**Requisitos:** Proyecto en Google Cloud, Drive API habilitada, OAuth o cuenta de servicio con acceso al archivo. Definir formato (ej. Sheet: fila 1 headers, columnas tema, respuesta).

### Opción C: Híbrido (recomendado)

1. **Subir documento** en la app (por empresa) → extraer texto → llamar a **IA (AI Studio / Vertex)** para generar tema + respuesta → el usuario revisa/edita → guardar en **`faqs`**.
2. **Opcional:** Por empresa se configura una **URL o ID de archivo de Drive**. Un botón “Sincronizar desde Drive” (o un job programado) lee ese archivo y actualiza `faqs` para esa empresa. Así podés tanto “subir un doc y que la IA proponga FAQs” como “ir editando un Doc y que eso se refleje en el chat”.

### Conectar AI Studio (Gemini)

- Entrá a [aistudio.google.com](https://aistudio.google.com), creá un proyecto y generá una **API key**.
- Desde el backend (Python) hacés un POST al endpoint de Gemini con el texto del documento y el prompt para extraer FAQs. La respuesta (JSON con temas y respuestas) se parsea y se guarda en Firestore `faqs` con el `company_id` correspondiente.
- No hace falta Drive para este flujo; Drive es opcional para tener una “fuente que se va modificando”.

### Resumen de pasos sugeridos

| Paso | Acción |
|------|--------|
| 1 | En **Configuración**, sección por empresa, agregar **“Subir documento para FAQs”**: el usuario elige empresa, sube PDF/Word. |
| 2 | Backend: extraer texto (PyPDF2, python-docx, etc.), armar prompt para Gemini: “Del siguiente texto generá preguntas frecuentes con respuestas en JSON: [{ \"tema\": \"...\", \"respuesta\": \"...\" }]”. |
| 3 | Llamar a **Gemini (AI Studio o Vertex)** con ese prompt y el texto; parsear el JSON. |
| 4 | Mostrar en la UI la lista generada para que el usuario edite/acepte; al guardar, escribir en Firestore **`faqs`** con el `company_id` (mismo esquema que hoy). |
| 5 | (Opcional) Por empresa: configurar **archivo de Drive**; botón o job “Sincronizar desde Drive” que lee ese archivo y actualiza `faqs`. |

Así se cumple: **subir documento → leerlo y analizarlo → que vaya modificando las preguntas de cada empresa** y, si querés, **leer un archivo de Drive que se va modificando** para ir contestando con contenido actualizado.

Si definís con cuál opción querés avanzar primero (solo subir doc + IA, solo Drive, o híbrido), se puede bajar a endpoints y cambios concretos en `web_chat.py` y en la pantalla de Configuración.
