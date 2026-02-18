import os
from typing import Optional

try:
    import firebase_admin
    from firebase_admin import credentials, firestore
except ImportError:
    firebase_admin = None
    credentials = None
    firestore = None


DEFAULT_CREDENTIALS_PATH = "claves.json"


def obtener_ruta_credenciales(
    env_var: str = "FIREBASE_CREDENTIALS",
    default_path: str = DEFAULT_CREDENTIALS_PATH,
) -> str:
    """Devuelve la ruta de credenciales desde variable de entorno o valor por defecto."""
    return os.getenv(env_var, default_path)


def inicializar_firestore(
    credentials_path: Optional[str] = None,
    verbose: bool = True,
):
    """
    Inicializa cliente de Firestore usando la clave configurada.

    Prioridad de inicialización:
    1) argumento credentials_path
    2) variable de entorno FIREBASE_CREDENTIALS
    3) archivo local 'claves.json'
    4) credenciales por defecto del entorno (ADC, ideal para Cloud Run/GCP)
    """
    if not firebase_admin:
        if verbose:
            print("⚠️ firebase_admin no está instalado. Se activa modo local.")
        return None

    ruta_clave = credentials_path or obtener_ruta_credenciales()
    env_ruta = str(os.getenv("FIREBASE_CREDENTIALS", "")).strip()
    ruta_explicita = credentials_path is not None or bool(env_ruta)

    # 1) Si hay ruta explícita o existe un claves.json local, intenta certificado.
    try_certificado = ruta_explicita or os.path.exists(ruta_clave)
    if try_certificado:
        if not os.path.exists(ruta_clave):
            if verbose:
                print(
                    f"⚠️ No existe el archivo de credenciales: {ruta_clave}. "
                    "Intento credenciales por defecto del entorno."
                )
        else:
            try:
                if not firebase_admin._apps:
                    cred = credentials.Certificate(ruta_clave)
                    firebase_admin.initialize_app(cred)
                cliente = firestore.client()
                if verbose:
                    print(f"✅ Conexión Firestore activa usando: {ruta_clave}")
                return cliente
            except Exception as exc:
                if verbose:
                    print(
                        f"⚠️ No se pudo conectar con Firestore usando archivo "
                        f"({ruta_clave}): {exc}"
                    )

    # 2) Fallback para Cloud Run/GCP: credenciales por defecto (ADC).
    try:
        if not firebase_admin._apps:
            firebase_admin.initialize_app()
        cliente = firestore.client()
        if verbose:
            print("✅ Conexión Firestore activa usando credenciales por defecto (ADC).")
        return cliente
    except Exception as exc:
        if verbose:
            print(f"⚠️ No se pudo conectar con Firestore por ADC: {exc}")
        return None

