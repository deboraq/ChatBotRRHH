#!/usr/bin/env python3
"""
Migra FAQs de la colección legacy 'faq_rrhh' a la colección 'faqs' con company_id.

Uso:
  python migrar_faqs_por_empresa.py [company_id]

Ejemplo:
  python migrar_faqs_por_empresa.py bacar

Cada documento en 'faqs' queda con:
  - id: "{company_id}_{tema_normalizado}"  (ej. bacar_vacaciones)
  - company_id: str
  - tema: str (normalizado a minúsculas)
  - respuesta: str
"""

import sys
from firebase_config import inicializar_firestore


def normalizar_tema(tema):
    return str(tema or "").strip().lower()


def main():
    company_id = (sys.argv[1] if len(sys.argv) > 1 else "bacar").strip().lower()
    if not company_id:
        print("Indicá un company_id (ej: bacar)")
        sys.exit(1)

    db = inicializar_firestore(verbose=False)
    if not db:
        print("No se pudo conectar a Firestore. Revisá FIREBASE_CREDENTIALS.")
        sys.exit(1)

    print(f"Leyendo temas desde 'faq_rrhh'...")
    try:
        docs = list(db.collection("faq_rrhh").stream())
    except Exception as e:
        print(f"Error leyendo faq_rrhh: {e}")
        sys.exit(1)

    if not docs:
        print("No hay documentos en faq_rrhh. Nada que migrar.")
        sys.exit(0)

    print(f"Migrando {len(docs)} temas a 'faqs' con company_id={company_id!r}...")
    for doc in docs:
        data = doc.to_dict() or {}
        tema_orig = doc.id
        tema = normalizar_tema(data.get("tema") or tema_orig)
        respuesta = data.get("respuesta") or ""
        if not tema:
            continue
        doc_id = f"{company_id}_{tema}"
        payload = {
            "company_id": company_id,
            "tema": tema,
            "respuesta": respuesta,
        }
        try:
            db.collection("faqs").document(doc_id).set(payload)
            print(f"  OK: {doc_id}")
        except Exception as e:
            print(f"  ERROR {doc_id}: {e}")

    print(f"\nListo. FAQs de '{company_id}' están en la colección 'faqs'.")


if __name__ == "__main__":
    main()
