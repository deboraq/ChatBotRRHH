# Almacenamiento y costo – ChatBot RRHH

Resumen de **qué guarda** tu proyecto y un **estimado** de uso y costo.

---

## 1. Firestore (base de datos)

Todo lo persistente del chat y la configuración está en **Firestore**. No usás Cloud Storage ni archivos en la nube para fotos/audios.

| Colección / documento | Qué guarda | Tamaño típico por ítem | Qué crece |
|------------------------|------------|-------------------------|-----------|
| **chatbot_config** (doc `general`) | Nombre empresa, contacto RRHH, etc. | ~1 KB | Casi nada (un doc) |
| **chatbot_empresas** | Empresas, sucursales, áreas, temas, número WhatsApp | ~2–5 KB por empresa | Poco (pocas empresas) |
| **chat_historial** | Cada mensaje del chat (colaborador + bot), por conversación | ~0,5–1 KB por mensaje | **Sí** (cada mensaje = 1 doc) |
| **rrhh_handoffs** | Cada derivación a agente (estado, empresa, agente, canal WhatsApp) | ~1–2 KB por handoff | **Sí** (cada conversación = 1 doc) |
| **rrhh_handoffs/{id}/mensajes** | Mensajes dentro de cada handoff (colaborador, agente, sistema) | ~0,5 KB por mensaje | **Sí** (cada mensaje = 1 doc) |
| **faqs** / **faq_rrhh** | FAQs por empresa o globales | ~1–3 KB por tema | Poco |
| **feedback_respuestas** | Respuestas de feedback (si/no) por tema | ~0,5 KB por respuesta | Moderado |
| **consultas_pendientes** | Consultas pendientes de respuesta | ~0,5 KB por ítem | Moderado |
| **rrhh_agentes** | Agentes “activos” (estado en tiempo real, se actualiza y borra) | ~1 KB por agente | Poco |

**Lo que más crece:** `chat_historial` y `rrhh_handoffs` + subcolección `mensajes`. Todo es **texto** (strings, fechas, IDs); no se guardan fotos ni audios.

---

## 2. Estimado de almacenamiento (Firestore)

- **Por mensaje de chat:** ~0,5–1 KB.
- **Por handoff:** ~1–2 KB + ~0,5 KB por mensaje dentro del handoff.

Ejemplo aproximado:

- 10 000 mensajes de chat → ~5–10 MB.
- 500 handoffs con 20 mensajes cada uno → 500 × (2 + 10) KB ≈ 6 MB.
- Empresas, FAQs, config → < 1 MB.

**Total típico (uso interno/mediano):** del orden de **10–50 MB** en Firestore. Firestore cobra por GB; el primer 1 GB está en el tier gratuito. Con ese uso **no pagás almacenamiento** por bastante tiempo.

---

## 3. Costo estimado (mensual, aproximado)

| Concepto | Uso típico | Nivel gratuito | Comentario |
|----------|------------|-----------------|------------|
| **Firestore almacenamiento** | 10–50 MB | 1 GB gratis | Dentro del free tier. |
| **Firestore lecturas/escrituras** | Miles por mes | 50K lecturas, 20K escrituras/día gratis | Depende del tráfico; uso moderado suele quedar bajo o dentro del gratis. |
| **Cloud Run** | Poco tráfico | 2 M de solicitudes/mes gratis | Uso interno suele estar muy por debajo. |
| **Twilio WhatsApp** | Por mensaje | Sandbox limitado; producción por mensaje | Aquí puede haber costo según cantidad de mensajes. |

**Conclusión:** para una app interna con tráfico no masivo, **el almacenamiento casi no tiene costo** (Firestore free tier). Lo que más puede costar es **Twilio** si en producción envían/reciben muchos mensajes por WhatsApp.

---

## 4. Qué no guardás (y por qué no suma almacenamiento)

- **Fotos o audios de WhatsApp:** la app hoy **no** los guarda; Twilio los sirve por URL un tiempo y no se persisten en tu proyecto. Si más adelante los descargás y los guardás (ej. en Cloud Storage), ahí sí contarían como almacenamiento.
- **Usuarios/roles RRHH:** si usás `RRHH_USERS_FILE` / `RRHH_ROLES_FILE`, son archivos JSON en el servidor (o en un disco montado en Cloud Run); no son colecciones de Firestore, pero ocupan muy poco (KB).

---

## 5. Si quisieras limitar crecimiento a futuro

- **chat_historial:** se puede agregar una tarea que borre o archive mensajes más viejos que X meses (p. ej. solo mantener último año).
- **rrhh_handoffs:** igual: política de retención (ej. borrar o archivar handoffs cerrados después de 1–2 años).

Eso mantendría Firestore en el mismo orden de magnitud (decenas de MB) aunque el uso crezca.
