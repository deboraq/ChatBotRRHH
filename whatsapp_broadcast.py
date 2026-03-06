"""
Envío de comunicados masivos por WhatsApp en lotes con pausa (throttling).

Evita bloqueos por spam: no envía cientos de mensajes de golpe.
Cuando conectes la API real de WhatsApp (Cloud API o proveedor), implementá
send_single_message() y opcionalmente load_template_message() usando este módulo.

Uso desde otro módulo:
  from whatsapp_broadcast import broadcast_messages
  broadcast_messages(phone_list, body_text="Texto del comunicado")
  # o con plantilla:
  broadcast_messages(phone_list, template_name="comunicado_rrhh", template_params=["Nombre", "Texto"])
"""

import os
import time
from typing import Callable, List, Optional

# Configuración por env (o valores por defecto conservadores)
BROADCAST_BATCH_SIZE = int(os.getenv("WHATSAPP_BROADCAST_BATCH_SIZE", "50"))
BROADCAST_DELAY_SECONDS = float(os.getenv("WHATSAPP_BROADCAST_DELAY_SECONDS", "3"))


def _noop_send(
    phone: str,
    body: Optional[str] = None,
    template_name: Optional[str] = None,
    template_params: Optional[List[str]] = None,
    phone_number_id: Optional[str] = None,
    access_token: Optional[str] = None,
    media_url: Optional[List[str]] = None,
) -> bool:
    """
    Placeholder: no envía nada. Reemplazá por tu integración real a WhatsApp.
    Devuelve True si el envío fue aceptado, False en caso contrario.
    """
    return True


# Puntero a la función real de envío (asigná desde tu integración de WhatsApp)
# La función debe aceptar al menos: phone, body, template_name, template_params, phone_number_id, access_token
send_single_message: Callable[..., bool] = _noop_send


def broadcast_messages(
    phone_list: List[str],
    body_text: Optional[str] = None,
    template_name: Optional[str] = None,
    template_params: Optional[List[str]] = None,
    batch_size: Optional[int] = None,
    delay_seconds: Optional[float] = None,
    phone_number_id: Optional[str] = None,
    access_token: Optional[str] = None,
    media_url: Optional[List[str]] = None,
) -> dict:
    """
    Envía mensajes a una lista de teléfonos en lotes con pausa entre lotes.

    - phone_list: lista de números en formato internacional (ej. 5491112345678).
    - body_text: texto del mensaje (solo si no usás plantilla; dentro de ventana 24h).
    - template_name: nombre de la plantilla aprobada (para comunicados proactivos).
    - template_params: parámetros de la plantilla en orden.
    - batch_size: mensajes por lote (default env WHATSAPP_BROADCAST_BATCH_SIZE o 50).
    - delay_seconds: pausa en segundos entre lotes (default env o 3).
    - phone_number_id: ID del número de WhatsApp (por empresa); se pasa a send_single_message.
    - access_token: token de la API de WhatsApp; se pasa a send_single_message.

    Devuelve un dict con: sent, failed, total, batches_used.
    """
    batch_size = batch_size or BROADCAST_BATCH_SIZE
    delay_seconds = delay_seconds or BROADCAST_DELAY_SECONDS
    phones = [p.strip() for p in phone_list if str(p).strip()]
    total = len(phones)
    sent = 0
    failed = 0
    batches_used = 0

    for i in range(0, total, batch_size):
        chunk = phones[i : i + batch_size]
        batches_used += 1
        for phone in chunk:
            ok = send_single_message(
                phone,
                body=body_text,
                template_name=template_name,
                template_params=template_params,
                phone_number_id=phone_number_id,
                access_token=access_token,
                media_url=media_url,
            )
            if ok:
                sent += 1
            else:
                failed += 1
        # Pausa entre lotes (no después del último)
        if i + batch_size < total:
            time.sleep(delay_seconds)

    return {
        "sent": sent,
        "failed": failed,
        "total": total,
        "batches_used": batches_used,
    }


def set_send_function(fn: Callable[..., bool]) -> None:
    """Asigná la función real que envía un mensaje por WhatsApp (API oficial)."""
    global send_single_message
    send_single_message = fn
