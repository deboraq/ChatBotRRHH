import os

# Cargar variables desde .env si existe python-dotenv (opcional)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import logging
import smtplib
import uuid
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from functools import wraps

from flask import Flask, g, jsonify, redirect, render_template, request, session, url_for

import app as chatbot
import auth_rrhh
import stats_service

# Activar envío por WhatsApp vía Twilio si hay credenciales
try:
    from twilio_whatsapp import register_twilio_sender
    register_twilio_sender()
except ImportError:
    pass

logger = logging.getLogger(__name__)
flask_app = Flask(__name__)
flask_app.config["SECRET_KEY"] = os.getenv("CHATBOT_WEB_SECRET", "dev-chatbot-secret")
# Firebase Hosting preserves the "__session" cookie across rewrites to Cloud Run.
flask_app.config["SESSION_COOKIE_NAME"] = os.getenv("CHATBOT_SESSION_COOKIE_NAME", "__session")
SERVER_BOOT_AT = datetime.now(timezone.utc).isoformat(timespec="seconds")

BOOTSTRAP_COMPANY_NAME = (
    str(os.getenv("CHATBOT_COMPANY_NAME", getattr(chatbot, "COMPANY_NAME", "Bacar"))).strip()
    or "Bacar"
)
BOOTSTRAP_HR_TEAM_NAME = (
    str(os.getenv("CHATBOT_HR_TEAM_NAME", getattr(chatbot, "HR_TEAM_NAME", "Atención"))).strip()
    or "Atención"
)
BOOTSTRAP_HR_CONTACT = (
    str(os.getenv("CHATBOT_HR_CONTACT", getattr(chatbot, "HR_CONTACT", "interno 104"))).strip()
    or "interno 104"
)

HANDOFF_STATUS_PENDING = "pendiente"
HANDOFF_STATUS_ACTIVE = "en_atencion"
HANDOFF_STATUS_CLOSED = "cerrada"

HANDOFF_END_COMMANDS = {
    "__cerrar_rrhh__",
    "cerrar rrhh",
    "finalizar rrhh",
    "terminar rrhh",
    "volver al bot",
}
HANDOFF_POLL_COMMANDS = {"__poll_rrhh__", "actualizar rrhh", "actualizar"}

IN_MEMORY_HANDOFFS = {}
IN_MEMORY_CHAT_HISTORY = []
IN_MEMORY_ACTIVE_AGENTS = {}
IN_MEMORY_GENERAL_SETTINGS = {}
IN_MEMORY_COMPANIES = {}

GENERAL_SETTINGS_COLLECTION = "chatbot_config"
GENERAL_SETTINGS_DOC = "general"
ACTIVE_AGENTS_COLLECTION = "rrhh_agentes"
COMPANIES_COLLECTION = "chatbot_empresas"
# Clave Firestore-safe para "Todas (ámbito empresa)" en areas_by_branch (Firestore no permite "" como nombre de campo).
AREA_BRANCH_KEY_EMPRESA = "__e"

try:
    ACTIVE_AGENT_TTL_SECONDS = max(
        60, int(str(os.getenv("RRHH_AGENT_ACTIVE_TTL_SECONDS", "180")).strip())
    )
except Exception:
    ACTIVE_AGENT_TTL_SECONDS = 180

AUTO_CLOSE_MIN_MINUTES = 5
AUTO_CLOSE_MAX_MINUTES = 7 * 24 * 60
AUTO_CLOSE_DEFAULT_MINUTES = 0

# Sesión por número de WhatsApp cuando el mensaje llega por webhook (colaborador escribe por WA).
WHATSAPP_SESSIONS = {}

WHATSAPP_CONTEXT_COLLECTION = "whatsapp_chat_context"


def _load_whatsapp_chat_context(phone):
    """Carga contexto de chat (empresa/sucursal/área/step) desde Firestore para este número."""
    if not chatbot.db or not phone:
        return
    norm = _normalize_phone_for_match(phone)
    if not norm:
        return
    try:
        doc = chatbot.db.collection(WHATSAPP_CONTEXT_COLLECTION).document(norm).get()
        if not doc.exists:
            return
        data = doc.to_dict() or {}
    except Exception:
        return
    sess = getattr(g, "whatsapp_session", None)
    if not sess:
        return
    for key in ("chat_context_step", "chat_context_company_id", "chat_context_branch", "chat_context_area", "company_id", "company_name"):
        if key in data and data[key] is not None:
            sess[key] = data[key]


def _save_whatsapp_chat_context(phone):
    """Guarda en Firestore el contexto de chat de la sesión WhatsApp actual."""
    if not chatbot.db or not phone:
        return
    norm = _normalize_phone_for_match(phone)
    if not norm:
        return
    sess = getattr(g, "whatsapp_session", None)
    if not sess:
        return
    payload = {
        "chat_context_step": sess.get("chat_context_step"),
        "chat_context_company_id": sess.get("chat_context_company_id"),
        "chat_context_branch": sess.get("chat_context_branch"),
        "chat_context_area": sess.get("chat_context_area"),
        "company_id": sess.get("company_id"),
        "company_name": sess.get("company_name"),
        "updated_at": _utc_now(),
    }
    payload = {k: v for k, v in payload.items() if v is not None}
    try:
        chatbot.db.collection(WHATSAPP_CONTEXT_COLLECTION).document(norm).set(payload, merge=True)
    except Exception:
        pass


def _sess():
    """Sesión efectiva: por WhatsApp (g.whatsapp_session) o sesión web (session)."""
    if getattr(g, "whatsapp_session", None) is not None:
        return g.whatsapp_session
    return session


def _accion(label, value, variant="default"):
    return {"label": label, "value": value, "variant": variant}


# Contexto de chat: empresa, sucursal y área elegidas por el colaborador (el asistente pregunta en ese orden).
CHAT_CONTEXT_STEP_COMPANY = "company"
CHAT_CONTEXT_STEP_BRANCH = "branch"
CHAT_CONTEXT_STEP_AREA = "area"
CHAT_CONTEXT_STEP_READY = "ready"


def _chat_context_step():
    return _sess().get("chat_context_step") or CHAT_CONTEXT_STEP_COMPANY


def _set_chat_context_company(company_id):
    key = _normalize_company_id(company_id)
    if key:
        _sess()["chat_context_company_id"] = key
        _set_company_session(key)
        company = _get_company(key, include_inactive=False)
        branches = _normalize_branches((company or {}).get("branches"))
        if branches:
            _sess()["chat_context_step"] = CHAT_CONTEXT_STEP_BRANCH
        else:
            _sess()["chat_context_step"] = CHAT_CONTEXT_STEP_AREA
            _sess().pop("chat_context_branch", None)


def _set_chat_context_branch(branch_name):
    branch_clean = str(branch_name or "").strip()
    if branch_clean:
        _sess()["chat_context_branch"] = branch_clean
        _sess()["chat_context_step"] = CHAT_CONTEXT_STEP_AREA


def _set_chat_context_area(area_name):
    area_clean = str(area_name or "").strip()
    if area_clean:
        _sess()["chat_context_area"] = area_clean
        _sess()["chat_context_step"] = CHAT_CONTEXT_STEP_READY


def _clear_chat_context():
    _sess().pop("chat_context_step", None)
    _sess().pop("chat_context_company_id", None)
    _sess().pop("chat_context_branch", None)
    _sess().pop("chat_context_area", None)


def _parse_menu_number(mensaje):
    """Si el mensaje es un número de menú (ej. '1', '1.', '2)', 'Sucursal 1'), devuelve el índice 1-based o None."""
    s = (mensaje or "").strip()
    if not s:
        return None
    s_clean = s.rstrip(".)")
    if s_clean.isdigit():
        n = int(s_clean)
        return n if n >= 1 else None
    import re
    m = re.search(r"\b([1-9]\d*)\b", s)
    if m:
        n = int(m.group(1))
        return n if n >= 1 else None
    return None


def _resolve_message_to_company(mensaje):
    """Devuelve (company_id, company) si el mensaje coincide con una empresa (nombre, id o número de menú)."""
    mensaje_norm = chatbot.normalizar_texto(mensaje)
    if not mensaje_norm:
        return None, None
    lista = _list_companies(include_inactive=False)
    num = _parse_menu_number(mensaje)
    if num is not None and 1 <= num <= len(lista):
        item = lista[num - 1]
        cid = _normalize_company_id(item.get("company_id"))
        return cid, item
    for item in lista:
        cid = _normalize_company_id(item.get("company_id"))
        raw_name = (item.get("company_name") or cid or "").strip()
        name = chatbot.normalizar_texto(raw_name)
        cid_norm = chatbot.normalizar_texto(cid or "")
        if not name:
            name = cid_norm
        if mensaje_norm == cid_norm or mensaje_norm == name:
            return cid, item
        if name and (mensaje_norm in name or (len(mensaje_norm) >= 2 and name in mensaje_norm)):
            return cid, item
    return None, None


def _resolve_message_to_area(mensaje, company_id, branch=None):
    """Devuelve el nombre del área si el mensaje coincide (nombre o número de menú)."""
    company = _get_company(company_id, include_inactive=False)
    if branch is not None and str(branch or "").strip():
        areas = _get_areas_for_branch(company, str(branch).strip())
    else:
        areas = _get_all_areas_for_company(company)
    mensaje_norm = chatbot.normalizar_texto(mensaje)
    if not mensaje_norm or not areas:
        return None
    num = _parse_menu_number(mensaje)
    if num is not None and 1 <= num <= len(areas):
        return str(areas[num - 1]).strip()
    for a in areas:
        an = str(a).strip()
        if chatbot.normalizar_texto(an) == mensaje_norm or mensaje_norm in chatbot.normalizar_texto(an):
            return an
    return None


def _construir_acciones_empresas(limite=10):
    acciones = []
    for i, item in enumerate(_list_companies(include_inactive=False)[:limite], start=1):
        cid = item.get("company_id")
        name = (item.get("company_name") or cid or "").strip()
        if cid and name:
            acciones.append(_accion(f"{i}. {name}", cid, "topic"))
    return acciones


def _get_branches_for_company(company):
    """Lista de nombres de sucursal para la empresa (para menú chat)."""
    if not company:
        return []
    return [_branch_name(b) for b in (company.get("branches") or []) if _branch_name(b)]


def _resolve_message_to_branch(mensaje, company_id):
    """Devuelve el nombre de la sucursal si el mensaje coincide (nombre o número de menú)."""
    company = _get_company(company_id, include_inactive=False)
    branches = _get_branches_for_company(company)
    mensaje_norm = chatbot.normalizar_texto(mensaje)
    if not mensaje_norm or not branches:
        return None
    num = _parse_menu_number(mensaje)
    if num is not None and 1 <= num <= len(branches):
        return str(branches[num - 1]).strip()
    for b in branches:
        bn = str(b).strip()
        if chatbot.normalizar_texto(bn) == mensaje_norm or mensaje_norm in chatbot.normalizar_texto(bn):
            return bn
    return None


def _construir_acciones_sucursales(company_id, limite=12):
    company = _get_company(company_id, include_inactive=False)
    branches = _get_branches_for_company(company)
    acciones = []
    for i, name in enumerate((branches or [])[:limite], start=1):
        if name:
            acciones.append(_accion(f"{i}. {name}", name, "topic"))
    return acciones


def _get_all_areas_for_company(company):
    """Unión de áreas de todas las sucursales + ámbito empresa (para menú chat)."""
    if not company:
        return []
    areas_by_branch = company.get("areas_by_branch")
    if isinstance(areas_by_branch, dict) and areas_by_branch:
        seen = set()
        out = []
        for branch in [""] + list(company.get("branches") or []):
            branch_key = "" if branch == "" else _branch_name(branch)
            for a in _get_areas_for_branch(company, branch_key):
                k = str(a).strip().lower()
                if k and k not in seen:
                    seen.add(k)
                    out.append(a)
        return out
    return _normalize_areas(company.get("areas"))


def _construir_acciones_areas(company_id, limite=12, branch=None):
    company = _get_company(company_id, include_inactive=False)
    if branch is not None and str(branch or "").strip():
        areas = _get_areas_for_branch(company, str(branch).strip())
    else:
        areas = _get_all_areas_for_company(company)
    acciones = []
    for i, a in enumerate((areas or [])[:limite], start=1):
        an = str(a).strip()
        if an:
            acciones.append(_accion(f"{i}. {an}", an, "topic"))
    return acciones


def _utc_now():
    return datetime.now(timezone.utc)


def _new_conversation_id():
    return f"conv-{uuid.uuid4().hex[:12]}"


def _as_utc_naive(dt):
    if not isinstance(dt, datetime):
        return None
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def _as_utc_aware(dt):
    if not isinstance(dt, datetime):
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _iso_utc(dt):
    dt2 = _as_utc_aware(dt)
    if not dt2:
        return ""
    return dt2.isoformat(timespec="seconds").replace("+00:00", "Z")


def _fmt_fecha(dt):
    dt2 = _as_utc_naive(dt)
    if not dt2:
        return "Sin fecha"
    return dt2.strftime("%Y-%m-%d %H:%M")


def _is_true_env(value, default=True):
    raw = str(value if value is not None else "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on", "si", "sí"}


def _smtp_settings():
    try:
        port = int(str(os.getenv("SMTP_PORT", "587")).strip() or "587")
    except Exception:
        port = 587
    return {
        "host": str(os.getenv("SMTP_HOST", "")).strip(),
        "port": port,
        "username": str(os.getenv("SMTP_USER", "")).strip(),
        "password": str(os.getenv("SMTP_PASSWORD", "")).strip(),
        "from_email": str(os.getenv("SMTP_FROM", "")).strip(),
        "use_tls": _is_true_env(os.getenv("SMTP_USE_TLS"), default=True),
    }


def _send_email(to_email, subject, body_text):
    cfg = _smtp_settings()
    recipient = str(to_email or "").strip()
    if not recipient:
        return False, "Email de destino inválido."
    if not cfg["host"]:
        return False, "SMTP no configurado: falta SMTP_HOST."

    sender = cfg["from_email"] or cfg["username"]
    if not sender:
        return False, "SMTP no configurado: falta SMTP_FROM o SMTP_USER."

    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = str(subject or "").strip() or "Notificación"
    message.set_content(str(body_text or "").strip() or "Mensaje automático")

    try:
        with smtplib.SMTP(cfg["host"], cfg["port"], timeout=20) as smtp:
            smtp.ehlo()
            if cfg["use_tls"]:
                smtp.starttls()
                smtp.ehlo()
            if cfg["username"]:
                smtp.login(cfg["username"], cfg["password"])
            smtp.send_message(message)
    except Exception as exc:
        return False, f"No se pudo enviar email: {exc}"
    return True, ""


def _send_password_reset_email(to_email, display_name, reset_url, expires_at_iso):
    name = str(display_name or "usuario").strip()
    subject = "Restablecer contraseña de acceso"
    body = (
        f"Hola {name},\n\n"
        "Recibimos una solicitud para restablecer tu contraseña.\n"
        f"Usá este enlace para crear una nueva clave:\n{reset_url}\n\n"
        f"Este enlace vence el: {expires_at_iso} (UTC).\n\n"
        "Si no solicitaste este cambio, ignorá este mensaje."
    )
    return _send_email(to_email=to_email, subject=subject, body_text=body)


def _default_general_settings():
    return {
        "company_name": BOOTSTRAP_COMPANY_NAME,
        "hr_team_name": BOOTSTRAP_HR_TEAM_NAME,
        "hr_contact": BOOTSTRAP_HR_CONTACT,
        "company_email": "",
        "company_address": "",
        "company_phone": "",
        "company_website": "",
        "handoff_auto_close_enabled": False,
        "handoff_auto_close_minutes": AUTO_CLOSE_DEFAULT_MINUTES,
    }


def _normalize_company_id(value):
    token = chatbot.normalizar_texto(value or "")
    token = token.replace(" ", "-")
    token = "".join(ch for ch in token if ch.isalnum() or ch in {"-", "_", "."})
    token = token.strip("-_.")
    if len(token) < 2:
        return ""
    return token[:64]


def _default_company_id():
    env_value = str(os.getenv("CHATBOT_DEFAULT_COMPANY_ID", "")).strip()
    if env_value:
        normalized = _normalize_company_id(env_value)
        if normalized:
            return normalized
    return _normalize_company_id(_default_general_settings().get("company_name")) or "empresa"


def _normalize_branch_item(item):
    """Normaliza un ítem de sucursal: string -> objeto con name; dict -> objeto con name, address, phone, encargado."""
    if item is None:
        return None
    if isinstance(item, dict):
        name = str(item.get("name") or "").strip()
        if not name:
            return None
        return {
            "name": name,
            "address": _normalize_optional_company_text(item.get("address"), max_len=240),
            "phone": _normalize_optional_company_text(item.get("phone"), max_len=80),
            "encargado": _normalize_optional_company_text(item.get("encargado"), max_len=120),
        }
    branch = str(item or "").strip()
    if not branch:
        return None
    return {
        "name": branch,
        "address": "",
        "phone": "",
        "encargado": "",
    }


def _normalize_branches(raw_branches):
    if raw_branches is None:
        return []
    values = raw_branches if isinstance(raw_branches, list) else [raw_branches]
    cleaned = []
    seen = set()
    for item in values:
        branch = _normalize_branch_item(item)
        if not branch:
            continue
        key = branch["name"].lower()
        if key in seen:
            continue
        cleaned.append(branch)
        seen.add(key)
    return cleaned


def _normalize_areas(raw_areas):
    """Lista de nombres de área (strings) normalizados y sin duplicados."""
    if raw_areas is None:
        return []
    values = raw_areas if isinstance(raw_areas, list) else [raw_areas]
    cleaned = []
    seen = set()
    for item in values:
        name = str(item or "").strip()
        if not name:
            continue
        name = name[:120]
        key = name.lower()
        if key in seen:
            continue
        cleaned.append(name)
        seen.add(key)
    return cleaned


def _normalize_areas_by_branch(raw):
    """Dict sucursal -> lista de áreas. Claves normalizadas (string); '' se guarda como AREA_BRANCH_KEY_EMPRESA por Firestore."""
    if not isinstance(raw, dict):
        return {}
    out = {}
    for branch_key, areas in raw.items():
        branch = str(branch_key or "").strip()[:120]
        key = AREA_BRANCH_KEY_EMPRESA if branch == "" else branch
        out[key] = _normalize_areas(areas)
    return out


def _get_areas_for_branch(company, branch):
    """Devuelve la lista de áreas para una empresa y sucursal. branch '' = ámbito empresa."""
    if not company:
        return []
    branch_key = _branch_name(branch) if isinstance(branch, dict) else (str(branch).strip() if branch is not None else "")
    areas_by_branch = company.get("areas_by_branch")
    if isinstance(areas_by_branch, dict):
        if branch_key in areas_by_branch:
            return list(areas_by_branch[branch_key] or [])
        if "" in areas_by_branch:
            return list(areas_by_branch[""] or [])
        if AREA_BRANCH_KEY_EMPRESA in areas_by_branch:
            return list(areas_by_branch[AREA_BRANCH_KEY_EMPRESA] or [])
    return _normalize_areas(company.get("areas"))


def _areas_by_branch_for_api(areas_by_branch):
    """Convierte areas_by_branch para la API: __e -> '' para que el frontend reciba siempre '' como 'Todas'."""
    if not isinstance(areas_by_branch, dict):
        return areas_by_branch or {}
    out = {}
    for k, v in areas_by_branch.items():
        key = "" if k == AREA_BRANCH_KEY_EMPRESA else k
        out[key] = list(v) if isinstance(v, list) else []
    return out


def _company_for_api(company):
    """Copia la empresa con areas_by_branch con claves aptas para el frontend ('' en lugar de __e)."""
    if not company or not isinstance(company, dict):
        return company
    out = dict(company)
    out["areas_by_branch"] = _areas_by_branch_for_api(company.get("areas_by_branch"))
    return out


def _normalize_optional_company_text(value, max_len=180):
    raw = str(value or "").strip()
    if not raw:
        return ""
    return raw[:max_len]


def _normalize_whatsapp_numbers(raw):
    """Lista de { "phone": str, "label": str } por empresa/área (ej. RRHH, Tesorería)."""
    if not raw:
        return []
    out = []
    seen_phones = set()
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, dict):
            continue
        phone = str(item.get("phone") or "").strip()
        if not phone:
            continue
        if not phone.startswith("+"):
            phone = "+" + phone.lstrip("0")
        key = "".join(c for c in phone if c.isdigit())
        if key in seen_phones:
            continue
        seen_phones.add(key)
        label = str(item.get("label") or "").strip() or "Principal"
        out.append({"phone": phone[:30], "label": label[:80]})
    return out


