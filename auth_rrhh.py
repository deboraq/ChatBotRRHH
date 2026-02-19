import json
import os
import re
from copy import deepcopy
from datetime import datetime, timezone
from hmac import compare_digest

from werkzeug.security import check_password_hash, generate_password_hash


BOOL_TRUE = {"1", "true", "yes", "on", "si", "sí"}
BOOL_FALSE = {"0", "false", "no", "off"}
USERNAME_RE = re.compile(r"^[A-Za-z0-9._-]{3,64}$")
ROLE_RE = re.compile(r"^[a-z0-9._-]{2,64}$")
COMPANY_ID_RE = re.compile(r"^[a-z0-9._-]{2,64}$")
MIN_PASSWORD_LENGTH = 6

# Permisos disponibles para roles de RRHH.
PERM_CONVERSATIONS_VIEW = "conversaciones_ver"
PERM_CONVERSATIONS_MANAGE = "conversaciones_gestionar"
PERM_HISTORY_VIEW = "historial_ver"
PERM_USERS_MANAGE = "usuarios_gestionar"
PERM_ROLES_MANAGE = "roles_gestionar"

PERMISSIONS_CATALOG = {
    PERM_CONVERSATIONS_VIEW: "Ver conversaciones RRHH",
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
        "display_name": "Agente RRHH",
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

    return {
        "username": username,
        "display_name": str(entry.get("display_name") or username),
        "role": _normalize_role(entry.get("role"), default="rrhh"),
        "password": password,
        "password_hash": password_hash,
        "assignments": assignments,
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
        roles[normalized["name"]] = normalized
    return roles


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
        },
        "",
    )


def list_file_users(path=None):
    source = path or users_file_path()
    users = _load_users_from_file(source)
    rows = []
    for entry in users:
        role = _normalize_role(entry.get("role"), default="rrhh")
        rows.append(
            {
                "username": entry["username"],
                "display_name": entry.get("display_name") or entry["username"],
                "role": role,
                "permissions": role_permissions(role),
                "assignments": _normalize_assignments(entry.get("assignments")),
            }
        )
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
            "permissions": role_permissions(entry["role"]),
            "assignments": _normalize_assignments(entry.get("assignments")),
        },
        "",
    )


def update_user_role(username, role, updated_by="", path=None):
    username_clean = str(username or "").strip()
    if not username_clean:
        return False, None, "Usuario requerido."

    role_clean = _normalize_role(role, default="")
    roles = get_roles_map()
    if role_clean not in roles:
        return False, None, "Rol inválido. Crealo primero desde la sección de roles."

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
    target_idx = -1
    for idx, item in enumerate(raw_entries):
        current_key = str(item.get("username") or "").strip().lower()
        if current_key == key:
            target_idx = idx
            break
    if target_idx < 0:
        return False, None, "Usuario no encontrado en archivo de usuarios."

    raw_entries[target_idx]["role"] = role_clean
    raw_entries[target_idx]["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    updated_by_clean = str(updated_by or "").strip()
    if updated_by_clean:
        raw_entries[target_idx]["updated_by"] = updated_by_clean

    file_users = _load_users_from_file(users_file_path())
    for idx, item in enumerate(file_users):
        if str(item.get("username") or "").strip().lower() == key:
            file_users[idx]["role"] = role_clean
            break
    merged_users = _merge_user_entries(file_users, env_users)
    ok_access, error = _validate_management_access(merged_users, roles)
    if not ok_access:
        return False, None, error

    if not _write_users_raw_entries(target_path, raw_entries):
        return False, None, "No pude actualizar el rol en el archivo de usuarios."

    item = raw_entries[target_idx]
    return (
        True,
        {
            "username": str(item.get("username") or username_clean),
            "display_name": str(item.get("display_name") or username_clean),
            "role": role_clean,
            "permissions": role_permissions(role_clean),
            "assignments": _normalize_assignments(item.get("assignments")),
        },
        "",
    )


def update_user_assignments(username, assignments=None, updated_by="", path=None):
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
    target_idx = -1
    for idx, item in enumerate(raw_entries):
        current_key = str(item.get("username") or "").strip().lower()
        if current_key == key:
            target_idx = idx
            break
    if target_idx < 0:
        return False, None, "Usuario no encontrado en archivo de usuarios."

    normalized_assignments = _normalize_assignments(assignments)
    if isinstance(assignments, list) and assignments and not normalized_assignments:
        return False, None, "Asignaciones inválidas. Verificá empresa/sucursal."

    raw_entries[target_idx]["assignments"] = normalized_assignments
    raw_entries[target_idx]["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    updated_by_clean = str(updated_by or "").strip()
    if updated_by_clean:
        raw_entries[target_idx]["updated_by"] = updated_by_clean

    if not _write_users_raw_entries(target_path, raw_entries):
        return False, None, "No pude actualizar asignaciones del usuario."

    item = raw_entries[target_idx]
    role_clean = _normalize_role(item.get("role"), default="rrhh")
    return (
        True,
        {
            "username": str(item.get("username") or username_clean),
            "display_name": str(item.get("display_name") or username_clean),
            "role": role_clean,
            "permissions": role_permissions(role_clean),
            "assignments": _normalize_assignments(item.get("assignments")),
        },
        "",
    )


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
