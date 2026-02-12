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

    Prioridad de ruta:
    1) argumento credentials_path
    2) variable de entorno FIREBASE_CREDENTIALS
    3) archivo local 'claves.json'
    """
    if not firebase_admin:
        if verbose:
            print("⚠️ firebase_admin no está instalado. Se activa modo local.")
        return None

    ruta_clave = credentials_path or obtener_ruta_credenciales()
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
            print(f"⚠️ No se pudo conectar con Firestore ({ruta_clave}): {exc}")
        return None