def _normalize_bool_flag(value, default=False):
    if isinstance(value, bool):
        return value
    raw = str(value if value is not None else "").strip().lower()
    if not raw:
        return bool(default)
    if raw in {"1", "true", "yes", "on", "si", "sí"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    return bool(default)


def _normalize_auto_close_minutes(value):
    try:
        minutes = int(str(value or 0).strip() or "0")
    except Exception:
        minutes = 0
    if minutes <= 0:
        return 0
    return max(AUTO_CLOSE_MIN_MINUTES, min(minutes, AUTO_CLOSE_MAX_MINUTES))


def _normalize_company_entry(entry):
    if not isinstance(entry, dict):
        return None
    company_name = str(entry.get("company_name") or "").strip()
    if not company_name:
        return None
    company_id = _normalize_company_id(entry.get("company_id") or company_name)
    if not company_id:
        return None
    hr_team_name = str(entry.get("hr_team_name") or "Atención").strip() or "Atención"
    hr_contact = str(entry.get("hr_contact") or "").strip() or "interno 104"
    branches = _normalize_branches(entry.get("branches"))
    company_email = _normalize_optional_company_text(entry.get("company_email"), max_len=200).lower()
    company_address = _normalize_optional_company_text(entry.get("company_address"), max_len=240)
    company_phone = _normalize_optional_company_text(entry.get("company_phone"), max_len=80)
    company_website = _normalize_optional_company_text(entry.get("company_website"), max_len=200)
    auto_close_minutes = _normalize_auto_close_minutes(entry.get("handoff_auto_close_minutes"))
    auto_close_enabled = _normalize_bool_flag(
        entry.get("handoff_auto_close_enabled"),
        default=auto_close_minutes > 0,
    )
    if not auto_close_enabled:
        auto_close_minutes = 0
    permitir_humano = _normalize_bool_flag(entry.get("permitir_hablar_con_humano"), default=True)
    temas_hab_raw = entry.get("temas_habilitados")
    if isinstance(temas_hab_raw, list):
        temas_habilitados = [str(t).strip().lower() for t in temas_hab_raw if str(t).strip()]
    else:
        temas_habilitados = []
    areas = _normalize_areas(entry.get("areas"))
    areas_by_branch = _normalize_areas_by_branch(entry.get("areas_by_branch"))
    if not areas_by_branch and areas:
        areas_by_branch = {AREA_BRANCH_KEY_EMPRESA: areas}
    whatsapp_numbers = _normalize_whatsapp_numbers(entry.get("whatsapp_numbers"))
    return {
        "company_id": company_id,
        "company_name": company_name,
        "hr_team_name": hr_team_name,
        "hr_contact": hr_contact,
        "company_email": company_email,
        "company_address": company_address,
        "company_phone": company_phone,
        "company_website": company_website,
        "handoff_auto_close_enabled": auto_close_enabled,
        "handoff_auto_close_minutes": auto_close_minutes,
        "branches": branches,
        "areas": areas,
        "areas_by_branch": areas_by_branch,
        "active": bool(entry.get("active", True)),
        "permitir_hablar_con_humano": permitir_humano,
        "temas_habilitados": temas_habilitados,
        "whatsapp_numbers": whatsapp_numbers,
    }


def _default_company_entry():
    defaults = _default_general_settings()
    return {
        "company_id": _default_company_id(),
        "company_name": defaults.get("company_name") or "Empresa",
        "hr_team_name": defaults.get("hr_team_name") or "Atención",
        "hr_contact": defaults.get("hr_contact") or "interno 104",
        "company_email": "",
        "company_address": "",
        "company_phone": "",
        "company_website": "",
        "handoff_auto_close_enabled": False,
        "handoff_auto_close_minutes": AUTO_CLOSE_DEFAULT_MINUTES,
        "branches": [],
        "areas": [],
        "areas_by_branch": {},
        "active": True,
        "permitir_hablar_con_humano": True,
        "temas_habilitados": [],
        "whatsapp_numbers": [],
    }


def _company_by_whatsapp_phone(phone):
    """Si el número recibido está configurado en alguna empresa, devuelve (company_id, company, label)."""
    if not phone:
        return None, None, None
    norm = _normalize_phone_for_match(phone)
    if not norm:
        return None, None, None
    for company in _list_companies(include_inactive=False):
        for line in (company.get("whatsapp_numbers") or []):
            p = (line.get("phone") or "").strip()
            if _normalize_phone_for_match(p) == norm:
                return company.get("company_id"), company, (line.get("label") or "").strip() or None
    return None, None, None


def _merge_company_entries(current, candidate):
    base = dict(current or {})
    extra = dict(candidate or {})
    for key in ("company_name", "hr_team_name", "hr_contact"):
        value = str(extra.get(key) or "").strip()
        if value:
            base[key] = value
    for key in ("company_email", "company_address", "company_phone", "company_website"):
        value = _normalize_optional_company_text(extra.get(key), max_len=240)
        if value:
            base[key] = value.lower() if key == "company_email" else value
    base_minutes = _normalize_auto_close_minutes(
        extra.get("handoff_auto_close_minutes", base.get("handoff_auto_close_minutes"))
    )
    base_enabled = _normalize_bool_flag(
        extra.get("handoff_auto_close_enabled", base.get("handoff_auto_close_enabled")),
        default=base_minutes > 0,
    )
    if not base_enabled:
        base_minutes = 0
    base["handoff_auto_close_enabled"] = base_enabled
    base["handoff_auto_close_minutes"] = base_minutes
    base["branches"] = _normalize_branches(
        list(base.get("branches") or []) + list(extra.get("branches") or [])
    )
    if "areas" in extra and isinstance(extra.get("areas"), list):
        base["areas"] = _normalize_areas(extra.get("areas"))
    else:
        base.setdefault("areas", [])
    if "areas_by_branch" in extra and isinstance(extra.get("areas_by_branch"), dict):
        base["areas_by_branch"] = _normalize_areas_by_branch(extra.get("areas_by_branch"))
    else:
        base.setdefault("areas_by_branch", base.get("areas_by_branch") or {})
    base["active"] = bool(base.get("active", True) or extra.get("active", True))
    base["company_id"] = str(base.get("company_id") or extra.get("company_id") or "").strip()
    if "permitir_hablar_con_humano" in extra:
        base["permitir_hablar_con_humano"] = _normalize_bool_flag(extra.get("permitir_hablar_con_humano"), default=True)
    else:
        base.setdefault("permitir_hablar_con_humano", True)
    if "temas_habilitados" in extra and isinstance(extra.get("temas_habilitados"), list):
        base["temas_habilitados"] = [str(t).strip().lower() for t in extra["temas_habilitados"] if str(t).strip()]
    else:
        base.setdefault("temas_habilitados", [])
    if "whatsapp_numbers" in extra and isinstance(extra.get("whatsapp_numbers"), list):
        base["whatsapp_numbers"] = _normalize_whatsapp_numbers(extra["whatsapp_numbers"])
    else:
        base.setdefault("whatsapp_numbers", [])
    return base


def _list_companies(include_inactive=False):
    rows = []
    if chatbot.db:
        try:
            for doc in chatbot.db.collection(COMPANIES_COLLECTION).stream():
                payload = doc.to_dict() or {}
                payload.setdefault("company_id", doc.id)
                normalized = _normalize_company_entry(payload)
                if normalized:
                    rows.append(normalized)
        except Exception:
            rows = []
    else:
        rows = []
        for company_id, payload in IN_MEMORY_COMPANIES.items():
            clone = dict(payload or {})
            clone.setdefault("company_id", company_id)
            normalized = _normalize_company_entry(clone)
            if normalized:
                rows.append(normalized)

    # Deduplica por company_id para evitar selectores con empresas repetidas.
    deduped = {}
    for item in rows:
        key = str(item.get("company_id") or "").strip()
        if not key:
            continue
        if key in deduped:
            deduped[key] = _merge_company_entries(deduped[key], item)
        else:
            deduped[key] = item
    rows = list(deduped.values())

    if not rows:
        rows = [_default_company_entry()]

    default_entry = _default_company_entry()
    if not any(item.get("company_id") == default_entry.get("company_id") for item in rows):
        rows.append(default_entry)

    if not include_inactive:
        rows = [item for item in rows if item.get("active", True)]
        if not rows:
            rows = [default_entry]

    rows.sort(key=lambda item: (str(item.get("company_name") or "").lower(), item.get("company_id")))
    return rows


def _company_map(include_inactive=False):
    return {item["company_id"]: item for item in _list_companies(include_inactive=include_inactive)}


def _get_company(company_id, include_inactive=True):
    key = _normalize_company_id(company_id)
    if not key:
        return None
    return _company_map(include_inactive=include_inactive).get(key)


def _upsert_company(payload):
    normalized = _normalize_company_entry(payload)
    if not normalized:
        return False, None, "Empresa inválida. Completá nombre y datos básicos."

    if chatbot.db:
        try:
            (
                chatbot.db.collection(COMPANIES_COLLECTION)
                .document(normalized["company_id"])
                .set(normalized, merge=False)
            )
            return True, normalized, ""
        except Exception as exc:
            return False, None, f"No pude guardar empresa: {exc}"

    IN_MEMORY_COMPANIES[normalized["company_id"]] = normalized
    return True, normalized, ""


def _delete_company(company_id):
    key = _normalize_company_id(company_id)
    if not key:
        return False, "Empresa inválida."
    if key == _default_company_id():
        return False, "No podés eliminar la empresa por defecto."

    companies = _list_companies(include_inactive=True)
    if len(companies) <= 1:
        return False, "Debe quedar al menos una empresa configurada."

    for user in auth_rrhh.get_users().values():
        assignments = user.get("assignments") if isinstance(user.get("assignments"), list) else []
        if any(str(item.get("company_id") or "").strip().lower() == key for item in assignments if isinstance(item, dict)):
            return False, "No podés eliminar una empresa asignada a usuarios."

    if chatbot.db:
        try:
            chatbot.db.collection(COMPANIES_COLLECTION).document(key).delete()
            return True, ""
        except Exception as exc:
            return False, f"No pude eliminar empresa: {exc}"

    if key not in IN_MEMORY_COMPANIES:
        return False, "Empresa no encontrada."
    IN_MEMORY_COMPANIES.pop(key, None)
    return True, ""


def _set_company_session(company_id):
    company = _get_company(company_id, include_inactive=False)
    if company is None:
        company = _list_companies(include_inactive=False)[0]
    current_user = _current_rrhh_user()
    if current_user and not _user_can_access_company(current_user, company.get("company_id")):
        allowed = _companies_for_user(current_user)
        if allowed:
            company = allowed[0]
    _sess()["company_id"] = company["company_id"]
    _sess()["company_name"] = company["company_name"]
    _sess()["company_hr_team_name"] = company.get("hr_team_name") or "Atención"
    return company


def _current_company():
    selected = _normalize_company_id(_sess().get("company_id"))
    company = _get_company(selected, include_inactive=False) if selected else None
    if company is None:
        if _list_companies(include_inactive=False):
            company = _list_companies(include_inactive=False)[0]
            _sess()["company_id"] = company["company_id"]
    current_user = _current_rrhh_user()
    if current_user and not _user_can_access_company(current_user, company.get("company_id")):
        allowed = _companies_for_user(current_user)
        if allowed:
            company = allowed[0]
            _sess()["company_id"] = company["company_id"]
    return company or _default_company_entry()


def _sanitize_general_settings(payload):
    defaults = _default_general_settings()
    data = dict(defaults)
    if not isinstance(payload, dict):
        return data

    for key in defaults:
        value = str(payload.get(key) or "").strip()
        if value:
            data[key] = value
    return data


def _read_general_settings():
    company = _current_company()
    auto_close_enabled = _normalize_bool_flag(
        company.get("handoff_auto_close_enabled", False),
        default=False,
    )
    auto_close_minutes = _normalize_auto_close_minutes(company.get("handoff_auto_close_minutes"))
    if not auto_close_enabled:
        auto_close_minutes = 0
    return {
        "company_id": company.get("company_id"),
        "company_name": company.get("company_name"),
        "hr_team_name": company.get("hr_team_name"),
        "hr_contact": company.get("hr_contact"),
        "company_email": company.get("company_email") or "",
        "company_address": company.get("company_address") or "",
        "company_phone": company.get("company_phone") or "",
        "company_website": company.get("company_website") or "",
        "handoff_auto_close_enabled": auto_close_enabled,
        "handoff_auto_close_minutes": auto_close_minutes,
        "branches": list(company.get("branches") or []),
        "permitir_hablar_con_humano": _normalize_bool_flag(company.get("permitir_hablar_con_humano"), default=True),
        "temas_habilitados": list(company.get("temas_habilitados") or []),
    }


def _write_general_settings(payload):
    current = _current_company()
    data = payload if isinstance(payload, dict) else {}
    company_id = _normalize_company_id((payload or {}).get("company_id") or current.get("company_id"))
    company_name = str((payload or {}).get("company_name") or current.get("company_name") or "").strip()
    hr_team_name = str((payload or {}).get("hr_team_name") or current.get("hr_team_name") or "").strip()
    hr_contact = str((payload or {}).get("hr_contact") or current.get("hr_contact") or "").strip()
    company_email_raw = (
        data.get("company_email")
        if "company_email" in data
        else current.get("company_email") or ""
    )
    company_email = _normalize_optional_company_text(
        company_email_raw,
        max_len=200,
    ).lower()
    company_address_raw = (
        data.get("company_address")
        if "company_address" in data
        else current.get("company_address") or ""
    )
    company_address = _normalize_optional_company_text(
        company_address_raw,
        max_len=240,
    )
    company_phone_raw = (
        data.get("company_phone")
        if "company_phone" in data
        else current.get("company_phone") or ""
    )
    company_phone = _normalize_optional_company_text(
        company_phone_raw,
        max_len=80,
    )
    company_website_raw = (
        data.get("company_website")
        if "company_website" in data
        else current.get("company_website") or ""
    )
    company_website = _normalize_optional_company_text(
        company_website_raw,
        max_len=200,
    )
    auto_close_enabled_raw = (
        data.get("handoff_auto_close_enabled")
        if "handoff_auto_close_enabled" in data
        else current.get("handoff_auto_close_enabled", False)
    )
    auto_close_enabled = _normalize_bool_flag(
        auto_close_enabled_raw,
        default=bool(current.get("handoff_auto_close_enabled", False)),
    )
    auto_close_minutes_raw = (
        data.get("handoff_auto_close_minutes")
        if "handoff_auto_close_minutes" in data
        else current.get("handoff_auto_close_minutes", AUTO_CLOSE_DEFAULT_MINUTES)
    )
    auto_close_minutes = _normalize_auto_close_minutes(auto_close_minutes_raw)
    if not auto_close_enabled:
        auto_close_minutes = 0
    branches = _normalize_branches((payload or {}).get("branches") or current.get("branches") or [])

    permitir_humano = _normalize_bool_flag(
        data.get("permitir_hablar_con_humano")
        if "permitir_hablar_con_humano" in data
        else current.get("permitir_hablar_con_humano", True),
        default=True,
    )
    temas_hab_raw = data.get("temas_habilitados") if "temas_habilitados" in data else current.get("temas_habilitados")
    temas_habilitados = (
        [str(t).strip().lower() for t in temas_hab_raw if str(t).strip()]
        if isinstance(temas_hab_raw, list)
        else []
    )
    ok, company, error = _upsert_company(
        {
            "company_id": company_id or current.get("company_id"),
            "company_name": company_name or current.get("company_name"),
            "hr_team_name": hr_team_name or current.get("hr_team_name"),
            "hr_contact": hr_contact or current.get("hr_contact"),
            "company_email": company_email,
            "company_address": company_address,
            "company_phone": company_phone,
            "company_website": company_website,
            "handoff_auto_close_enabled": auto_close_enabled,
            "handoff_auto_close_minutes": auto_close_minutes,
            "branches": branches,
            "areas": _normalize_areas(data.get("areas") if "areas" in data else (current.get("areas") or [])),
            "active": True,
            "permitir_hablar_con_humano": permitir_humano,
            "temas_habilitados": temas_habilitados,
        }
    )
    if not ok:
        return False, None, error
    _set_company_session(company.get("company_id"))
    return True, _read_general_settings(), ""


def _apply_company_branding(settings=None):
    cfg = settings or _read_general_settings()
    if hasattr(chatbot, "actualizar_configuracion_empresa"):
        chatbot.actualizar_configuracion_empresa(
            company_name=cfg.get("company_name"),
            hr_team_name=cfg.get("hr_team_name"),
            hr_contact=cfg.get("hr_contact"),
        )
    return cfg


def _farewell_message():
    cfg = _apply_company_branding()
    return (
        f"Gracias por comunicarte con {cfg.get('hr_team_name', 'Atención')} "
        f"de {cfg.get('company_name', 'la empresa')}. ¡Buen día!"
    )


def _manual_agent_id(name):
    normalized = chatbot.normalizar_texto(name)[:48]
    if not normalized:
        normalized = f"agente-{uuid.uuid4().hex[:8]}"
    return f"manual:{normalized}"


def _agent_payload(display_name, agent_id="", role="rrhh", company_id="", area=""):
    shown = str(display_name or "Agente").strip() or "Agente"
    identifier = str(agent_id or "").strip().lower() or _manual_agent_id(shown)
    company_key = _normalize_company_id(company_id)
    area_str = str(area or "").strip()
    return {
        "agent_id": identifier,
        "display_name": shown,
        "role": str(role or "rrhh").strip().lower() or "rrhh",
        "company_id": company_key,
        "area": area_str,
    }


def _active_agent_from_current_user():
    current = _current_rrhh_user()
    if not current:
        return None
    company_id = _selected_company_id_for_rrhh()
    return _agent_payload(
        display_name=current.get("display_name") or current.get("username") or "Agente",
        agent_id=str(current.get("username") or "").strip().lower(),
        role=current.get("role") or "rrhh",
        company_id=company_id,
        area=current.get("area") or "",
    )


def _auth_enabled():
    return auth_rrhh.is_auth_enabled()


def _safe_next_path(next_path, fallback="/rrhh"):
    raw = str(next_path or "").strip()
    if not raw:
        return fallback
    if not raw.startswith("/") or raw.startswith("//"):
        return fallback
    return raw


def _request_path_with_query():
    path = request.path
    if request.query_string:
        path = f"{path}?{request.query_string.decode('utf-8', errors='ignore')}"
    return _safe_next_path(path)


def _current_rrhh_user():
    username = str(session.get("rrhh_user") or "").strip()
    if not username:
        return None
    current = {
        "username": username,
        "display_name": str(session.get("rrhh_display_name") or username),
        "role": str(session.get("rrhh_role") or "rrhh"),
        "assignments": session.get("rrhh_assignments") or [],
        "area": str(session.get("rrhh_area") or "").strip(),
    }
    if _auth_enabled():
        # Si el rol/nombre cambian en archivo, sincroniza sesión en caliente.
        entry = auth_rrhh.get_users().get(username.lower())
        if not entry:
            _clear_rrhh_user()
            return None
        current["display_name"] = str(entry.get("display_name") or username)
        current["role"] = str(entry.get("role") or "rrhh")
        current["assignments"] = list(entry.get("assignments") or [])
        current["area"] = str(entry.get("area") or "").strip()
        _set_rrhh_user(current)
    return current


def _set_rrhh_user(user_payload):
    session["rrhh_user"] = str(user_payload.get("username") or "").strip()
    session["rrhh_display_name"] = str(
        user_payload.get("display_name") or session["rrhh_user"]
    ).strip()
    session["rrhh_role"] = str(user_payload.get("role") or "rrhh").strip()
    session["rrhh_assignments"] = list(user_payload.get("assignments") or [])
    session["rrhh_area"] = str(user_payload.get("area") or "").strip()


def _clear_rrhh_user():
    session.pop("rrhh_user", None)
    session.pop("rrhh_display_name", None)
    session.pop("rrhh_role", None)
    session.pop("rrhh_assignments", None)
    session.pop("rrhh_area", None)


def _rrhh_agent_name(default="Agente"):
    current = _current_rrhh_user()
    if not current:
        return default
    return str(current.get("display_name") or current.get("username") or default)


def _resolve_rrhh_agent(payload):
    if _auth_enabled():
        current_agent = _active_agent_from_current_user()
        if current_agent:
            return current_agent
    fallback_name = str((payload or {}).get("agente") or "Agente").strip() or "Agente"
    return _agent_payload(display_name=fallback_name, company_id=_selected_company_id_for_rrhh())


def _upsert_active_agent(agent, source="heartbeat"):
    payload = _agent_payload(
        display_name=agent.get("display_name") or "Agente",
        agent_id=agent.get("agent_id") or "",
        role=agent.get("role") or "rrhh",
        company_id=agent.get("company_id") or _selected_company_id_for_rrhh(),
        area=agent.get("area") or "",
    )
    payload["updated_at"] = _utc_now()
    payload["available"] = True
    payload["source"] = str(source or "heartbeat")

    if chatbot.db:
        try:
            (
                chatbot.db.collection(ACTIVE_AGENTS_COLLECTION)
                .document(payload["agent_id"])
                .set(payload, merge=True)
            )
        except Exception:
            return payload
        return payload

    IN_MEMORY_ACTIVE_AGENTS[payload["agent_id"]] = payload
    return payload


def _list_active_agents(ttl_seconds=ACTIVE_AGENT_TTL_SECONDS, company_id=None, branch=None):
    now = _as_utc_naive(_utc_now()) or datetime.utcnow()
    ttl = max(30, int(ttl_seconds or ACTIVE_AGENT_TTL_SECONDS))
    threshold = now - timedelta(seconds=ttl)

    if chatbot.db:
        rows = []
        try:
            for doc in chatbot.db.collection(ACTIVE_AGENTS_COLLECTION).stream():
                data = doc.to_dict() or {}
                data["agent_id"] = str(data.get("agent_id") or doc.id)
                rows.append(data)
        except Exception:
            rows = []
    else:
        rows = [dict(value) for value in IN_MEMORY_ACTIVE_AGENTS.values()]

    active = []
    target_company = _normalize_company_id(company_id)
    branch_str = str(branch or "").strip() if branch is not None else None
    users_map = auth_rrhh.get_users() if _auth_enabled() else {}

    for item in rows:
        updated_at = _as_utc_naive(item.get("updated_at"))
        if updated_at is None or updated_at < threshold:
            continue
        if item.get("available") is False:
            continue
        item_company = _normalize_company_id(item.get("company_id"))
        if target_company and item_company != target_company:
            continue
        if branch_str is not None and users_map:
            agent_id_raw = str(item.get("agent_id") or "").strip().lower()
            user_entry = users_map.get(agent_id_raw)
            if user_entry and not auth_rrhh.assignment_matches_company_branch(
                user_entry.get("assignments"), target_company, branch_str
            ):
                continue
        role = str(item.get("role") or "").strip().lower()
        if role and not auth_rrhh.role_has_permission(role, auth_rrhh.PERM_CONVERSATIONS_MANAGE):
            continue
        agent_id_raw = str(item.get("agent_id") or "").strip().lower()
        area_stored = str(item.get("area") or "").strip()
        if not area_stored and users_map and agent_id_raw:
            user_entry = users_map.get(agent_id_raw)
            area_stored = str((user_entry or {}).get("area") or "").strip()
        active.append(
            _agent_payload(
                item.get("display_name"),
                item.get("agent_id"),
                role,
                company_id=item_company,
                area=area_stored,
            )
        )
        active[-1]["updated_at"] = item.get("updated_at")

    active.sort(key=lambda x: (str(x.get("display_name") or "").lower(), x.get("agent_id") or ""))
    return active


def _serialize_active_agent(agent):
    return {
        "agent_id": str(agent.get("agent_id") or ""),
        "display_name": str(agent.get("display_name") or ""),
        "role": str(agent.get("role") or ""),
        "company_id": str(agent.get("company_id") or ""),
        "updated_at": _fmt_fecha(agent.get("updated_at")),
    }


def _heartbeat_current_agent(source="rrhh_panel"):
    if _auth_enabled():
        current = _active_agent_from_current_user()
        if not current:
            return None
        if not auth_rrhh.role_has_permission(
            current.get("role"), auth_rrhh.PERM_CONVERSATIONS_MANAGE
        ):
            return None
        return _upsert_active_agent(current, source=source)
    return None


def _open_handoff_load_by_agent(company_id=None):
    counts = {}
    for conv in _list_handoffs(include_closed=False, limit=1000, company_id=company_id):
        estado = str(conv.get("estado") or "").strip().lower()
        if estado == HANDOFF_STATUS_CLOSED:
            continue
        agent_id = str(conv.get("rrhh_agente_id") or "").strip().lower()
        if not agent_id:
            continue
        counts[agent_id] = counts.get(agent_id, 0) + 1
    return counts


def _agent_areas_set(agent):
    """Conjunto de áreas del agente (normalizadas) para matching."""
    area_str = str(agent.get("area") or "").strip()
    if not area_str:
        return set()
    return {a.strip().lower() for a in area_str.split(",") if a.strip()}


def _select_auto_agent(company_id=None, branch=None, area=None):
    active_agents = _list_active_agents(company_id=company_id, branch=branch or None)
    if not active_agents:
        return None
    area_norm = str(area or "").strip().lower() if area else None
    if area_norm:
        by_area = [a for a in active_agents if area_norm in _agent_areas_set(a)]
        if by_area:
            active_agents = by_area
    load = _open_handoff_load_by_agent(company_id=company_id)
    return sorted(
        active_agents,
        key=lambda agent: (
            load.get(agent.get("agent_id"), 0),
            str(agent.get("display_name") or "").lower(),
            str(agent.get("agent_id") or ""),
        ),
    )[0]


def _resolve_target_agent_for_reassignment(payload):
    data = payload or {}
    requested_id = str(data.get("agente_id") or "").strip().lower()
    requested_name = str(data.get("agente") or "").strip()

    if requested_id:
        for agent in _list_active_agents(company_id=_selected_company_id_for_rrhh()):
            if agent.get("agent_id") == requested_id:
                return agent
        return None

    if requested_name:
        return _agent_payload(
            display_name=requested_name,
            company_id=_selected_company_id_for_rrhh(),
        )

    return _resolve_rrhh_agent(data)


def _can_manage_configuration():
    """Acceso a la página Configuración (al menos un módulo)."""
    if not _auth_enabled():
        return True
    return (
        _has_permission(auth_rrhh.PERM_CONFIG_MANAGE)
        or _has_permission(auth_rrhh.PERM_USERS_MANAGE)
        or _has_permission(auth_rrhh.PERM_ROLES_MANAGE)
    )


def _can_manage_general_config():
    """Empresas, Sucursales, Áreas."""
    if not _auth_enabled():
        return True
    return _has_permission(auth_rrhh.PERM_CONFIG_MANAGE)


def _companies_for_user(user_payload):
    companies = _list_companies(include_inactive=False)
    assignments = list((user_payload or {}).get("assignments") or [])
    if not assignments:
        return companies
    allowed = {
        str(item.get("company_id") or "").strip().lower()
        for item in assignments
        if isinstance(item, dict)
    }
    return [item for item in companies if item.get("company_id") in allowed]


def _user_can_access_company(user_payload, company_id):
    company_key = _normalize_company_id(company_id)
    if not company_key:
        return False
    username = str((user_payload or {}).get("username") or "").strip()
    if username:
        return auth_rrhh.user_has_company_access(username, company_key)
    assignments = list((user_payload or {}).get("assignments") or [])
    if not assignments:
        return True
    return any(
        str(item.get("company_id") or "").strip().lower() == company_key
        for item in assignments
        if isinstance(item, dict)
    )


def _selected_company_id_for_rrhh():
    current = _current_company()
    return current.get("company_id")


def _default_landing_for_user(user_payload):
    role = str((user_payload or {}).get("role") or "")
    if auth_rrhh.role_has_permission(role, auth_rrhh.PERM_CONVERSATIONS_VIEW):
        return "/rrhh"
    if auth_rrhh.role_has_permission(role, auth_rrhh.PERM_HISTORY_VIEW):
        return "/historial"
    if auth_rrhh.role_has_permission(role, auth_rrhh.PERM_USERS_MANAGE) or auth_rrhh.role_has_permission(
        role, auth_rrhh.PERM_ROLES_MANAGE
    ):
        return "/configuracion"
    return "/"


def _has_permission(permission):
    if not _auth_enabled():
        return True
    current = _current_rrhh_user()
    if not current:
        return False
    entry = auth_rrhh.get_users().get((current.get("username") or "").lower()) or current
    selected_company = _selected_company_id_for_rrhh() or ""
    effective_role = auth_rrhh.get_role_for_context(entry, selected_company, branch=None)
    if not effective_role:
        effective_role = current.get("role") or "rrhh"
    return auth_rrhh.role_has_permission(effective_role, permission)


def _auth_json_error():
    return jsonify({"ok": False, "error": "No autorizado"}), 401


def _forbidden_json_error(message="No tenés permisos para esta acción."):
    return jsonify({"ok": False, "error": message}), 403


def rrhh_auth_required(handler):
    @wraps(handler)
    def wrapped(*args, **kwargs):
        if not _auth_enabled():
            return handler(*args, **kwargs)
        if _current_rrhh_user() is not None:
            return handler(*args, **kwargs)
        if request.path.startswith("/api/"):
            return _auth_json_error()
        return redirect(url_for("login_page", next=_request_path_with_query()))

    return wrapped


def rrhh_permission_required(permission, message="No tenés permisos para esta acción."):
    def decorator(handler):
        @wraps(handler)
        def wrapped(*args, **kwargs):
            if not _auth_enabled():
                return handler(*args, **kwargs)
            if _current_rrhh_user() is None:
                if request.path.startswith("/api/"):
                    return _auth_json_error()
                return redirect(url_for("login_page", next=_request_path_with_query()))
            if not _has_permission(permission):
                if request.path.startswith("/api/"):
                    return _forbidden_json_error(message)
                return (message, 403)
            return handler(*args, **kwargs)

        return wrapped

    return decorator


def _session_chat_id():
    chat_id = _sess().get("chat_session_id")
    if chat_id:
        return chat_id
    chat_id = _new_conversation_id()
    _sess()["chat_session_id"] = chat_id
    return chat_id


def _new_history_id():
    return f"hist-{uuid.uuid4().hex[:14]}"


def _add_chat_history(
    conversation_id,
    remitente,
    texto,
    canal="asistente",
    agente="",
    metadata=None,
):
    payload = {
        "history_id": _new_history_id(),
        "conversation_id": str(conversation_id or "sin_conversacion"),
        "remitente": str(remitente or "desconocido"),
        "texto": str(texto or "").strip(),
        "canal": str(canal or "asistente"),
        "agente": str(agente or "").strip(),
        "fecha": _utc_now(),
        "metadata": metadata or {},
    }
    if not payload["texto"]:
        return

    if chatbot.db:
        chatbot.db.collection("chat_historial").add(payload)
        return

    IN_MEMORY_CHAT_HISTORY.append(payload)


def _list_chat_history(limit=300):
    if chatbot.db:
        rows = []
        for doc in chatbot.db.collection("chat_historial").stream():
            data = doc.to_dict() or {}
            data["id"] = doc.id
            rows.append(data)
    else:
        rows = list(IN_MEMORY_CHAT_HISTORY)

    rows.sort(
        key=lambda x: _as_utc_naive(x.get("fecha")) or datetime.min,
        reverse=True,
    )
    return rows[:limit]


def _serialize_history_item(item):
    fecha = _as_utc_aware(item.get("fecha"))
    return {
        "id": str(item.get("id") or item.get("history_id") or ""),
        "conversation_id": str(item.get("conversation_id") or ""),
        "remitente": str(item.get("remitente") or ""),
        "canal": str(item.get("canal") or ""),
        "agente": str(item.get("agente") or ""),
        "texto": str(item.get("texto") or ""),
        "fecha": _fmt_fecha(fecha),
        "fecha_iso": _iso_utc(fecha),
        "metadata": item.get("metadata") or {},
    }


def _set_handoff_session(conversation_id):
    _sess()["handoff_conversation_id"] = conversation_id
    _sess()["last_rrhh_seen_iso"] = ""


def _clear_handoff_session():
    _sess().pop("handoff_conversation_id", None)
    _sess().pop("last_rrhh_seen_iso", None)


def _get_handoff_session_id():
    return _sess().get("handoff_conversation_id")


def _get_last_seen_rrhh():
    raw = _sess().get("last_rrhh_seen_iso", "")
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw)
        return _as_utc_naive(parsed)
    except Exception:
        return None


