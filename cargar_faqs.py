import argparse
import json
import os
from pathlib import Path

try:
    from firebase_config import inicializar_firestore as inicializar_firestore_central
except Exception:
    inicializar_firestore_central = None

DEFAULT_CREDENTIALS_PATH = "claves.json"

# 1. LISTADO ORIGINAL DE PREGUNTAS FRECUENTES (FAQS) PARA BACAR
FAQS_BACAR = [
    {
        "tema": "vacaciones",
        "respuesta": "Se deben solicitar con 15 dias de anticipacion a traves del portal Legajos.online.",
    },
    {
        "tema": "fraccionamiento",
        "respuesta": "Las vacaciones se pueden fraccionar en periodos minimos de 7 dias, con aval de tu responsable directo.",
    },
    {
        "tema": "recibo",
        "respuesta": "Los recibos de sueldo estan disponibles para firma digital el cuarto dia habil de cada mes en la plataforma habitual.",
    },
    {
        "tema": "aguinaldo",
        "respuesta": "El SAC se abona en dos cuotas: la primera con vencimiento el 30 de junio y la segunda el 18 de diciembre.",
    },
    {
        "tema": "obra social",
        "respuesta": "Para cambios o consultas sobre tu cobertura medica, debes enviar un correo a beneficios@bacar.com.ar.",
    },
    {
        "tema": "licencia examen",
        "respuesta": "Tenes derecho a 2 dias corridos por examen, hasta 20 dias anuales. Presenta el certificado al dia siguiente de rendir.",
    },
    {
        "tema": "ART",
        "respuesta": "En caso de accidente laboral, comunicate inmediatamente al 0800 de nuestra aseguradora y avisa a tu supervisor.",
    },
    {
        "tema": "uniforme",
        "respuesta": "La reposicion de uniformes se realiza cada 6 meses. Podes solicitar el tuyo en la oficina de suministros.",
    },
    {
        "tema": "adelanto",
        "respuesta": "Los pedidos de adelanto de sueldo se reciben hasta el dia 20 de cada mes y no deben superar el 30% del neto.",
    },
    {
        "tema": "nacimiento",
        "respuesta": "Por nacimiento de hijo, contas con 2 dias corridos de licencia paga (segun CCT). Recorda traer el acta de nacimiento.",
    },
    {
        "tema": "casamiento",
        "respuesta": "La licencia por matrimonio es de 10 dias corridos. Debes avisar con 30 dias de antelacion.",
    },
    {
        "tema": "capacitacion",
        "respuesta": "Podes ver los cursos disponibles en la intranet de Bacar, seccion 'Mi Desarrollo'.",
    },
]

PERFILES = {
    "bacar": {
        "descripcion": "FAQs internas historicas de Bacar",
        "faqs": FAQS_BACAR,
    },
    "camioneros_cordoba": {
        "descripcion": "Preguntero para empresa de caudales basado en CCT de Camioneros Cordoba",
        "json_path": "faqs_camioneros_cordoba_caudales.json",
    },
}


def obtener_ruta_credenciales(
    env_var="FIREBASE_CREDENTIALS",
    default_path=DEFAULT_CREDENTIALS_PATH,
):
    return os.getenv(env_var, default_path)


def normalizar_tema(tema):
    return str(tema).strip().lower().replace(" ", "_")


def conectar_firestore(credentials_path=None, verbose=True):
    if inicializar_firestore_central:
        db = inicializar_firestore_central(
            credentials_path=credentials_path,
            verbose=verbose,
        )
        if db:
            return db
        raise ConnectionError("No se pudo conectar con Firestore usando firebase_config.")

    try:
        import firebase_admin
        from firebase_admin import credentials, firestore
    except ModuleNotFoundError as error:
        raise ModuleNotFoundError(
            "No se encontro 'firebase_admin'. Instala dependencias o ejecuta con --dry-run."
        ) from error

    ruta_clave = credentials_path or obtener_ruta_credenciales()
    if not firebase_admin._apps:
        cred = credentials.Certificate(ruta_clave)
        firebase_admin.initialize_app(cred)
    return firestore.client()


def cargar_faqs_json(ruta_json):
    ruta = Path(ruta_json)
    if not ruta.exists():
        raise FileNotFoundError(f"No se encontro el archivo de FAQs: {ruta.resolve()}")

    with ruta.open(encoding="utf-8") as archivo:
        faqs = json.load(archivo)

    if not isinstance(faqs, list):
        raise ValueError("El archivo JSON debe contener una lista de FAQs.")

    return faqs


def validar_faqs(faqs):
    for idx, faq in enumerate(faqs, start=1):
        if not isinstance(faq, dict):
            raise ValueError(f"FAQ #{idx} invalida: debe ser un objeto JSON.")
        if "tema" not in faq or "respuesta" not in faq:
            raise ValueError(f"FAQ #{idx} invalida: requiere campos 'tema' y 'respuesta'.")


def cargar_datos(
    perfil,
    coleccion_nombre="faq_rrhh",
    dry_run=False,
    credentials_path=None,
):
    perfil_cfg = PERFILES[perfil]
    faqs = perfil_cfg.get("faqs")
    if faqs is None:
        faqs = cargar_faqs_json(perfil_cfg["json_path"])

    validar_faqs(faqs)

    print(f"Perfil seleccionado: {perfil} ({perfil_cfg['descripcion']})")
    print(f"Coleccion destino: {coleccion_nombre}")
    print(f"Total de FAQs: {len(faqs)}")

    if dry_run:
        print("\nModo DRY-RUN activado. Vista previa:")
        for faq in faqs[:5]:
            print(f"- {faq['tema']}: {faq['respuesta'][:80]}...")
        if len(faqs) > 5:
            print(f"... y {len(faqs) - 5} mas")
        return

    db = conectar_firestore(credentials_path=credentials_path, verbose=True)
    coleccion = db.collection(coleccion_nombre)
    print("\nSubiendo FAQs a Firestore...")

    for faq in faqs:
        # Usamos el tema normalizado como ID para evitar duplicados y diferencias de casing.
        doc_id = normalizar_tema(faq["tema"])
        payload = dict(faq)
        payload["tema"] = doc_id
        coleccion.document(doc_id).set(payload)
        print(f"Categoria cargada: {faq['tema']} (id: {doc_id})")

    print("\nExito: la base de FAQs quedo actualizada.")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Carga FAQs de RRHH en Firestore con perfiles reutilizables."
    )
    parser.add_argument(
        "--perfil",
        choices=sorted(PERFILES.keys()),
        default="bacar",
        help="Perfil de FAQs a cargar.",
    )
    parser.add_argument(
        "--coleccion",
        default="faq_rrhh",
        help="Nombre de la coleccion destino en Firestore.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Valida y muestra vista previa sin escribir en Firestore.",
    )
    parser.add_argument(
        "--credentials",
        help=(
            "Ruta al JSON de Firebase. Si no se informa, usa FIREBASE_CREDENTIALS "
            "o el archivo local claves.json."
        ),
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    try:
        cargar_datos(
            perfil=args.perfil,
            coleccion_nombre=args.coleccion,
            dry_run=args.dry_run,
            credentials_path=args.credentials,
        )
    except Exception as error:
        print(f"Error: {error}")