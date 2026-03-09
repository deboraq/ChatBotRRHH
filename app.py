import os
import re
import unicodedata
from datetime import datetime
from difflib import SequenceMatcher

from firebase_config import inicializar_firestore

try:
    from textblob import TextBlob
except ImportError:
    TextBlob = None

try:
    from thefuzz import process
except ImportError:
    process = None

# ==========================================================
# 1. CONFIGURACIÓN INICIAL Y CONEXIÓN CON FIRESTORE
# ==========================================================
COMPANY_NAME = str(os.getenv("CHATBOT_COMPANY_NAME", "Bacar")).strip() or "Bacar"
HR_TEAM_NAME = str(os.getenv("CHATBOT_HR_TEAM_NAME", "Atención")).strip() or "Atención"
HR_CONTACT = str(os.getenv("CHATBOT_HR_CONTACT", "interno 104")).strip() or "interno 104"


def construir_mensaje_bienvenida():
    return f"👋 ¡Hola! Soy el asistente de {HR_TEAM_NAME} de {COMPANY_NAME}. ¿En qué puedo ayudarte hoy?"


def construir_mensaje_contacto():
    return f"📞 Para hablar con un representante, comunicate al {HR_CONTACT}."


def construir_mensaje_despedida():
    return f"Gracias por comunicarte con {HR_TEAM_NAME} de {COMPANY_NAME}. ¡Buen día!"


def actualizar_configuracion_empresa(company_name=None, hr_team_name=None, hr_contact=None):
    global COMPANY_NAME, HR_TEAM_NAME, HR_CONTACT, MENSAJE_BIENVENIDA, MENSAJE_CONTACTO

    if company_name is not None:
        COMPANY_NAME = str(company_name).strip() or COMPANY_NAME
    if hr_team_name is not None:
        HR_TEAM_NAME = str(hr_team_name).strip() or HR_TEAM_NAME
    if hr_contact is not None:
        HR_CONTACT = str(hr_contact).strip() or HR_CONTACT

    MENSAJE_BIENVENIDA = construir_mensaje_bienvenida()
    MENSAJE_CONTACTO = construir_mensaje_contacto()
    if "capacitacion" in FAQ_FALLBACK:
        FAQ_FALLBACK["capacitacion"] = (
            f"Podés ver los cursos disponibles en la intranet de {COMPANY_NAME}, sección "
            "'Mi Desarrollo'."
        )


MENSAJE_BIENVENIDA = (
    construir_mensaje_bienvenida()
)
MENSAJE_CONTACTO = construir_mensaje_contacto()
MENSAJE_AYUDA = (
    "🆘 Puedo ayudarte con vacaciones, fraccionamiento, recibo, aguinaldo, ART y otros temas.\n"
    "Escribí tu consulta o poné 'menu' para ver todas las opciones."
)
RESPUESTA_DIAS_VACACIONES = (
    "📅 Los días de vacaciones dependen de tu antigüedad:\n"
    "- Hasta 5 años: 14 días corridos.\n"
    "- Más de 5 y hasta 10: 21 días corridos.\n"
    "- Más de 10 y hasta 20: 28 días corridos.\n"
    "- Más de 20 años: 35 días corridos.\n"
    "Si querés, también te explico cómo se gestiona el fraccionamiento."
)
TEMAS_SIN_FEEDBACK = {"saludo", "ayuda", "RRHH"}
# "no" no se incluye para no confundirlo con feedback negativo.
PALABRAS_SALIDA = {"salir", "chau", "exit", "adios", "adiós"}