def _set_last_seen_rrhh(dt):
    dt2 = _as_utc_naive(dt)
    session["last_rrhh_seen_iso"] = dt2.isoformat() if dt2 else ""


def _from_firestore_doc(snapshot):
    data = snapshot.to_dict() or {}
    data["id"] = snapshot.id
    return data


def _normalize_phone_for_match(phone):
    """Normaliza número para comparar (whatsapp:+549... o +549... -> dígitos)."""
    p = (phone or "").strip().lower()
    if not p:
        return ""
    if p.startswith("whatsapp:"):
        p = p[9:].strip()
    return "".join(c for c in p if c.isdigit())


def _find_open_handoff_by_whatsapp_phone(phone):
    """Devuelve el conversation_id de un handoff abierto para este número de WhatsApp, o None."""
    if not phone:
        return None
    norm = _normalize_phone_for_match(phone)
    if not norm:
        return None
    for conv in _list_handoffs(include_closed=False, limit=50):
        to_phone = (conv.get("whatsapp_to_phone") or "").strip()
        if not to_phone:
            continue
        if _normalize_phone_for_match(to_phone) == norm:
            return conv.get("id")
    return None


def _fetch_handoff(conversation_id):
    if chatbot.db:
        doc = chatbot.db.collection("rrhh_handoffs").document(conversation_id).get()
        if not doc.exists:
            return None
        data = doc.to_dict() or {}
        data["id"] = conversation_id
        return data

    return IN_MEMORY_HANDOFFS.get(conversation_id)


def _upsert_handoff(conversation_id, payload, merge=True):
    if chatbot.db:
        doc_ref = chatbot.db.collection("rrhh_handoffs").document(conversation_id)
        doc_ref.set(payload, merge=merge)
        return

    existing = IN_MEMORY_HANDOFFS.get(conversation_id, {})
    if merge:
        existing.update(payload)
        IN_MEMORY_HANDOFFS[conversation_id] = existing
    else:
        IN_MEMORY_HANDOFFS[conversation_id] = dict(payload)
    IN_MEMORY_HANDOFFS[conversation_id]["id"] = conversation_id
    IN_MEMORY_HANDOFFS[conversation_id].setdefault("mensajes", [])


def _branch_name(item):
    if isinstance(item, dict) and item.get("name") is not None:
        return str(item.get("name") or "").strip()
    return str(item or "").strip()


def _list_handoffs(include_closed=False, limit=100, company_id=None, branches=None, areas=None):
    if chatbot.db:
        docs = [
            _from_firestore_doc(doc)
            for doc in chatbot.db.collection("rrhh_handoffs").stream()
        ]
    else:
        docs = [dict(value) for value in IN_MEMORY_HANDOFFS.values()]

    filtered = []
    target_company = _normalize_company_id(company_id)
    branch_set = None
    if branches is not None and len(branches) > 0:
        branch_set = {_branch_name(b).lower() for b in branches if _branch_name(b)}
    area_set = None
    if areas is not None and len(areas) > 0:
        area_set = {str(a).strip().lower() for a in areas if str(a).strip()}
    for item in docs:
        estado = str(item.get("estado") or "").strip().lower()
        if not include_closed and estado == HANDOFF_STATUS_CLOSED:
            continue
        if target_company:
            item_company = _normalize_company_id(item.get("company_id"))
            if item_company != target_company:
                continue
        if branch_set is not None:
            conv_branch = str(item.get("branch") or "").strip().lower()
            if conv_branch and conv_branch not in branch_set:
                continue
        if area_set is not None:
            conv_area = str(item.get("area") or "").strip().lower()
            if conv_area and conv_area not in area_set:
                continue
        filtered.append(item)

    filtered.sort(key=lambda x: _as_utc_naive(x.get("updated_at")) or datetime.min, reverse=True)
    return filtered[:limit]


def _all_handoff_records_for_stats():
    if chatbot.db:
        rows = []
        for doc in chatbot.db.collection("rrhh_handoffs").stream():
            payload = doc.to_dict() or {}
            payload["id"] = doc.id
            rows.append(payload)
        return rows
    return [dict(value) for value in IN_MEMORY_HANDOFFS.values()]


def _companies_for_filter_context():
    """Lista de empresas con branches y areas para filtros (estadísticas, historial)."""
    current = _current_rrhh_user()
    companies = (
        _companies_for_user(current)
        if current
        else _list_companies(include_inactive=False)
    )
    out = []
    for c in companies:
        cid = c.get("company_id")
        if not cid:
            continue
        branches = []
        for b in (c.get("branches") or []):
            name = _branch_name(b)
            if name:
                branches.append({"name": name})
        areas = _get_all_areas_for_company(c)
        areas_list = [str(a).strip() for a in (areas or []) if str(a).strip()]
        out.append({
            "company_id": cid,
            "company_name": (c.get("company_name") or cid).strip(),
            "branches": branches,
            "areas": areas_list,
        })
    return out


def _add_handoff_message(
    conversation_id,
    remitente,
    texto,
    agente="",
    visible_to_colaborador=True,
    media_url=None,
):
    now = _utc_now()
    texto_str = str(texto).strip()
    media_list = []
    if media_url is not None:
        if isinstance(media_url, (list, tuple)):
            media_list = [str(u).strip() for u in media_url if u and str(u).strip().startswith("http")]
        elif isinstance(media_url, str) and media_url.strip().startswith("http"):
            media_list = [media_url.strip()]
    payload = {
        "remitente": remitente,
        "texto": texto_str,
        "agente": str(agente or "").strip(),
        "fecha": now,
        "visible_to_colaborador": bool(visible_to_colaborador),
    }
    if media_list:
        payload["media_url"] = media_list

    if chatbot.db:
        (
            chatbot.db.collection("rrhh_handoffs")
            .document(conversation_id)
            .collection("mensajes")
            .add(payload)
        )
    else:
        conv = IN_MEMORY_HANDOFFS.setdefault(conversation_id, {"id": conversation_id})
        conv.setdefault("mensajes", []).append(payload)

    _upsert_handoff(
        conversation_id,
        {
            "updated_at": now,
            "ultimo_mensaje": payload["texto"],
            "ultimo_remitente": str(remitente or "").strip().lower(),
            "ultimo_mensaje_fecha": now,
        },
        merge=True,
    )
    _add_chat_history(
        conversation_id=conversation_id,
        remitente=remitente,
        texto=payload["texto"],
        canal="rrhh",
        agente=payload["agente"],
        metadata={"visible_to_colaborador": payload["visible_to_colaborador"]},
    )
    # Enviar por WhatsApp al colaborador si la conversación es por WA: mensajes del agente y cierre de conversación
    if payload["visible_to_colaborador"] and remitente in ("rrhh", "sistema"):
        has_text = bool(payload.get("texto"))
        has_media = bool(payload.get("media_url"))
        if has_text or has_media:
            conv = _fetch_handoff(conversation_id)
            to_phone = (conv or {}).get("whatsapp_to_phone", "").strip()
            from_number = (conv or {}).get("whatsapp_from_number", "").strip()
            if to_phone and from_number:
                try:
                    from twilio_whatsapp import send_one
                    send_one(
                        to_phone,
                        body=payload.get("texto") or None,
                        phone_number_id=from_number,
                        media_url=payload.get("media_url") or None,
                    )
                except Exception:
                    pass


def _list_handoff_messages(conversation_id, limit=300):
    if chatbot.db:
        docs = (
            chatbot.db.collection("rrhh_handoffs")
            .document(conversation_id)
            .collection("mensajes")
            .stream()
        )
        rows = []
        for doc in docs:
            data = doc.to_dict() or {}
            data["id"] = doc.id
            rows.append(data)
    else:
        conv = IN_MEMORY_HANDOFFS.get(conversation_id, {})
        rows = list(conv.get("mensajes", []))

    rows.sort(key=lambda x: _as_utc_naive(x.get("fecha")) or datetime.min)
    return rows[-limit:]


def _join_messages_for_user(messages):
    if not messages:
        return ""
    lineas = []
    for msg in messages:
        remitente = str(msg.get("remitente") or "").strip().lower()
        texto = str(msg.get("texto") or "").strip()
        agente = str(msg.get("agente") or "").strip()
        fecha = _fmt_fecha(msg.get("fecha"))
        if remitente == "rrhh":
            prefijo = f"👩‍💼 Agente{f' ({agente})' if agente else ''}"
        elif remitente == "sistema":
            prefijo = "ℹ️ Sistema"
        else:
            prefijo = "📩"
        lineas.append(f"{prefijo} [{fecha}]: {texto}")
    return "\n".join(lineas)


def _take_handoff(conversation_id, agente, auto_taken=False):
    conv = _fetch_handoff(conversation_id)
    if not conv:
        return False
    agent = _agent_payload(
        display_name=(agente or {}).get("display_name") if isinstance(agente, dict) else agente,
        agent_id=(agente or {}).get("agent_id") if isinstance(agente, dict) else "",
        role=(agente or {}).get("role") if isinstance(agente, dict) else "rrhh",
        company_id=(
            (agente or {}).get("company_id")
            if isinstance(agente, dict)
            else conv.get("company_id")
        ),
    )

    # Evita mensajes de sistema duplicados cuando la conversación ya estaba tomada
    # por el mismo agente.
    estado_actual = str(conv.get("estado") or "").strip().lower()
    agente_actual_id = str(conv.get("rrhh_agente_id") or "").strip().lower()
    agente_actual_nombre = str(conv.get("rrhh_agente") or "").strip().lower()
    if estado_actual == HANDOFF_STATUS_ACTIVE and (
        (agent.get("agent_id") and agent.get("agent_id") == agente_actual_id)
        or (
            not agent.get("agent_id")
            and agent.get("display_name")
            and agent.get("display_name").strip().lower() == agente_actual_nombre
        )
    ):
        _upsert_handoff(
            conversation_id,
            {"updated_at": _utc_now()},
            merge=True,
        )
        return True

    _upsert_handoff(
        conversation_id,
        {
            "estado": HANDOFF_STATUS_ACTIVE,
            "rrhh_agente": agent["display_name"],
            "rrhh_agente_id": agent["agent_id"],
            "updated_at": _utc_now(),
            "rrhh_asignacion_automatica": bool(auto_taken),
        },
        merge=True,
    )
    if auto_taken:
        _add_handoff_message(
            conversation_id,
            remitente="sistema",
            texto=f"Tu conversación fue asignada automáticamente a un agente ({agent['display_name']}).",
            visible_to_colaborador=False,
        )
    else:
        _add_handoff_message(
            conversation_id,
            remitente="sistema",
            texto=f"Tu conversación fue tomada por un agente ({agent['display_name']}).",
        )
    return True


