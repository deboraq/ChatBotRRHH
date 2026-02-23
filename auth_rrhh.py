import json
import os
import re
import hashlib
import secrets
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from hmac import compare_digest

from werkzeug.security import check_password_hash, generate_password_hash


BOOL_TRUE = {"1", "true", "yes", "on", "si", "sí"}
BOOL_FALSE = {"0", "false", "no", "off"}
USERNAME_RE = re.compile(r"^[A-Za-z0-9._-]{3,64}$")
ROLE_RE = re.compile(r"^[a-z0-9._-]{2,64}$")
COMPANY_ID_RE = re.compile(r"^[a-z0-9._-]{2,64}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD_LENGTH = 6
PASSWORD_RESET_TTL_MINUTES = 60

# Permisos disponibles para roles operativos del panel.
PERM_CONVERSATIONS_VIEW = "conversaciones_ver"
PERM_CONVERSATIONS_MANAGE = "conversaciones_gestionar"
PERM_HISTORY_VIEW = "historial_ver"
PERM_USERS_MANAGE = "usuarios_gestionar"
PERM_ROLES_MANAGE = "roles_gestionar"

PERMISSIONS_CATALOG = {
    PERM_CONVERSATIONS_VIEW: "Ver conversaciones",
    PERM_CONVERSATIONS_MANAGE: "Tomar, responder y cerrar conversaciones",
    PERM_HISTORY_VIEW: "Ver historial completo",
    PERM_USERS_MANAGE: "Crear y editar usuarios",
    PERM_ROLES_MANAGE: "Crear y editar roles/permisos",
}

DEFAULT_ROLE_DEFINITIONS = {
    "admin": {
        "display_name": "Administrador",
        "permissions": list(PERMISSIONS_CATALOG.keys()),
    },
    "rrhh": {
        "display_name": "Agente de atención",
        "permissions": [
            PERM_CONVERSATIONS_VIEW,
            PERM_CONVERSATIONS_MANAGE,
            PERM_HISTORY_VIEW,
        ],
    },
}


def _parse_bool_mode(value, default="auto"):
    raw = str(value or "").strip().lower()
    if not raw:
        return default
    return raw


def _normalize_role(role, default="rrhh"):
    raw = str(role or default).strip().lower()
    return raw or default


def _normalize_permissions(permissions):
    if permissions is None:
        return None
    if not isinstance(permissions, list):
        return []
    valid = []
    seen = set()
    for perm in permissions:
        key = str(perm or "").strip().lower()
        if key in PERMISSIONS_CATALOG and key not in seen:
            valid.append(key)
            seen.add(key)
    return valid


def _normalize_company_id(value):
    raw = str(value or "").strip().lower()
    if not raw:
        return ""
    if COMPANY_ID_RE.fullmatch(raw):
        return raw
    raw = re.sub(r"\s+", "-", raw)
    raw = re.sub(r"[^a-z0-9._-]", "", raw)
    if not COMPANY_ID_RE.fullmatch(raw):
        return ""
    return raw


def _normalize_email(value):
    raw = str(value or "").strip().lower()
    if not raw:
        return ""
    if len(raw) > 254:
        return ""
    if not EMAIL_RE.fullmatch(raw):
        return ""
    return raw


def _normalize_text(value, max_len=160):
    raw = str(value or "").strip()
    if not raw:
        return ""
    return raw[:max_len]


def _normalize_assignments(assignments):
    if assignments is None:
        return []
    if not isinstance(assignments, list):
        return []

    normalized = []
    seen = set()
    for item in assignments:
        company_id = ""
        branch = ""
        if isinstance(item, dict):
            company_id = _normalize_company_id(item.get("company_id"))
            branch = str(item.get("branch") or "").strip()
        elif isinstance(item, str):
            token = str(item or "").strip()
            if ":" in token:
                left, right = token.split(":", 1)
                company_id = _normalize_company_id(left)
                branch = str(right or "").strip()
            else:
                company_id = _normalize_company_id(token)
                branch = ""
        if not company_id:
            continue
        key = f"{company_id}|{branch.lower()}"
        if key in seen:
            continue
        normalized.append({"company_id": company_id, "branch": branch})
        seen.add(key)
    return normalized


def assignment_matches_company(assignments, company_id):
    company_key = _normalize_company_id(company_id)
    if not company_key:
        return False
    items = _normalize_assignments(assignments)
    if not items:
        return True
    return any(item.get("company_id") == company_key for item in items)


def users_file_path():
    path = str(os.getenv("RRHH_USERS_FILE", "rrhh_users.json")).strip()
    return path or "rrhh_users.json"


def roles_file_path():
    path = str(os.getenv("RRHH_ROLES_FILE", "rrhh_roles.json")).strip()
    return path or "rrhh_roles.json"


def all_permissions():
    return list(PERMISSIONS_CATALOG.keys())


def permissions_catalog():
    return [
        {"key": key, "label": label}
        for key, label in PERMISSIONS_CATALOG.items()
    ]


def _normalize_user_entry(entry):
    if not isinstance(entry, dict):
        return None

    username = str(entry.get("username") or "").strip()
    if not username:
        return None

    password = str(entry.get("password") or "")
    password_hash = str(entry.get("password_hash") or "")
    if not password and not password_hash:
        return None

    legacy_companies = entry.get("companies")
    if not isinstance(legacy_companies, list):
        legacy_companies = []
    legacy_assignments = [{"company_id": value, "branch": ""} for value in legacy_companies]
    assignments = _normalize_assignments(entry.get("assignments"))
    if not assignments and legacy_assignments:
        assignments = _normalize_assignments(legacy_assignments)

    email = _normalize_email(entry.get("email"))
    phone = _normalize_text(entry.get("phone"), max_len=60)
    area = _normalize_text(entry.get("area"), max_len=120)

    return {
        "username": username,
        "display_name": str(entry.get("display_name") or username),
        "role": _normalize_role(entry.get("role"), default="rrhh"),
        "password": password,
        "password_hash": password_hash,
        "assignments": assignments,
        "email": email,
        "phone": phone,
        "area": area,
    }


def _normalize_role_entry(entry):
    if not isinstance(entry, dict):
        return None
    name = _normalize_role(entry.get("name"), default="")
    if not name or not ROLE_RE.fullmatch(name):
        return None
    permissions = _normalize_permissions(entry.get("permissions"))
    if permissions is None:
        permissions = []
    return {
        "name": name,
        "display_name": str(entry.get("display_name") or name).strip() or name,
        "permissions": permissions,
    }


def _read_json(path):
    if not path or not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


def _write_json(path, payload):
    try:
        abs_path = os.path.abspath(path)
        base_dir = os.path.dirname(abs_path)
        if base_dir and not os.path.exists(base_dir):
            os.makedirs(base_dir, exist_ok=True)
        with open(abs_path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
        return True
    except Exception:
        return False


def _load_users_raw_entries(path):
    data = _read_json(path)
    if data is None:
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


def _load_roles_raw_entries(path):
    data = _read_json(path)
    if data is None:
        return []

    if isinstance(data, dict):
        entries = data.get("roles", [])
    elif isinstance(data, list):
        entries = data
    else:
        entries = []
    if not isinstance(entries, list):
        return []
    return [item for item in entries if isinstance(item, dict)]


def _write_users_raw_entries(path, entries):
    return _write_json(path, {"users": entries})


def _write_roles_raw_entries(path, entries):
    return _write_json(path, {"roles": entries})


def _load_users_from_file(path):
    users = []
    for item in _load_users_raw_entries(path):
        normalized = _normalize_user_entry(item)
        if normalized:
            users.append(normalized)
    return users


def _load_admin_user_from_env():
    username = str(os.getenv("RRHH_ADMIN_USER", "")).strip()
    if not username:
        return []
    password = str(os.getenv("RRHH_ADMIN_PASSWORD", ""))
    password_hash = str(os.getenv("RRHH_ADMIN_PASSWORD_HASH", ""))
    raw_companies = str(os.getenv("RRHH_ADMIN_COMPANIES", "")).strip()
    assignments = []
    if raw_companies:
        assignments = [
            {"company_id": part.strip(), "branch": ""}
            for part in raw_companies.split(",")
            if str(part or "").strip()
        ]

    entry = _normalize_user_entry(
        {
            "username": username,
            "display_name": os.getenv("RRHH_ADMIN_DISPLAY_NAME", username),
            "role": os.getenv("RRHH_ADMIN_ROLE", "admin"),
            "password": password,
            "password_hash": password_hash,
            "assignments": assignments,
            "email": os.getenv("RRHH_ADMIN_EMAIL", ""),
            "phone": os.getenv("RRHH_ADMIN_PHONE", ""),
            "area": os.getenv("RRHH_ADMIN_AREA", ""),
        }
    )
    return [entry] if entry else []


def _build_roles_map(role_entries):
    roles = {}
    for name, payload in deepcopy(DEFAULT_ROLE_DEFINITIONS).items():
        roles[name] = {
            "name": name,
            "display_name": str(payload.get("display_name") or name),
            "permissions": _normalize_permissions(payload.get("permissions")) or [],
        }
    for item in role_entries:
        normalized = _normalize_role_entry(item)
        if not normalized:
            continue
        if normalized["name"] == "rrhh" and normalized.get("display_name", "").strip().lower() == "agente rrhh":
            normalized["display_name"] = "Agente de atención"
        roles[normalized["name"]] = normalized
    return roles


def _public_user_payload(entry, fallback_username=""):
    username = str(entry.get("username") or fallback_username).strip()
    role = _normalize_role(entry.get("role"), default="rrhh")
    return {
        "username": username,
        "display_name": str(entry.get("display_name") or username),
        "role": role,
        "permissions": role_permissions(role),
        "assignments": _normalize_assignments(entry.get("assignments")),
        "email": _normalize_email(entry.get("email")),
        "phone": _normalize_text(entry.get("phone"), max_len=60),
        "area": _normalize_text(entry.get("area"), max_len=120),
    }


def _build_users_from_raw_entries(raw_entries):
    users = []
    for item in raw_entries:
        normalized = _normalize_user_entry(item)
        if normalized:
            users.append(normalized)
    return users


def _find_raw_user_index(raw_entries, username_key):
    key = str(username_key or "").strip().lower()
    if not key:
        return -1
    for idx, item in enumerate(raw_entries):
        current_key = str(item.get("username") or "").strip().lower()
        if current_key == key:
            return idx
    return -1


def _parse_iso_datetime(raw):
    value = str(raw or "").strip()
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _password_reset_secret():
    return str(os.getenv("CHATBOT_WEB_SECRET", "dev-chatbot-secret")).strip() or "dev-chatbot-secret"


def _hash_reset_token(token):
    payload = f"{_password_reset_secret()}::{str(token or '').strip()}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _clear_password_reset_fields(entry):
    if not isinstance(entry, dict):
        return
    entry.pop("password_reset_token_hash", None)
    entry.pop("password_reset_expires_at", None)
    entry.pop("password_reset_requested_at", None)
    entry.pop("password_reset_requested_by", None)


def _normalize_password_reset_ttl(ttl_minutes):
    try:
        ttl = int(str(ttl_minutes or PASSWORD_RESET_TTL_MINUTES))
    except Exception:
        ttl = PASSWORD_RESET_TTL_MINUTES
    return max(5, min(ttl, 24 * 60))


def get_roles_map(path=None):
    source = path or roles_file_path()
    return _build_roles_map(_load_roles_raw_entries(source))


def list_roles(path=None):
    roles = []
    for role in get_roles_map(path).values():
        roles.append(
            {
                "name": role["name"],
                "display_name": role.get("display_name") or role["name"],
                "permissions": list(role.get("permissions") or []),
            }
        )
    roles.sort(key=lambda item: item["name"])
    return roles


def available_roles(path=None):
    return sorted(get_roles_map(path).keys())


def role_permissions(role, path=None):
    role_key = _normalize_role(role, default="")
    roles = get_roles_map(path)
    payload = roles.get(role_key)
    if payload is None:
        return []
    return list(payload.get("permissions") or [])


def role_has_permission(role, permission, path=None, roles_map=None):
    perm = str(permission or "").strip().lower()
    if perm not in PERMISSIONS_CATALOG:
        return False
    role_key = _normalize_role(role, default="")
    roles = roles_map if roles_map is not None else get_roles_map(path)
    payload = roles.get(role_key)
    if payload is None:
        return False
    return perm in (payload.get("permissions") or [])


def _merge_user_entries(file_entries, env_entries):
    merged = {}
    for entry in file_entries + env_entries:
        username = str(entry.get("username") or "").strip()
        if not username:
            continue
        key = username.lower()
        merged[key] = {
            "username": username,
            "role": _normalize_role(entry.get("role"), default="rrhh"),
        }
    return list(merged.values())


def _validate_management_access(user_entries, roles_map):
    if not user_entries:
        return True, ""
    needed = [PERM_USERS_MANAGE, PERM_ROLES_MANAGE]
    for perm in needed:
        ok = any(
            role_has_permission(entry.get("role"), perm, roles_map=roles_map)
            for entry in user_entries
        )
        if not ok:
            return False, f"Debe quedar al menos un usuario con permiso '{perm}'."
    return True, ""


def get_users():
    users = {}
    for entry in _load_users_from_file(users_file_path()) + _load_admin_user_from_env():
        users[entry["username"].strip().lower()] = entry
    return users


def user_has_company_access(username, company_id):
    key = str(username or "").strip().lower()
    if not key:
        return False
    entry = get_users().get(key)
    if not entry:
        return False
    return assignment_matches_company(entry.get("assignments"), company_id)


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

    return (
        True,
        {
            "username": entry["username"],
            "display_name": entry.get("display_name") or entry["username"],
            "role": _normalize_role(entry.get("role"), default="rrhh"),
            "assignments": _normalize_assignments(entry.get("assignments")),
            "email": _normalize_email(entry.get("email")),
            "phone": _normalize_text(entry.get("phone"), max_len=60),
            "area": _normalize_text(entry.get("area"), max_len=120),
        },
        "",
    )


def list_file_users(path=None):
    source = path or users_file_path()
    users = _load_users_from_file(source)
    rows = []
    for entry in users:
        rows.append(_public_user_payload(entry, fallback_username=entry.get("username")))
    rows.sort(key=lambda row: row["username"].lower())
    return rows


def create_role(name, display_name="", permissions=None, path=None):
    role_name = _normalize_role(name, default="")
    if not role_name or not ROLE_RE.fullmatch(role_name):
        return (
            False,
            None,
            "Nombre de rol inválido. Usá 2-64 caracteres: minúsculas, números, punto, guion o guion bajo.",
        )

    perms = _normalize_permissions(permissions)
    if perms is None:
        perms = []
    if not perms:
        return False, None, "El rol debe tener al menos un permiso."

    roles_map = get_roles_map(path)
    if role_name in roles_map:
        return False, None, "Ese rol ya existe."

    target_path = path or roles_file_path()
    raw_entries = _load_roles_raw_entries(target_path)
    raw_entries.append(
        {
            "name": role_name,
            "display_name": str(display_name or role_name).strip() or role_name,
            "permissions": perms,
        }
    )

    prospective_roles = _build_roles_map(raw_entries)
    user_entries = _merge_user_entries(_load_users_from_file(users_file_path()), _load_admin_user_from_env())
    ok_access, error = _validate_management_access(user_entries, prospective_roles)
    if not ok_access:
        return False, None, error

    if not _write_roles_raw_entries(target_path, raw_entries):
        return False, None, "No pude guardar el rol en el archivo de roles."

    return (
        True,
        {
            "name": role_name,
            "display_name": str(display_name or role_name).strip() or role_name,
            "permissions": perms,
        },
        "",
    )


def update_role(name, display_name=None, permissions=None, path=None):
    role_name = _normalize_role(name, default="")
    if not role_name:
        return False, None, "Nombre de rol requerido."
    if not ROLE_RE.fullmatch(role_name):
        return False, None, "Nombre de rol inválido."

    target_path = path or roles_file_path()
    raw_entries = _load_roles_raw_entries(target_path)
    current_roles = _build_roles_map(raw_entries)
    current = current_roles.get(role_name)
    if current is None:
        return False, None, "Rol no encontrado."

    next_display = (
        str(display_name).strip()
        if display_name is not None
        else str(current.get("display_name") or role_name)
    )
    if not next_display:
        next_display = role_name

    next_permissions = _normalize_permissions(permissions)
    if next_permissions is None:
        next_permissions = list(current.get("permissions") or [])
    if not next_permissions:
        return False, None, "El rol debe tener al menos un permiso."

    updated = False
    new_raw_entries = []
    for item in raw_entries:
        normalized = _normalize_role(item.get("name"), default="")
        if normalized == role_name:
            clone = dict(item)
            clone["name"] = role_name
            clone["display_name"] = next_display
            clone["permissions"] = next_permissions
            new_raw_entries.append(clone)
            updated = True
        else:
            new_raw_entries.append(item)

    if not updated:
        # Si era un rol por defecto sin override, crea el override.
        new_raw_entries.append(
            {
                "name": role_name,
                "display_name": next_display,
                "permissions": next_permissions,
            }
        )

    prospective_roles = _build_roles_map(new_raw_entries)
    user_entries = _merge_user_entries(_load_users_from_file(users_file_path()), _load_admin_user_from_env())
    ok_access, error = _validate_management_access(user_entries, prospective_roles)
    if not ok_access:
        return False, None, error

    if not _write_roles_raw_entries(target_path, new_raw_entries):
        return False, None, "No pude actualizar el rol en el archivo de roles."

    return (
        True,
        {
            "name": role_name,
            "display_name": next_display,
            "permissions": next_permissions,
        },
        "",
    )


def create_user(
    username,
    password,
    display_name="",
    role="rrhh",
    created_by="",
    assignments=None,
    email="",
    phone="",
    area="",
    path=None,
):
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

    role_clean = _normalize_role(role, default="rrhh")
    roles = get_roles_map()
    if role_clean not in roles:
        return False, None, "Rol inválido. Crealo primero desde la sección de roles."
    normalized_assignments = _normalize_assignments(assignments)
    if isinstance(assignments, list) and assignments and not normalized_assignments:
        return False, None, "Asignaciones inválidas. Usá empresa y sucursal válidas."

    email_raw = str(email or "").strip()
    email_clean = _normalize_email(email_raw)
    if email_raw and not email_clean:
        return False, None, "Email inválido."
    phone_clean = _normalize_text(phone, max_len=60)
    area_clean = _normalize_text(area, max_len=120)

    key = username_clean.lower()
    if key in get_users():
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
        "assignments": normalized_assignments,
        "email": email_clean,
        "phone": phone_clean,
        "area": area_clean,
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
        _public_user_payload(entry, fallback_username=username_clean),
        "",
    )


def update_user_profile(
    username,
    role=None,
    assignments=None,
    display_name=None,
    email=None,
    phone=None,
    area=None,
    updated_by="",
    path=None,
):
    username_clean = str(username or "").strip()
    if not username_clean:
        return False, None, "Usuario requerido."

    env_users = _load_admin_user_from_env()
    env_usernames = {str(item.get("username") or "").strip().lower() for item in env_users}
    key = username_clean.lower()
    if key in env_usernames:
        return (
            False,
            None,
            "Ese usuario se gestiona por variables de entorno y no puede editarse desde el panel.",
        )

    target_path = path or users_file_path()
    raw_entries = _load_users_raw_entries(target_path)
    target_idx = _find_raw_user_index(raw_entries, key)
    if target_idx < 0:
        return False, None, "Usuario no encontrado en archivo de usuarios."

    roles = get_roles_map()
    updated_entry = dict(raw_entries[target_idx])

    if role is not None:
        role_clean = _normalize_role(role, default="")
        if role_clean not in roles:
            return False, None, "Rol inválido. Crealo primero desde la sección de roles."
        updated_entry["role"] = role_clean

    if assignments is not None:
        normalized_assignments = _normalize_assignments(assignments)
        if isinstance(assignments, list) and assignments and not normalized_assignments:
            return False, None, "Asignaciones inválidas. Verificá empresa/sucursal."
        updated_entry["assignments"] = normalized_assignments

    if display_name is not None:
        updated_entry["display_name"] = str(display_name or "").strip() or username_clean

    if email is not None:
        email_raw = str(email or "").strip()
        email_clean = _normalize_email(email_raw)
        if email_raw and not email_clean:
            return False, None, "Email inválido."
        updated_entry["email"] = email_clean

    if phone is not None:
        updated_entry["phone"] = _normalize_text(phone, max_len=60)

    if area is not None:
        updated_entry["area"] = _normalize_text(area, max_len=120)

    updated_entry["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    updated_by_clean = str(updated_by or "").strip()
    if updated_by_clean:
        updated_entry["updated_by"] = updated_by_clean

    new_raw_entries = list(raw_entries)
    new_raw_entries[target_idx] = updated_entry

    prospective_file_users = _build_users_from_raw_entries(new_raw_entries)
    merged_users = _merge_user_entries(prospective_file_users, env_users)
    ok_access, error = _validate_management_access(merged_users, roles)
    if not ok_access:
        return False, None, error

    if not _write_users_raw_entries(target_path, new_raw_entries):
        return False, None, "No pude actualizar el usuario en el archivo."

    return True, _public_user_payload(updated_entry, fallback_username=username_clean), ""


def update_user_role(username, role, updated_by="", path=None):
    return update_user_profile(
        username=username,
        role=role,
        updated_by=updated_by,
        path=path,
    )


def update_user_assignments(username, assignments=None, updated_by="", path=None):
    return update_user_profile(
        username=username,
        assignments=assignments,
        updated_by=updated_by,
        path=path,
    )


def create_password_reset_token(username, ttl_minutes=PASSWORD_RESET_TTL_MINUTES, requested_by="", path=None):
    username_clean = str(username or "").strip()
    if not username_clean:
        return False, None, "Usuario requerido."

    env_users = _load_admin_user_from_env()
    env_usernames = {str(item.get("username") or "").strip().lower() for item in env_users}
    key = username_clean.lower()
    if key in env_usernames:
        return (
            False,
            None,
            "Ese usuario se gestiona por variables de entorno y no puede restablecerse desde el panel.",
        )

    target_path = path or users_file_path()
    raw_entries = _load_users_raw_entries(target_path)
    target_idx = _find_raw_user_index(raw_entries, key)
    if target_idx < 0:
        return False, None, "Usuario no encontrado en archivo de usuarios."

    entry = dict(raw_entries[target_idx])
    email = _normalize_email(entry.get("email"))
    if not email:
        return False, None, "El usuario no tiene email cargado."

    ttl = _normalize_password_reset_ttl(ttl_minutes)

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=ttl)
    token = secrets.token_urlsafe(32)
    entry["password_reset_token_hash"] = _hash_reset_token(token)
    entry["password_reset_expires_at"] = expires_at.isoformat(timespec="seconds")
    entry["password_reset_requested_at"] = now.isoformat(timespec="seconds")
    requested_by_clean = str(requested_by or "").strip()
    if requested_by_clean:
        entry["password_reset_requested_by"] = requested_by_clean

    new_raw_entries = list(raw_entries)
    new_raw_entries[target_idx] = entry
    if not _write_users_raw_entries(target_path, new_raw_entries):
        return False, None, "No pude guardar el token de restablecimiento."

    return (
        True,
        {
            "username": str(entry.get("username") or username_clean),
            "display_name": str(entry.get("display_name") or username_clean),
            "email": email,
            "token": token,
            "expires_at": expires_at.isoformat(timespec="seconds"),
        },
        "",
    )


def create_password_reset_token_for_identity(
    username,
    email,
    ttl_minutes=PASSWORD_RESET_TTL_MINUTES,
    requested_by="",
    path=None,
):
    username_clean = str(username or "").strip()
    if not username_clean:
        return False, None, "Usuario requerido."

    email_clean = _normalize_email(email)
    if not email_clean:
        return False, None, "Email inválido."

    env_users = _load_admin_user_from_env()
    env_usernames = {str(item.get("username") or "").strip().lower() for item in env_users}
    key = username_clean.lower()
    if key in env_usernames:
        return (
            False,
            None,
            "Ese usuario se gestiona por variables de entorno y no puede restablecerse automáticamente.",
        )

    target_path = path or users_file_path()
    raw_entries = _load_users_raw_entries(target_path)
    target_idx = _find_raw_user_index(raw_entries, key)
    if target_idx < 0:
        return False, None, "Usuario o email inválido."

    entry = dict(raw_entries[target_idx])
    user_email = _normalize_email(entry.get("email"))
    if not user_email or not compare_digest(user_email, email_clean):
        return False, None, "Usuario o email inválido."

    ttl = _normalize_password_reset_ttl(ttl_minutes)
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=ttl)
    token = secrets.token_urlsafe(32)
    entry["password_reset_token_hash"] = _hash_reset_token(token)
    entry["password_reset_expires_at"] = expires_at.isoformat(timespec="seconds")
    entry["password_reset_requested_at"] = now.isoformat(timespec="seconds")
    requested_by_clean = str(requested_by or "").strip()
    if requested_by_clean:
        entry["password_reset_requested_by"] = requested_by_clean

    new_raw_entries = list(raw_entries)
    new_raw_entries[target_idx] = entry
    if not _write_users_raw_entries(target_path, new_raw_entries):
        return False, None, "No pude guardar el token de restablecimiento."

    return (
        True,
        {
            "username": str(entry.get("username") or username_clean),
            "display_name": str(entry.get("display_name") or username_clean),
            "email": user_email,
            "token": token,
            "expires_at": expires_at.isoformat(timespec="seconds"),
        },
        "",
    )