# Respaldo local para que el chatbot siga funcionando aun sin Firebase.
FAQ_FALLBACK = {
    "vacaciones": (
        "Se deben solicitar con 15 días de anticipación a través del portal "
        "Legajos.online."
    ),
    "fraccionamiento": (
        "Las vacaciones se pueden fraccionar en períodos mínimos de 7 días, "
        "con aval de tu responsable directo."
    ),
    "recibo": (
        "Los recibos de sueldo están disponibles para firma digital el cuarto día "
        "hábil de cada mes en la plataforma habitual."
    ),
    "aguinaldo": (
        "El SAC se abona en dos cuotas: la primera con vencimiento el 30 de junio "
        "y la segunda el 18 de diciembre."
    ),
    "obra social": (
        "Para cambios o consultas sobre tu cobertura médica, debés enviar un correo "
        "a beneficios@bacar.com.ar."
    ),
    "licencia examen": (
        "Tenés derecho a 2 días corridos por examen, hasta 20 días anuales. "
        "Presentá el certificado al día siguiente de rendir."
    ),
    "art": (
        "En caso de accidente laboral, comunicate inmediatamente al 0800 de nuestra "
        "aseguradora y avisá a tu supervisor."
    ),
    "uniforme": (
        "La reposición de uniformes se realiza cada 6 meses. Podés solicitar el tuyo "
        "en la oficina de suministros."
    ),
    "adelanto": (
        "Los pedidos de adelanto de sueldo se reciben hasta el día 20 de cada mes y "
        "no deben superar el 30% del neto."
    ),
    "nacimiento": (
        "Por nacimiento de hijo, contás con 2 días corridos de licencia paga "
        "(según CCT). Recordá traer el acta de nacimiento."
    ),
    "casamiento": (
        "La licencia por matrimonio es de 10 días corridos. Debés avisar con 30 días "
        "de antelación."
    ),
    "capacitacion": (
        f"Podés ver los cursos disponibles en la intranet de {COMPANY_NAME}, sección "
        "'Mi Desarrollo'."
    ),
}

db = inicializar_firestore(verbose=False)
if db:
    print(f"✅ SISTEMA {COMPANY_NAME.upper()}: Conexión exitosa con la base de datos.")
    print("🚀 El asistente virtual está listo para operar.\n")
else:
    print("🧪 Se activa modo local con respuestas de respaldo.")
    print("ℹ️ Para usar Firebase, definí FIREBASE_CREDENTIALS con tu archivo JSON.\n")

# ==========================================================
# 2. DICCIONARIO DE INTELIGENCIA Y SINÓNIMOS
# ==========================================================
SINONIMOS = {
    "vacaciones": [
        "descanso",
        "licencia anual",
        "dias libres",
        "vacas",
        "feriado",
        "dias de vacaciones",
        "cuantos dias de vacaciones",
        "cuanto me corresponde de vacaciones",
    ],
    "fraccionamiento": [
        "fraccionar",
        "fraccionadas",
        "fraccionado",
        "vacaciones fraccionadas",
        "dividir vacaciones",
        "partir vacaciones",
    ],
    "art": ["accidente", "me lastime", "seguro laboral", "la art", "lesion"],
    "recibo": ["sueldo", "comprobante", "liquidacion", "haberes", "recibos"],
    "aguinaldo": [
        "sac",
        "sueldo anual complementario",
        "cobro diciembre",
        "cobro junio",
    ],
    "hola": ["buen dia", "buenas", "hola bot", "buenos dias", "holaa", "saludos"],
    "ayuda": ["no se que hacer", "help", "necesito ayuda", "ayudame", "que hago"],
}

INTENCIONES_CONTACTO = {
    "rrhh", "representante", "persona", "humano", "asesor", "operador",
    "asistente", "agente", "hablar con un agente", "hablar con un asistente",
    "hablar con alguien", "contacto humano", "atencion humana",
}
INTENCIONES_CAMBIAR_EMPRESA = {
    "otra empresa", "cambiar empresa", "cambiar de empresa", "otra compania",
    "cambiar compania", "hablar con otra empresa", "quiero otra empresa",
    "cambiar a otra empresa", "elegir otra empresa",
}
PALABRAS_NEGATIVAS = {
    "mal",
    "pesimo",
    "horrible",
    "enojado",
    "frustrado",
    "molesto",
    "bronca",
    "inutil",
}
FRASES_NEGATIVAS = {
    "no entendes",
    "no entiende",
    "no me entendes",
    "no me entiende",
    "no sirve",
    "no funciona",
    "no me ayuda",
    "no me resolviste",
}
PALABRAS_POSITIVAS = {
    "gracias",
    "excelente",
    "genial",
    "perfecto",
    "util",
    "sirvio",
    "bueno",
    "buenisimo",
}
FRASES_POSITIVAS = {
    "me sirvio",
    "muy util",
    "muchas gracias",
    "me ayudaste",
    "quedo claro",
}