def _close_handoff(conversation_id, quien):
    conv = _fetch_handoff(conversation_id)
    if not conv:
        return False
    _upsert_handoff(
        conversation_id,
        {
            "estado": HANDOFF_STATUS_CLOSED,
            "updated_at": _utc_now(),
        },
        merge=True,
    )
    _add_handoff_message(
        conversation_id,
        remitente="sistema",
        texto=f"La conversación fue cerrada por {quien}.",
    )
    return True


def _handoff_auto_close_policy(company=None):
    current = company if isinstance(company, dict) else _current_company()
    enabled = _normalize_bool_flag(current.get("handoff_auto_close_enabled"), default=False)
    minutes = _normalize_auto_close_minutes(
        current.get("handoff_auto_close_minutes", AUTO_CLOSE_DEFAULT_MINUTES)
    )
    if not enabled or minutes <= 0:
        return False, 0
    return True, minutes


def _handoff_last_activity(conv):
    if not isinstance(conv, dict):
        return None
    return (
        _as_utc_naive(conv.get("ultimo_mensaje_fecha"))
        or _as_utc_naive(conv.get("updated_at"))
        or _as_utc_naive(conv.get("created_at"))
    )


def _auto_close_expired_handoffs(company=None, force=False, override_minutes=None):
    target_company = company if isinstance(company, dict) else _current_company()
    company_id = _normalize_company_id(target_company.get("company_id"))
    if not company_id:
        return {
            "company_id": "",
            "auto_close_enabled": False,
            "auto_close_minutes": 0,
            "closed_count": 0,
            "checked_count": 0,
        }

    enabled, minutes = _handoff_auto_close_policy(target_company)
    if override_minutes is not None:
        minutes = _normalize_auto_close_minutes(override_minutes)
        enabled = minutes > 0
    if not enabled:
        return {
            "company_id": company_id,
            "auto_close_enabled": False,
            "auto_close_minutes": 0,
            "closed_count": 0,
            "checked_count": 0,
        }

    now = _as_utc_naive(_utc_now()) or datetime.utcnow()
    conversations = _list_handoffs(include_closed=False, limit=1000, company_id=company_id)
    closed_count = 0
    checked_count = 0
    for conv in conversations:
        estado = str(conv.get("estado") or "").strip().lower()
        if estado not in {HANDOFF_STATUS_PENDING, HANDOFF_STATUS_ACTIVE}:
            continue
        checked_count += 1
        conversation_id = str(conv.get("conversation_id") or conv.get("id") or "").strip()
        if not conversation_id:
            continue
        last_activity = _handoff_last_activity(conv)
        if last_activity is None:
            continue
        idle_minutes = (now - last_activity).total_seconds() / 60.0
        if idle_minutes < minutes:
            continue
        if _close_handoff(
            conversation_id,
            f"sistema por inactividad ({minutes} min)",
        ):
            closed_count += 1

    return {
        "company_id": company_id,
        "auto_close_enabled": True,
        "auto_close_minutes": minutes,
        "closed_count": closed_count,
        "checked_count": checked_count,
        "forced": bool(force),
    }


def _reassign_handoff(conversation_id, agente_destino, reasignado_por=""):
    conv = _fetch_handoff(conversation_id)
    if not conv:
        return False, "Conversación no encontrada"
    target = _agent_payload(
        display_name=(agente_destino or {}).get("display_name")
        if isinstance(agente_destino, dict)
        else agente_destino,
        agent_id=(agente_destino or {}).get("agent_id")
        if isinstance(agente_destino, dict)
        else "",
        role=(agente_destino or {}).get("role")
        if isinstance(agente_destino, dict)
        else "rrhh",
        company_id=(
            (agente_destino or {}).get("company_id")
            if isinstance(agente_destino, dict)
            else conv.get("company_id")
        ),
    )
    if not target.get("display_name"):
        return False, "Agente destino inválido"

    _upsert_handoff(
        conversation_id,
        {
            "estado": HANDOFF_STATUS_ACTIVE,
            "rrhh_agente": target["display_name"],
            "rrhh_agente_id": target["agent_id"],
            "updated_at": _utc_now(),
            "rrhh_asignacion_automatica": False,
        },
        merge=True,
    )
    actor = str(reasignado_por or "").strip() or "sistema"
    _add_handoff_message(
        conversation_id,
        remitente="sistema",
        texto=f"Conversación reasignada a {target['display_name']} por {actor}.",
        visible_to_colaborador=False,
    )
    return True, ""


def _collect_new_messages_for_collaborator(conversation_id):
    last_seen = _get_last_seen_rrhh()
    messages = _list_handoff_messages(conversation_id)
    nuevos = []
    max_seen = last_seen
    for msg in messages:
        remitente = str(msg.get("remitente") or "").strip().lower()
        if remitente not in {"rrhh", "sistema"}:
            continue
        if remitente == "sistema" and msg.get("visible_to_colaborador", True) is False:
            continue
        fecha = _as_utc_naive(msg.get("fecha"))
        if last_seen is not None and fecha is not None and fecha <= last_seen:
            continue
        nuevos.append(msg)
        if fecha is not None and (max_seen is None or fecha > max_seen):
            max_seen = fecha

    if max_seen is not None:
        _set_last_seen_rrhh(max_seen)
    return nuevos


def construir_temas_map(company_id=None, temas_habilitados=None):
    """
    Construye el mapa número -> tema para el menú.
    Si temas_habilitados es una lista no vacía, solo se incluyen esos temas (normalizados).
    """
    if company_id is None:
        company_id = (_current_company() or {}).get("company_id")
    temas = chatbot.obtener_temas_desde_firestore(company_id=company_id)
    if not temas:
        temas = sorted(chatbot.FAQ_FALLBACK.keys(), key=chatbot.normalizar_texto)
    if temas_habilitados and isinstance(temas_habilitados, list):
        allow_set = {chatbot.normalizar_texto(t) for t in temas_habilitados}
        temas = [t for t in temas if chatbot.normalizar_texto(t) in allow_set]
    return {str(i): tema for i, tema in enumerate(temas, start=1)}


# Límite de temas mostrados en el menú (formato: 1. Tema, 2. Tema, ... H. Hablar con un agente)
MENU_TEMAS_LIMITE = 12


def construir_menu_texto(temas_map, permitir_hablar_con_humano=True):
    """Texto del menú en formato: Menú de temas disponibles: / 1. X / 2. Y / ... / H. Hablar con un agente."""
    lineas = ["Menú de temas disponibles:"]
    for numero, tema in temas_map.items():
        lineas.append(f"{numero}. {tema.capitalize()}")
    if permitir_hablar_con_humano:
        lineas.append("H. Hablar con un agente")
    return "\n".join(lineas)


def construir_acciones_menu(temas_map, limite=None, permitir_hablar_con_humano=True):
    """Botones del menú: numerados (1. Tema, 2. Tema, ...), opcional Ver menú completo, y H. Hablar con un agente."""
    if limite is None:
        limite = MENU_TEMAS_LIMITE
    acciones = []
    items = list(temas_map.items())
    for numero, tema in items[:limite]:
        acciones.append(_accion(f"{numero}. {tema.capitalize()}", numero, "topic"))

    if len(temas_map) > limite:
        acciones.append(_accion("Ver menú completo", "menu", "secondary"))

    if permitir_hablar_con_humano:
        acciones.append(_accion("H. Hablar con un agente", "h", "secondary"))
    return acciones


def construir_acciones_feedback():
    return [
        _accion("Sí", "si", "positive"),
        _accion("No", "no", "negative"),
        _accion("Nueva consulta", "menu", "secondary"),
    ]


def construir_acciones_sugerencias(consulta, temas_map, permitir_hablar_con_humano=True):
    sugerencias = chatbot.sugerir_temas(consulta, temas_map)
    acciones = []
    for tema in sugerencias[:4]:
        acciones.append(_accion(tema.capitalize(), tema, "topic"))
    acciones.append(_accion("Ver menú", "menu", "secondary"))
    if permitir_hablar_con_humano:
        acciones.append(_accion("H. Hablar con un agente", "h", "secondary"))
    return acciones


def construir_acciones_handoff():
    return [
        _accion("Actualizar mensajes", "__poll_rrhh__", "secondary"),
        _accion("Finalizar chat con agente", "__cerrar_rrhh__", "negative"),
    ]


def armar_respuesta_no_entendida(consulta, temas_map):
    lineas = [
        "⚠️ Lo siento, no tengo información registrada sobre eso.",
        "Probá con una palabra clave como: vacaciones, fraccionamiento, recibo o aguinaldo.",
        "También podés escribir 'menu' para ver todas las opciones.",
    ]
    sugerencias = chatbot.sugerir_temas(consulta, temas_map)
    if sugerencias:
        lineas.append(f"Tal vez quisiste decir: {', '.join(sugerencias)}")
    return "\n".join(lineas)


def limpiar_estado_conversacion():
    _sess().pop("pending_feedback_topic", None)


def _payload(
    reply,
    await_feedback=False,
    end_session=False,
    quick_actions=None,
    handoff_active=False,
):
    return {
        "reply": reply,
        "await_feedback": await_feedback,
        "end_session": end_session,
        "quick_actions": quick_actions or [],
        "handoff_active": handoff_active,
    }


def _firebase_project_id():
    if chatbot.db is None:
        return "modo_local_sin_firestore"
    return str(getattr(chatbot.db, "project", "desconocido"))


def _iniciar_handoff_rrhh(mensaje_usuario):
    chat_session_id = _session_chat_id()
    company = _current_company()
    company_id = company.get("company_id")
    active_id = _get_handoff_session_id()
    existing = _fetch_handoff(active_id) if active_id else None
    now = _utc_now()

    if existing is not None:
        estado_actual = str(existing.get("estado") or "").strip().lower()
        existing_company = _normalize_company_id(existing.get("company_id"))
        if estado_actual in {HANDOFF_STATUS_PENDING, HANDOFF_STATUS_ACTIVE} and existing_company == company_id:
            conversation_id = active_id
        else:
            _clear_handoff_session()
            conversation_id = _new_conversation_id()
            existing = None
    else:
        conversation_id = _new_conversation_id()

    if existing is None:
        collaborator_area = _sess().get("chat_context_area") or ""
        collaborator_branch = _sess().get("chat_context_branch") or ""
        assigned_agent = _select_auto_agent(
            company_id=company_id,
            branch=collaborator_branch or None,
            area=collaborator_area or None,
        )
        if not assigned_agent:
            assigned_agent = _select_auto_agent(company_id=company_id, branch=None, area=None)
        estado_inicial = HANDOFF_STATUS_ACTIVE if assigned_agent else HANDOFF_STATUS_PENDING
        handoff_payload = {
            "conversation_id": conversation_id,
            "company_id": company_id,
            "company_name": company.get("company_name"),
            "branch": collaborator_branch,
            "area": collaborator_area,
            "estado": estado_inicial,
            "created_at": now,
            "updated_at": now,
            "rrhh_agente": assigned_agent.get("display_name", "") if assigned_agent else "",
            "rrhh_agente_id": assigned_agent.get("agent_id", "") if assigned_agent else "",
            "rrhh_asignacion_automatica": bool(assigned_agent),
            "ultimo_mensaje": "",
            "ultima_consulta": mensaje_usuario.strip() or "Solicitud de derivación",
            "chat_session_id": chat_session_id,
        }
        if getattr(g, "whatsapp_from", None) and getattr(g, "whatsapp_to", None):
            handoff_payload["channel"] = "whatsapp"
            handoff_payload["whatsapp_to_phone"] = g.whatsapp_from
            handoff_payload["whatsapp_from_number"] = g.whatsapp_to
        _upsert_handoff(conversation_id, handoff_payload, merge=False)
        _add_handoff_message(
            conversation_id,
            remitente="sistema",
            texto="El colaborador solicitó hablar con un agente.",
            visible_to_colaborador=False,
        )
        if assigned_agent:
            _take_handoff(conversation_id, assigned_agent, auto_taken=True)

    if mensaje_usuario.strip():
        _add_handoff_message(
            conversation_id,
            remitente="colaborador",
            texto=mensaje_usuario,
        )
        _upsert_handoff(
            conversation_id,
            {
                "ultima_consulta": mensaje_usuario.strip(),
                "updated_at": now,
                "chat_session_id": chat_session_id,
            },
            merge=True,
        )

    _set_handoff_session(conversation_id)
    return conversation_id


def procesar_feedback_pendiente(texto_usuario, tema_pendiente, temas_map, permitir_hablar_con_humano=True, company_id=None):
    tipo, texto_norm = chatbot.clasificar_input_feedback(texto_usuario)

    if tipo == "feedback":
        guardado = chatbot.registrar_feedback(tema_pendiente, texto_norm, company_id=company_id)
        limpiar_estado_conversacion()
        if guardado:
            texto = (
                "¡Gracias por tu feedback! 🙌\n"
                "Si querés, escribime otra consulta o poné 'menu' para ver temas."
            )
        else:
            texto = (
                "⚠️ Recibí tu feedback, pero no pude guardarlo en la base de datos.\n"
                "Podés seguir usando el chat y revisar tu conexión Firebase."
            )
        return _payload(
            texto,
            quick_actions=construir_acciones_menu(temas_map, limite=6, permitir_hablar_con_humano=permitir_hablar_con_humano),
        )

    if tipo == "menu":
        limpiar_estado_conversacion()
        return _payload(
            construir_menu_texto(temas_map, permitir_hablar_con_humano=permitir_hablar_con_humano),
            quick_actions=construir_acciones_menu(temas_map, permitir_hablar_con_humano=permitir_hablar_con_humano),
        )

    if tipo == "salir":
        limpiar_estado_conversacion()
        return _payload(_farewell_message(), end_session=True)

    if tipo == "consulta":
        limpiar_estado_conversacion()
        return None

    return _payload(
        "Podés responder 'si' o 'no'. Si preferís, también podés escribir una nueva consulta.",
        await_feedback=True,
        quick_actions=construir_acciones_feedback(),
    )


def responder_chat(mensaje_usuario):
    company = _current_company()
    company_id = (company or {}).get("company_id")
    permitir = (company or {}).get("permitir_hablar_con_humano", True)
    temas_habilitados = (company or {}).get("temas_habilitados") or []
    temas_map = construir_temas_map(company_id=company_id, temas_habilitados=temas_habilitados)
    mensaje_norm = chatbot.normalizar_texto(mensaje_usuario)

    def _acciones_menu(limite=8):
        return construir_acciones_menu(temas_map, limite=limite, permitir_hablar_con_humano=permitir)

    if not mensaje_norm:
        return _payload(
            "No llegué a entender tu consulta. ¿Podés reformularla?",
            quick_actions=_acciones_menu(6),
        )

    if mensaje_norm in chatbot.PALABRAS_SALIDA:
        handoff_id = _get_handoff_session_id()
        if handoff_id:
            _close_handoff(handoff_id, "colaborador")
            _clear_handoff_session()
        return _payload(_farewell_message(), end_session=True)

    handoff_id = _get_handoff_session_id()
    if handoff_id:
        _auto_close_expired_handoffs(company=_current_company())
        conv = _fetch_handoff(handoff_id)
        if conv and str(conv.get("estado") or "").strip().lower() == HANDOFF_STATUS_CLOSED:
            _clear_handoff_session()
            handoff_id = None

    if handoff_id:
        if mensaje_norm in HANDOFF_END_COMMANDS:
            _close_handoff(handoff_id, "colaborador")
            _clear_handoff_session()
            return _payload(
                "✅ Cerré la conversación con el agente. Si querés, seguimos con el asistente virtual.",
                quick_actions=_acciones_menu(6),
            )

        # Si es un saludo, asumimos que quiere volver al bot (no derivar a agente).
        if chatbot.es_saludo(mensaje_norm) or mensaje_norm == "menu":
            _close_handoff(handoff_id, "colaborador")
            _clear_handoff_session()
            if mensaje_norm == "menu":
                return _payload(
                    construir_menu_texto(temas_map, permitir_hablar_con_humano=permitir),
                    quick_actions=construir_acciones_menu(temas_map, permitir_hablar_con_humano=permitir),
                )
            return _payload(
                chatbot.MENSAJE_BIENVENIDA,
                quick_actions=_acciones_menu(6),
            )

        if mensaje_norm in HANDOFF_POLL_COMMANDS:
            nuevos = _collect_new_messages_for_collaborator(handoff_id)
            if nuevos:
                return _payload(
                    _join_messages_for_user(nuevos),
                    handoff_active=True,
                    quick_actions=construir_acciones_handoff(),
                )
            conv = _fetch_handoff(handoff_id) or {}
            estado = str(conv.get("estado") or "").strip().lower()
            if estado == HANDOFF_STATUS_PENDING:
                texto = "⏳ Tu consulta sigue en cola. Un agente te responde en breve."
            else:
                agente = conv.get("rrhh_agente") or "el equipo"
                texto = f"🟢 Chat activo con {agente}. Aún no hay nuevos mensajes."
            return _payload(
                texto,
                handoff_active=True,
                quick_actions=construir_acciones_handoff(),
            )

        # Mientras está activo el handoff, los mensajes van al canal humano.
        media_urls_colab = getattr(g, "whatsapp_media_urls", None) or []
        _add_handoff_message(
            handoff_id,
            remitente="colaborador",
            texto=mensaje_usuario,
            media_url=media_urls_colab if media_urls_colab else None,
        )
        _upsert_handoff(
            handoff_id,
            {"ultima_consulta": mensaje_usuario.strip(), "updated_at": _utc_now()},
            merge=True,
        )
        conv = _fetch_handoff(handoff_id) or {}
        estado = str(conv.get("estado") or "").strip().lower()
        if estado == HANDOFF_STATUS_PENDING:
            texto = "📨 Mensaje enviado. Un agente todavía no tomó la conversación."
        else:
            agente = conv.get("rrhh_agente") or "un agente"
            texto = f"📨 Mensaje enviado a {agente}. Te responderán por este chat."
        return _payload(
            texto,
            handoff_active=True,
            quick_actions=construir_acciones_handoff(),
        )

    tema_pendiente = _sess().get("pending_feedback_topic")
    if tema_pendiente:
        payload = procesar_feedback_pendiente(mensaje_usuario, tema_pendiente, temas_map, permitir_hablar_con_humano=permitir, company_id=company_id)
        if payload is not None:
            return payload
        # Si llega una nueva consulta durante feedback, sigue flujo normal.

    if chatbot.solicita_contacto_rrhh(mensaje_norm):
        if not permitir:
            return _payload(
                "En este momento la derivación a un agente está desactivada para esta empresa. "
                "Para activarla: entrá a Preferencias en el panel, sección «Reglas del chat», elegí la empresa y marcá «Mostrar botón de derivación y permitir hablar con un agente», luego Guardar. "
                "Mientras tanto podés consultar el menú de temas.",
                quick_actions=_acciones_menu(6),
            )
        conversation_id = _iniciar_handoff_rrhh(mensaje_usuario)
        conv = _fetch_handoff(conversation_id) or {}
        assigned = str(conv.get("rrhh_agente") or "").strip()
        if assigned:
            respuesta = (
                "👩‍💼 Perfecto. Derivé tu consulta al equipo de atención.\n"
                f"Te asigné automáticamente con {assigned}. Podés seguir escribiendo por este chat."
            )
        else:
            respuesta = (
                "👩‍💼 Perfecto. Derivé tu consulta al equipo de atención.\n"
                "Te van a responder por este mismo chat. Podés seguir escribiendo aquí."
            )
        return _payload(
            respuesta,
            handoff_active=True,
            quick_actions=construir_acciones_handoff(),
        )

    if mensaje_norm == "menu":
        return _payload(
            construir_menu_texto(temas_map, permitir_hablar_con_humano=permitir),
            quick_actions=construir_acciones_menu(temas_map, permitir_hablar_con_humano=permitir),
        )

    respuesta, tema_id = chatbot.obtener_respuesta(mensaje_usuario, temas_map, company_id=company_id)
    if respuesta:
        requiere_feedback = tema_id not in chatbot.TEMAS_SIN_FEEDBACK
        if requiere_feedback:
            _sess()["pending_feedback_topic"] = tema_id
            respuesta = f"{respuesta}\n\n¿Esta información te fue de utilidad? (si/no)"
            return _payload(
                respuesta,
                await_feedback=True,
                quick_actions=construir_acciones_feedback(),
            )
        return _payload(
            respuesta,
            quick_actions=_acciones_menu(4),
        )

    guardado_pendiente = chatbot.registrar_pendiente(mensaje_usuario, company_id=company_id)
    respuesta = armar_respuesta_no_entendida(mensaje_usuario, temas_map)
    if not guardado_pendiente:
        respuesta += "\nℹ️ No pude registrar esta consulta en la base de datos."
    return _payload(
        respuesta,
        quick_actions=construir_acciones_sugerencias(mensaje_usuario, temas_map, permitir_hablar_con_humano=permitir),
    )


