"""
Ejecutar una vez para crear el procesador de Document AI.
Requisitos: pip install google-cloud-documentai
Uso: GOOGLE_APPLICATION_CREDENTIALS=claves.json python crear_procesador_document_ai.py
"""
import os
import sys

try:
    from google.cloud import documentai_v1 as documentai
except ImportError:
    print("Instalá el cliente: pip install google-cloud-documentai")
    sys.exit(1)

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("DOCUMENT_AI_PROJECT_ID") or "it-analyzer"
LOCATION = os.getenv("DOCUMENT_AI_LOCATION") or "us"
# OCR_PROCESSOR = extraer texto de PDFs; FORM_PARSER_PROCESSOR = formularios con campos
PROCESSOR_TYPE = os.getenv("DOCUMENT_AI_PROCESSOR_TYPE") or "OCR_PROCESSOR"
DISPLAY_NAME = "chatbot-knowledge-ocr"


def main():
    client = documentai.DocumentProcessorServiceClient()
    parent = f"projects/{PROJECT_ID}/locations/{LOCATION}"
    processor = documentai.Processor(
        display_name=DISPLAY_NAME,
        type_=PROCESSOR_TYPE,
    )
    result = client.create_processor(parent=parent, processor=processor)
    processor_id = result.name.split("/")[-1]
    print("Procesador creado correctamente.")
    print("Agregá a tu .env:")
    print(f"DOCUMENT_AI_PROJECT_ID={PROJECT_ID}")
    print(f"DOCUMENT_AI_LOCATION={LOCATION}")
    print(f"DOCUMENT_AI_PROCESSOR_ID={processor_id}")


if __name__ == "__main__":
    main()
