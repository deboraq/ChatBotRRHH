"""
Envío de mensajes por WhatsApp usando Twilio.

Configurá TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN y (opcional) TWILIO_WHATSAPP_FROM
en el entorno. Luego podés usar esta función con whatsapp_broadcast:

  from twilio_whatsapp import register_twilio_sender
  register_twilio_sender()
  from whatsapp_broadcast import broadcast_messages
  broadcast_messages(phone_list, body_text="Texto", phone_number_id="whatsapp:+14155238886")
"""

import os
from typing import List, Optional

# Opcional: número "desde" por defecto (formato whatsapp:+...)
TWILIO_WHATSAPP_FROM = os.getenv("TWILIO_WHATSAPP_FROM", "").strip()

# Último error de Twilio (para mostrar mensaje amigable en la app)
last_twilio_error = ""


def _format_to_whatsapp(phone: str) -> str:
    """Asegura que el número tenga prefijo whatsapp: y formato E.164."""
    p = (phone or "").strip()
    if not p:
        return ""
    if p.startswith("whatsapp:"):
        return p
    if not p.startswith("+"):
        p = "+" + p.lstrip("0")
    return "whatsapp:" + p


def send_one(
    phone: str,
    body: Optional[str] = None,
    template_name: Optional[str] = None,
    template_params: Optional[List[str]] = None,
    phone_number_id: Optional[str] = None,
    access_token: Optional[str] = None,
    media_url: Optional[List[str]] = None,
) -> bool:
    """
    Envía un mensaje por WhatsApp con Twilio.

    - phone: número destino (se normaliza a whatsapp:+...).
    - body: texto del mensaje (prioridad).
    - template_name: ignorado por Twilio simple API; se puede usar para lógica propia.
    - template_params: si no hay body, se usa como texto uniendo con espacios.
    - phone_number_id: número "desde" en formato whatsapp:+... (por empresa). Si no, se usa TWILIO_WHATSAPP_FROM.
    - access_token: no usado (Twilio usa Account SID + Auth Token del entorno).
    - media_url: lista de URLs públicas de imagen/audio/PDF para adjuntar (opcional).
    """
    global last_twilio_error
    try:
        from twilio.rest import Client
    except ImportError:
        return False

    account_sid = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
    auth_token = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
    if not account_sid or not auth_token:
        return False

    to = _format_to_whatsapp(phone)
    if not to or to == "whatsapp:":
        return False

    from_ = (phone_number_id or TWILIO_WHATSAPP_FROM or "").strip()
    if not from_.startswith("whatsapp:"):
        from_ = _format_to_whatsapp(from_) if from_ else TWILIO_WHATSAPP_FROM
    if not from_ or from_ == "whatsapp:":
        return False

    text = (body or "").strip()
    if not text and template_params:
        text = " ".join(str(p or "").strip() for p in template_params)
    # Normalizar: acepta string, lista de strings, o None
    if isinstance(media_url, str):
        media_url = [media_url] if media_url.strip() else []
    urls = [u.strip() for u in (media_url or []) if isinstance(u, str) and u.strip()]
    if not text and not urls:
        return False

    try:
        client = Client(account_sid, auth_token)
        kwargs = {"from_": from_, "to": to}
        if text:
            kwargs["body"] = text
        if urls:
            kwargs["media_url"] = urls
        client.messages.create(**kwargs)
        last_twilio_error = ""
        return True
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("Twilio WhatsApp envío fallido: to=%s from_=%s error=%s", to, from_, e)
        last_twilio_error = str(e)
        return False


def register_twilio_sender() -> None:
    """Registra send_one como la función de envío de whatsapp_broadcast."""
    from whatsapp_broadcast import set_send_function
    set_send_function(send_one)
