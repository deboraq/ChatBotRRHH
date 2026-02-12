from collections import Counter
from datetime import datetime, timedelta, timezone


def _normalizar_texto(valor):
    return str(valor).strip().lower() if valor is not None else ""


def _extraer_fecha(valor):
    if isinstance(valor, datetime):
        if valor.tzinfo is None:
            return valor
        return valor.astimezone(timezone.utc).replace(tzinfo=None)
    return None


def _serie_vacia(labels):
    return {"labels": labels, "feedback": [0] * len(labels), "pendientes": [0] * len(labels)}


def _labels_ultimos_dias(now, days):
    inicio = (now - timedelta(days=days - 1)).date()
    return [(inicio + timedelta(days=i)).isoformat() for i in range(days)]


def build_statistics_from_records(feedback_records, pendientes_records, now=None, days=7):
    now = now or datetime.now(timezone.utc)
    labels = _labels_ultimos_dias(now, days)
    serie = _serie_vacia(labels)
    labels_set = set(labels)
    label_index = {label: idx for idx, label in enumerate(labels)}

    total_feedback = len(feedback_records)
    votos_si = 0
    votos_no = 0
    temas_counter = Counter()
    sentimientos_counter = Counter()

    for item in feedback_records:
        voto = _normalizar_texto(item.get("fue_util"))
        if voto in {"si", "sí", "yes", "y", "true"}:
            votos_si += 1
        elif voto in {"no", "n", "false"}:
            votos_no += 1

        tema = _normalizar_texto(item.get("tema"))
        if tema:
            temas_counter[tema] += 1

        fecha = _extraer_fecha(item.get("fecha"))
        if fecha:
            key = fecha.date().isoformat()
            if key in labels_set:
                idx = label_index[key]
                serie["feedback"][idx] += 1

    total_pendientes = len(pendientes_records)
    for item in pendientes_records:
        sentimiento = _normalizar_texto(item.get("sentimiento")) or "no informado"
        sentimientos_counter[sentimiento] += 1

        fecha = _extraer_fecha(item.get("fecha"))
        if fecha:
            key = fecha.date().isoformat()
            if key in labels_set:
                idx = label_index[key]
                serie["pendientes"][idx] += 1

    utilidad_pct = 0.0
    if total_feedback > 0:
        utilidad_pct = round((votos_si / total_feedback) * 100, 2)

    return {
        "available": True,
        "kpis": {
            "total_feedback": total_feedback,
            "votos_si": votos_si,
            "votos_no": votos_no,
            "utilidad_pct": utilidad_pct,
            "total_pendientes": total_pendientes,
        },
        "top_temas": [
            {"tema": tema, "cantidad": cantidad}
            for tema, cantidad in temas_counter.most_common(8)
        ],
        "pendientes_por_sentimiento": [
            {"sentimiento": sentimiento, "cantidad": cantidad}
            for sentimiento, cantidad in sentimientos_counter.most_common()
        ],
        "series_7_dias": serie,
        "updated_at": now.isoformat(timespec="seconds"),
    }


def obtener_estadisticas(db, now=None, days=7):
    if db is None:
        current_time = now or datetime.now(timezone.utc)
        labels = _labels_ultimos_dias(current_time, days)
        return {
            "available": False,
            "reason": "Sin conexión a Firestore",
            "kpis": {
                "total_feedback": 0,
                "votos_si": 0,
                "votos_no": 0,
                "utilidad_pct": 0.0,
                "total_pendientes": 0,
            },
            "top_temas": [],
            "pendientes_por_sentimiento": [],
            "series_7_dias": _serie_vacia(labels),
            "updated_at": current_time.isoformat(timespec="seconds"),
        }

    feedback_records = [doc.to_dict() for doc in db.collection("feedback_respuestas").stream()]
    pendientes_records = [doc.to_dict() for doc in db.collection("consultas_pendientes").stream()]
    return build_statistics_from_records(
        feedback_records=feedback_records,
        pendientes_records=pendientes_records,
        now=now,
        days=days,
    )