def _serialize_handoff(conv):
    updated_at = _as_utc_aware(conv.get("updated_at"))
    ultimo_mensaje_fecha = _as_utc_aware(conv.get("ultimo_mensaje_fecha")) or updated_at
    return {
        "conversation_id": conv.get("conversation_id") or conv.get("id"),
        "company_id": conv.get("company_id") or "",
        "company_name": conv.get("company_name") or "",
        "branch": conv.get("branch") or "",
        "area": conv.get("area") or "",
        "estado": conv.get("estado") or HANDOFF_STATUS_PENDING,
        "rrhh_agente": conv.get("rrhh_agente") or "",
        "rrhh_agente_id": conv.get("rrhh_agente_id") or "",
        "rrhh_asignacion_automatica": bool(conv.get("rrhh_asignacion_automatica")),
        "ultima_consulta": conv.get("ultima_consulta") or "",
        "ultimo_remitente": str(conv.get("ultimo_remitente") or "").strip().lower(),
        "ultimo_mensaje_iso": _iso_utc(ultimo_mensaje_fecha),
        "updated_at": _fmt_fecha(updated_at),
        "updated_at_iso": _iso_utc(updated_at),
    }


def _serialize_messages(messages):
    payload = []
    for msg in messages:
        fecha = _as_utc_aware(msg.get("fecha"))
        item = {
            "remitente": str(msg.get("remitente") or ""),
            "texto": str(msg.get("texto") or ""),
            "agente": str(msg.get("agente") or ""),
            "fecha": _fmt_fecha(fecha),
            "fecha_iso": _iso_utc(fecha),
        }
        if msg.get("media_url"):
            item["media_url"] = msg["media_url"] if isinstance(msg["media_url"], list) else [msg["media_url"]]
        payload.append(item)
    return payload


def _conversation_matches_selected_company(conv):
    if not isinstance(conv, dict):
        return False
    selected_company = _selected_company_id_for_rrhh()
    if not selected_company:
        return True
    return _normalize_company_id(conv.get("company_id")) == selected_company


def reset_in_memory_handoffs():
    IN_MEMORY_HANDOFFS.clear()
    IN_MEMORY_CHAT_HISTORY.clear()
    IN_MEMORY_ACTIVE_AGENTS.clear()
    IN_MEMORY_GENERAL_SETTINGS.clear()
    IN_MEMORY_COMPANIES.clear()


def _can_view_stats():
    if not _auth_enabled():
        return True
    return _has_permission(auth_rrhh.PERM_STATS_VIEW)


def _can_manage_preferences():
    if not _auth_enabled():
        return True
    return _has_permission(auth_rrhh.PERM_PREFERENCES_MANAGE)


@flask_app.get("/")
def home():
    """Vista principal: layout con sidebar de módulos y contenido en iframe (por defecto chat)."""
    requested_company = _normalize_company_id(request.args.get("empresa"))
    if requested_company and _get_company(requested_company, include_inactive=False):
        _set_company_session(requested_company)
    else:
        _set_company_session(session.get("company_id") or _default_company_id())
    settings = _apply_company_branding(_read_general_settings())
    company_name = settings.get("company_name") or "Empresa"
    hr_display = (settings.get("hr_team_name") or "Atención").strip()
    if hr_display.upper() == "RRHH":
        hr_display = "Atención"
    # Mostrar siempre todos los módulos en el sidebar; al hacer clic en uno protegido se redirige a login si hace falta.
    user = _current_rrhh_user()
    show_all = _auth_enabled() and user is None
    return render_template(
        "index.html",
        company_name=company_name,
        hr_team_name=hr_display,
        can_view_config=_can_manage_configuration() if not show_all else True,
        can_view_stats=_can_view_stats() if not show_all else True,
        can_manage_preferences=_can_manage_preferences() if not show_all else True,
        can_view_conversations=_has_permission(auth_rrhh.PERM_CONVERSATIONS_VIEW) if not show_all else True,
        can_view_history=_has_permission(auth_rrhh.PERM_HISTORY_VIEW) if not show_all else True,
        can_view_comunicados=_has_permission(auth_rrhh.PERM_COMUNICADOS_SEND) if not show_all else False,
    )


@flask_app.get("/chat")
def chat_page():
    """Contenido del chatbot para incrustar en el layout principal (iframe o vista por defecto)."""
    _clear_chat_context()
    step = _chat_context_step()
    if step == CHAT_CONTEXT_STEP_READY or step == CHAT_CONTEXT_STEP_AREA or step == CHAT_CONTEXT_STEP_BRANCH:
        requested_company = _normalize_company_id(
            session.get("chat_context_company_id") or session.get("company_id") or _default_company_id()
        )
        _set_company_session(requested_company)
    else:
        _set_company_session(session.get("company_id") or _default_company_id())

    settings = _apply_company_branding(_read_general_settings())
    company = _current_company()
    company_id = (company or {}).get("company_id")
    company_name = settings.get("company_name") or "Empresa"
    hr_display = (settings.get("hr_team_name") or "Atención").strip()
    if hr_display.upper() == "RRHH":
        hr_display = "Atención"

    if step == CHAT_CONTEXT_STEP_COMPANY:
        quick_actions_iniciales = _construir_acciones_empresas(limite=8)
        nombres_empresas = [a.get("label") or a.get("value") for a in quick_actions_iniciales if a.get("label") or a.get("value")]
        if nombres_empresas:
            bienvenida = f"👋 ¡Hola! ¿De qué empresa me hablás?\nMenú:\n" + "\n".join(nombres_empresas) + "\n\nEscribí el número o el nombre."
        else:
            bienvenida = "👋 ¡Hola! ¿De qué empresa me hablás? Elegí una opción o escribí el nombre."
    elif step == CHAT_CONTEXT_STEP_BRANCH:
        ctx_company_id = session.get("chat_context_company_id") or company_id
        company_for_branch = _get_company(ctx_company_id, include_inactive=False)
        area_name_company = (company_for_branch or {}).get("company_name") or ctx_company_id or "Empresa"
        quick_actions_iniciales = _construir_acciones_sucursales(ctx_company_id, limite=8)
        nombres_sucursales = [a.get("label") or a.get("value") for a in quick_actions_iniciales if a.get("label") or a.get("value")]
        if nombres_sucursales:
            bienvenida = f"¿De qué sucursal me hablás? (empresa: {area_name_company})\nMenú:\n" + "\n".join(nombres_sucursales) + "\n\nEscribí el número o el nombre."
        else:
            bienvenida = f"¿De qué sucursal me hablás? (empresa: {area_name_company})"
    elif step == CHAT_CONTEXT_STEP_AREA:
        ctx_company_id = session.get("chat_context_company_id") or company_id
        ctx_branch = session.get("chat_context_branch") or ""
        company_for_area = _get_company(ctx_company_id, include_inactive=False)
        area_name_company = (company_for_area or {}).get("company_name") or ctx_company_id or "Empresa"
        quick_actions_iniciales = _construir_acciones_areas(ctx_company_id, limite=8, branch=ctx_branch or None)
        nombres_areas = [a.get("label") or a.get("value") for a in quick_actions_iniciales if a.get("label") or a.get("value")]
        suf = f" (sucursal: {ctx_branch})" if ctx_branch else ""
        if nombres_areas:
            bienvenida = f"¿De qué área me hablás? (empresa: {area_name_company}{suf})\nMenú:\n" + "\n".join(nombres_areas) + "\n\nEscribí el número o el nombre."
        else:
            bienvenida = f"¿De qué área me hablás? (empresa: {area_name_company}{suf})"
    else:
        permitir = (company or {}).get("permitir_hablar_con_humano", True)
        temas_habilitados = (company or {}).get("temas_habilitados") or []
        temas_map = construir_temas_map(company_id=company_id, temas_habilitados=temas_habilitados)
        area_ctx = session.get("chat_context_area") or ""
        branch_ctx = session.get("chat_context_branch") or ""
        partes = []
        if branch_ctx:
            partes.append(f"sucursal: {branch_ctx}")
        if area_ctx:
            partes.append(f"área: {area_ctx}")
        if partes:
            bienvenida = f"👋 ¡Hola! Soy el asistente de {hr_display} de {company_name} ({', '.join(partes)}). ¿En qué puedo ayudarte hoy?"
        else:
            bienvenida = f"👋 ¡Hola! Soy el asistente de {hr_display} de {company_name}. ¿En qué puedo ayudarte hoy?"
        quick_actions_iniciales = construir_acciones_menu(temas_map, limite=6, permitir_hablar_con_humano=permitir)

    return render_template(
        "chat.html",
        bienvenida=bienvenida,
        quick_actions_iniciales=quick_actions_iniciales,
        company_name=company_name,
        hr_team_name=hr_display,
    )


@flask_app.after_request
def add_no_cache_headers(response):
    # Evita cache agresivo de Safari en páginas/API dinámicas.
    if not request.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


@flask_app.get("/rrhh")
@rrhh_permission_required(
    auth_rrhh.PERM_CONVERSATIONS_VIEW,
    message="No tenés permisos para ver el panel de conversaciones.",
)
def rrhh_page():
    company = _set_company_session(session.get("company_id") or _default_company_id())
    settings = _apply_company_branding(_read_general_settings())
    current_user = _current_rrhh_user()
    available_companies = (
        _companies_for_user(current_user) if current_user else _list_companies(include_inactive=False)
    )
    return render_template(
        "rrhh.html",
        auth_enabled=_auth_enabled(),
        rrhh_user=current_user,
        can_manage_users=False,
        can_manage_roles=False,
        can_manage_config=_can_manage_configuration(),
        available_companies=available_companies,
        company_name=settings.get("company_name"),
        hr_team_name=settings.get("hr_team_name"),
        selected_company_id=company.get("company_id"),
        selected_company_name=company.get("company_name"),
    )


@flask_app.get("/configuracion")
@rrhh_auth_required
def configuracion_page():
    if not _can_manage_configuration():
        return ("No tenés permisos para acceder a configuración.", 403)
    company = _set_company_session(session.get("company_id") or _default_company_id())
    settings = _read_general_settings()
    companies_raw = _list_companies(include_inactive=True)
    companies = [_company_for_api(c) for c in companies_raw]
    return render_template(
        "configuracion.html",
        auth_enabled=_auth_enabled(),
        rrhh_user=_current_rrhh_user(),
        can_manage_users=_has_permission(auth_rrhh.PERM_USERS_MANAGE),
        can_manage_roles=_has_permission(auth_rrhh.PERM_ROLES_MANAGE),
        can_manage_general=_can_manage_general_config(),
        general_settings=settings,
        companies=companies,
        selected_company_id=company.get("company_id"),
    )


@flask_app.get("/historial")
@rrhh_permission_required(
    auth_rrhh.PERM_HISTORY_VIEW,
    message="No tenés permisos para ver el historial.",
)
def historial_page():
    return render_template(
        "historial.html",
        auth_enabled=_auth_enabled(),
        rrhh_user=_current_rrhh_user(),
    )


def _normalize_phones_for_comunicado(raw_list):
    """Convierte una lista de entradas (números, con espacios/comas) en una lista de números E.164.
    Números argentinos de 10 dígitos (ej. 3515416836) se convierten a +5493515416836."""
    out = []
    seen = set()
    for item in raw_list:
        s = str(item or "").strip()
        if not s:
            continue
        for part in s.replace(",", " ").replace(";", " ").split():
            num = "".join(c for c in part if c.isdigit() or c == "+").strip()
            if not num:
                continue
            if num.startswith("+"):
                num = num.lstrip("+")
            digits = "".join(c for c in num if c.isdigit())
            # Argentina: 10 dígitos sin código país -> agregar 54 y 9 (móvil)
            if len(digits) == 10 and not digits.startswith("54"):
                digits = "54" + "9" + digits
            if not digits:
                continue
            normalized = "+" + digits
            if normalized != "+" and normalized not in seen:
                seen.add(normalized)
                out.append(normalized)
    return out


@flask_app.get("/comunicados")
@rrhh_permission_required(
    auth_rrhh.PERM_COMUNICADOS_SEND,
    message="No tenés permisos para enviar comunicados.",
)
def comunicados_page():
    """Pantalla para enviar comunicados por WhatsApp: elegir empresa, cargar contactos, escribir mensaje."""
    company = _set_company_session(session.get("company_id") or _default_company_id())
    current_user = _current_rrhh_user()
    available_companies = (
        _companies_for_user(current_user) if current_user else _list_companies(include_inactive=False)
    )
    return render_template(
        "comunicados.html",
        auth_enabled=_auth_enabled(),
        rrhh_user=current_user,
        available_companies=available_companies,
        selected_company_id=company.get("company_id"),
        selected_company_name=company.get("company_name"),
    )


COMUNICADOS_CONTACTOS_COLLECTION = "comunicados_contactos"


def _get_comunicados_contactos(company_id):
    """Lista de contactos guardados para comunicados (por empresa)."""
    cid = _normalize_company_id(company_id)
    if not cid:
        return []
    if chatbot.db:
        doc = chatbot.db.collection(COMUNICADOS_CONTACTOS_COLLECTION).document(cid).get()
        if doc.exists:
            data = doc.to_dict() or {}
            return list(data.get("contactos") or [])
    return []


def _add_comunicado_contacto(company_id, nombre, telefono, legajo=None):
    """Agrega un contacto a la lista de la empresa (nombre, teléfono, legajo opcional)."""
    cid = _normalize_company_id(company_id)
    if not cid:
        return False
    nombre = str(nombre or "").strip() or "Sin nombre"
    telefono = str(telefono or "").strip()
    if not telefono:
        return False
    legajo = str(legajo or "").strip() if legajo is not None else ""
    if chatbot.db:
        doc_ref = chatbot.db.collection(COMUNICADOS_CONTACTOS_COLLECTION).document(cid)
        doc = doc_ref.get()
        contactos = list((doc.to_dict() or {}).get("contactos") or []) if doc.exists else []
        contactos.append({"nombre": nombre, "telefono": telefono, "legajo": legajo})
        doc_ref.set({"contactos": contactos}, merge=True)
        return True
    return False


@flask_app.get("/api/comunicados/plantilla")
@rrhh_permission_required(
    auth_rrhh.PERM_COMUNICADOS_SEND,
    message="Sin permiso.",
)
def api_comunicados_plantilla():
    """Descarga plantilla CSV (para abrir en Excel: guardar como CSV y subir). Columnas: teléfono, nombre, legajo."""
    from flask import Response
    csv_content = "\ufeffteléfono,nombre,legajo\n+5491112345678,Ejemplo,12345\n"
    return Response(csv_content, mimetype="text/csv", headers={
        "Content-Disposition": "attachment; filename=plantilla_contactos_comunicados.csv",
    })


@flask_app.get("/api/comunicados/contactos")
@rrhh_permission_required(
    auth_rrhh.PERM_COMUNICADOS_SEND,
    message="Sin permiso.",
)
def api_comunicados_contactos_list():
    """Lista contactos guardados para la empresa (para seleccionar destinatarios)."""
    company_id = _normalize_company_id(request.args.get("company_id") or "")
    contactos = _get_comunicados_contactos(company_id)
    return jsonify({"ok": True, "contactos": contactos})


@flask_app.post("/api/comunicados/contactos")
@rrhh_permission_required(
    auth_rrhh.PERM_COMUNICADOS_SEND,
    message="Sin permiso.",
)
def api_comunicados_contactos_add():
    """Agrega un contacto a la lista de la empresa (nombre, teléfono, legajo opcional)."""
    data = request.get_json(silent=True) or {}
    company_id = _normalize_company_id(data.get("company_id") or "")
    nombre = str(data.get("nombre") or "").strip()
    telefono = str(data.get("telefono") or "").strip()
    legajo = data.get("legajo")
    if not telefono:
        return jsonify({"ok": False, "error": "El teléfono es obligatorio."}), 400
    if _add_comunicado_contacto(company_id, nombre or "Sin nombre", telefono, legajo=legajo):
        return jsonify({"ok": True, "contactos": _get_comunicados_contactos(company_id)})
    return jsonify({"ok": False, "error": "No se pudo guardar."}), 500


def _remove_comunicado_contacto(company_id, telefono):
    """Elimina un contacto de la lista de la empresa por teléfono (misma normalización que envío)."""
    cid = _normalize_company_id(company_id)
    if not cid:
        return False
    telefono = str(telefono or "").strip()
    if not telefono:
        return False
    normalized_input_list = _normalize_phones_for_comunicado([telefono])
    if not normalized_input_list:
        return False
    normalized_input = normalized_input_list[0]
    if chatbot.db:
        doc_ref = chatbot.db.collection(COMUNICADOS_CONTACTOS_COLLECTION).document(cid)
        doc = doc_ref.get()
        contactos = list((doc.to_dict() or {}).get("contactos") or []) if doc.exists else []
        contactos_new = []
        removed = False
        for c in contactos:
            tel_stored = (c.get("telefono") or "").strip()
            norm_stored = _normalize_phones_for_comunicado([tel_stored])
            if norm_stored and norm_stored[0] == normalized_input and not removed:
                removed = True
                continue
            contactos_new.append(c)
        if not removed:
            return False
        doc_ref.set({"contactos": contactos_new}, merge=True)
        return True
    return False


@flask_app.delete("/api/comunicados/contactos")
@rrhh_permission_required(
    auth_rrhh.PERM_COMUNICADOS_SEND,
    message="Sin permiso.",
)
def api_comunicados_contactos_remove():
    """Elimina un contacto de la lista de la empresa (por company_id y telefono)."""
    data = request.get_json(silent=True) or {}
    company_id = _normalize_company_id(data.get("company_id") or "")
    telefono = str(data.get("telefono") or "").strip()
    if not company_id or not telefono:
        return jsonify({"ok": False, "error": "Faltan company_id o teléfono."}), 400
    if _remove_comunicado_contacto(company_id, telefono):
        return jsonify({"ok": True, "contactos": _get_comunicados_contactos(company_id)})
    return jsonify({"ok": False, "error": "No se encontró el contacto o no se pudo eliminar."}), 404


@flask_app.post("/api/comunicados/enviar")
@rrhh_permission_required(
    auth_rrhh.PERM_COMUNICADOS_SEND,
    message="No tenés permisos para enviar comunicados.",
)
def api_comunicados_enviar():
    """Envía un comunicado por WhatsApp a la lista de destinatarios (Twilio, en lotes)."""
    data = request.get_json(silent=True) or {}
    company_id = _normalize_company_id(data.get("company_id") or "")
    destinatarios_raw = data.get("destinatarios")
    if isinstance(destinatarios_raw, list):
        phones = _normalize_phones_for_comunicado(destinatarios_raw)
    elif isinstance(destinatarios_raw, str):
        phones = _normalize_phones_for_comunicado([destinatarios_raw])
    else:
        phones = []
    mensaje_raw = str(data.get("mensaje") or "").strip()
    try:
        mensaje = mensaje_raw.encode("utf-8", errors="replace").decode("utf-8")
    except Exception:
        mensaje = "".join(c for c in mensaje_raw if ord(c) < 0xD800 or ord(c) > 0xDFFF)
    imagen_url = (data.get("imagen_url") or data.get("media_url") or "").strip()
    if isinstance(imagen_url, list):
        media_urls = [u.strip() for u in imagen_url if isinstance(u, str) and u.strip()]
    else:
        media_urls = [imagen_url] if imagen_url else []

    if not phones:
        return jsonify({"ok": False, "error": "No hay destinatarios. Pegá números o importá un archivo."}), 400
    if not mensaje and not media_urls:
        return jsonify({"ok": False, "error": "Escribí el texto del comunicado o agregá una imagen (URL)."}), 400

    phone_number_id = (data.get("whatsapp_phone") or "").strip()
    if not phone_number_id and company_id:
        company = _get_company(company_id, include_inactive=False)
        if company:
            nums = company.get("whatsapp_numbers") or []
            label = (data.get("whatsapp_label") or "").strip().lower()
            if label and nums:
                for line in nums:
                    if (str(line.get("label") or "")).strip().lower() == label:
                        phone_number_id = (line.get("phone") or "").strip()
                        break
            if not phone_number_id and nums:
                phone_number_id = (nums[0].get("phone") or "").strip()
    if not phone_number_id:
        phone_number_id = os.getenv("TWILIO_WHATSAPP_FROM", "").strip()
    if not phone_number_id:
        return jsonify({"ok": False, "error": "WhatsApp no configurado (falta TWILIO_WHATSAPP_FROM o números por empresa)."}), 503
    if not phone_number_id.startswith("whatsapp:"):
        try:
            from twilio_whatsapp import _format_to_whatsapp
            phone_number_id = _format_to_whatsapp(phone_number_id) or phone_number_id
        except Exception:
            pass

    try:
        from whatsapp_broadcast import broadcast_messages
    except ImportError:
        return jsonify({"ok": False, "error": "Módulo de envío no disponible."}), 503

    result = broadcast_messages(
        phone_list=phones,
        body_text=mensaje or None,
        phone_number_id=phone_number_id,
        media_url=media_urls if media_urls else None,
    )
    sent = result.get("sent", 0)
    failed = result.get("failed", 0)
    total = result.get("total", 0)
    resp = {
        "ok": True,
        "sent": sent,
        "failed": failed,
        "total": total,
        "batches_used": result.get("batches_used", 0),
    }
    if failed > 0:
        try:
            from twilio_whatsapp import last_twilio_error as twilio_err
            err_text = (twilio_err or "").strip()
            err_lower = err_text.lower()
            if "50 daily" in err_lower or ("exceeded" in err_lower and "limit" in err_lower) or "63038" in err_lower:
                resp["error_detail"] = (
                    "Tu cuenta Twilio alcanzó el límite de 50 mensajes por día (cuenta trial). "
                    "Mañana se reinicia el límite, o pasate a una cuenta de pago en twilio.com para enviar más."
                )
            else:
                resp["error_detail"] = (
                    "Algunos o todos los envíos fallaron. Revisá TWILIO_WHATSAPP_FROM, "
                    "que los números tengan WhatsApp y que la URL de la imagen sea pública (Twilio tiene que poder descargarla)."
                )
                if err_text:
                    resp["error_detail"] += " Error de Twilio: " + err_text[:400]
        except Exception:
            resp["error_detail"] = (
                "Algunos o todos los envíos fallaron. Revisá en el servidor TWILIO_WHATSAPP_FROM, "
                "TWILIO_ACCOUNT_SID y TWILIO_AUTH_TOKEN. Ver consola del servidor para el error."
            )
    return jsonify(resp)


