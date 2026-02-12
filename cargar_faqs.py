from firebase_config import inicializar_firestore


db = inicializar_firestore(verbose=False)

# 2. LISTADO DE PREGUNTAS FRECUENTES (FAQS) PARA BACAR
faqs_bacar = [
    {"tema": "vacaciones", "respuesta": "Se deben solicitar con 15 días de anticipación a través del portal Legajos.online."},
    {"tema": "fraccionamiento", "respuesta": "Las vacaciones se pueden fraccionar en períodos mínimos de 7 días, con aval de tu responsable directo."},
    {"tema": "recibo", "respuesta": "Los recibos de sueldo están disponibles para firma digital el cuarto día hábil de cada mes en la plataforma habitual."},
    {"tema": "aguinaldo", "respuesta": "El SAC se abona en dos cuotas: la primera con vencimiento el 30 de junio y la segunda el 18 de diciembre."},
    {"tema": "obra social", "respuesta": "Para cambios o consultas sobre tu cobertura médica, debés enviar un correo a beneficios@bacar.com.ar."},
    {"tema": "licencia examen", "respuesta": "Tenés derecho a 2 días corridos por examen, hasta 20 días anuales. Presentá el certificado al día siguiente de rendir."},
    {"tema": "art", "respuesta": "En caso de accidente laboral, comunicate inmediatamente al 0800 de nuestra aseguradora y avisá a tu supervisor."},
    {"tema": "uniforme", "respuesta": "La reposición de uniformes se realiza cada 6 meses. Podés solicitar el tuyo en la oficina de suministros."},
    {"tema": "adelanto", "respuesta": "Los pedidos de adelanto de sueldo se reciben hasta el día 20 de cada mes y no deben superar el 30% del neto."},
    {"tema": "nacimiento", "respuesta": "Por nacimiento de hijo, contás con 2 días corridos de licencia paga (según CCT). Recordá traer el acta de nacimiento."},
    {"tema": "casamiento", "respuesta": "La licencia por matrimonio es de 10 días corridos. Debés avisar con 30 días de antelación."},
    {"tema": "capacitacion", "respuesta": "Podés ver los cursos disponibles en la intranet de Bacar, sección 'Mi Desarrollo'."}
]


def normalizar_tema(tema):
    return str(tema).strip().lower()


def cargar_datos():
    if not db:
        print("⚠️ No se puede cargar información porque no hay conexión a Firebase.")
        print("ℹ️ Definí FIREBASE_CREDENTIALS=tu-clave.json y reintentá.")
        return

    print("🚀 Subiendo info oficial a Firestore...")
    coleccion = db.collection("faq_rrhh")
    
    for faq in faqs_bacar:
        tema = normalizar_tema(faq["tema"])
        payload = {"tema": tema, "respuesta": faq["respuesta"]}
        # Usamos el tema normalizado como ID para evitar duplicados y errores de casing.
        coleccion.document(tema).set(payload)
        print(f"✅ Categoría cargada: {tema}")
    
    print("\n¡Éxito! Tu base de datos de RRHH ya está completa.")

if __name__ == "__main__":
    cargar_datos()