def reset_password_with_token(token, new_password, path=None):
    raw_token = str(token or "").strip()
    if len(raw_token) < 16:
        return False, None, "Token inválido o expirado."

    password_raw = str(new_password or "")
    if len(password_raw) < MIN_PASSWORD_LENGTH:
        return (
            False,
            None,
            f"La contraseña debe tener al menos {MIN_PASSWORD_LENGTH} caracteres.",
        )

    target_path = path or users_file_path()
    raw_entries = _load_users_raw_entries(target_path)
    if not raw_entries:
        return False, None, "Token inválido o expirado."

    token_hash = _hash_reset_token(raw_token)
    now = datetime.now(timezone.utc)
    target_idx = -1
    target_entry = None
    expired_idx = -1
    changed = False
    for idx, item in enumerate(raw_entries):
        current_hash = str(item.get("password_reset_token_hash") or "").strip()
        if not current_hash or current_hash != token_hash:
            continue
        expires_at = _parse_iso_datetime(item.get("password_reset_expires_at"))
        if expires_at is None or expires_at < now:
            expired_idx = idx
            continue
        target_idx = idx
        target_entry = dict(item)
        break

    if target_idx < 0:
        if expired_idx >= 0:
            expired_entry = dict(raw_entries[expired_idx])
            _clear_password_reset_fields(expired_entry)
            raw_entries[expired_idx] = expired_entry
            changed = True
        if changed:
            _write_users_raw_entries(target_path, raw_entries)
        return False, None, "Token inválido o expirado."

    target_entry["password_hash"] = generate_password_hash(password_raw)
    target_entry.pop("password", None)
    _clear_password_reset_fields(target_entry)
    target_entry["updated_at"] = now.isoformat(timespec="seconds")
    raw_entries[target_idx] = target_entry

    if not _write_users_raw_entries(target_path, raw_entries):
        return False, None, "No pude actualizar la contraseña."

    return True, _public_user_payload(target_entry), ""


