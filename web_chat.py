import os

from flask import Flask, jsonify, render_template, request, session

import app as chatbot
import stats_service


flask_app = Flask(__name__)
flask_app.config["SECRET_KEY"] = os.getenv("CHATBOT_WEB_SECRET", "dev-chatbot-secret")


def _accion(label, value, variant="default"):
    return {"label": label, "value": value, "variant": variant}


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


def procesar_feedback_pendiente(texto_usuario, tema_pendiente, temas_map):
    tipo, texto_norm = chatbot.clasificar_input_feedback(texto_usuario)

    if tipo == "feedback":
        chatbot.registrar_feedback(tema_pendiente, texto_norm)
        limpiar_estado_conversacion()
        return (
            "¡Gracias por tu feedback! 🙌\n"
            "Si querés, escribime otra consulta o poné 'menu' para ver temas.",
            False,
            False,
            construir_acciones_menu(temas_map, limite=6),
        )

    if tipo == "menu":
        limpiar_estado_conversacion()
        return (
            construir_menu_texto(temas_map),
            False,
            False,
            construir_acciones_menu(temas_map),
        )

    if tipo == "salir":
        limpiar_estado_conversacion()
        return "Gracias por comunicarte con RRHH de Bacar. ¡Buen día!", False, True, []

    if tipo == "consulta":
        limpiar_estado_conversacion()
        return None, False, False, []

    return (
        "Podés responder 'si' o 'no'. Si preferís, también podés escribir una nueva consulta.",
        True,
        False,
        construir_acciones_feedback(),
    )


def responder_chat(mensaje_usuario):
    temas_map = construir_temas_map()
    mensaje_norm = chatbot.normalizar_texto(mensaje_usuario)

    if not mensaje_norm:
        return (
            "No llegué a entender tu consulta. ¿Podés reformularla?",
            False,
            False,
            construir_acciones_menu(temas_map, limite=6),
        )

    tema_pendiente = session.get("pending_feedback_topic")
    if tema_pendiente:
        (
            respuesta_feedback,
            espera_feedback,
            finalizar,
            quick_actions,
        ) = procesar_feedback_pendiente(
            mensaje_usuario,
            tema_pendiente,
            temas_map,
        )
        if respuesta_feedback is not None:
            return respuesta_feedback, espera_feedback, finalizar, quick_actions
        # Si llega una nueva consulta durante feedback, sigue flujo normal.

    if mensaje_norm == "menu":
        return construir_menu_texto(temas_map), False, False, construir_acciones_menu(
            temas_map
        )

    if mensaje_norm in chatbot.PALABRAS_SALIDA:
        return "Gracias por comunicarte con RRHH de Bacar. ¡Buen día!", False, True, []

    respuesta, tema_id = chatbot.obtener_respuesta(mensaje_usuario, temas_map)
    if respuesta:
        requiere_feedback = tema_id not in chatbot.TEMAS_SIN_FEEDBACK
        quick_actions = []
        if requiere_feedback:
            session["pending_feedback_topic"] = tema_id
            respuesta = (
                f"{respuesta}\n\n"
                "¿Esta información te fue de utilidad? (si/no)"
            )
            quick_actions = construir_acciones_feedback()
        else:
            quick_actions = construir_acciones_menu(temas_map, limite=4)
        return respuesta, requiere_feedback, False, quick_actions

    chatbot.registrar_pendiente(mensaje_usuario)
    return (
        armar_respuesta_no_entendida(mensaje_usuario, temas_map),
        False,
        False,
        construir_acciones_sugerencias(mensaje_usuario, temas_map),
    )


@flask_app.get("/")
def home():
    temas_map = construir_temas_map()
    return render_template(
        "chat.html",
        bienvenida=chatbot.MENSAJE_BIENVENIDA,
        quick_actions_iniciales=construir_acciones_menu(temas_map, limite=6),
    )


@flask_app.get("/estadisticas")
def stats_page():
    return render_template("stats.html")


@flask_app.post("/api/chat")
def chat_api():
    data = request.get_json(silent=True) or {}
    mensaje = data.get("message", "")

    if not isinstance(mensaje, str):
        return jsonify({"ok": False, "error": "Formato de mensaje inválido"}), 400

    respuesta, espera_feedback, finalizar, quick_actions = responder_chat(mensaje)
    return jsonify(
        {
            "ok": True,
            "reply": respuesta,
            "await_feedback": espera_feedback,
            "end_session": finalizar,
            "quick_actions": quick_actions,
        }
    )


@flask_app.get("/api/stats")
def stats_api():
    stats = stats_service.obtener_estadisticas(chatbot.db)
    return jsonify({"ok": True, **stats})


@flask_app.post("/api/reset")
def reset_api():
    limpiar_estado_conversacion()
    temas_map = construir_temas_map()
    return jsonify(
        {
            "ok": True,
            "reply": "Sesión reiniciada. ¿En qué puedo ayudarte?",
            "quick_actions": construir_acciones_menu(temas_map, limite=6),
        }
    )


if __name__ == "__main__":
    puerto = int(os.getenv("PORT", "5000"))
    flask_app.run(host="0.0.0.0", port=puerto, debug=False)