@flask_app.get("/estadisticas")
@rrhh_auth_required
def stats_page():
    if not _can_view_stats():
        return ("No tenés permisos para ver estadísticas.", 403)
    return render_template("stats.html")


@flask_app.get("/preferencias")
@rrhh_auth_required
def preferencias_page():
    """Preferencias de uso: modo oscuro/claro, empresa activa, autocierre y reglas del chat."""
    if not _can_manage_preferences():
        return ("No tenés permisos para gestionar preferencias.", 403)
    return render_template("preferencias.html")


def _process_chat_turn(mensaje_trim):
    """Procesa un mensaje del chat y devuelve el dict de respuesta (reply, quick_actions, etc.). Usado por /api/chat y por el webhook de WhatsApp."""
    _apply_company_branding(_read_general_settings())
    mensaje = mensaje_trim
    step = _chat_context_step()

    if step == CHAT_CONTEXT_STEP_COMPANY:
        mensaje_norm = chatbot.normalizar_texto(mensaje_trim)
        if chatbot.solicita_contacto_rrhh(mensaje_norm):
            opciones = _construir_acciones_empresas(limite=8)
            nombres = [a.get("label") or a.get("value") for a in opciones if a.get("label") or a.get("value")]
            reply = "Para hablar con un agente primero elegí tu empresa en el menú."
            if nombres:
                reply += "\n\nMenú:\n" + "\n".join(nombres) + "\n\nEscribí el número o el nombre."
            return {
                "ok": True,
                "reply": reply,
                "await_feedback": False,
                "end_session": False,
                "quick_actions": opciones,
                "handoff_active": False,
            }
        cid, company = _resolve_message_to_company(mensaje_trim)
        if cid and company:
            _set_chat_context_company(cid)
            company_for_next = _get_company(cid, include_inactive=False)
            branches = _get_branches_for_company(company_for_next)
            areas = _get_all_areas_for_company(company_for_next)
            if branches:
                reply = f"Perfecto, {company.get('company_name') or cid}. ¿De qué sucursal me hablás?"
                quick_actions = _construir_acciones_sucursales(cid, limite=8)
            elif areas:
                reply = f"Perfecto, {company.get('company_name') or cid}. ¿De qué área me hablás?"
                quick_actions = _construir_acciones_areas(cid, limite=8)
            else:
                _set_chat_context_area("")
                _sess()["chat_context_step"] = CHAT_CONTEXT_STEP_READY
                reply = "Listo. ¿Sobre qué tema querés consultar? Escribí el número o el nombre del menú."
                company = _current_company()
                temas_map = construir_temas_map(
                    company_id=cid,
                    temas_habilitados=(company or {}).get("temas_habilitados") or [],
                )
                quick_actions = construir_acciones_menu(
                    temas_map, limite=6,
                    permitir_hablar_con_humano=(company or {}).get("permitir_hablar_con_humano", True),
                )
            return {
                "ok": True,
                "reply": reply,
                "await_feedback": False,
                "end_session": False,
                "quick_actions": quick_actions,
                "handoff_active": False,
            }
        opciones = _construir_acciones_empresas(limite=8)
        nombres = [a.get("label") or a.get("value") for a in opciones if a.get("label") or a.get("value")]
        if nombres:
            reply = f"No encontré esa empresa.\nMenú:\n" + "\n".join(nombres) + "\n\nEscribí el número o el nombre."
        else:
            reply = "No encontré esa empresa. Elegí una de las opciones o escribí el nombre correcto."
        return {
            "ok": True,
            "reply": reply,
            "await_feedback": False,
            "end_session": False,
            "quick_actions": opciones,
            "handoff_active": False,
        }

    if step == CHAT_CONTEXT_STEP_BRANCH:
        ctx_cid = _sess().get("chat_context_company_id") or (_current_company() or {}).get("company_id")
        mensaje_norm_b = chatbot.normalizar_texto(mensaje_trim)
        if chatbot.solicita_contacto_rrhh(mensaje_norm_b):
            opciones_b = _construir_acciones_sucursales(ctx_cid, limite=8)
            nombres_b = [a.get("label") or a.get("value") for a in opciones_b if a.get("label") or a.get("value")]
            reply_b = "Para hablar con un agente primero elegí tu sucursal en el menú."
            if nombres_b:
                reply_b += "\n\nMenú:\n" + "\n".join(nombres_b) + "\n\nEscribí el número o el nombre."
            return {"ok": True, "reply": reply_b, "await_feedback": False, "end_session": False, "quick_actions": opciones_b, "handoff_active": False}
        branch = _resolve_message_to_branch(mensaje_trim, ctx_cid)
        if branch:
            _set_chat_context_branch(branch)
            company = _set_company_session(ctx_cid)
            company_for_area = _get_company(ctx_cid, include_inactive=False)
            areas = _get_areas_for_branch(company_for_area, branch)
            if areas:
                reply = f"Perfecto. ¿De qué área me hablás?"
                quick_actions = _construir_acciones_areas(ctx_cid, limite=8, branch=branch)
            else:
                _set_chat_context_area("")
                _sess()["chat_context_step"] = CHAT_CONTEXT_STEP_READY
                settings = _apply_company_branding(_read_general_settings())
                company_name = (settings.get("company_name") or "Empresa").strip() or "Empresa"
                hr_display = (settings.get("hr_team_name") or "Atención").strip() or "Atención"
                if hr_display.upper() == "RRHH":
                    hr_display = "Atención"
                reply = (
                    "👋 Listo (sucursal: {}). Soy el asistente de {} de {}.\n"
                    "¿Sobre qué tema querés consultar? Escribí el número o el nombre del menú."
                ).format(branch, hr_display, company_name)
                permitir = (company or {}).get("permitir_hablar_con_humano", True)
                temas_map = construir_temas_map(
                    company_id=ctx_cid,
                    temas_habilitados=(company or {}).get("temas_habilitados") or [],
                )
                quick_actions = construir_acciones_menu(temas_map, limite=6, permitir_hablar_con_humano=permitir)
            return {
                "ok": True,
                "reply": reply,
                "await_feedback": False,
                "end_session": False,
                "quick_actions": quick_actions,
                "handoff_active": False,
            }
        opciones_branch = _construir_acciones_sucursales(ctx_cid, limite=8)
        nombres_branch = [a.get("label") or a.get("value") for a in opciones_branch if a.get("label") or a.get("value")]
        if nombres_branch:
            reply = f"No encontré esa sucursal.\nMenú:\n" + "\n".join(nombres_branch) + "\n\nEscribí el número o el nombre."
        else:
            reply = "No encontré esa sucursal. Elegí una de las opciones."
        return {
            "ok": True,
            "reply": reply,
            "await_feedback": False,
            "end_session": False,
            "quick_actions": opciones_branch,
            "handoff_active": False,
        }

    if step == CHAT_CONTEXT_STEP_AREA:
        ctx_cid = _sess().get("chat_context_company_id") or (_current_company() or {}).get("company_id")
        ctx_branch = _sess().get("chat_context_branch") or None
        mensaje_norm_a = chatbot.normalizar_texto(mensaje_trim)
        if chatbot.solicita_contacto_rrhh(mensaje_norm_a):
            opciones_a = _construir_acciones_areas(ctx_cid, limite=8, branch=ctx_branch)
            nombres_a = [a.get("label") or a.get("value") for a in opciones_a if a.get("label") or a.get("value")]
            reply_a = "Para hablar con un agente primero elegí tu área en el menú."
            if nombres_a:
                reply_a += "\n\nMenú:\n" + "\n".join(nombres_a) + "\n\nEscribí el número o el nombre."
            return {"ok": True, "reply": reply_a, "await_feedback": False, "end_session": False, "quick_actions": opciones_a, "handoff_active": False}
        area = _resolve_message_to_area(mensaje_trim, ctx_cid, branch=ctx_branch)
        if area:
            _set_chat_context_area(area)
            company = _set_company_session(ctx_cid)
            permitir = (company or {}).get("permitir_hablar_con_humano", True)
            temas_habilitados = (company or {}).get("temas_habilitados") or []
            temas_map = construir_temas_map(company_id=ctx_cid, temas_habilitados=temas_habilitados)
            settings = _apply_company_branding(_read_general_settings())
            company_name = (settings.get("company_name") or "Empresa").strip() or "Empresa"
            hr_display = (settings.get("hr_team_name") or "Atención").strip() or "Atención"
            if hr_display.upper() == "RRHH":
                hr_display = "Atención"
            reply = (
                "👋 Listo (área: {}). Soy el asistente de {} de {}.\n"
                "¿Sobre qué tema querés consultar? Escribí el número o el nombre del menú."
            ).format(area, hr_display, company_name)
            return {
                "ok": True,
                "reply": reply,
                "await_feedback": False,
                "end_session": False,
                "quick_actions": construir_acciones_menu(temas_map, limite=6, permitir_hablar_con_humano=permitir),
                "handoff_active": False,
            }
        opciones_area = _construir_acciones_areas(ctx_cid, limite=8, branch=ctx_branch)
        nombres_area = [a.get("label") or a.get("value") for a in opciones_area if a.get("label") or a.get("value")]
        if nombres_area:
            reply = f"No encontré ese área.\nMenú:\n" + "\n".join(nombres_area) + "\n\nEscribí el número o el nombre."
        else:
            reply = "No encontré ese área. Elegí una de las opciones."
        return {
            "ok": True,
            "reply": reply,
            "await_feedback": False,
            "end_session": False,
            "quick_actions": opciones_area,
            "handoff_active": False,
        }

    if step == CHAT_CONTEXT_STEP_READY:
        mensaje_norm_ready = chatbot.normalizar_texto(mensaje_trim)
        quiere_cambiar = getattr(chatbot, "solicita_cambiar_empresa", None) and chatbot.solicita_cambiar_empresa(mensaje_norm_ready)
        if not quiere_cambiar:
            cid_actual = _normalize_company_id(_sess().get("company_id") or _default_company_id())
            cid_otro, company_otra = _resolve_message_to_company(mensaje_trim)
            if cid_otro and company_otra and cid_otro != cid_actual:
                quiere_cambiar = True
        if quiere_cambiar:
            _sess()["chat_context_step"] = CHAT_CONTEXT_STEP_COMPANY
            _sess().pop("chat_context_company_id", None)
            _sess().pop("chat_context_branch", None)
            _sess().pop("chat_context_area", None)
            _sess().pop("company_id", None)
            _sess().pop("company_name", None)
            opciones = _construir_acciones_empresas(limite=8)
            nombres = [a.get("label") or a.get("value") for a in opciones if a.get("label") or a.get("value")]
            reply = "Sin problema. Elegí la empresa con la que querés hablar."
            if nombres:
                reply += "\n\nMenú:\n" + "\n".join(nombres) + "\n\nEscribí el número o el nombre."
            return {
                "ok": True,
                "reply": reply,
                "await_feedback": False,
                "end_session": False,
                "quick_actions": opciones,
                "handoff_active": False,
            }

    company = _set_company_session(_sess().get("company_id") or _default_company_id())
    mensaje_norm = chatbot.normalizar_texto(mensaje)
    handoff_before = bool(_get_handoff_session_id())
    log_asistente_input = not (
        handoff_before
        and mensaje_norm not in HANDOFF_POLL_COMMANDS
        and mensaje_norm not in HANDOFF_END_COMMANDS
    )
    if log_asistente_input:
        input_conversation_id = _get_handoff_session_id() or _session_chat_id()
        _add_chat_history(
            conversation_id=input_conversation_id,
            remitente="colaborador",
            texto=mensaje,
            canal="asistente",
            metadata={"source": "api_chat", "company_id": company.get("company_id")},
        )

    payload = responder_chat(mensaje)
    output_conversation_id = _get_handoff_session_id() or _session_chat_id()
    _add_chat_history(
        conversation_id=output_conversation_id,
        remitente="bot",
        texto=payload.get("reply", ""),
        canal="asistente",
        metadata={
            "await_feedback": bool(payload.get("await_feedback")),
            "handoff_active": bool(payload.get("handoff_active")),
            "end_session": bool(payload.get("end_session")),
            "company_id": company.get("company_id"),
        },
    )
    return {"ok": True, **payload}


@flask_app.post("/api/chat")
def chat_api():
    data = request.get_json(silent=True) or {}
    mensaje = data.get("message", "")
    if not isinstance(mensaje, str):
        return jsonify({"ok": False, "error": "Formato de mensaje inválido"}), 400
    mensaje_trim = (mensaje or "").strip()
    result = _process_chat_turn(mensaje_trim)
    return jsonify(result)


@flask_app.get("/webhook/twilio/whatsapp")
def webhook_twilio_whatsapp_get():
    """Twilio a veces valida la URL con GET. Respondemos TwiML vacío."""
    from twilio.twiml.messaging_response import MessagingResponse
    resp = MessagingResponse()
    return str(resp), 200, {"Content-Type": "text/xml"}


@flask_app.post("/webhook/twilio/whatsapp")
def webhook_twilio_whatsapp():
    """Recibe mensajes entrantes de Twilio (colaborador escribe por WhatsApp al número de Bacar)."""
    from_phone = (request.form.get("From") or "").strip()
    to_phone = (request.form.get("To") or "").strip()
    body = (request.form.get("Body") or "").strip()
    # Twilio envía fotos/audios con NumMedia y MediaUrl0, MediaUrl1, ...
    media_urls = []
    try:
        num_media = int(request.form.get("NumMedia") or 0)
        for i in range(num_media):
            url = (request.form.get(f"MediaUrl{i}") or "").strip()
            if url:
                media_urls.append(url)
    except (ValueError, TypeError):
        pass
    logger.info(
        "Webhook Twilio WhatsApp: From=%r To=%r Body_len=%s NumMedia=%s",
        from_phone, to_phone, len(body), len(media_urls)
    )
    if not from_phone:
        logger.warning("Webhook Twilio: sin From, devolviendo 400")
        return ("", 400)
    if not body and not media_urls:
        logger.info("Webhook Twilio: sin Body ni medios, ignorando (200)")
        return ("", 200)
    if media_urls:
        if body:
            body = body + "\n📎 Archivos: " + " ".join(media_urls)
        else:
            body = "📎 Envió " + str(len(media_urls)) + " archivo(s)"
    g.whatsapp_from = from_phone
    g.whatsapp_to = to_phone
    g.whatsapp_session = WHATSAPP_SESSIONS.setdefault(from_phone, {})
    if not g.whatsapp_session.get("chat_context_step"):
        _load_whatsapp_chat_context(from_phone)
    if not g.whatsapp_session.get("chat_context_company_id"):
        cid, company, line_label = _company_by_whatsapp_phone(to_phone)
        if cid and company:
            g.whatsapp_session["chat_context_company_id"] = cid
            g.whatsapp_session["company_id"] = cid
            g.whatsapp_session["company_name"] = company.get("company_name") or cid
            branches = _get_branches_for_company(company)
            areas = _get_all_areas_for_company(company)
            label_norm = (line_label or "").strip().lower()
            if label_norm and areas and any(str(a).strip().lower() == label_norm for a in areas):
                g.whatsapp_session["chat_context_area"] = line_label.strip()
                g.whatsapp_session["chat_context_step"] = CHAT_CONTEXT_STEP_READY
            elif branches:
                g.whatsapp_session["chat_context_step"] = CHAT_CONTEXT_STEP_BRANCH
            elif areas:
                g.whatsapp_session["chat_context_step"] = CHAT_CONTEXT_STEP_AREA
            else:
                g.whatsapp_session["chat_context_step"] = CHAT_CONTEXT_STEP_READY
    if not g.whatsapp_session.get("handoff_conversation_id"):
        open_handoff_id = _find_open_handoff_by_whatsapp_phone(from_phone)
        if open_handoff_id:
            g.whatsapp_session["handoff_conversation_id"] = open_handoff_id
            logger.info("Webhook Twilio: sesión recuperada, handoff=%s", open_handoff_id)
    g.whatsapp_media_urls = media_urls
    try:
        result = _process_chat_turn(body)
    except Exception as e:
        logger.exception("Webhook Twilio: error en _process_chat_turn: %s", e)
        from twilio.twiml.messaging_response import MessagingResponse
        resp = MessagingResponse()
        return str(resp), 200, {"Content-Type": "text/xml"}
    reply = (result.get("reply") or "").strip()
    if reply:
        try:
            from twilio_whatsapp import send_one
            send_one(from_phone, body=reply, phone_number_id=to_phone)
        except Exception as e:
            logger.warning("Webhook Twilio: no se pudo enviar respuesta por WhatsApp: %s", e)
    _save_whatsapp_chat_context(from_phone)
    from twilio.twiml.messaging_response import MessagingResponse
    resp = MessagingResponse()
    return str(resp), 200, {"Content-Type": "text/xml"}


@flask_app.get("/login")
def login_page():
    if not _auth_enabled():
        return redirect(url_for("rrhh_page"))
    if _current_rrhh_user() is not None:
        return redirect(_safe_next_path(request.args.get("next"), fallback="/rrhh"))
    companies = _list_companies(include_inactive=False)
    selected_company = _normalize_company_id(
        request.args.get("empresa") or session.get("company_id") or _default_company_id()
    )
    if not any(item.get("company_id") == selected_company for item in companies):
        selected_company = companies[0]["company_id"] if companies else _default_company_id()
    return render_template(
        "login.html",
        error="",
        next_path=_safe_next_path(request.args.get("next"), fallback="/rrhh"),
        companies=companies,
        selected_company=selected_company,
    )


@flask_app.post("/login")
def login_submit():
    if not _auth_enabled():
        return redirect(url_for("rrhh_page"))

    data = request.get_json(silent=True) if request.is_json else request.form
    username = str((data or {}).get("username") or "").strip()
    password = str((data or {}).get("password") or "")
    company_id = _normalize_company_id((data or {}).get("company_id") or request.args.get("empresa"))
    next_path = _safe_next_path((data or {}).get("next") or request.args.get("next"), "/rrhh")

    ok, user_payload, error = auth_rrhh.authenticate(username, password)
    if not ok:
        if request.is_json:
            return jsonify({"ok": False, "error": error}), 401
        companies = _list_companies(include_inactive=False)
        selected_company = company_id or (companies[0]["company_id"] if companies else _default_company_id())
        return (
            render_template(
                "login.html",
                error=error,
                next_path=next_path,
                companies=companies,
                selected_company=selected_company,
            ),
            401,
        )

    user_companies = _companies_for_user(user_payload)
    if not user_companies:
        message = "Tu usuario no tiene empresas asignadas o activas."
        if request.is_json:
            return jsonify({"ok": False, "error": message}), 403
        return (
            render_template(
                "login.html",
                error=message,
                next_path=next_path,
                companies=_list_companies(include_inactive=False),
                selected_company=company_id or _default_company_id(),
            ),
            403,
        )
    if company_id and not any(item.get("company_id") == company_id for item in user_companies):
        message = "No tenés acceso a la empresa seleccionada."
        if request.is_json:
            return jsonify({"ok": False, "error": message}), 403
        return (
            render_template(
                "login.html",
                error=message,
                next_path=next_path,
                companies=user_companies,
                selected_company=company_id,
            ),
            403,
        )

    chosen_company = company_id or (
        user_companies[0]["company_id"] if user_companies else _default_company_id()
    )
    if not _user_can_access_company(user_payload, chosen_company):
        message = "No tenés acceso a la empresa seleccionada."
        if request.is_json:
            return jsonify({"ok": False, "error": message}), 403
        return (
            render_template(
                "login.html",
                error=message,
                next_path=next_path,
                companies=user_companies,
                selected_company=chosen_company,
            ),
            403,
        )

    company = _set_company_session(chosen_company)
    _set_rrhh_user(user_payload)
    if request.is_json:
        return jsonify(
            {
                "ok": True,
                "redirect_to": next_path,
                "user": user_payload,
                "company": {
                    "company_id": company.get("company_id"),
                    "company_name": company.get("company_name"),
                },
            }
        )
    return redirect(next_path)


