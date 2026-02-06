import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-1.5-flash')

# BASE DE CONOCIMIENTO (Extraída de tu presentación de Bacar)
FAQS = {
    "sueldo": "Podés descargar tu recibo de sueldo en el portal [URL_PORTAL_BACAR] usando tu legajo.",
    "vacaciones": "Hasta 5 años: 14 días. De 5 a 10 años: 21 días. Más de 10 años: 28 días.",
    "licencia": "Para ausencias por enfermedad, debés informar a RRHH antes de las 9:00 hs con certificado.",
    "horario": "Los turnos se publican el día 25 de cada mes en el tablero principal.",
    "beneficios": "Contamos con descuentos en gimnasios y farmacias adheridas para todo el personal."
}

def respuesta_inteligente(consulta):
    consulta = consulta.lower()
    
    # 1. Intenta usar la IA con tu contexto de RRHH
    try:
        prompt = f"Eres el asistente de RRHH de Bacar. Responde de forma breve (máx 300 caracteres) a: {consulta}. Usa esta info si es necesario: {FAQS}"
        response = model.generate_content(prompt)
        return response.text
    except:
        # 2. Fallback: Si la IA falla, busca por palabra clave (como dice tu plan)
        for clave, respuesta in FAQS.items():
            if clave in consulta:
                return f"(Modo Seguro) {respuesta}"
        return "Lo siento, para esa consulta específica debés contactar a un representante de RRHH."

if __name__ == "__main__":
    print("\n" + "="*40)
    print("🏢 SISTEMA DE RRHH BACAR - MODO TERMINAL")
    print("="*40)
    
    while True:
        user_msj = input("\nColaborador: ")
        if user_msj.lower() in ["salir", "exit"]: break
        print(f"\nBot: {respuesta_inteligente(user_msj)}")