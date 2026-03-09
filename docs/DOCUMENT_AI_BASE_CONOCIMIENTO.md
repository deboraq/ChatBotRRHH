# Conectar Document AI para la base de conocimiento

La base de conocimiento por empresa acepta **CSV** y **Excel** directamente. Si querés subir **PDF** (por ejemplo un manual escaneado o un documento con preguntas y respuestas), podés usar **Google Cloud Document AI** para extraer el texto y luego el sistema lo convierte en pares pregunta/respuesta.

---

## 1. Qué hace Document AI acá

- **Entrada:** un PDF subido en Configuración → Base de conocimiento (por empresa).
- **Document AI:** extrae el texto del PDF (OCR si está escaneado).
- **La app:** toma ese texto, lo divide en bloques y trata de armar pares **Pregunta / Respuesta** (por reglas o por formato que definas). Esos pares se guardan en Firestore como el resto de la base de conocimiento.

Sin Document AI, solo podés usar CSV o Excel. Con Document AI podés usar además PDF.

---

## 2. Crear y configurar el processor en Google Cloud

### 2.1 Habilitar Document AI

1. Entrá a [Google Cloud Console](https://console.cloud.google.com).
2. Elegí el proyecto (el mismo que usás para Firebase/Cloud Run, ej. `it-analyzer`).
3. En el buscador escribí **Document AI API** y habilitá la API.
4. Andá a [Document AI – Processors](https://console.cloud.google.com/ai/document-ai/processors).
5. **Create processor:**
   - **Type:** "Document OCR" (para PDFs con texto o escaneos).
   - **Region:** la misma que tu app (ej. `southamerica-east1` si estás en Brasil; si no hay, usá `us`).
   - Nombre: ej. `base-conocimiento-ocr`.
6. Copiá el **Processor ID** (algo como `a1b2c3d4e5f6g7h8`).

### 2.2 Variables de entorno

En tu `.env` (o en Cloud Run como variables de entorno) agregá:

```env
# Document AI (opcional; solo para subir PDF en base de conocimiento)
DOCUMENT_AI_PROJECT_ID=it-analyzer
DOCUMENT_AI_LOCATION=southamerica-east1
DOCUMENT_AI_PROCESSOR_ID=a1b2c3d4e5f6g7h8
```

- `DOCUMENT_AI_PROJECT_ID`: mismo proyecto de Firebase/Cloud Run.
- `DOCUMENT_AI_LOCATION`: región donde creaste el processor (ej. `us`, `southamerica-east1`).
- `DOCUMENT_AI_PROCESSOR_ID`: ID del processor que copiaste.

Si **no** configurás estas variables, la opción de subir PDF no se usará y todo seguirá funcionando con CSV/Excel.

---

## 3. Permisos (Cloud Run / servicio)

Si la app corre en **Cloud Run**, la cuenta de servicio que usa el proyecto ya suele tener acceso a las APIs del proyecto. Si al procesar un PDF ves errores de permisos:

1. En Cloud Console → **IAM** → buscá la cuenta de servicio de Cloud Run (ej. `chatbot-rrhh-run@it-analyzer.iam.gserviceaccount.com`).
2. Asignale el rol **Document AI API User** (o el rol que use Document AI en tu proyecto).

En desarrollo local, si usás `gcloud auth application-default login`, con eso suele alcanzar para que Document AI funcione.

---

## 4. Cómo se usa en la app

- En **Configuración → Base de conocimiento**, elegís la empresa y subís un archivo.
- **CSV / Excel:** se procesan como hoy (columnas Pregunta / Respuesta).
- **PDF:**  
  - Si están definidas `DOCUMENT_AI_*`, la app envía el PDF a Document AI, recibe el texto y luego intenta armar pares pregunta/respuesta (por ejemplo por párrafos o por formato tipo “P: … R: …”).  
  - Si no están definidas, la subida de PDF puede estar deshabilitada o mostrar un mensaje de que hay que configurar Document AI.

El formato del PDF (cómo están escritas las preguntas y respuestas) influye en cómo se parten los pares. Lo más predecible es tener en el PDF algo como:

- Una pregunta por línea o bloque, y debajo la respuesta; o
- Líneas que empiecen con "P:" y "R:" (o "Pregunta:" y "Respuesta:").

Así la lógica de parsing puede cortar el texto en pares de forma estable.

---

## 5. Costo

Document AI cobra por página procesada. Revisá [Pricing - Document AI](https://cloud.google.com/document-ai/pricing). El uso típico para subir un manual o un PDF de FAQ por empresa suele ser bajo (pocas páginas por vez).

---

## 6. Resumen

| Paso | Acción |
|------|--------|
| 1 | Habilitar Document AI API en el proyecto. |
| 2 | Crear un processor tipo Document OCR en la región que uses. |
| 3 | Copiar Processor ID y configurar `DOCUMENT_AI_PROJECT_ID`, `DOCUMENT_AI_LOCATION`, `DOCUMENT_AI_PROCESSOR_ID` en `.env` o Cloud Run. |
| 4 | (Opcional) Dar rol Document AI a la cuenta de servicio de Cloud Run si hace falta. |
| 5 | Subir un PDF en Base de conocimiento y probar; si no está configurado Document AI, seguir usando solo CSV/Excel. |

Con eso tenés Document AI conectado para la base de conocimiento y podés usar PDF además de CSV y Excel.