def delete_user(username, deleted_by="", path=None):
    username_clean = str(username or "").strip()
    if not username_clean:
        return False, "Usuario requerido."

    env_users = _load_admin_user_from_env()
    env_usernames = {str(item.get("username") or "").strip().lower() for item in env_users}
    key = username_clean.lower()
    if key in env_usernames:
        return (
            False,
            "Ese usuario se gestiona por variables de entorno y no puede eliminarse desde el panel.",
        )

    target_path = path or users_file_path()
    raw_entries = _load_users_raw_entries(target_path)
    kept = []
    removed = None
    for item in raw_entries:
        current_key = str(item.get("username") or "").strip().lower()
        if current_key == key and removed is None:
            removed = item
            continue
        kept.append(item)
    if removed is None:
        return False, "Usuario no encontrado en archivo de usuarios."

    prospective_file_users = _load_users_from_file(target_path)
    prospective_file_users = [
        item
        for item in prospective_file_users
        if str(item.get("username") or "").strip().lower() != key
    ]
    merged_users = _merge_user_entries(prospective_file_users, env_users)
    ok_access, error = _validate_management_access(merged_users, get_roles_map())
    if not ok_access:
        return False, error

    if not _write_users_raw_entries(target_path, kept):
        return False, "No pude eliminar el usuario del archivo."

    return True, ""


def delete_role(name, path=None):
    role_name = _normalize_role(name, default="")
    if not role_name:
        return False, "Nombre de rol requerido."
    if role_name in DEFAULT_ROLE_DEFINITIONS:
        return False, "No se pueden eliminar los roles base del sistema."

    target_path = path or roles_file_path()
    raw_entries = _load_roles_raw_entries(target_path)
    found = False
    kept = []
    for item in raw_entries:
        item_name = _normalize_role(item.get("name"), default="")
        if item_name == role_name and not found:
            found = True
            continue
        kept.append(item)
    if not found:
        return False, "Rol no encontrado en archivo de roles."

    # Impide borrar roles que estén asignados a usuarios actuales.
    for user in get_users().values():
        if _normalize_role(user.get("role"), default="rrhh") == role_name:
            return False, "No podés eliminar un rol asignado a usuarios."

    if not _write_roles_raw_entries(target_path, kept):
        return False, "No pude eliminar el rol del archivo."
    return True, ""


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Genera hash de contraseña para RRHH.")
    parser.add_argument("--hash", dest="password", required=True, help="Contraseña a hashear")
    args = parser.parse_args()
    print(generate_password_hash(args.password))
