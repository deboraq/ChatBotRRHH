"""
Prueba de envío por WhatsApp con Twilio.

Uso (el número debe haber unido el sandbox con "join stand-prevent"):

  python test_twilio_envio.py +5493515416836
  python test_twilio_envio.py 5493515416836 "Hola, mensaje de prueba"
"""

import os
import sys

# Cargar .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

def main():
    if len(sys.argv) < 2:
        print("Uso: python test_twilio_envio.py <número> [texto]")
        print("Ejemplo: python test_twilio_envio.py +5493515416836 \"Hola desde la app\"")
        sys.exit(1)

    phone = sys.argv[1].strip()
    body = sys.argv[2].strip() if len(sys.argv) > 2 else "Mensaje de prueba desde el chatbot RRHH."

    from twilio_whatsapp import send_one

    ok = send_one(phone, body=body)
    if ok:
        print("Enviado correctamente a", phone)
    else:
        print("Error al enviar. Revisá TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN y TWILIO_WHATSAPP_FROM en .env")
        print("El número destino debe haber unido el sandbox (join stand-prevent al +1 415 523 8886).")
        sys.exit(1)

if __name__ == "__main__":
    main()
