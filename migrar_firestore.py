import argparse
import uuid

try:
    import firebase_admin
    from firebase_admin import credentials, firestore
except ImportError:
    firebase_admin = None
    credentials = None
    firestore = None


COLECCIONES_POR_DEFECTO = [
    "faq_rrhh",
    "feedback_respuestas",
    "consultas_pendientes",
]


def inicializar_cliente(credentials_path, app_name):
    cred = credentials.Certificate(credentials_path)
    app = firebase_admin.initialize_app(cred, name=app_name)
    return firestore.client(app=app), app


def copiar_documento_recursivo(src_doc_ref, dst_doc_ref, dry_run=False):
    """Copia un documento y sus subcolecciones (si existen)."""
    snapshot = src_doc_ref.get()
    if not snapshot.exists:
        return 0

    copiados = 0
    if not dry_run:
        dst_doc_ref.set(snapshot.to_dict() or {})
    copiados += 1

    for subcol in src_doc_ref.collections():
        for subdoc in subcol.stream():
            src_subdoc_ref = src_doc_ref.collection(subcol.id).document(subdoc.id)
            dst_subdoc_ref = dst_doc_ref.collection(subcol.id).document(subdoc.id)
            copiados += copiar_documento_recursivo(
                src_subdoc_ref,
                dst_subdoc_ref,
                dry_run=dry_run,
            )

    return copiados


def copiar_coleccion(src_db, dst_db, coleccion, dry_run=False):
    total = 0
    for doc in src_db.collection(coleccion).stream():
        src_doc_ref = src_db.collection(coleccion).document(doc.id)
        dst_doc_ref = dst_db.collection(coleccion).document(doc.id)
        total += copiar_documento_recursivo(src_doc_ref, dst_doc_ref, dry_run=dry_run)
    return total


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Migra colecciones de Firestore entre dos proyectos Firebase "
            "(ideal para cambio de cuenta/proyecto)."
        )
    )
    parser.add_argument(
        "--source-credentials",
        required=True,
        help="Ruta al JSON de service account del proyecto origen.",
    )
    parser.add_argument(
        "--target-credentials",
        required=True,
        help="Ruta al JSON de service account del proyecto destino.",
    )
    parser.add_argument(
        "--collections",
        nargs="*",
        default=COLECCIONES_POR_DEFECTO,
        help=(
            "Colecciones a migrar. Si no se indica, se migran: "
            f"{', '.join(COLECCIONES_POR_DEFECTO)}"
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Solo simula y cuenta documentos sin escribir en destino.",
    )
    return parser.parse_args()


def main():
    if not firebase_admin:
        print("❌ Falta dependencia: firebase_admin")
        print("👉 Instalá: pip install -r requirements-full.txt")
        return 1

    args = parse_args()
    src_app_name = f"src-{uuid.uuid4()}"
    dst_app_name = f"dst-{uuid.uuid4()}"
    src_app = None
    dst_app = None

    try:
        src_db, src_app = inicializar_cliente(args.source_credentials, src_app_name)
        dst_db, dst_app = inicializar_cliente(args.target_credentials, dst_app_name)

        print("🚚 Iniciando migración de Firestore")
        print(f"   Origen:  {args.source_credentials}")
        print(f"   Destino: {args.target_credentials}")
        if args.dry_run:
            print("   Modo:    DRY-RUN (sin escritura)")
        print("   Colecciones:", ", ".join(args.collections))
        print("-" * 60)

        total_global = 0
        for coleccion in args.collections:
            try:
                total = copiar_coleccion(
                    src_db,
                    dst_db,
                    coleccion,
                    dry_run=args.dry_run,
                )
                total_global += total
                print(f"✅ {coleccion}: {total} documento(s) copiado(s)")
            except Exception as exc:
                print(f"❌ Error migrando '{coleccion}': {exc}")

        print("-" * 60)
        if args.dry_run:
            print(f"🧪 Dry-run finalizado. Documentos detectados: {total_global}")
        else:
            print(f"🎉 Migración finalizada. Total de documentos copiados: {total_global}")
        return 0
    finally:
        if src_app is not None:
            firebase_admin.delete_app(src_app)
        if dst_app is not None:
            firebase_admin.delete_app(dst_app)


if __name__ == "__main__":
    raise SystemExit(main())