@flask_app.route("/logout", methods=["GET", "POST"])
def logout_page():
    session.clear()
    redirect_target = "login_page" if _auth_enabled() else "rrhh_page"
    response = redirect(url_for(redirect_target))
    session_cookie_name = flask_app.config.get("SESSION_COOKIE_NAME", "session")
    response.delete_cookie(session_cookie_name)
    return response


@flask_app.get("/recuperar-clave")
def password_recovery_page():
    if not _auth_enabled():
        return redirect(url_for("login_page"))
    if _current_rrhh_user() is not None:
        return redirect(_safe_next_path(request.args.get("next"), fallback="/rrhh"))
    return render_template(
        "recover_password.html",
        error="",
        success=False,
        message="",
        reset_link="",
    )


@flask_app.post("/recuperar-clave")
def password_recovery_submit():
    if not _auth_enabled():
        return redirect(url_for("login_page"))

    data = request.get_json(silent=True) if request.is_json else request.form
    username = str((data or {}).get("username") or "").strip()
    email = str((data or {}).get("email") or "").strip()
    generic_success_message = (
        "Si los datos coinciden, enviamos un enlace de restablecimiento al email indicado."
    )

    if not username or not email:
        if request.is_json:
            return jsonify({"ok": False, "error": "Ingresá usuario y email."}), 400
        return (
            render_template(
                "recover_password.html",
                error="Ingresá usuario y email.",
                success=False,
                message="",
                reset_link="",
            ),
            400,
        )

    ok, payload, _error = auth_rrhh.create_password_reset_token_for_identity(
        username=username,
        email=email,
        ttl_minutes=60,
        requested_by=f"self:{username}",
    )
    if not ok:
        if request.is_json:
            return jsonify({"ok": True, "message": generic_success_message})
        return render_template(
            "recover_password.html",
            error="",
            success=True,
            message=generic_success_message,
            reset_link="",
        )

    reset_url = url_for("password_reset_page", token=payload.get("token"), _external=True)
    try:
        mail_ok, mail_error = _send_password_reset_email(
            to_email=payload.get("email"),
            display_name=payload.get("display_name") or payload.get("username"),
            reset_url=reset_url,
            expires_at_iso=payload.get("expires_at"),
        )
    except Exception as exc:
        mail_ok, mail_error = False, str(exc)
    smtp_not_configured = mail_error and "SMTP no configurado" in (mail_error or "")
    if request.is_json:
        if mail_ok:
            return jsonify({"ok": True, "mail_sent": True, "message": generic_success_message})
        if smtp_not_configured:
            return jsonify({
                "ok": True,
                "mail_sent": False,
                "message": "El envío por email no está configurado. Usá este enlace para restablecer tu contraseña.",
                "reset_link": reset_url,
            })
        return jsonify({"ok": False, "error": mail_error or "No se pudo enviar el email."}), 502

    if mail_ok:
        return render_template(
            "recover_password.html",
            error="",
            success=True,
            message=generic_success_message,
            reset_link="",
        )
    if smtp_not_configured:
        return render_template(
            "recover_password.html",
            error="",
            success=True,
            message="El envío por email no está configurado. Copiá el enlace de abajo para restablecer tu contraseña (válido por 1 hora).",
            reset_link=reset_url,
        )
    return (
        render_template(
            "recover_password.html",
            error=mail_error or "No se pudo enviar el email de restablecimiento.",
            success=False,
            message="",
            reset_link="",
        ),
        502,
    )


@flask_app.get("/restablecer-clave/<token>")
def password_reset_page(token):
    return render_template(
        "reset_password.html",
        token=str(token or "").strip(),
        error="",
        success=False,
        message="",
    )


@flask_app.post("/restablecer-clave/<token>")
def password_reset_submit(token):
    data = request.get_json(silent=True) if request.is_json else request.form
    password = str((data or {}).get("password") or "")
    confirm = str((data or {}).get("confirm_password") or "")
    if not password:
        return (
            render_template(
                "reset_password.html",
                token=str(token or "").strip(),
                error="Ingresá una contraseña nueva.",
                success=False,
                message="",
            ),
            400,
        )
    if password != confirm:
        return (
            render_template(
                "reset_password.html",
                token=str(token or "").strip(),
                error="Las contraseñas no coinciden.",
                success=False,
                message="",
            ),
            400,
        )

    ok, user, error = auth_rrhh.reset_password_with_token(str(token or "").strip(), password)
    if not ok:
        return (
            render_template(
                "reset_password.html",
                token=str(token or "").strip(),
                error=error or "No se pudo restablecer la contraseña.",
                success=False,
                message="",
            ),
            400,
        )

    return render_template(
        "reset_password.html",
        token="",
        error="",
        success=True,
        message=f"Contraseña actualizada para {user.get('username')}. Ya podés iniciar sesión.",
    )


@flask_app.get("/api/historial")
@rrhh_permission_required(auth_rrhh.PERM_HISTORY_VIEW, message="Sin permiso para ver historial.")
def historial_api():
    try:
        limit = int(request.args.get("limit", "200"))
    except Exception:
        limit = 200
    limit = max(1, min(limit, 1000))

    remitente = str(request.args.get("remitente", "")).strip().lower()
    canal = str(request.args.get("canal", "")).strip().lower()
    conversation_id = str(request.args.get("conversation_id", "")).strip()
    q = str(request.args.get("q", "")).strip().lower()
    company_id_raw = request.args.get("company_id", "").strip() or None
    company_id = _normalize_company_id(company_id_raw) if company_id_raw else None
    branches_param = request.args.get("branches")
    branches = [b.strip() for b in (branches_param or "").split(",") if b.strip()] if branches_param else None
    areas_param = request.args.get("areas")
    areas = [a.strip() for a in (areas_param or "").split(",") if a.strip()] if areas_param else None

    raw_items = _list_chat_history(limit=1500)
    handoff_ids = set()
    if company_id:
        handoffs = _list_handoffs(
            include_closed=True,
            limit=10000,
            company_id=company_id,
            branches=branches if branches else None,
            areas=areas if areas else None,
        )
        for h in handoffs or []:
            hid = str(h.get("id") or h.get("conversation_id") or "").strip()
            if hid:
                handoff_ids.add(hid)

    items = []
    for item in raw_items:
        if company_id:
            meta = item.get("metadata") or {}
            item_company = _normalize_company_id(meta.get("company_id"))
            conv_id = str(item.get("conversation_id") or "").strip()
            if item_company != company_id and conv_id not in handoff_ids:
                continue
        serialized = _serialize_history_item(item)
        if remitente and serialized["remitente"].lower() != remitente:
            continue
        if canal and serialized["canal"].lower() != canal:
            continue
        if conversation_id and serialized["conversation_id"] != conversation_id:
            continue
        if q and q not in serialized["texto"].lower():
            continue
        items.append(serialized)

    filter_applied = {
        "company_id": company_id,
        "branches": branches or [],
        "areas": areas or [],
    }
    return jsonify(
        {
            "ok": True,
            "total": len(items),
            "limit": limit,
            "items": items[:limit],
            "filter_applied": filter_applied,
        }
    )


@flask_app.get("/api/chat/poll")
def chat_poll_api():
    _auto_close_expired_handoffs(company=_current_company())
    handoff_id = _get_handoff_session_id()
    if not handoff_id:
        return jsonify({"ok": True, "handoff_active": False, "messages": []})

    conv = _fetch_handoff(handoff_id)
    if not conv:
        _clear_handoff_session()
        return jsonify({"ok": True, "handoff_active": False, "messages": []})

    estado = str(conv.get("estado") or "").strip().lower()
    if estado == HANDOFF_STATUS_CLOSED:
        _clear_handoff_session()

    nuevos = _collect_new_messages_for_collaborator(handoff_id)
    return jsonify(
        {
            "ok": True,
            "handoff_active": estado in {HANDOFF_STATUS_PENDING, HANDOFF_STATUS_ACTIVE},
            "messages": _serialize_messages(nuevos),
            "quick_actions": construir_acciones_handoff()
            if estado in {HANDOFF_STATUS_PENDING, HANDOFF_STATUS_ACTIVE}
            else [],
        }
    )


@flask_app.get("/api/configuracion/general")
@rrhh_auth_required
def configuracion_general_api():
    if not _can_manage_configuration() and not _can_manage_preferences():
        return _forbidden_json_error("Sin permiso para ver configuración.")
    settings = _read_general_settings()
    return jsonify({"ok": True, "settings": settings, "selected_company_id": _current_company().get("company_id")})


@flask_app.post("/api/configuracion/general")
@rrhh_auth_required
def configuracion_general_update_api():
    if not _can_manage_preferences() and not _can_manage_general_config():
        return _forbidden_json_error("Sin permiso para editar configuración general.")
    data = request.get_json(silent=True) or {}
    ok, settings, error = _write_general_settings(data)
    if not ok:
        return jsonify({"ok": False, "error": error}), 400
    _apply_company_branding(settings)
    return jsonify({"ok": True, "settings": settings})


@flask_app.get("/api/configuracion/empresas")
@rrhh_auth_required
def configuracion_empresas_api():
    if not _can_manage_configuration():
        return _forbidden_json_error("Sin permiso para ver empresas.")
    companies = [_company_for_api(c) for c in _list_companies(include_inactive=True)]
    return jsonify(
        {
            "ok": True,
            "companies": companies,
            "selected_company_id": _current_company().get("company_id"),
        }
    )


@flask_app.post("/api/configuracion/empresas")
@rrhh_auth_required
def configuracion_crear_empresa_api():
    if not _can_manage_general_config():
        return _forbidden_json_error("Sin permiso para crear empresas.")
    data = request.get_json(silent=True) or {}
    ok, company, error = _upsert_company(data)
    if not ok:
        return jsonify({"ok": False, "error": error}), 400
    return jsonify({"ok": True, "company": _company_for_api(company)})


@flask_app.post("/api/configuracion/empresas/<company_id>")
@rrhh_auth_required
def configuracion_editar_empresa_api(company_id):
    if not _can_manage_general_config():
        return _forbidden_json_error("Sin permiso para editar empresas.")
    current = _get_company(company_id, include_inactive=True)
    if not current:
        return jsonify({"ok": False, "error": "Empresa no encontrada."}), 404
    data = request.get_json(silent=True) or {}
    payload = {
        "company_id": current.get("company_id"),
        "company_name": data.get("company_name", current.get("company_name")),
        "hr_team_name": data.get("hr_team_name", current.get("hr_team_name")),
        "hr_contact": data.get("hr_contact", current.get("hr_contact")),
        "company_email": data.get("company_email", current.get("company_email")),
        "company_address": data.get("company_address", current.get("company_address")),
        "company_phone": data.get("company_phone", current.get("company_phone")),
        "company_website": data.get("company_website", current.get("company_website")),
        "handoff_auto_close_enabled": data.get(
            "handoff_auto_close_enabled",
            current.get("handoff_auto_close_enabled", False),
        ),
        "handoff_auto_close_minutes": data.get(
            "handoff_auto_close_minutes",
            current.get("handoff_auto_close_minutes", AUTO_CLOSE_DEFAULT_MINUTES),
        ),
        "branches": data.get("branches", current.get("branches") or []),
        "areas": _normalize_areas(data.get("areas", current.get("areas") or [])),
        "areas_by_branch": _normalize_areas_by_branch(
            data.get("areas_by_branch") if "areas_by_branch" in data else (current.get("areas_by_branch") or {})
        ),
        "active": bool(data.get("active", current.get("active", True))),
        "permitir_hablar_con_humano": _normalize_bool_flag(
            data.get("permitir_hablar_con_humano", current.get("permitir_hablar_con_humano", True)),
            default=True,
        ),
        "temas_habilitados": current.get("temas_habilitados") or [],
        "whatsapp_numbers": _normalize_whatsapp_numbers(
            data.get("whatsapp_numbers") if "whatsapp_numbers" in data else (current.get("whatsapp_numbers") or [])
        ),
    }
    th = data.get("temas_habilitados")
    if isinstance(th, list):
        payload["temas_habilitados"] = [str(t).strip().lower() for t in th if str(t).strip()]
    ok, company, error = _upsert_company(payload)
    if not ok:
        return jsonify({"ok": False, "error": error}), 400
    if _normalize_company_id(session.get("company_id")) == company.get("company_id"):
        _set_company_session(company.get("company_id"))
    return jsonify({"ok": True, "company": _company_for_api(company)})


@flask_app.delete("/api/configuracion/empresas/<company_id>")
@rrhh_auth_required
def configuracion_eliminar_empresa_api(company_id):
    if not _can_manage_general_config():
        return _forbidden_json_error("Sin permiso para eliminar empresas.")
    ok, error = _delete_company(company_id)
    if not ok:
        status_code = 404 if "no encontrada" in error.lower() else 409
        return jsonify({"ok": False, "error": error}), status_code
    if _normalize_company_id(session.get("company_id")) == _normalize_company_id(company_id):
        _set_company_session(_default_company_id())
    return jsonify({"ok": True})


@flask_app.post("/api/configuracion/empresa/seleccionar")
@rrhh_auth_required
def configuracion_seleccionar_empresa_api():
    if not _can_manage_general_config():
        return _forbidden_json_error("Sin permiso para cambiar empresa activa.")
    data = request.get_json(silent=True) or {}
    company_id = _normalize_company_id(data.get("company_id"))
    company = _get_company(company_id, include_inactive=True)
    if not company:
        available = _list_companies(include_inactive=True)
        if not available:
            return jsonify({"ok": False, "error": "Empresa no encontrada."}), 404
        company = available[0]
    selected = _set_company_session(company.get("company_id"))
    settings = _read_general_settings()
    _apply_company_branding(settings)
    return jsonify({"ok": True, "company": selected, "settings": settings})


@flask_app.post("/api/configuracion/conversaciones/autocierre/ejecutar")
@rrhh_auth_required
def configuracion_autocierre_ejecutar_api():
    if not _can_manage_general_config():
        return _forbidden_json_error("Sin permiso para ejecutar autocierre.")
    company = _current_company()
    result = _auto_close_expired_handoffs(company=company, force=True)
    return jsonify({"ok": True, **result})


@flask_app.get("/api/rrhh/conversaciones")
@rrhh_permission_required(
    auth_rrhh.PERM_CONVERSATIONS_VIEW,
    message="Sin permiso para ver conversaciones.",
)
def rrhh_conversaciones_api():
    _heartbeat_current_agent()
    include_closed = str(request.args.get("include_closed", "false")).lower() == "true"
    include_all_filters = str(request.args.get("include_all_filters", "false")).lower() == "true"
    branches_param = request.args.get("branches")
    if branches_param is not None:
        branches = [b.strip() for b in str(branches_param).split(",") if b.strip()]
    else:
        branches = None
    areas_param = request.args.get("areas")
    if areas_param is not None:
        areas = [a.strip() for a in str(areas_param).split(",") if a.strip()]
    else:
        areas = None
    company = _current_company()
    company_id_norm = _normalize_company_id(company.get("company_id"))
    default_branches = None
    default_areas = None
    if _auth_enabled() and not include_all_filters and branches is None and areas is None:
        user = _current_rrhh_user()
        if user:
            assignments = user.get("assignments") or []
            branch_set = set()
            for a in assignments:
                if isinstance(a, dict) and _normalize_company_id(a.get("company_id")) == company_id_norm:
                    b = str(a.get("branch") or "").strip()
                    if b:
                        branch_set.add(b)
            if branch_set:
                default_branches = list(branch_set)
            user_area = str(user.get("area") or "").strip()
            if user_area:
                default_areas = [user_area]
    if branches is None and default_branches is not None:
        branches = default_branches
    if areas is None and default_areas is not None:
        areas = default_areas
    auto_close_result = _auto_close_expired_handoffs(company=company)
    convs = _list_handoffs(
        include_closed=include_closed,
        limit=150,
        company_id=company.get("company_id"),
        branches=branches,
        areas=areas,
    )
    company_branches = []
    for b in (company.get("branches") or []):
        name = _branch_name(b)
        if name:
            company_branches.append({"name": name})
    company_areas = _get_all_areas_for_company(company)
    out = {
        "ok": True,
        "conversaciones": [_serialize_handoff(c) for c in convs],
        "agente_actual": _rrhh_agent_name() if _auth_enabled() else "",
        "agentes_activos": [
            _serialize_active_agent(agent)
            for agent in _list_active_agents(company_id=company.get("company_id"))
        ],
        "selected_company_id": company.get("company_id"),
        "selected_company_name": company.get("company_name"),
        "branches": company_branches,
        "areas": [str(a).strip() for a in (company_areas or []) if str(a).strip()],
        "autocierre": auto_close_result,
    }
    if default_branches is not None:
        out["filter_by_branches"] = default_branches
    if default_areas is not None:
        out["filter_by_areas"] = default_areas
    return jsonify(out)


@flask_app.post("/api/rrhh/empresa/seleccionar")
@rrhh_permission_required(
    auth_rrhh.PERM_CONVERSATIONS_VIEW,
    message="Sin permiso para cambiar empresa activa.",
)
def rrhh_seleccionar_empresa_api():
    data = request.get_json(silent=True) or {}
    company_id = _normalize_company_id(data.get("company_id"))
    if not company_id:
        return jsonify({"ok": False, "error": "Seleccioná una empresa válida."}), 400

    company = _get_company(company_id, include_inactive=False)
    if not company:
        return jsonify({"ok": False, "error": "Empresa no encontrada o inactiva."}), 404

    current_user = _current_rrhh_user()
    if current_user and not _user_can_access_company(current_user, company_id):
        return _forbidden_json_error("No tenés acceso a la empresa seleccionada.")

    selected = _set_company_session(company.get("company_id"))
    _apply_company_branding(_read_general_settings())
    return jsonify(
        {
            "ok": True,
            "company": {
                "company_id": selected.get("company_id"),
                "company_name": selected.get("company_name"),
            },
        }
    )


@flask_app.get("/api/rrhh/usuarios")
@rrhh_permission_required(
    auth_rrhh.PERM_USERS_MANAGE,
    message="Sin permiso para gestionar usuarios.",
)
def rrhh_usuarios_api():
    users = auth_rrhh.list_file_users()
    companies_raw = _list_companies(include_inactive=False)
    companies = [_company_for_api(c) for c in companies_raw]
    return jsonify(
        {
            "ok": True,
            "users": users,
            "users_file": auth_rrhh.users_file_path(),
            "valid_roles": auth_rrhh.available_roles(),
            "permissions_catalog": auth_rrhh.permissions_catalog(),
            "companies": companies,
        }
    )


@flask_app.post("/api/rrhh/usuarios")
@rrhh_permission_required(
    auth_rrhh.PERM_USERS_MANAGE,
    message="Sin permiso para crear usuarios.",
)
def rrhh_crear_usuario_api():
    data = request.get_json(silent=True) or {}
    username = str(data.get("username") or "").strip()
    password = str(data.get("password") or "")
    display_name = str(data.get("display_name") or "").strip()
    role = str(data.get("role") or "rrhh").strip().lower()
    assignments = data.get("assignments")
    email = str(data.get("email") or "").strip()
    phone = str(data.get("phone") or "").strip()
    area = str(data.get("area") or "").strip()
    created_by = (_current_rrhh_user() or {}).get("username") or ""

    ok, user, error = auth_rrhh.create_user(
        username=username,
        password=password,
        display_name=display_name,
        role=role,
        created_by=created_by,
        assignments=assignments,
        email=email,
        phone=phone,
        area=area,
    )
    if not ok:
        status_code = 409 if "existe" in error.lower() else 400
        return jsonify({"ok": False, "error": error}), status_code

    return jsonify({"ok": True, "user": user})


@flask_app.get("/api/rrhh/roles")
@rrhh_permission_required(
    auth_rrhh.PERM_ROLES_MANAGE,
    message="Sin permiso para ver roles.",
)
def rrhh_roles_api():
    return jsonify(
        {
            "ok": True,
            "roles": auth_rrhh.list_roles(),
            "roles_file": auth_rrhh.roles_file_path(),
            "permissions_catalog": auth_rrhh.permissions_catalog(),
        }
    )


@flask_app.post("/api/rrhh/roles")
@rrhh_permission_required(
    auth_rrhh.PERM_ROLES_MANAGE,
    message="Sin permiso para crear roles.",
)
def rrhh_crear_rol_api():
    data = request.get_json(silent=True) or {}
    name = str(data.get("name") or "").strip().lower()
    display_name = str(data.get("display_name") or "").strip()
    permissions = data.get("permissions")
    company_ids = data.get("company_ids")
    if isinstance(company_ids, list):
        company_ids = [str(c or "").strip() for c in company_ids if str(c or "").strip()]
    else:
        company_ids = None
    ok, role, error = auth_rrhh.create_role(
        name=name,
        display_name=display_name,
        permissions=permissions,
        company_ids=company_ids,
    )
    if not ok:
        status = 409 if "existe" in error.lower() else 400
        return jsonify({"ok": False, "error": error}), status
    return jsonify({"ok": True, "role": role})


