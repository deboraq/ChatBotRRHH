import os
import uuid
from datetime import datetime, timezone

from flask import Flask, jsonify, render_template, request, session

import app as chatbot
import stats_service


flask_app = Flask(__name__)
flask_app.config["SECRET_KEY"] = os.getenv("CHATBOT_WEB_SECRET", "dev-chatbot-secret")
SERVER_BOOT_AT = datetime.now(timezone.utc).isoformat(timespec="seconds")

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


def _accion(label, value, variant="default"):
    return {"label": label, "value": value, "variant": variant}


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


def _fmt_fecha(dt):
    dt2 = _as_utc_naive(dt)
    if not dt2:
        return "Sin fecha"
    return dt2.strftime("%Y-%m-%d %H:%M")


def _set_handoff_session(conversation_id):
    session["handoff_conversation_id"] = conversation_id
    session["last_rrhh_seen_iso"] = ""


def _clear_handoff_session():
    session.pop("handoff_conversation_id", None)
    session.pop("last_rrhh_seen_iso", None)


def _get_handoff_session_id():
    return session.get("handoff_conversation_id")


def _get_last_seen_rrhh():
    raw = session.get("last_rrhh_seen_iso", "")
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


def _list_handoffs(include_closed=False, limit=100):
    if chatbot.db:
        docs = [
            _from_firestore_doc(doc)
            for doc in chatbot.db.collection("rrhh_handoffs").stream()
        ]
    else:
        docs = [dict(value) for value in IN_MEMORY_HANDOFFS.values()]

    filtered = []
    for item in docs:
        estado = str(item.get("estado") or "").strip().lower()
        if not include_closed and estado == HANDOFF_STATUS_CLOSED:
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


def _add_handoff_message(
    conversation_id,
    remitente,
    texto,
    agente="",
    visible_to_colaborador=True,
):
    now = _utc_now()
    payload = {
        "remitente": remitente,
        "texto": str(texto).strip(),
        "agente": str(agente or "").strip(),
        "fecha": now,
        "visible_to_colaborador": bool(visible_to_colaborador),
    }

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
        },
        merge=True,
    )


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
            prefijo = f"👩‍💼 RRHH{f' ({agente})' if agente else ''}"
        elif remitente == "sistema":
            prefijo = "ℹ️ Sistema"
        else:
            prefijo = "📩"
        lineas.append(f"{prefijo} [{fecha}]: {texto}")
    return "\n".join(lineas)