def normalizar_texto(texto):
    texto = str(texto).lower().strip()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(char for char in texto if not unicodedata.combining(char))
    texto = re.sub(r"[^\w\s]", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def contiene_frase(texto_normalizado, frase_normalizada):
    if not texto_normalizado or not frase_normalizada:
        return False
    patron = rf"\b{re.escape(frase_normalizada)}\b"
    return re.search(patron, texto_normalizado) is not None


def puntuar_sentimiento_reglas(consulta_original, consulta_norm):
    score = 0.0

    for frase in FRASES_NEGATIVAS:
        if contiene_frase(consulta_norm, frase):
            score -= 2
    for palabra in PALABRAS_NEGATIVAS:
        if contiene_frase(consulta_norm, palabra):
            score -= 0.7

    for frase in FRASES_POSITIVAS:
        if contiene_frase(consulta_norm, frase):
            score += 1.7
    for palabra in PALABRAS_POSITIVAS:
        if contiene_frase(consulta_norm, palabra):
            score += 0.6

    signos_exclamacion = str(consulta_original).count("!")
    if signos_exclamacion >= 2:
        if score < 0:
            score -= 0.5
        elif score > 0:
            score += 0.3

    return score


def fuzzy_extract_one(query, choices):
    if not choices:
        return None

    if process:
        return process.extractOne(query, choices)

    mejor_opcion = None
    mejor_score = -1
    for opcion in choices:
        score = int(SequenceMatcher(None, query, opcion).ratio() * 100)
        if score > mejor_score:
            mejor_opcion = opcion
            mejor_score = score

    if mejor_opcion is None:
        return None
    return mejor_opcion, mejor_score


def fuzzy_extract(query, choices, limit=3):
    if not choices:
        return []

    if process:
        return process.extract(query, choices, limit=limit)

    puntajes = [(opcion, int(SequenceMatcher(None, query, opcion).ratio() * 100)) for opcion in choices]
    puntajes.sort(key=lambda item: item[1], reverse=True)
    return puntajes[:limit]


def _normalize_company_id(value):
    """Normaliza company_id para uso en Firestore (minúsculas, sin espacios)."""
    if value is None:
        return ""
    return str(value).strip().lower()


# Base de conocimiento por empresa (pregunta/respuesta desde archivo subido)
COMPANY_KNOWLEDGE_COLLECTION = "company_knowledge"


KNOWLEDGE_MATCH_THRESHOLD = 65  # mínimo de similitud (0-100) para usar respuesta de la base
KNOWLEDGE_PARTIAL_THRESHOLD = 55  # umbral para respuesta parcial + oferta de derivación

# Mapeo de temas a áreas de derivación
AREAS_POR_TEMA = {
    "vacaciones": "RRHH",
    "fraccionamiento": "RRHH",
    "licencia": "RRHH",
    "licencia examen": "RRHH",
    "casamiento": "RRHH",
    "nacimiento": "RRHH",
    "adelanto": "RRHH",
    "recibo": "Liquidaciones",
    "aguinaldo": "Liquidaciones",
    "art": "Seguridad e Higiene",
    "obra social": "Beneficios",
    "uniforme": "Suministros",
    "capacitacion": "Capacitación",
}


def obtener_knowledge_empresa(company_id=None):
    """Devuelve la lista de {pregunta, respuesta} para la empresa (desde Firestore)."""
    if not db:
        return []
    cid = _normalize_company_id(company_id)
    if not cid:
        return []
    try:
        doc = db.collection(COMPANY_KNOWLEDGE_COLLECTION).document(cid).get()
        if not doc.exists:
            return []
        data = doc.to_dict() or {}
        entries = data.get("entries") or []
        return [{"pregunta": str(e.get("pregunta") or "").strip(), "respuesta": str(e.get("respuesta") or "").strip()} for e in entries if isinstance(e, dict) and (e.get("pregunta") or e.get("respuesta"))]
    except Exception as exc:
        print(f"⚠️ Error al leer base de conocimiento: {exc}")
        return []


def buscar_en_knowledge(entrada_norm, entries):
    """
    Busca la mejor respuesta en la base de conocimiento de la empresa.
    Devuelve (respuesta, score) siempre con el mejor resultado encontrado.
    Score 0 significa que no hubo ningún match.
    Prioridad: coincidencia exacta en pregunta, luego contiene_frase, luego fuzzy.
    """
    if not entrada_norm or not entries:
        return None, 0
    # Exact match
    for e in entries:
        p = normalizar_texto(e.get("pregunta") or "")
        if p and entrada_norm == p:
            return (e.get("respuesta") or "").strip(), 100
    # La pregunta del usuario contiene alguna pregunta de la base (o al revés)
    for e in entries:
        p = normalizar_texto(e.get("pregunta") or "")
        if not p:
            continue
        if contiene_frase(entrada_norm, p) or contiene_frase(p, entrada_norm):
            return (e.get("respuesta") or "").strip(), 90
        if len(entrada_norm) >= 3 and (p in entrada_norm or entrada_norm in p):
            return (e.get("respuesta") or "").strip(), 85
    # Fuzzy sobre las preguntas — requiere al menos una palabra clave en común
    preguntas_norm = [normalizar_texto(e.get("pregunta") or "") for e in entries if (e.get("pregunta") or "").strip()]
    if not preguntas_norm:
        return None, 0
    match = fuzzy_extract_one(entrada_norm, preguntas_norm)
    if match and match[1] > 0:
        # Verificar que haya al menos una palabra significativa en común (>= 4 letras)
        palabras_usuario = {w for w in entrada_norm.split() if len(w) >= 4}
        palabras_match = {w for w in match[0].split() if len(w) >= 4}
        if palabras_usuario & palabras_match:
            idx = preguntas_norm.index(match[0])
            return (entries[idx].get("respuesta") or "").strip(), match[1]
    return None, 0


def _detectar_intencion(entrada_norm):
    """Detecta si el usuario pregunta por fecha/cuándo, cantidad, proceso, etc."""
    if any(contiene_frase(entrada_norm, p) for p in ["cuando", "que fecha", "en que mes", "que dia", "que momento"]):
        return "fecha"
    if any(contiene_frase(entrada_norm, p) for p in ["cuanto", "cuantos", "dias", "cantidad", "cuantas"]):
        return "cantidad"
    if any(contiene_frase(entrada_norm, p) for p in ["como", "de que manera", "de que forma", "pasos"]):
        return "proceso"
    return "general"


def _mensaje_derivacion(tema=None):
    """Genera mensaje de oferta de derivación al área correspondiente."""
    area = AREAS_POR_TEMA.get(normalizar_texto(tema or ""), "RRHH") if tema else "RRHH"
    return f"Si necesitás más ayuda o querés gestionar esto personalmente, puedo derivarte con el área de **{area}**. ¿Lo hacemos?"


def guardar_knowledge_empresa(company_id, entries):
    """Guarda la base de conocimiento (lista de {pregunta, respuesta}) para la empresa."""
    if not db:
        return False
    cid = _normalize_company_id(company_id)
    if not cid:
        return False
    try:
        payload = {
            "entries": [{"pregunta": str(e.get("pregunta") or "").strip(), "respuesta": str(e.get("respuesta") or "").strip()} for e in entries if isinstance(e, dict)],
            "updated_at": datetime.now(),
        }
        db.collection(COMPANY_KNOWLEDGE_COLLECTION).document(cid).set(payload, merge=True)
        return True
    except Exception as exc:
        print(f"⚠️ Error al guardar base de conocimiento: {exc}")
        return False


guardar_company_knowledge = guardar_knowledge_empresa  # alias para compatibilidad


def obtener_temas_desde_firestore(company_id=None):
    """
    Obtiene la lista de temas (FAQs) disponibles.
    Si company_id está definido, lee de la colección 'faqs' filtrada por company_id.
    Si no hay resultados o company_id es None, usa la colección legacy 'faq_rrhh'.
    """
    if not db:
        return []
    cid = _normalize_company_id(company_id)

    if cid:
        try:
            refs = db.collection("faqs").where("company_id", "==", cid).stream()
            temas = []
            for doc in refs:
                data = doc.to_dict() or {}
                tema = data.get("tema") or doc.id.split("_", 1)[-1] if "_" in doc.id else doc.id
                temas.append(tema)
            if temas:
                return sorted(set(temas), key=normalizar_texto)
        except Exception as exc:
            print(f"⚠️ No se pudieron leer temas desde Firestore (faqs): {exc}")

    try:
        docs = db.collection("faq_rrhh").stream()
        return sorted((doc.id for doc in docs), key=normalizar_texto)
    except Exception as exc:
        print(f"⚠️ No se pudieron leer temas desde Firestore (faq_rrhh): {exc}")
        return []


# ==========================================================
# 3. FUNCIONES DE ADMINISTRACIÓN DE DATOS Y REGISTROS
# ==========================================================
def mostrar_menu(company_id=None):
    print("\n" + "═" * 55)
    print(" 🏢 ASISTENTE VIRTUAL - BACAR SA ")
    print("═" * 55)
    print("Seleccioná un número o escribí el tema de tu consulta:")

    temas_disponibles = obtener_temas_desde_firestore(company_id=company_id)
    if not temas_disponibles:
        temas_disponibles = sorted(FAQ_FALLBACK.keys(), key=normalizar_texto)
        print("⚠️ Mostrando temas en modo local (sin conexión a Firestore).")

    temas_map = {}
    for i, tema in enumerate(temas_disponibles, start=1):
        temas_map[str(i)] = tema
        print(f" {i}. {tema.capitalize()}")

    print(" H. Hablar con un agente")
    print("─" * 55)
    return temas_map


def guardar_en_firestore(coleccion, payload):
    if not db:
        return False
    try:
        db.collection(coleccion).add(payload)
        return True
    except Exception as exc:
        print(f"⚠️ No se pudo guardar en '{coleccion}': {exc}")
        return False


def registrar_feedback(tema, utilidad, company_id=None):
    payload = {"tema": tema, "fue_util": utilidad, "fecha": datetime.now()}
    if company_id is not None and str(company_id).strip():
        payload["company_id"] = str(company_id).strip()
    if not guardar_en_firestore("feedback_respuestas", payload):
        print("ℹ️ Feedback no persistido por falta de conexión.")
        return False
    return True

def analizar_sentimiento(consulta):
    consulta_norm = normalizar_texto(consulta)
    if not consulta_norm:
        return "neutral"

    score_reglas = puntuar_sentimiento_reglas(consulta, consulta_norm)
    polaridad = 0.0
    if TextBlob is not None:
        try:
            analisis = TextBlob(consulta)
            polaridad = analisis.sentiment.polarity
        except Exception:
            polaridad = 0.0

    score_total = score_reglas + (polaridad * 2)
    if score_total <= -0.8 or score_reglas <= -2:
        return "negativo/enojado"
    if score_total >= 0.8 or score_reglas >= 2:
        return "positivo/amigable"
    return "neutral"


def registrar_pendiente(consulta, company_id=None):
    payload = {
        "pregunta": consulta,
        "fecha": datetime.now(),
        "estado": "pendiente",
        "sentimiento": analizar_sentimiento(consulta),
    }
    if company_id is not None and str(company_id).strip():
        payload["company_id"] = str(company_id).strip()
    if not guardar_en_firestore("consultas_pendientes", payload):
        print("ℹ️ Consulta pendiente no persistida por falta de conexión.")
        return False
    return True


def obtener_respuesta_faq(tema, company_id=None):
    """
    Obtiene la respuesta FAQ para un tema.
    Si company_id está definido, busca primero en la colección 'faqs' (por company_id + tema).
    Si no encuentra, usa 'faq_rrhh' y luego FAQ_FALLBACK.
    """
    tema_norm = normalizar_texto(tema)
    cid = _normalize_company_id(company_id)

    if db and cid:
        try:
            doc_id = f"{cid}_{tema_norm}"
            doc = db.collection("faqs").document(doc_id).get()
            if doc.exists:
                respuesta = (doc.to_dict() or {}).get("respuesta")
                if respuesta:
                    return respuesta
            refs = db.collection("faqs").where("company_id", "==", cid).stream()
            for d in refs:
                data = d.to_dict() or {}
                if normalizar_texto(data.get("tema") or d.id) == tema_norm:
                    respuesta = data.get("respuesta")
                    if respuesta:
                        return respuesta
        except Exception as exc:
            print(f"⚠️ Error al consultar FAQ en Firestore (faqs): {exc}")

    if db:
        try:
            doc = db.collection("faq_rrhh").document(tema).get()
            if doc.exists:
                respuesta = doc.to_dict().get("respuesta")
                if respuesta:
                    return respuesta
            for doc in db.collection("faq_rrhh").stream():
                if normalizar_texto(doc.id) == tema_norm:
                    respuesta = doc.to_dict().get("respuesta")
                    if respuesta:
                        return respuesta
        except Exception as exc:
            print(f"⚠️ Error al consultar FAQ en Firestore: {exc}")

    return FAQ_FALLBACK.get(tema_norm)


# ==========================================================
# 4. LÓGICA DE PROCESAMIENTO DE CONVERSACIÓN (RESPUESTAS)
# ==========================================================
def detectar_tema(entrada_norm, temas_map):
    tema_directo = temas_map.get(entrada_norm)
    if tema_directo:
        return tema_directo

    indice_temas = {normalizar_texto(tema): tema for tema in temas_map.values()}

    # Prioriza frases largas para evitar falsos positivos.
    for tema_norm, tema_real in sorted(indice_temas.items(), key=lambda item: len(item[0]), reverse=True):
        if contiene_frase(entrada_norm, tema_norm):
            return tema_real

    for oficial, variaciones in SINONIMOS.items():
        tema_destino = indice_temas.get(normalizar_texto(oficial), normalizar_texto(oficial))
        for alias in [oficial, *variaciones]:
            if contiene_frase(entrada_norm, normalizar_texto(alias)):
                return tema_destino

    if len(entrada_norm) < 3:
        return None

    opciones = {}
    for tema_norm, tema_real in indice_temas.items():
        opciones[tema_norm] = tema_real

    for oficial, variaciones in SINONIMOS.items():
        tema_destino = indice_temas.get(normalizar_texto(oficial), normalizar_texto(oficial))
        for alias in [oficial, *variaciones]:
            alias_norm = normalizar_texto(alias)
            if len(alias_norm) >= 3:
                opciones.setdefault(alias_norm, tema_destino)

    if not opciones:
        return None

    match = fuzzy_extract_one(entrada_norm, list(opciones.keys()))
    if match and match[1] >= 78:
        return opciones[match[0]]
    return None


def es_saludo(entrada_norm):
    saludos = ["hola", *SINONIMOS["hola"]]
    return any(contiene_frase(entrada_norm, normalizar_texto(saludo)) for saludo in saludos)


def solicita_contacto_rrhh(entrada_norm):
    if entrada_norm == "h":
        return True
    return any(contiene_frase(entrada_norm, clave) for clave in INTENCIONES_CONTACTO)


def solicita_cambiar_empresa(entrada_norm):
    """True si el usuario pide cambiar de empresa (ej. 'quiero hablar con otra empresa')."""
    if any(contiene_frase(entrada_norm, clave) for clave in INTENCIONES_CAMBIAR_EMPRESA):
        return True
    # Fallback: "otra" + "empresa" o "cambiar" + "empresa" en el mensaje
    if "empresa" in entrada_norm and ("otra" in entrada_norm or "cambiar" in entrada_norm):
        return True
    if "compania" in entrada_norm and ("otra" in entrada_norm or "cambiar" in entrada_norm):
        return True
    return False


def sugerir_temas(entrada, temas_map, limite=3):
    entrada_norm = normalizar_texto(entrada)
    if len(entrada_norm) < 3 or not temas_map:
        return []

    opciones = {normalizar_texto(tema): tema for tema in temas_map.values()}
    resultados = fuzzy_extract(entrada_norm, list(opciones.keys()), limit=limite)
    sugerencias = []
    for tema_norm, score in resultados:
        if score >= 62:
            sugerencias.append(opciones[tema_norm])
    return sugerencias


def consulta_sobre_dias_vacaciones(entrada_norm):
    if not any(
        contiene_frase(entrada_norm, palabra)
        for palabra in ["vacaciones", "vacacion", "descanso", "licencia anual"]
    ):
        return False

    pistas = ["cuanto", "cuantos", "dias", "corresponde", "corresponden", "antiguedad"]
    return any(contiene_frase(entrada_norm, pista) for pista in pistas)


def clasificar_input_feedback(texto):
    texto_norm = normalizar_texto(texto)
    if not texto_norm:
        return "vacio", texto_norm
    if texto_norm in {"si", "no"}:
        return "feedback", texto_norm
    if texto_norm == "menu":
        return "menu", texto_norm
    if texto_norm in PALABRAS_SALIDA:
        return "salir", texto_norm
    return "consulta", texto_norm


def manejar_feedback_interactivo(tema_id, texto_feedback):
    tipo_feedback, feedback_norm = clasificar_input_feedback(texto_feedback)

    if tipo_feedback == "feedback":
        registrar_feedback(tema_id, feedback_norm)
        print("\nBot: ¡Muchas gracias por tu feedback!")
        print("Bot: ¿Tenés otra duda o preferís volver al 'menu' principal?")
        print("👉 Escribí tu duda, la palabra 'menu' o 'salir'.")
        return "continuar", None

    if tipo_feedback == "menu":
        return "menu", None

    if tipo_feedback == "salir":
        print(f"\nBot: {construir_mensaje_despedida()}")
        return "salir", None

    if tipo_feedback == "consulta":
        print("\nBot: Entiendo tu mensaje como una nueva consulta.")
        return "consulta", texto_feedback

    print("\nBot: Podés responder 'si' o 'no', o escribir una nueva consulta.")
    return "continuar", None


def obtener_respuesta(entrada, temas_map, company_id=None):
    """
    Devuelve (respuesta, tema_id) según la entrada del usuario.
    Si la empresa tiene base de conocimiento (archivo subido), se busca ahí primero.
    Luego se usa company_id para FAQs en 'faqs' y temas_map.
    """
    entrada_norm = normalizar_texto(entrada)
    if not entrada_norm:
        return "⚠️ No llegué a entender tu consulta. ¿Podrías reformularla?", "ayuda"

    if solicita_contacto_rrhh(entrada_norm):
        return MENSAJE_CONTACTO, "RRHH"

    tema_elegido = detectar_tema(entrada_norm, temas_map)
    saludo_detectado = es_saludo(entrada_norm)

    if saludo_detectado and not tema_elegido:
        return MENSAJE_BIENVENIDA, "saludo"

    if tema_elegido:
        tema_norm = normalizar_texto(tema_elegido)
        if tema_norm == "ayuda":
            return MENSAJE_AYUDA, "ayuda"
        if tema_norm == "hola":
            return MENSAJE_BIENVENIDA, "saludo"

    # Base de conocimiento por empresa — si existe, es la única fuente de respuestas
    if company_id:
        entries = obtener_knowledge_empresa(company_id)
        if entries:
            resp, score = buscar_en_knowledge(entrada_norm, entries)
            intencion = _detectar_intencion(entrada_norm)

            if resp and score >= KNOWLEDGE_MATCH_THRESHOLD:
                # Respuesta buena encontrada — pedir feedback primero
                if intencion == "fecha" and score < 95:
                    return (
                        f"{resp}\n\n📅 Para coordinar *cuándo* gestionar esto, podés hablar con un agente de RRHH."
                    ), "knowledge_answer"
                return resp, "knowledge_answer"

            if resp and score >= KNOWLEDGE_PARTIAL_THRESHOLD:
                # Match parcial — dar lo que hay, pedir feedback (si dice "no" se ofrecerá derivación)
                return (
                    f"Esto es lo más cercano que encontré en nuestra base de datos:\n\n{resp}"
                ), "knowledge_answer"

            # La empresa tiene knowledge base pero no hubo match — igual pedir feedback
            if tema_elegido:
                area = AREAS_POR_TEMA.get(normalizar_texto(tema_elegido), "RRHH")
                return (
                    f"No encontré información específica sobre \"{tema_elegido}\" en la base de datos de tu empresa."
                ), "knowledge_answer"
            return (
                "No encontré información sobre eso en nuestra base de datos."
            ), "knowledge_answer"

    # Sin knowledge base — usar FAQs tradicionales
    if saludo_detectado and tema_elegido and normalizar_texto(tema_elegido) not in {"hola", "ayuda"}:
        respuesta = obtener_respuesta_faq(tema_elegido, company_id=company_id)
        if respuesta:
            return f"👋 ¡Hola! Sobre tu consulta de {tema_elegido}:\n{respuesta}", tema_elegido

    if tema_elegido:
        tema_norm = normalizar_texto(tema_elegido)
        if tema_norm == "vacaciones" and consulta_sobre_dias_vacaciones(entrada_norm):
            return RESPUESTA_DIAS_VACACIONES, tema_elegido
        respuesta = obtener_respuesta_faq(tema_elegido, company_id=company_id)
        if respuesta:
            return respuesta, tema_elegido

    if entrada_norm == "ayuda":
        return MENSAJE_AYUDA, "ayuda"
    return None, None


# ==========================================================
# 5. BUCLE PRINCIPAL DE INTERACCIÓN
# ==========================================================
if __name__ == "__main__":
    dict_temas = mostrar_menu()
    consulta_pendiente = None

    while True:
        if consulta_pendiente is not None:
            msj_usuario = consulta_pendiente
            consulta_pendiente = None
            print(f"\nColaborador: {msj_usuario}")
        else:
            msj_usuario = input("\nColaborador: ")

        msj_norm = normalizar_texto(msj_usuario)

        if msj_norm in PALABRAS_SALIDA:
            print(f"\nBot: {construir_mensaje_despedida()}")
            break

        if msj_norm == "menu":
            dict_temas = mostrar_menu()
            continue

        respuesta_bot, tema_id = obtener_respuesta(msj_usuario, dict_temas)

        if respuesta_bot:
            print(f"\nBot: {respuesta_bot}")

            if tema_id not in TEMAS_SIN_FEEDBACK:
                print("-" * 45)
                fdbk = input("Bot: ¿Esta información te fue de utilidad? (si/no): ").strip()
                accion_feedback, nueva_consulta = manejar_feedback_interactivo(tema_id, fdbk)

                if accion_feedback == "menu":
                    dict_temas = mostrar_menu()
                elif accion_feedback == "salir":
                    break
                elif accion_feedback == "consulta":
                    consulta_pendiente = nueva_consulta
        else:
            print("\nBot: ⚠️ Lo siento, no tengo información registrada sobre eso.")
            print("👉 Para que pueda ayudarte, por favor intentá lo siguiente:")
            print("   - Escribí el NÚMERO de la opción (ejemplo: '1')")
            print("   - Escribí la PALABRA clave (ejemplo: 'Vacaciones')")
            print("   - Escribí 'menu' para volver al inicio.")
            sugerencias = sugerir_temas(msj_usuario, dict_temas)
            if sugerencias:
                print(f"   - Tal vez quisiste decir: {', '.join(sugerencias)}")
            registrar_pendiente(msj_usuario)

# FINAL DEL PROGRAMA - PROPIEDAD DE BACAR SA - 2026