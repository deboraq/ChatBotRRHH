"""
Envío de comunicados masivos por WhatsApp en lotes con pausa (throttling).
"""

import os
import time
from typing import Callable, List, Optional

BROADCAST_BATCH_SIZE = int(os.getenv("WHATSAPP_BROADCAST_BATCH_SIZE", "10"))
BROADCAST_DELAY_MSG = float(os.getenv("WHATSAPP_BROADCAST_DELAY_MSG", "1.5"))
BROADCAST_DELAY_BATCH = float(os.getenv("WHATSAPP_BROADCAST_DELAY_BATCH", "20"))


def _noop_send(phone, body=None, template_name=None, template_params=None,
               phone_number_id=None, access_token=None, media_url=None, **kwargs):
    return True


send_single_message: Callable = _noop_send


def broadcast_messages(
    phone_list: List[str],
    body_text: Optional[str] = None,
    template_name: Optional[str] = None,
    template_params: Optional[List[str]] = None,
    batch_size: Optional[int] = None,
    delay_seconds: Optional[float] = None,
    delay_per_message: Optional[float] = None,
    phone_number_id: Optional[str] = None,
    access_token: Optional[str] = None,
    media_url=None,
    on_progress: Optional[Callable] = None,
) -> dict:
    """
    Envía mensajes en lotes con pausa entre mensajes y entre lotes.
    on_progress(sent, failed, total, batch_num, total_batches, waiting, wait_remaining) se llama en cada evento.
    """
    batch_size = batch_size if batch_size is not None else BROADCAST_BATCH_SIZE
    delay_batch = delay_seconds if delay_seconds is not None else BROADCAST_DELAY_BATCH
    delay_msg = delay_per_message if delay_per_message is not None else BROADCAST_DELAY_MSG

    phones = [p.strip() for p in phone_list if str(p).strip()]
    total = len(phones)
    sent = 0
    failed = 0
    batches_used = 0
    total_batches = (total + batch_size - 1) // batch_size if total > 0 else 1

    for i in range(0, total, batch_size):
        chunk = phones[i:i + batch_size]
        batches_used += 1
        batch_num = batches_used
        is_last_batch = (i + batch_size) >= total

        for j, phone in enumerate(chunk):
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
            if on_progress:
                on_progress(sent, failed, total, batch_num, total_batches, False, 0)
            # delay between messages (not after the last message of the batch)
            if j < len(chunk) - 1:
                time.sleep(delay_msg)

        # countdown between batches
        if not is_last_batch:
            delay_int = max(1, int(delay_batch))
            for remaining in range(delay_int, 0, -1):
                if on_progress:
                    on_progress(sent, failed, total, batch_num, total_batches, True, remaining)
                time.sleep(1)

    return {
        "sent": sent,
        "failed": failed,
        "total": total,
        "batches_used": batches_used,
    }


def set_send_function(fn: Callable) -> None:
    global send_single_message
    send_single_message = fn