@flask_app.post("/api/rrhh/roles/<role_name>")
@rrhh_permission_required(
    auth_rrhh.PERM_ROLES_MANAGE,
    message="Sin permiso para editar roles.",
)
def rrhh_editar_rol_api(role_name):
    data = request.get_json(silent=True) or {}
    display_name = data.get("display_name")
    permissions = data.get("permissions")
    company_ids = data.get("company_ids")
    if company_ids is not None and isinstance(company_ids, list):
        company_ids = [str(c or "").strip() for c in company_ids if str(c or "").strip()]
    ok, role, error = auth_rrhh.update_role(
        name=role_name,
        display_name=display_name,
        permissions=permissions,
        company_ids=company_ids,
    )
    if not ok:
        msg = error.lower()
        if "no encontrado" in msg:
            status = 404
        elif "debe quedar al menos un usuario con permiso" in msg:
            status = 409
        else:
            status = 400
        return jsonify({"ok": False, "error": error}), status
    return jsonify({"ok": True, "role": role})


@flask_app.post("/api/rrhh/usuarios/<username>/rol")
@rrhh_permission_required(
    auth_rrhh.PERM_USERS_MANAGE,
    message="Sin permiso para editar roles de usuarios.",
)
def rrhh_actualizar_rol_api(username):
    data = request.get_json(silent=True) or {}
    role = str(data.get("role") or "").strip().lower()
    updated_by = (_current_rrhh_user() or {}).get("username") or ""

    ok, user, error = auth_rrhh.update_user_role(
        username=username,
        role=role,
        updated_by=updated_by,
    )
    if not ok:
        msg = error.lower()
        if "no encontrado" in msg:
            status_code = 404
        elif "debe quedar al menos un usuario con permiso" in msg:
            status_code = 409
        else:
            status_code = 400
        return jsonify({"ok": False, "error": error}), status_code
    return jsonify({"ok": True, "user": user})


@flask_app.post("/api/rrhh/usuarios/<username>/asignaciones")
@rrhh_permission_required(
    auth_rrhh.PERM_USERS_MANAGE,
    message="Sin permiso para editar asignaciones de usuarios.",
)
def rrhh_actualizar_asignaciones_api(username):
    data = request.get_json(silent=True) or {}
    assignments = data.get("assignments")
    updated_by = (_current_rrhh_user() or {}).get("username") or ""
    ok, user, error = auth_rrhh.update_user_assignments(
        username=username,
        assignments=assignments,
        updated_by=updated_by,
    )
    if not ok:
        msg = error.lower()
        status_code = 404 if "no encontrado" in msg else 400
        return jsonify({"ok": False, "error": error}), status_code
    return jsonify({"ok": True, "user": user})


@flask_app.post("/api/rrhh/usuarios/<username>/perfil")
@rrhh_permission_required(
    auth_rrhh.PERM_USERS_MANAGE,
    message="Sin permiso para editar usuarios.",
)
def rrhh_actualizar_perfil_usuario_api(username):
    data = request.get_json(silent=True) or {}
    updated_by = (_current_rrhh_user() or {}).get("username") or ""
    ok, user, error = auth_rrhh.update_user_profile(
        username=username,
        role=data.get("role"),
        assignments=data.get("assignments"),
        display_name=data.get("display_name"),
        email=data.get("email"),
        phone=data.get("phone"),
        area=data.get("area"),
        updated_by=updated_by,
    )
    if not ok:
        msg = str(error or "").lower()
        if "no encontrado" in msg:
            status_code = 404
        elif "debe quedar al menos un usuario con permiso" in msg:
            status_code = 409
        else:
            status_code = 400
        return jsonify({"ok": False, "error": error}), status_code
    return jsonify({"ok": True, "user": user})


@flask_app.delete("/api/rrhh/usuarios/<username>")
@rrhh_permission_required(
    auth_rrhh.PERM_USERS_MANAGE,
    message="Sin permiso para eliminar usuarios.",
)
def rrhh_eliminar_usuario_api(username):
    deleted_by = (_current_rrhh_user() or {}).get("username") or ""
    ok, error = auth_rrhh.delete_user(username=username, deleted_by=deleted_by)
    if not ok:
        msg = error.lower()
        status_code = 404 if "no encontrado" in msg else 409 if "debe quedar" in msg else 400
        return jsonify({"ok": False, "error": error}), status_code
    return jsonify({"ok": True})


@flask_app.post("/api/rrhh/usuarios/<username>/enviar-reset")
@rrhh_permission_required(
    auth_rrhh.PERM_USERS_MANAGE,
    message="Sin permiso para gestionar usuarios.",
)
def rrhh_enviar_reset_password_api(username):
    data = request.get_json(silent=True) or {}
    requested_by = (_current_rrhh_user() or {}).get("username") or ""
    ok, payload, error = auth_rrhh.create_password_reset_token(
        username=username,
        ttl_minutes=data.get("ttl_minutes", 60),
        requested_by=requested_by,
    )
    if not ok:
        msg = str(error or "").lower()
        status_code = 404 if "no encontrado" in msg else 400
        return jsonify({"ok": False, "error": error}), status_code

    reset_url = url_for("password_reset_page", token=payload.get("token"), _external=True)
    mail_ok, mail_error = _send_password_reset_email(
        to_email=payload.get("email"),
        display_name=payload.get("display_name") or payload.get("username"),
        reset_url=reset_url,
        expires_at_iso=payload.get("expires_at"),
    )
    if not mail_ok:
        return jsonify(
            {
                "ok": True,
                "mail_sent": False,
                "warning": mail_error,
                "reset_url": reset_url,
                "email": payload.get("email"),
                "expires_at": payload.get("expires_at"),
            }
        )

    return jsonify(
        {
            "ok": True,
            "mail_sent": True,
            "email": payload.get("email"),
            "expires_at": payload.get("expires_at"),
        }
    )


@flask_app.delete("/api/rrhh/roles/<role_name>")
@rrhh_permission_required(
    auth_rrhh.PERM_ROLES_MANAGE,
    message="Sin permiso para eliminar roles.",
)
def rrhh_eliminar_rol_api(role_name):
    ok, error = auth_rrhh.delete_role(role_name)
    if not ok:
        msg = error.lower()
        status = 404 if "no encontrado" in msg else 409 if "no podés" in msg else 400
        return jsonify({"ok": False, "error": error}), status
    return jsonify({"ok": True})


@flask_app.get("/api/rrhh/conversaciones/<conversation_id>/mensajes")
@rrhh_permission_required(
    auth_rrhh.PERM_CONVERSATIONS_VIEW,
    message="Sin permiso para ver conversaciones.",
)
def rrhh_mensajes_api(conversation_id):
    conv = _fetch_handoff(conversation_id)
    if not conv:
        return jsonify({"ok": False, "error": "Conversación no encontrada"}), 404
    if not _conversation_matches_selected_company(conv):
        return jsonify({"ok": False, "error": "Conversación no disponible para esta empresa."}), 404
    mensajes = _list_handoff_messages(conversation_id)
    return jsonify(
        {
            "ok": True,
            "conversation_id": conversation_id,
            "estado": conv.get("estado") or HANDOFF_STATUS_PENDING,
            "rrhh_agente": conv.get("rrhh_agente") or "",
            "rrhh_agente_id": conv.get("rrhh_agente_id") or "",
            "rrhh_asignacion_automatica": bool(conv.get("rrhh_asignacion_automatica")),
            "mensajes": _serialize_messages(mensajes),
        }
    )


@flask_app.post("/api/rrhh/conversaciones/<conversation_id>/tomar")
@rrhh_permission_required(
    auth_rrhh.PERM_CONVERSATIONS_MANAGE,
    message="Sin permiso para gestionar conversaciones.",
)
def rrhh_tomar_api(conversation_id):
    data = request.get_json(silent=True) or {}
    agente = _resolve_rrhh_agent(data)
    conv = _fetch_handoff(conversation_id)
    if not conv:
        return jsonify({"ok": False, "error": "Conversación no encontrada"}), 404
    if not _conversation_matches_selected_company(conv):
        return jsonify({"ok": False, "error": "Conversación no disponible para esta empresa."}), 404
    if not _take_handoff(conversation_id, agente):
        return jsonify({"ok": False, "error": "Conversación no encontrada"}), 404
    return jsonify({"ok": True, "conversation_id": conversation_id, "estado": HANDOFF_STATUS_ACTIVE})


@flask_app.post("/api/rrhh/conversaciones/<conversation_id>/reasignar")
@rrhh_permission_required(
    auth_rrhh.PERM_CONVERSATIONS_MANAGE,
    message="Sin permiso para gestionar conversaciones.",
)
def rrhh_reasignar_api(conversation_id):
    conv = _fetch_handoff(conversation_id)
    if not conv:
        return jsonify({"ok": False, "error": "Conversación no encontrada"}), 404
    if not _conversation_matches_selected_company(conv):
        return jsonify({"ok": False, "error": "Conversación no disponible para esta empresa."}), 404
    data = request.get_json(silent=True) or {}
    target_agent = _resolve_target_agent_for_reassignment(data)
    if not target_agent:
        return jsonify({"ok": False, "error": "Agente destino no disponible."}), 400
    actor = _resolve_rrhh_agent({})
    ok, error = _reassign_handoff(
        conversation_id,
        target_agent,
        reasignado_por=actor.get("display_name"),
    )
    if not ok:
        return jsonify({"ok": False, "error": error}), 404
    return jsonify(
        {
            "ok": True,
            "conversation_id": conversation_id,
            "estado": HANDOFF_STATUS_ACTIVE,
            "rrhh_agente": target_agent.get("display_name"),
            "rrhh_agente_id": target_agent.get("agent_id"),
        }
    )


@flask_app.post("/api/rrhh/conversaciones/<conversation_id>/cerrar")
@rrhh_permission_required(
    auth_rrhh.PERM_CONVERSATIONS_MANAGE,
    message="Sin permiso para gestionar conversaciones.",
)
def rrhh_cerrar_api(conversation_id):
    data = request.get_json(silent=True) or {}
    agente = _resolve_rrhh_agent(data)
    conv = _fetch_handoff(conversation_id)
    if not conv:
        return jsonify({"ok": False, "error": "Conversación no encontrada"}), 404
    if not _conversation_matches_selected_company(conv):
        return jsonify({"ok": False, "error": "Conversación no disponible para esta empresa."}), 404
    if not _close_handoff(conversation_id, agente.get("display_name")):
        return jsonify({"ok": False, "error": "Conversación no encontrada"}), 404
    return jsonify({"ok": True, "conversation_id": conversation_id, "estado": HANDOFF_STATUS_CLOSED})


# Límite de subida para adjuntos (10 MB)
UPLOAD_MAX_BYTES = 10 * 1024 * 1024
UPLOAD_ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "webp", "pdf"}


def _get_storage_bucket():
    """Devuelve el bucket de Firebase Storage si está disponible."""
    try:
        from firebase_admin import storage
        bucket_name = os.getenv("FIREBASE_STORAGE_BUCKET", "").strip()
        if bucket_name:
            return storage.bucket(bucket_name)
        return storage.bucket()
    except Exception:
        return None


def _proxy_twilio_media(url_decoded):
    """Descarga un recurso de Twilio (MediaUrl) con auth y lo devuelve. Solo permite URLs de api.twilio.com."""
    url_decoded = (url_decoded or "").strip()
    if not url_decoded.startswith("https://api.twilio.com/"):
        return None
    sid = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
    token = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
    if not sid or not token:
        return None
    try:
        from base64 import b64encode
        from urllib.request import Request, urlopen
        auth = b64encode(f"{sid}:{token}".encode()).decode()
        req = Request(url_decoded, headers={"Authorization": f"Basic {auth}"})
        resp = urlopen(req, timeout=15)
        content = resp.read()
        content_type = resp.headers.get("Content-Type") or "application/octet-stream"
        from flask import Response
        return Response(content, mimetype=content_type)
    except Exception:
        return None


@flask_app.get("/api/rrhh/media")
@rrhh_permission_required(
    auth_rrhh.PERM_CONVERSATIONS_VIEW,
    message="Sin permiso para ver adjuntos.",
)
def rrhh_media_proxy():
    """Proxy para ver en el panel archivos/imágenes que el colaborador envió por WhatsApp (Twilio MediaUrl)."""
    from urllib.parse import unquote
    u = request.args.get("u", "").strip()
    if not u:
        return ("", 400)
    url_decoded = unquote(u)
    response = _proxy_twilio_media(url_decoded)
    if response is None:
        return ("", 404)
    return response


@flask_app.post("/api/rrhh/upload")
@rrhh_permission_required(
    auth_rrhh.PERM_CONVERSATIONS_MANAGE,
    message="Sin permiso para subir archivos.",
)
def rrhh_upload_api():
    """Sube un archivo (imagen o PDF) y devuelve una URL pública o firmada para usar como adjunto."""
    url, err = _upload_file_to_storage("handoff_uploads")
    if err:
        if "Storage no configurado" in err:
            return jsonify({"ok": False, "error": err}), 501
        if "supera el límite" in err:
            return jsonify({"ok": False, "error": err}), 400
        if "Tipo no permitido" in err:
            return jsonify({"ok": False, "error": err}), 400
        if "No se envió" in err:
            return jsonify({"ok": False, "error": err}), 400
        return jsonify({"ok": False, "error": err}), 500
    return jsonify({"ok": True, "url": url})


def _upload_file_to_storage(prefix_path: str):
    """Sube el archivo del request a Firebase Storage. prefix_path ej: 'handoff_uploads' o 'comunicados_uploads'."""
    bucket = _get_storage_bucket()
    if not bucket:
        return None, "Storage no configurado (Firebase Storage)."
    file_storage = request.files.get("file")
    if not file_storage or not file_storage.filename:
        return None, "No se envió ningún archivo."
    raw = file_storage.read()
    if len(raw) > UPLOAD_MAX_BYTES:
        return None, f"El archivo supera el límite de {UPLOAD_MAX_BYTES // (1024*1024)} MB."
    ext = (file_storage.filename or "").rsplit(".", 1)[-1].lower()
    if ext not in UPLOAD_ALLOWED_EXTENSIONS:
        return None, f"Tipo no permitido. Permitidos: {', '.join(UPLOAD_ALLOWED_EXTENSIONS)}."
    content_type = file_storage.content_type or ("application/pdf" if ext == "pdf" else "image/jpeg")
    safe_name = "".join(c for c in file_storage.filename if c.isalnum() or c in "._- ").strip() or "archivo"
    path = f"{prefix_path}/{uuid.uuid4().hex}_{safe_name}"
    try:
        blob = bucket.blob(path)
        blob.upload_from_string(raw, content_type=content_type)
        try:
            url = blob.generate_signed_url(expiration=timedelta(days=7), method="GET")
        except Exception:
            blob.make_public()
            url = blob.public_url
        return url, None
    except Exception as e:
        return None, str(e)


@flask_app.post("/api/comunicados/upload")
@rrhh_permission_required(
    auth_rrhh.PERM_COMUNICADOS_SEND,
    message="No tenés permisos para enviar comunicados.",
)
def api_comunicados_upload():
    """Sube una imagen o PDF para adjuntar al comunicado; devuelve la URL pública o firmada."""
    url, err = _upload_file_to_storage("comunicados_uploads")
    if err:
        if "Storage no configurado" in err:
            return jsonify({"ok": False, "error": err + " Configurá FIREBASE_STORAGE_BUCKET (ej: it-analyzer.firebasestorage.app)."}), 501
        if "No se envió" in err or "Tipo no permitido" in err or "supera el límite" in err:
            return jsonify({"ok": False, "error": err}), 400
        return jsonify({"ok": False, "error": err}), 500
    return jsonify({"ok": True, "url": url})


@flask_app.post("/api/rrhh/conversaciones/<conversation_id>/mensajes")
@rrhh_permission_required(
    auth_rrhh.PERM_CONVERSATIONS_MANAGE,
    message="Sin permiso para gestionar conversaciones.",
)
def rrhh_responder_api(conversation_id):
    data = request.get_json(silent=True) or {}
    mensaje = str(data.get("mensaje") or "").strip()
    media_url_raw = data.get("media_url") or data.get("media_urls")
    media_urls = []
    if isinstance(media_url_raw, list):
        media_urls = [str(u).strip() for u in media_url_raw if u and str(u).strip().startswith("http")]
    elif isinstance(media_url_raw, str) and media_url_raw.strip().startswith("http"):
        media_urls = [media_url_raw.strip()]
    agente = _resolve_rrhh_agent(data)
    if not mensaje and not media_urls:
        return jsonify({"ok": False, "error": "Escribí un mensaje o agregá la URL de una imagen/archivo"}), 400

    conv = _fetch_handoff(conversation_id)
    if not conv:
        return jsonify({"ok": False, "error": "Conversación no encontrada"}), 404
    if not _conversation_matches_selected_company(conv):
        return jsonify({"ok": False, "error": "Conversación no disponible para esta empresa."}), 404

    estado = str(conv.get("estado") or "").strip().lower()
    if estado == HANDOFF_STATUS_CLOSED:
        return jsonify({"ok": False, "error": "La conversación está cerrada"}), 400

    if estado != HANDOFF_STATUS_ACTIVE:
        _take_handoff(conversation_id, agente)

    # Idempotencia básica para evitar duplicados por doble submit/click en pocos segundos.
    ultimo_texto_rrhh = str(conv.get("ultimo_rrhh_text") or "").strip()
    ultimo_agente_rrhh = str(conv.get("ultimo_rrhh_agente_id") or "").strip().lower()
    ultimo_rrhh_at = _as_utc_naive(conv.get("ultimo_rrhh_at"))
    ahora = _as_utc_naive(_utc_now())
    is_same_message = ultimo_texto_rrhh.lower() == mensaje.lower()
    same_agent = ultimo_agente_rrhh == str(agente.get("agent_id") or "").strip().lower()
    if ultimo_rrhh_at and ahora and is_same_message and same_agent and not media_urls:
        if (ahora - ultimo_rrhh_at).total_seconds() <= 8:
            return jsonify({"ok": True, "conversation_id": conversation_id, "duplicate_ignored": True})

    _add_handoff_message(
        conversation_id,
        remitente="rrhh",
        texto=mensaje or "(archivo adjunto)",
        agente=agente.get("display_name"),
        media_url=media_urls if media_urls else None,
    )
    _upsert_handoff(
        conversation_id,
        {
            "rrhh_agente": agente.get("display_name"),
            "rrhh_agente_id": agente.get("agent_id"),
            "updated_at": _utc_now(),
            "ultimo_rrhh_text": mensaje,
            "ultimo_rrhh_agente_id": str(agente.get("agent_id") or "").strip().lower(),
            "ultimo_rrhh_at": _utc_now(),
        },
        merge=True,
    )
    return jsonify({"ok": True, "conversation_id": conversation_id})


@flask_app.get("/api/filtros/contexto")
@rrhh_auth_required
def filtros_contexto_api():
    """Empresas con branches y areas para filtros en estadísticas e historial."""
    company = _current_company()
    ctx = _companies_for_filter_context()
    return jsonify({
        "ok": True,
        "companies": ctx,
        "selected_company_id": company.get("company_id") if company else None,
    })


@flask_app.get("/api/stats")
@rrhh_auth_required
def stats_api():
    if not _can_view_stats():
        return jsonify({"ok": False, "error": "Sin permiso para ver estadísticas."}), 403
    company_id_raw = request.args.get("company_id", "").strip() or None
    company_id = _normalize_company_id(company_id_raw) if company_id_raw else None
    branches_param = request.args.get("branches")
    branches = [b.strip() for b in (branches_param or "").split(",") if b.strip()] if branches_param else None
    areas_param = request.args.get("areas")
    areas = [a.strip() for a in (areas_param or "").split(",") if a.strip()] if areas_param else None
    if company_id:
        handoff_records = _list_handoffs(
            include_closed=True,
            limit=10000,
            company_id=company_id,
            branches=branches if branches else None,
            areas=areas if areas else None,
        )
    else:
        handoff_records = _all_handoff_records_for_stats()
    stats = stats_service.obtener_estadisticas(
        chatbot.db,
        rrhh_records=handoff_records,
        company_id=company_id,
    )
    filter_applied = {
        "company_id": company_id,
        "branches": branches or [],
        "areas": areas or [],
    }
    response = jsonify(
        {
            "ok": True,
            "source_project": _firebase_project_id(),
            "server_boot_at": SERVER_BOOT_AT,
            "filter_applied": filter_applied,
            **stats,
        }
    )
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Server-Boot-At"] = SERVER_BOOT_AT
    response.headers["X-Firebase-Project"] = _firebase_project_id()
    return response


@flask_app.post("/api/reset")
def reset_api():
    limpiar_estado_conversacion()
    _clear_handoff_session()
    _clear_chat_context()
    session["chat_session_id"] = _new_conversation_id()
    return jsonify(
        {
            "ok": True,
            "reply": "Sesión reiniciada. ¿De qué empresa me hablás? Elegí una opción o escribí el nombre.",
            "quick_actions": _construir_acciones_empresas(limite=8),
            "handoff_active": False,
        }
    )


if __name__ == "__main__":
    puerto = int(os.getenv("PORT", "5000"))
    flask_app.run(host="0.0.0.0", port=puerto, debug=False)
