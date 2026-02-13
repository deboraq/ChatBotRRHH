import json
import os
import re
from hmac import compare_digest
from datetime import datetime, timezone

from werkzeug.security import check_password_hash, generate_password_hash


BOOL_TRUE = {"1", "true", "yes", "on", "si", "sí"}
BOOL_FALSE = {"0", "false", "no", "off"}
VALID_ROLES = {"rrhh", "admin"}
USERNAME_RE = re.compile(r"^[A-Za-z0-9._-]{3,64}$")
MIN_PASSWORD_LENGTH = 6


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


def users_file_path():
    path = str(os.getenv("RRHH_USERS_FILE", "rrhh_users.json")).strip()
    return path or "rrhh_users.json"


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
            # El admin por entorno queda con rol admin por defecto.
            "role": os.getenv("RRHH_ADMIN_ROLE", "admin"),
            "password": password,
            "password_hash": password_hash,
        }
    )
    return [entry] if entry else []


def get_users():
    users_file = users_file_path()
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


def _load_users_raw_entries(path):
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

    if not isinstance(entries, list):
        return []
    return [item for item in entries if isinstance(item, dict)]


def _write_users_raw_entries(path, entries):
    try:
        abs_path = os.path.abspath(path)
        base_dir = os.path.dirname(abs_path)
        if base_dir and not os.path.exists(base_dir):
            os.makedirs(base_dir, exist_ok=True)
        payload = {"users": entries}
        with open(abs_path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
        return True
    except Exception:
        return False


def list_file_users(path=None):
    source = path or users_file_path()
    users = _load_users_from_file(source)
    rows = []
    for entry in users:
        rows.append(
            {
                "username": entry["username"],
                "display_name": entry.get("display_name") or entry["username"],
                "role": entry.get("role") or "rrhh",
            }
        )
    rows.sort(key=lambda row: row["username"].lower())
    return rows


def create_user(username, password, display_name="", role="rrhh", created_by="", path=None):
    username_clean = str(username or "").strip()
    if not USERNAME_RE.fullmatch(username_clean):
        return (
            False,
            None,
            "Usuario inválido. Usá 3-64 caracteres: letras, números, punto, guion o guion bajo.",
        )

    password_raw = str(password or "")
    if len(password_raw) < MIN_PASSWORD_LENGTH:
        return (
            False,
            None,
            f"La contraseña debe tener al menos {MIN_PASSWORD_LENGTH} caracteres.",
        )

    role_clean = str(role or "rrhh").strip().lower()
    if role_clean not in VALID_ROLES:
        return False, None, "Rol inválido. Valores permitidos: rrhh, admin."

    key = username_clean.lower()
    existing = get_users()
    if key in existing:
        return False, None, "Ese usuario ya existe."

    target_path = path or users_file_path()
    raw_entries = _load_users_raw_entries(target_path)
    for item in raw_entries:
        raw_user = str(item.get("username") or "").strip().lower()
        if raw_user == key:
            return False, None, "Ese usuario ya existe."

    entry = {
        "username": username_clean,
        "display_name": str(display_name or username_clean).strip() or username_clean,
        "role": role_clean,
        "password_hash": generate_password_hash(password_raw),
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    created_by_clean = str(created_by or "").strip()
    if created_by_clean:
        entry["created_by"] = created_by_clean

    raw_entries.append(entry)
    if not _write_users_raw_entries(target_path, raw_entries):
        return False, None, "No pude guardar el usuario en el archivo de usuarios."

    return (
        True,
        {
            "username": entry["username"],
            "display_name": entry["display_name"],
            "role": entry["role"],
        },
        "",
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Genera hash de contraseña para RRHH.")
    parser.add_argument("--hash", dest="password", required=True, help="Contraseña a hashear")
    args = parser.parse_args()
    print(generate_password_hash(args.password))
