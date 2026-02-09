import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime

# ==========================================================
# 1. CONFIGURACIÓN INICIAL Y CONEXIÓN CON FIRESTORE
# ==========================================================
# Se establece la conexión oficial con la base de datos de Bacar SA
try:
    if not firebase_admin._apps:
        cred = credentials.Certificate("claves.json")
        firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("✅ SISTEMA BACAR: Conexión Exitosa con la Base de Datos.")
    print("🚀 El asistente virtual de RRHH está listo para operar.\n")
except Exception as e:
    print(f"❌ Error crítico al conectar con Firestore: {e}")
    db = None

# ==========================================================
# 2. DICCIONARIO DE INTELIGENCIA Y SINÓNIMOS
# ==========================================================
# Definimos palabras clave para que el bot entienda el lenguaje natural
# Esto permite que el colaborador no tenga que escribir palabras exactas
SINONIMOS = {
    "vacaciones": ["descanso", "licencia anual", "días libres", "vacas", "feriado"],
    "art": ["accidente", "me lastimé", "seguro laboral", "la art", "lesión"],
    "recibo": ["sueldo", "comprobante", "liquidación", "haberes", "recibos"],
    "aguinaldo": ["sac", "sueldo anual complementario", "cobro diciembre", "cobro junio"],
    "hola": ["buen día", "buenas", "hola bot", "buenos días", "holaa", "hola", "saludos"],
    "ayuda": ["no sé qué hacer", "help", "necesito ayuda", "ayudame", "que hago"]
}

# ==========================================================
# 3. FUNCIONES DE ADMINISTRACIÓN DE DATOS Y REGISTROS
# ==========================================================
def mostrar_menu():
    """Muestra el menú oficial numerado en la terminal de Bacar SA"""
    print("\n" + "═"*55)
    print(" 🏢 ASISTENTE VIRTUAL DE RRHH - BACAR SA ")
    print("═"*55)
    print("Seleccioná un número o escribí el tema de tu consulta:")
    
    temas_map = {}
    if db:
        docs = db.collection('faq_rrhh').stream()
        lista_temas = sorted([doc.id for doc in docs])
        for i, tema in enumerate(lista_temas, 1):
            temas_map[str(i)] = tema
            print(f" {i}. {tema.capitalize()}")
        
        print(" H. Hablar con alguien de RRHH")
        print("─"*55)
    return temas_map

def registrar_feedback(tema, utilidad):
    """Guarda en Firestore si la respuesta fue útil para el empleado"""
    db.collection('feedback_respuestas').add({
        'tema': tema, 
        'fue_util': utilidad, 
        'fecha': datetime.now()
    })

def registrar_pendiente(consulta):
    """Guarda dudas que el bot no pudo resolver para auditoría de RRHH"""
    db.collection('consultas_pendientes').add({
        'pregunta': consulta, 
        'fecha': datetime.now(), 
        'estado': 'pendiente'
    })

# ==========================================================
# 4. LÓGICA DE PROCESAMIENTO DE CONVERSACIÓN (RESPUESTAS)
# ==========================================================
def obtener_respuesta(entrada, temas_map):
    entrada_clean = entrada.lower().strip()
    tema_elegido = None
    
    # 1. Buscamos concordancia por número o nombre de tema
    tema_elegido = temas_map.get(entrada_clean)
    if not tema_elegido:
        for id_tema in temas_map.values():
            if id_tema.lower() in entrada_clean:
                tema_elegido = id_tema
                break

    # 2. Buscamos concordancia por diccionario de sinónimos
    if not tema_elegido:
        for oficial, variaciones in SINONIMOS.items():
            if any(v in entrada_clean for v in variaciones):
                tema_elegido = oficial
                break

    # 3. Detectar si el mensaje contiene un saludo de cortesía
    saludo_detectado = any(s in entrada_clean for s in SINONIMOS["hola"])

    # --- RESPUESTAS LÓGICAS ---
    if saludo_detectado and tema_elegido and tema_elegido != "hola":
        doc = db.collection('faq_rrhh').document(tema_elegido).get()
        if doc.exists:
            res_doc = doc.to_dict().get('respuesta')
            return f"👋 ¡Hola! Sobre tu consulta de {tema_elegido}:\n{res_doc}", tema_elegido

    if saludo_detectado:
        return "👋 ¡Hola! Soy el asistente de RRHH de Bacar. ¿En qué puedo ayudarte hoy?", "saludo"

    if tema_elegido:
        doc = db.collection('faq_rrhh').document(tema_elegido).get()
        if doc.exists:
            return doc.to_dict().get('respuesta'), tema_elegido
            
    if entrada_clean == 'h':
        return "📞 Para hablar con un representante, comunicate al interno 104.", "RRHH"

    return None, None

# ==========================================================
# 5. BUCLE PRINCIPAL DE INTERACCIÓN Y CIERRE (130-160)
# ==========================================================
if __name__ == "__main__":
    dict_temas = mostrar_menu()
    
    while True:
        msj_usuario = input("\nColaborador: ")
        
        if msj_usuario.lower() in ["salir", "chau", "exit", "no", "adiós"]:
            print("\nBot: Gracias por comunicarte con RRHH de Bacar. ¡Buen día!")
            break
        
        if msj_usuario.lower() == "menu":
            dict_temas = mostrar_menu()
            continue
            
        respuesta_bot, tema_id = obtener_respuesta(msj_usuario, dict_temas)
        
        if respuesta_bot:
            print(f"\nBot: {respuesta_bot}")
            
            if tema_id not in ["saludo", "ayuda", "RRHH"]:
                print("-" * 45)
                fdbk = input("Bot: ¿Esta información te fue de utilidad? (si/no): ").lower().strip()
                if fdbk in ["si", "no"]:
                    registrar_feedback(tema_id, fdbk)
                    print("\nBot: ¡Muchas gracias por tu feedback!")
                    
                    # CIERRE INTERACTIVO DE SESIÓN
                    print("Bot: ¿Tenés otra duda o preferís volver al 'menu' principal?")
                    print("👉 Escribí tu duda, la palabra 'menu' o 'salir'.")
        else:
            print("\nBot: ⚠️ Lo siento, no tengo información registrada sobre eso.")
            print("👉 Para que pueda ayudarte, por favor intentá lo siguiente:")
            print("   - Escribí el NÚMERO de la opción (ejemplo: '1')")
            print("   - Escribí la PALABRA clave (ejemplo: 'Vacaciones')")
            print("   - Escribí 'menu' para volver al inicio.")
            registrar_pendiente(msj_usuario)

# FINAL DEL PROGRAMA - PROPIEDAD DE BACAR SA - 2024
# ==========================================================