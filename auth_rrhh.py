import json
import os
from hmac import compare_digest

from werkzeug.security import check_password_hash, generate_password_hash


BOOL_TRUE = {"1", "true", "yes", "on", "si", "sí"}
BOOL_FALSE = {"0", "false", "no", "off"}


def _parse_bool_mode(value, default="auto"):
    raw = str(value or "").strip().lower()
    if not raw:
        return default
    return raw


def _normalize_entry(entry):
    if not isinstance(entry, dict):
        return None

    username = str(entry.get("username") or "").strip()
    if not username:
        return None

    password = str(entry.get("password") or "")
    password_hash = str(entry.get("password_hash") or "")
    if not password and not password_hash:
        return None

    return {
        "username": username,
        "display_name": str(entry.get("display_name") or username),
        "role": str(entry.get("role") or "rrhh"),
        "password": password,
        "password_hash": password_hash,
    }


def _load_users_from_file(path):
    if not path or not os.path.exists(path):
        return []

    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        return []

    if isinstance(data, dict):
        entries = data.get("users", [])
    elif isinstance(data, list):
        entries = data
    else:
        entries = []

    users = []
    for item in entries:
        normalized = _normalize_entry(item)
        if normalized:
            users.append(normalized)
    return users


def _load_admin_user_from_env():
    username = str(os.getenv("RRHH_ADMIN_USER", "")).strip()
    if not username:
        return []

    password = str(os.getenv("RRHH_ADMIN_PASSWORD", ""))
    password_hash = str(os.getenv("RRHH_ADMIN_PASSWORD_HASH", ""))
    entry = _normalize_entry(
        {
            "username": username,
            "display_name": os.getenv("RRHH_ADMIN_DISPLAY_NAME", username),
            "role": os.getenv("RRHH_ADMIN_ROLE", "rrhh"),
            "password": password,
            "password_hash": password_hash,
        }
    )
    return [entry] if entry else []


def get_users():
    users_file = os.getenv("RRHH_USERS_FILE", "rrhh_users.json")
    users = {}

    for entry in _load_users_from_file(users_file) + _load_admin_user_from_env():
        users[entry["username"].strip().lower()] = entry

    return users


def is_auth_enabled():
    mode = _parse_bool_mode(os.getenv("RRHH_AUTH_ENABLED", "auto"))
    users = get_users()

    if mode in BOOL_TRUE:
        return bool(users)
    if mode in BOOL_FALSE:
        return False
    return bool(users)


def _check_password(entry, password):
    raw_password = str(password or "")
    password_hash = entry.get("password_hash") or ""
    password_plain = entry.get("password") or ""

    if password_hash:
        try:
            return check_password_hash(password_hash, raw_password)
        except Exception:
            return False
    return compare_digest(password_plain, raw_password)


def authenticate(username, password):
    users = get_users()
    key = str(username or "").strip().lower()
    if not key:
        return False, None, "Usuario y contraseña requeridos."

    entry = users.get(key)
    if not entry:
        return False, None, "Usuario o contraseña inválidos."

    if not _check_password(entry, password):
        return False, None, "Usuario o contraseña inválidos."

    user_payload = {
        "username": entry["username"],
        "display_name": entry.get("display_name") or entry["username"],
        "role": entry.get("role") or "rrhh",
    }
    return True, user_payload, ""


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Genera hash de contraseña para RRHH.")
    parser.add_argument("--hash", dest="password", required=True, help="Contraseña a hashear")
    args = parser.parse_args()
    print(generate_password_hash(args.password))
