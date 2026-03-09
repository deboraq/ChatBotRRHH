# Cómo conectar Document AI (Google Cloud)

La base de conocimiento por empresa permite subir un **CSV o Excel** con columnas `pregunta` y `respuesta`. Si en cambio tenés **PDFs** (formularios, documentos escaneados) con preguntas y respuestas, podés usar Document AI para extraer el texto y luego procesarlo.

---

## 1. Activar Document AI y crear un procesador

### Opción A: Por consola (paso a paso)

**Qué hacer con los botones que ves:** En la pantalla de Document AI aparecen **"Explorar procesadores"** y **"Crear procesador personalizado"**. Para leer PDFs y extraer texto no hace falta el personalizado. Clic en **"Explorar procesadores"** (o en el menú izquierdo en **"Galería del procesador"**). Ahí elegís un procesador tipo OCR y lo creás en tu proyecto.

**Ya tenés la API activada.** Ahora hay que crear el “procesador” (es el motor que lee los PDFs).

1. **Abrí Document AI en la consola**  
   Entrá a este link (con tu proyecto ya elegido):  
   **image.png**  
   O: menú ☰ → **“Vertex AI”** o **“AI”** → **“Document AI”**.

2. **Crear el procesador**  
   - En la página de Document AI vas a ver una lista de procesadores (puede estar vacía al principio).  
   - Buscá el botón **“Create processor”** o **“Crear procesador”** (arriba o en el centro) y hacé clic.

3. **Elegir tipo y región**  
   - Te va a pedir **región**: elegí una, por ejemplo **“us (United States)”** o **“global”**.  
   - Te muestra una lista de **tipos de procesador**. Para extraer texto de PDFs (preguntas y respuestas), elegí uno de estos:
     - **“Document OCR”** o **“OCR Processor”** → extrae todo el texto del PDF.  
     - Si solo ves categorías, entrá en **“Digitize”** o **“General”** y elegí el que diga **OCR** o **Document OCR**.
   - Poné un **nombre** para el procesador (ej. `chatbot-knowledge`).  
   - Clic en **“Create”** / **“Crear”**.

4. **Anotar el ID del procesador**  
   - Después de crearlo, entrás al procesador y ves el detalle.  
   - Ahí aparece el **Processor ID** (o “ID del procesador”): una cadena de letras y números (ej. `a1b2c3d4e5f6g7h8`).  
   - Copiá ese ID y guardalo; lo vas a poner en el `.env` como `DOCUMENT_AI_PROCESSOR_ID=...`.  
   - La **región** que elegiste (ej. `us`) va en el `.env` como `DOCUMENT_AI_LOCATION=us`.

**En resumen:** Document AI → Create processor → elegir OCR / Document OCR → elegir región → Create → copiar el Processor ID al `.env`.

**Si te dice "No tienes permisos suficientes" / "Editor de Document AI":**  
Tu usuario no tiene el rol necesario para crear procesadores. Tenés dos opciones:

