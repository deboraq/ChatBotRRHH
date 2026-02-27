# Dónde se cargan las FAQs y cómo se ven en el chat

## En una frase

**Las FAQs viven en Firebase (Firestore).** Cada empresa puede tener las suyas. Hoy se cargan con **scripts** (o desde la consola de Firebase); más adelante se puede sumar una pantalla en Configuración para editarlas desde la app.

---

## Dónde están guardadas (Firestore)

Hay dos colecciones:

| Colección   | Uso |
|------------|-----|
| **`faq_rrhh`** | La que usaba todo el mundo antes (una sola lista global). Sigue existiendo como respaldo. |
| **`faqs`**     | La nueva: cada documento tiene **empresa** (`company_id`) + **tema** + **respuesta**. Así cada empresa tiene su propio set. |

**Regla del chat:**  
Si la empresa del usuario tiene FAQs en **`faqs`**, el chat usa esas.  
Si no tiene (o no hay nada en `faqs` para esa empresa), el chat usa **`faq_rrhh`** y, si falta algo, el fallback local del código.

---

## Cómo se cargan hoy (quién las “pasa”)

**No las pasás a “mí” (al asistente).** Las cargás **en Firestore**, y el chat las **lee** de ahí según la empresa.

Formas de cargarlas hoy:

### 1. Script para una empresa (recomendado para arrancar)

- **Bacar (o la primera empresa):**  
  En `cargar_faqs.py` están los temas y respuestas de Bacar. Ese script escribe en **`faq_rrhh`**.  
  Luego podés copiarlos a la nueva estructura por empresa con:
  ```bash
  python migrar_faqs_por_empresa.py bacar
  ```
  Eso crea en **`faqs`** los documentos con `company_id = "bacar"`.

- **Otra empresa:**  
  Habría que tener otro script (o ampliar uno) que escriba en **`faqs`** con otro `company_id`, mismo formato: `company_id`, `tema`, `respuesta`. No hay pantalla todavía; es script o consola de Firebase.

### 2. Consola de Firebase

- Entrás a [Firebase Console](https://console.firebase.google.com) → tu proyecto → Firestore.
- En la colección **`faqs`** creás documentos con:
  - **ID del documento:** por ejemplo `bacar_vacaciones` (o `{company_id}_{tema}`).
  - Campos: `company_id` (string), `tema` (string), `respuesta` (string).

Así “cada empresa va generando” sus FAQs en Firebase: o con un script que vos corrés, o creando/editando documentos en la consola (o en el futuro desde la app).

---

## Cómo lo ve el usuario en el chat

1. El usuario entra al chat (localhost o el link que uses).
2. La app sabe **qué empresa es** (por sesión o por `?empresa=bacar` en la URL).
3. Para esa empresa:
   - Se buscan temas en **`faqs`** con ese `company_id`.
   - Si hay resultados → el **menú** (1. Vacaciones, 2. ART, etc.) y las **respuestas** salen de ahí.
   - Si no hay nada en `faqs` para esa empresa → se usa **`faq_rrhh`** (y el fallback del código).
4. Eso es lo que “ve” en el chat: el menú y las respuestas que están en Firestore para esa empresa.

No hay otra “pantalla de carga” de FAQs en la app todavía; la fuente de verdad es Firestore (colección `faqs` por empresa, o `faq_rrhh` como respaldo).

---

## Resumen

| Pregunta | Respuesta |
|----------|-----------|
| ¿Dónde se cargan las FAQs? | En **Firestore**, en la colección **`faqs`** (por empresa) o, como respaldo, en **`faq_rrhh`**. |
| ¿Te las paso a vos? | No; las cargás **en Firebase** (con un script o desde la consola). El chat las **lee** de ahí. |
| ¿Cada empresa genera sus FAQs en Firebase? | Sí. Cada empresa tiene sus documentos en **`faqs`** con su `company_id`. Pueden cargarlos con script o, más adelante, desde una pantalla en Configuración. |
| ¿Cómo lo veo en el chat? | Según la **empresa activa** (sesión o `?empresa=...`), el chat muestra el menú y las respuestas de esa empresa que están en **`faqs`** (o en `faq_rrhh` si no hay nada para esa empresa). |

Si querés, el siguiente paso puede ser una **pantalla en Configuración** para “FAQs de esta empresa”: listar, agregar y editar temas y respuestas para la empresa seleccionada, y que la app siga leyendo desde **`faqs`** como ahora.
