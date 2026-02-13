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
MENSAJE_BIENVENIDA = (
    "👋 ¡Hola! Soy el asistente de RRHH de Bacar. ¿En qué puedo ayudarte hoy?"
)
MENSAJE_CONTACTO = "📞 Para hablar con un representante, comunicate al interno 104."
MENSAJE_AYUDA = (
    "🆘 Puedo ayudarte con vacaciones, fraccionamiento, recibo, aguinaldo, ART y otros temas de RRHH.\n"
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
        "Podés ver los cursos disponibles en la intranet de Bacar, sección "
        "'Mi Desarrollo'."
    ),
}

db = inicializar_firestore(verbose=False)
if db:
    print("✅ SISTEMA BACAR: Conexión exitosa con la base de datos.")
    print("🚀 El asistente virtual de RRHH está listo para operar.\n")
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

INTENCIONES_CONTACTO = {"rrhh", "representante", "persona", "humano", "asesor", "operador"}
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


def obtener_temas_desde_firestore():
    if not db:
        return []
    try:
        docs = db.collection("faq_rrhh").stream()
        return sorted((doc.id for doc in docs), key=normalizar_texto)
    except Exception as exc:
        print(f"⚠️ No se pudieron leer temas desde Firestore: {exc}")
        return []


# ==========================================================
# 3. FUNCIONES DE ADMINISTRACIÓN DE DATOS Y REGISTROS
# ==========================================================
def mostrar_menu():
    print("\n" + "═" * 55)
    print(" 🏢 ASISTENTE VIRTUAL DE RRHH - BACAR SA ")
    print("═" * 55)
    print("Seleccioná un número o escribí el tema de tu consulta:")

    temas_disponibles = obtener_temas_desde_firestore()
    if not temas_disponibles:
        temas_disponibles = sorted(FAQ_FALLBACK.keys(), key=normalizar_texto)
        print("⚠️ Mostrando temas en modo local (sin conexión a Firestore).")

    temas_map = {}
    for i, tema in enumerate(temas_disponibles, start=1):
        temas_map[str(i)] = tema
        print(f" {i}. {tema.capitalize()}")

    print(" H. Hablar con alguien de RRHH")
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


def registrar_feedback(tema, utilidad):
    payload = {"tema": tema, "fue_util": utilidad, "fecha": datetime.now()}
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


def registrar_pendiente(consulta):
    payload = {
        "pregunta": consulta,
        "fecha": datetime.now(),
        "estado": "pendiente",
        "sentimiento": analizar_sentimiento(consulta),
    }
    if not guardar_en_firestore("consultas_pendientes", payload):
        print("ℹ️ Consulta pendiente no persistida por falta de conexión.")
        return False
    return True


def obtener_respuesta_faq(tema):
    tema_norm = normalizar_texto(tema)

    if db:
        try:
            doc = db.collection("faq_rrhh").document(tema).get()
            if doc.exists:
                respuesta = doc.to_dict().get("respuesta")
                if respuesta:
                    return respuesta

            # Soporte para IDs con mayúsculas/minúsculas distintas (ej. ART vs art).
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
        print("\nBot: Gracias por comunicarte con RRHH de Bacar. ¡Buen día!")
        return "salir", None

    if tipo_feedback == "consulta":
        print("\nBot: Entiendo tu mensaje como una nueva consulta.")
        return "consulta", texto_feedback

    print("\nBot: Podés responder 'si' o 'no', o escribir una nueva consulta.")
    return "continuar", None


def obtener_respuesta(entrada, temas_map):
    entrada_norm = normalizar_texto(entrada)
    if not entrada_norm:
        return "⚠️ No llegué a entender tu consulta. ¿Podrías reformularla?", "ayuda"

    if solicita_contacto_rrhh(entrada_norm):
        return MENSAJE_CONTACTO, "RRHH"

    tema_elegido = detectar_tema(entrada_norm, temas_map)
    saludo_detectado = es_saludo(entrada_norm)

    if saludo_detectado and tema_elegido and normalizar_texto(tema_elegido) not in {"hola", "ayuda"}:
        respuesta = obtener_respuesta_faq(tema_elegido)
        if respuesta:
            return f"👋 ¡Hola! Sobre tu consulta de {tema_elegido}:\n{respuesta}", tema_elegido

    if saludo_detectado:
        return MENSAJE_BIENVENIDA, "saludo"

    if tema_elegido:
        tema_norm = normalizar_texto(tema_elegido)
        if tema_norm == "ayuda":
            return MENSAJE_AYUDA, "ayuda"
        if tema_norm == "hola":
            return MENSAJE_BIENVENIDA, "saludo"
        if tema_norm == "vacaciones" and consulta_sobre_dias_vacaciones(entrada_norm):
            return RESPUESTA_DIAS_VACACIONES, tema_elegido

        respuesta = obtener_respuesta_faq(tema_elegido)
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
            print("\nBot: Gracias por comunicarte con RRHH de Bacar. ¡Buen día!")
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