def _take_handoff(conversation_id, agente):
    conv = _fetch_handoff(conversation_id)
    if not conv:
        return False
    _upsert_handoff(
        conversation_id,
        {
            "estado": HANDOFF_STATUS_ACTIVE,
            "rrhh_agente": agente,
            "updated_at": _utc_now(),
        },
        merge=True,
    )
    _add_handoff_message(
        conversation_id,
        remitente="sistema",
        texto=f"Tu conversación fue tomada por RRHH ({agente}).",
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


def construir_temas_map():
    temas = chatbot.obtener_temas_desde_firestore()
    if not temas:
        temas = sorted(chatbot.FAQ_FALLBACK.keys(), key=chatbot.normalizar_texto)
    return {str(i): tema for i, tema in enumerate(temas, start=1)}


def construir_menu_texto(temas_map):
    lineas = ["📚 Menú de temas disponibles:"]
    for numero, tema in temas_map.items():
        lineas.append(f"{numero}. {tema.capitalize()}")
    lineas.append("H. Hablar con alguien de RRHH")
    return "\n".join(lineas)


def construir_acciones_menu(temas_map, limite=8):
    acciones = []
    for numero, tema in list(temas_map.items())[:limite]:
        acciones.append(_accion(f"{numero}. {tema.capitalize()}", numero, "topic"))

    if len(temas_map) > limite:
        acciones.append(_accion("Ver menú completo", "menu", "secondary"))

    acciones.append(_accion("Hablar con RRHH", "h", "secondary"))
    return acciones


def construir_acciones_feedback():
    return [
        _accion("Sí", "si", "positive"),
        _accion("No", "no", "negative"),
        _accion("Nueva consulta", "menu", "secondary"),
    ]


def construir_acciones_sugerencias(consulta, temas_map):
    sugerencias = chatbot.sugerir_temas(consulta, temas_map)
    acciones = []
    for tema in sugerencias[:4]:
        acciones.append(_accion(tema.capitalize(), tema, "topic"))
    acciones.append(_accion("Ver menú", "menu", "secondary"))
    acciones.append(_accion("Hablar con RRHH", "h", "secondary"))
    return acciones


def construir_acciones_handoff():
    return [
        _accion("Actualizar mensajes RRHH", "__poll_rrhh__", "secondary"),
        _accion("Finalizar chat con RRHH", "__cerrar_rrhh__", "negative"),
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
    session.pop("pending_feedback_topic", None)


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
    active_id = _get_handoff_session_id()
    existing = _fetch_handoff(active_id) if active_id else None
    now = _utc_now()

    if existing is not None:
        estado_actual = str(existing.get("estado") or "").strip().lower()
        if estado_actual in {HANDOFF_STATUS_PENDING, HANDOFF_STATUS_ACTIVE}:
            conversation_id = active_id
        else:
            _clear_handoff_session()
            conversation_id = _new_conversation_id()
            existing = None
    else:
        conversation_id = _new_conversation_id()

    if existing is None:
        _upsert_handoff(
            conversation_id,
            {
                "conversation_id": conversation_id,
                "estado": HANDOFF_STATUS_PENDING,
                "created_at": now,
                "updated_at": now,
                "rrhh_agente": "",
                "ultimo_mensaje": "",
                "ultima_consulta": mensaje_usuario.strip() or "Solicitud de contacto RRHH",
            },
            merge=False,
        )
        _add_handoff_message(
            conversation_id,
            remitente="sistema",
            texto="El colaborador solicitó hablar con RRHH.",
            visible_to_colaborador=False,
        )

    if mensaje_usuario.strip():
        _add_handoff_message(
            conversation_id,
            remitente="colaborador",
            texto=mensaje_usuario,
        )
        _upsert_handoff(
            conversation_id,
            {"ultima_consulta": mensaje_usuario.strip(), "updated_at": now},
            merge=True,
        )

    _set_handoff_session(conversation_id)
    return conversation_id


def procesar_feedback_pendiente(texto_usuario, tema_pendiente, temas_map):
    tipo, texto_norm = chatbot.clasificar_input_feedback(texto_usuario)

    if tipo == "feedback":
        guardado = chatbot.registrar_feedback(tema_pendiente, texto_norm)
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
            quick_actions=construir_acciones_menu(temas_map, limite=6),
        )

    if tipo == "menu":
        limpiar_estado_conversacion()
        return _payload(
            construir_menu_texto(temas_map),
            quick_actions=construir_acciones_menu(temas_map),
        )

    if tipo == "salir":
        limpiar_estado_conversacion()
        return _payload("Gracias por comunicarte con RRHH de Bacar. ¡Buen día!", end_session=True)

    if tipo == "consulta":
        limpiar_estado_conversacion()
        return None

    return _payload(
        "Podés responder 'si' o 'no'. Si preferís, también podés escribir una nueva consulta.",
        await_feedback=True,
        quick_actions=construir_acciones_feedback(),
    )


def responder_chat(mensaje_usuario):
    temas_map = construir_temas_map()
    mensaje_norm = chatbot.normalizar_texto(mensaje_usuario)

    if not mensaje_norm:
        return _payload(
            "No llegué a entender tu consulta. ¿Podés reformularla?",
            quick_actions=construir_acciones_menu(temas_map, limite=6),
        )

    if mensaje_norm in chatbot.PALABRAS_SALIDA:
        handoff_id = _get_handoff_session_id()
        if handoff_id:
            _close_handoff(handoff_id, "colaborador")
            _clear_handoff_session()
        return _payload("Gracias por comunicarte con RRHH de Bacar. ¡Buen día!", end_session=True)

    handoff_id = _get_handoff_session_id()
    if handoff_id:
        conv = _fetch_handoff(handoff_id)
        if conv and str(conv.get("estado") or "").strip().lower() == HANDOFF_STATUS_CLOSED:
            _clear_handoff_session()
            handoff_id = None

    if handoff_id:
        if mensaje_norm in HANDOFF_END_COMMANDS:
            _close_handoff(handoff_id, "colaborador")
            _clear_handoff_session()
            return _payload(
                "✅ Cerré la conversación con RRHH. Si querés, seguimos con el asistente virtual.",
                quick_actions=construir_acciones_menu(temas_map, limite=6),
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
                texto = "⏳ Tu consulta sigue en cola. RRHH te responde en breve."
            else:
                agente = conv.get("rrhh_agente") or "equipo RRHH"
                texto = f"🟢 Chat activo con {agente}. Aún no hay nuevos mensajes."
            return _payload(
                texto,
                handoff_active=True,
                quick_actions=construir_acciones_handoff(),
            )

        # Mientras está activo el handoff, los mensajes van al canal humano.
        _add_handoff_message(handoff_id, remitente="colaborador", texto=mensaje_usuario)
        _upsert_handoff(
            handoff_id,
            {"ultima_consulta": mensaje_usuario.strip(), "updated_at": _utc_now()},
            merge=True,
        )
        conv = _fetch_handoff(handoff_id) or {}
        estado = str(conv.get("estado") or "").strip().lower()
        if estado == HANDOFF_STATUS_PENDING:
            texto = "📨 Mensaje enviado. RRHH todavía no tomó la conversación."
        else:
            agente = conv.get("rrhh_agente") or "RRHH"
            texto = f"📨 Mensaje enviado a {agente}. Te responderán por este chat."
        return _payload(
            texto,
            handoff_active=True,
            quick_actions=construir_acciones_handoff(),
        )

    tema_pendiente = session.get("pending_feedback_topic")
    if tema_pendiente:
        payload = procesar_feedback_pendiente(mensaje_usuario, tema_pendiente, temas_map)
        if payload is not None:
            return payload
        # Si llega una nueva consulta durante feedback, sigue flujo normal.

    if chatbot.solicita_contacto_rrhh(mensaje_norm):
        conversation_id = _iniciar_handoff_rrhh(mensaje_usuario)
        return _payload(
            "👩‍💼 Perfecto. Derivé tu consulta al equipo de RRHH.\n"
            "Te van a responder por este mismo chat. Podés seguir escribiendo aquí.",
            handoff_active=True,
            quick_actions=construir_acciones_handoff(),
        )

    if mensaje_norm == "menu":
        return _payload(
            construir_menu_texto(temas_map),
            quick_actions=construir_acciones_menu(temas_map),
        )

    respuesta, tema_id = chatbot.obtener_respuesta(mensaje_usuario, temas_map)
    if respuesta:
        requiere_feedback = tema_id not in chatbot.TEMAS_SIN_FEEDBACK
        if requiere_feedback:
            session["pending_feedback_topic"] = tema_id
            respuesta = f"{respuesta}\n\n¿Esta información te fue de utilidad? (si/no)"
            return _payload(
                respuesta,
                await_feedback=True,
                quick_actions=construir_acciones_feedback(),
            )
        return _payload(
            respuesta,
            quick_actions=construir_acciones_menu(temas_map, limite=4),
        )

    guardado_pendiente = chatbot.registrar_pendiente(mensaje_usuario)
    respuesta = armar_respuesta_no_entendida(mensaje_usuario, temas_map)
    if not guardado_pendiente:
        respuesta += "\nℹ️ No pude registrar esta consulta en la base de datos."
    return _payload(
        respuesta,
        quick_actions=construir_acciones_sugerencias(mensaje_usuario, temas_map),
    )


def _serialize_handoff(conv):
    return {
        "conversation_id": conv.get("conversation_id") or conv.get("id"),
        "estado": conv.get("estado") or HANDOFF_STATUS_PENDING,
        "rrhh_agente": conv.get("rrhh_agente") or "",
        "ultima_consulta": conv.get("ultima_consulta") or "",
        "updated_at": _fmt_fecha(conv.get("updated_at")),
    }


def _serialize_messages(messages):
    payload = []
    for msg in messages:
        payload.append(
            {
                "remitente": str(msg.get("remitente") or ""),
                "texto": str(msg.get("texto") or ""),
                "agente": str(msg.get("agente") or ""),
                "fecha": _fmt_fecha(msg.get("fecha")),
                "fecha_iso": (_as_utc_naive(msg.get("fecha")) or datetime.min).isoformat(
                    timespec="seconds"
                ),
            }
        )
    return payload


def reset_in_memory_handoffs():
    IN_MEMORY_HANDOFFS.clear()


@flask_app.get("/")
def home():
    temas_map = construir_temas_map()
    return render_template(
        "chat.html",
        bienvenida=chatbot.MENSAJE_BIENVENIDA,
        quick_actions_iniciales=construir_acciones_menu(temas_map, limite=6),
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
def rrhh_page():
    return render_template("rrhh.html")


@flask_app.get("/estadisticas")
def stats_page():
    return render_template("stats.html")


@flask_app.post("/api/chat")
def chat_api():
    data = request.get_json(silent=True) or {}
    mensaje = data.get("message", "")

    if not isinstance(mensaje, str):
        return jsonify({"ok": False, "error": "Formato de mensaje inválido"}), 400

    payload = responder_chat(mensaje)
    return jsonify({"ok": True, **payload})


@flask_app.get("/api/chat/poll")
def chat_poll_api():
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


@flask_app.get("/api/rrhh/conversaciones")
def rrhh_conversaciones_api():
    include_closed = str(request.args.get("include_closed", "false")).lower() == "true"
    convs = _list_handoffs(include_closed=include_closed, limit=150)
    return jsonify({"ok": True, "conversaciones": [_serialize_handoff(c) for c in convs]})


@flask_app.get("/api/rrhh/conversaciones/<conversation_id>/mensajes")
def rrhh_mensajes_api(conversation_id):
    conv = _fetch_handoff(conversation_id)
    if not conv:
        return jsonify({"ok": False, "error": "Conversación no encontrada"}), 404
    mensajes = _list_handoff_messages(conversation_id)
    return jsonify(
        {
            "ok": True,
            "conversation_id": conversation_id,
            "estado": conv.get("estado") or HANDOFF_STATUS_PENDING,
            "rrhh_agente": conv.get("rrhh_agente") or "",
            "mensajes": _serialize_messages(mensajes),
        }
    )


@flask_app.post("/api/rrhh/conversaciones/<conversation_id>/tomar")
def rrhh_tomar_api(conversation_id):
    data = request.get_json(silent=True) or {}
    agente = str(data.get("agente") or "RRHH").strip() or "RRHH"
    if not _take_handoff(conversation_id, agente):
        return jsonify({"ok": False, "error": "Conversación no encontrada"}), 404
    return jsonify({"ok": True, "conversation_id": conversation_id, "estado": HANDOFF_STATUS_ACTIVE})


@flask_app.post("/api/rrhh/conversaciones/<conversation_id>/cerrar")
def rrhh_cerrar_api(conversation_id):
    data = request.get_json(silent=True) or {}
    agente = str(data.get("agente") or "RRHH").strip() or "RRHH"
    if not _close_handoff(conversation_id, agente):
        return jsonify({"ok": False, "error": "Conversación no encontrada"}), 404
    return jsonify({"ok": True, "conversation_id": conversation_id, "estado": HANDOFF_STATUS_CLOSED})


@flask_app.post("/api/rrhh/conversaciones/<conversation_id>/mensajes")
def rrhh_responder_api(conversation_id):
    data = request.get_json(silent=True) or {}
    mensaje = str(data.get("mensaje") or "").strip()
    agente = str(data.get("agente") or "RRHH").strip() or "RRHH"
    if not mensaje:
        return jsonify({"ok": False, "error": "Mensaje vacío"}), 400

    conv = _fetch_handoff(conversation_id)
    if not conv:
        return jsonify({"ok": False, "error": "Conversación no encontrada"}), 404

    estado = str(conv.get("estado") or "").strip().lower()
    if estado == HANDOFF_STATUS_CLOSED:
        return jsonify({"ok": False, "error": "La conversación está cerrada"}), 400

    if estado != HANDOFF_STATUS_ACTIVE:
        _take_handoff(conversation_id, agente)

    _add_handoff_message(
        conversation_id,
        remitente="rrhh",
        texto=mensaje,
        agente=agente,
    )
    _upsert_handoff(
        conversation_id,
        {"rrhh_agente": agente, "updated_at": _utc_now()},
        merge=True,
    )
    return jsonify({"ok": True, "conversation_id": conversation_id})


@flask_app.get("/api/stats")
def stats_api():
    handoff_records = _all_handoff_records_for_stats()
    stats = stats_service.obtener_estadisticas(chatbot.db, rrhh_records=handoff_records)
    response = jsonify(
        {
            "ok": True,
            "source_project": _firebase_project_id(),
            "server_boot_at": SERVER_BOOT_AT,
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
    temas_map = construir_temas_map()
    return jsonify(
        {
            "ok": True,
            "reply": "Sesión reiniciada. ¿En qué puedo ayudarte?",
            "quick_actions": construir_acciones_menu(temas_map, limite=6),
            "handoff_active": False,
        }
    )


if __name__ == "__main__":
    puerto = int(os.getenv("PORT", "5000"))
    flask_app.run(host="0.0.0.0", port=puerto, debug=False)