1. **Que un admin del proyecto te dé el rol**  
   Alguien con rol **Owner** o **Administrador de IAM** en el proyecto debe ir a **IAM y administración > IAM** (https://console.cloud.google.com/iam-admin/iam), buscar tu cuenta (o el correo con el que entrás a la consola), hacer clic en el lápiz (Editar) y agregar el rol **"Editor de Document AI"** (Document AI Editor). Guardar.

2. **Crear el procesador con otra cuenta**  
   Si tenés otra cuenta que sea Owner/Admin del proyecto `it-analyzer`, entrá a la consola con esa cuenta, andá a Document AI > Galería del procesador, elegí Document OCR y creá el procesador. Después podés usar el Processor ID en el chatbot con tu cuenta de servicio (`claves.json`).

---

### Opción B: Por línea de comandos (copiá y ejecutá)

**Paso 1 – Activar la API** (reemplazá `it-analyzer` por tu proyecto):

```bash
gcloud config set project it-analyzer
gcloud services enable documentai.googleapis.com
```

**Paso 2 – Crear el procesador** con este script. Guardalo como `crear_procesador_document_ai.py` en la carpeta del proyecto:

```python
"""Ejecutar una vez para crear el procesador de Document AI. Requiere: pip install google-cloud-documentai"""
import os
from google.cloud import documentai_v1 as documentai

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("DOCUMENT_AI_PROJECT_ID") or "it-analyzer"
LOCATION = os.getenv("DOCUMENT_AI_LOCATION") or "us"
# Tipo: OCR_PROCESSOR para extraer texto de PDFs; FORM_PARSER_PROCESSOR para formularios
PROCESSOR_TYPE = "OCR_PROCESSOR"
DISPLAY_NAME = "chatbot-knowledge-ocr"

def main():
    client = documentai.DocumentProcessorServiceClient()
    parent = f"projects/{PROJECT_ID}/locations/{LOCATION}"
    processor = documentai.Processor(
        display_name=DISPLAY_NAME,
        type_=PROCESSOR_TYPE,
    )
    result = client.create_processor(parent=parent, processor=processor)
    # El ID está en result.name: projects/.../processors/XXXXX
    processor_id = result.name.split("/")[-1]
    print(f"Procesador creado.")
    print(f"DOCUMENT_AI_PROJECT_ID={PROJECT_ID}")
    print(f"DOCUMENT_AI_LOCATION={LOCATION}")
    print(f"DOCUMENT_AI_PROCESSOR_ID={processor_id}")
    print("Agregá estas líneas a tu .env")

if __name__ == "__main__":
    main()
```

Ejecutalo (con las credenciales de tu proyecto configuradas, ej. `GOOGLE_APPLICATION_CREDENTIALS=claves.json`):

```bash
python crear_procesador_document_ai.py
```

Copiá el `DOCUMENT_AI_PROCESSOR_ID` que imprime y agregalo al `.env`.

---

## 2. Credenciales y variables de entorno

- Las mismas credenciales de Firebase (cuenta de servicio o `claves.json`) pueden tener acceso a Document AI si la cuenta tiene el rol **Document AI API User** (o **Document AI Editor**).
- En la consola: **IAM y administración > IAM**, buscá la cuenta de servicio que usás para el chatbot y agregale el rol **"Document AI API User"**.

Opcional en `.env`:

```env
DOCUMENT_AI_PROJECT_ID=it-analyzer
DOCUMENT_AI_LOCATION=us
DOCUMENT_AI_PROCESSOR_ID=abc123def456
```

(Si no los ponés, se puede usar el proyecto por defecto de `gcloud` o de las credenciales.)

---

## 3. Instalar el cliente de Document AI

```bash
pip install google-cloud-documentai
```

---

## 4. Uso desde el chatbot (subida de PDF)

Cuando el usuario suba un **PDF** en la sección "Base de conocimiento" de Configuración:

1. **Subir el archivo** al backend (como ya se hace con comunicados/adjuntos).
2. **Llamar a Document AI** con ese archivo para extraer texto:
   - Si usás **Form Parser**: obtenés entidades/campos (key-value) que podés mapear a pregunta/respuesta.
   - Si usás **Document OCR**: obtenés el texto completo; después podés partirlo por líneas o por bloques (ej. "P: ... R: ...") y armar la lista de `{pregunta, respuesta}`.
3. **Guardar en Firestore** en `company_knowledge/{company_id}` con la misma estructura que usa el CSV: `entries: [{ pregunta, respuesta }, ...]`.

Ejemplo mínimo de código (extracción de texto con Document AI):

```python
from google.cloud import documentai_v1 as documentai

def extraer_texto_document_ai(file_bytes: bytes, mime_type: str = "application/pdf") -> str:
    client = documentai.DocumentProcessorServiceClient()
    name = f"projects/{PROJECT_ID}/locations/{LOCATION}/processors/{PROCESSOR_ID}"
    raw_doc = documentai.RawDocument(content=file_bytes, mime_type=mime_type)
    request = documentai.ProcessRequest(name=name, raw_document=raw_doc)
    result = client.process_document(request=request)
    return result.document.text
```

Después podés partir `result.document.text` por líneas o por un patrón (ej. "Pregunta:", "Respuesta:") y armar las entradas para `guardar_knowledge_empresa`.

---

## 5. Resumen

| Paso | Acción |
|------|--------|
| 1 | Activar Document AI API y crear procesador (Form Parser u OCR). |
| 2 | Dar rol "Document AI API User" a la cuenta de servicio del chatbot. |
| 3 | `pip install google-cloud-documentai`. |
| 4 | En el endpoint de subida de "Base de conocimiento", si el archivo es PDF: llamar a Document AI, extraer texto (o campos), convertir a lista pregunta/respuesta y guardar con `guardar_knowledge_empresa`. |

Para **CSV/Excel** no hace falta Document AI: el backend ya puede parsear esas columnas directamente. Document AI sirve cuando la fuente es **PDF o imagen**.
