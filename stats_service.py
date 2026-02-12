from collections import Counter
from datetime import datetime, timedelta, timezone


def _normalizar_texto(valor):
    return str(valor).strip().lower() if valor is not None else ""


def _es_voto_si(voto):
    voto_norm = _normalizar_texto(voto)
    return voto_norm in {"si", "sí", "yes", "y", "true"}


def _es_voto_no(voto):
    voto_norm = _normalizar_texto(voto)
    return voto_norm in {"no", "n", "false"}


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


def _formatear_fecha(dt):
    if not dt:
        return "Sin fecha"
    return dt.strftime("%Y-%m-%d %H:%M")


def _ordenar_por_fecha_desc(items):
    def _key(item):
        fecha_iso = item.get("fecha_iso")
        if not fecha_iso:
            return ""
        return fecha_iso

    return sorted(items, key=_key, reverse=True)


def _normalizar_estado_handoff(estado):
    estado_norm = _normalizar_texto(estado)
    if estado_norm in {"en_atencion", "en atención", "activa"}:
        return "en_atencion"
    if estado_norm in {"cerrada", "cerrado"}:
        return "cerrada"
    return "pendiente"


def build_statistics_from_records(
    feedback_records,
    pendientes_records,
    rrhh_records=None,
    now=None,
    days=7,
    detail_limit=200,
):
    rrhh_records = rrhh_records or []
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
    feedback_reciente = []
    pendientes_recientes = []
    rrhh_recientes = []

    for item in feedback_records:
        voto = _normalizar_texto(item.get("fue_util"))
        if _es_voto_si(voto):
            votos_si += 1
        elif _es_voto_no(voto):
            votos_no += 1

        tema = _normalizar_texto(item.get("tema"))
        if tema:
            temas_counter[tema] += 1

        fecha = _extraer_fecha(item.get("fecha"))
        feedback_reciente.append(
            {
                "fecha": _formatear_fecha(fecha),
                "fecha_iso": fecha.isoformat(timespec="seconds") if fecha else "",
                "tema": tema or "sin tema",
                "fue_util": voto or "sin dato",
            }
        )
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
        pendientes_recientes.append(
            {
                "fecha": _formatear_fecha(fecha),
                "fecha_iso": fecha.isoformat(timespec="seconds") if fecha else "",
                "pregunta": str(item.get("pregunta") or "sin pregunta"),
                "sentimiento": sentimiento,
                "estado": _normalizar_texto(item.get("estado")) or "sin estado",
            }
        )
        if fecha:
            key = fecha.date().isoformat()
            if key in labels_set:
                idx = label_index[key]
                serie["pendientes"][idx] += 1

    utilidad_pct = 0.0
    if total_feedback > 0:
        utilidad_pct = round((votos_si / total_feedback) * 100, 2)

    top_temas_todos = [
        {"tema": tema, "cantidad": cantidad}
        for tema, cantidad in temas_counter.most_common()
    ]
    sentimientos_todos = [
        {"sentimiento": sentimiento, "cantidad": cantidad}
        for sentimiento, cantidad in sentimientos_counter.most_common()
    ]

    feedback_reciente_ordenado = _ordenar_por_fecha_desc(feedback_reciente)
    feedback_no_util = [
        item for item in feedback_reciente_ordenado if _es_voto_no(item.get("fue_util"))
    ][:detail_limit]
    feedback_si_util = [
        item for item in feedback_reciente_ordenado if _es_voto_si(item.get("fue_util"))
    ][:detail_limit]
    feedback_reciente = feedback_reciente_ordenado[:detail_limit]
    pendientes_recientes = _ordenar_por_fecha_desc(pendientes_recientes)[:detail_limit]
    desglose_diario = [
        {
            "fecha": label,
            "feedback": serie["feedback"][idx],
            "pendientes": serie["pendientes"][idx],
        }
        for idx, label in enumerate(labels)
    ]

    rrhh_pendientes = 0
    rrhh_en_atencion = 0
    rrhh_cerradas = 0
    for item in rrhh_records:
        estado = _normalizar_estado_handoff(item.get("estado"))
        if estado == "en_atencion":
            rrhh_en_atencion += 1
        elif estado == "cerrada":
            rrhh_cerradas += 1
        else:
            rrhh_pendientes += 1

        updated_at = _extraer_fecha(item.get("updated_at")) or _extraer_fecha(
            item.get("created_at")
        )
        rrhh_recientes.append(
            {
                "conversation_id": str(
                    item.get("conversation_id") or item.get("id") or "sin_id"
                ),
                "estado": estado,
                "agente": str(item.get("rrhh_agente") or "sin asignar"),
                "ultima_consulta": str(item.get("ultima_consulta") or ""),
                "fecha": _formatear_fecha(updated_at),
                "fecha_iso": updated_at.isoformat(timespec="seconds") if updated_at else "",
            }
        )

    rrhh_recientes = _ordenar_por_fecha_desc(rrhh_recientes)[:detail_limit]
    rrhh_abiertas = rrhh_pendientes + rrhh_en_atencion

    return {
        "available": True,
        "kpis": {
            "total_feedback": total_feedback,
            "votos_si": votos_si,
            "votos_no": votos_no,
            "no_util_total": votos_no,
            "utilidad_pct": utilidad_pct,
            "total_pendientes": total_pendientes,
            "rrhh_total": len(rrhh_records),
            "rrhh_abiertas": rrhh_abiertas,
            "rrhh_pendientes": rrhh_pendientes,
            "rrhh_en_atencion": rrhh_en_atencion,
            "rrhh_cerradas": rrhh_cerradas,
        },
        "top_temas": top_temas_todos[:8],
        "pendientes_por_sentimiento": sentimientos_todos,
        "series_7_dias": serie,
        "detail": {
            "feedback_reciente": feedback_reciente,
            "feedback_no_util": feedback_no_util,
            "feedback_si_util": feedback_si_util,
            "pendientes_recientes": pendientes_recientes,
            "ranking_temas": top_temas_todos,
            "ranking_sentimientos": sentimientos_todos,
            "desglose_diario": desglose_diario,
            "rrhh_conversaciones": rrhh_recientes,
            "votos": {
                "si": votos_si,
                "no": votos_no,
            },
        },
        "updated_at": now.isoformat(timespec="seconds"),
    }


def obtener_estadisticas(db, now=None, days=7, rrhh_records=None):
    rrhh_records = rrhh_records or []
    if db is None:
        rrhh_pendientes = 0
        rrhh_en_atencion = 0
        rrhh_cerradas = 0
        rrhh_conversaciones = []
        for item in rrhh_records:
            estado = _normalizar_estado_handoff(item.get("estado"))
            if estado == "en_atencion":
                rrhh_en_atencion += 1
            elif estado == "cerrada":
                rrhh_cerradas += 1
            else:
                rrhh_pendientes += 1
            updated_at = _extraer_fecha(item.get("updated_at")) or _extraer_fecha(
                item.get("created_at")
            )
            rrhh_conversaciones.append(
                {
                    "conversation_id": str(
                        item.get("conversation_id") or item.get("id") or "sin_id"
                    ),
                    "estado": estado,
                    "agente": str(item.get("rrhh_agente") or "sin asignar"),
                    "ultima_consulta": str(item.get("ultima_consulta") or ""),
                    "fecha": _formatear_fecha(updated_at),
                    "fecha_iso": updated_at.isoformat(timespec="seconds") if updated_at else "",
                }
            )
        rrhh_conversaciones = _ordenar_por_fecha_desc(rrhh_conversaciones)[:200]
        rrhh_abiertas = rrhh_pendientes + rrhh_en_atencion

        current_time = now or datetime.now(timezone.utc)
        labels = _labels_ultimos_dias(current_time, days)
        return {
            "available": False,
            "reason": "Sin conexión a Firestore",
            "kpis": {
                "total_feedback": 0,
                "votos_si": 0,
                "votos_no": 0,
                "no_util_total": 0,
                "utilidad_pct": 0.0,
                "total_pendientes": 0,
                "rrhh_total": len(rrhh_records),
                "rrhh_abiertas": rrhh_abiertas,
                "rrhh_pendientes": rrhh_pendientes,
                "rrhh_en_atencion": rrhh_en_atencion,
                "rrhh_cerradas": rrhh_cerradas,
            },
            "top_temas": [],
            "pendientes_por_sentimiento": [],
            "series_7_dias": _serie_vacia(labels),
            "detail": {
                "feedback_reciente": [],
                "feedback_no_util": [],
                "feedback_si_util": [],
                "pendientes_recientes": [],
                "ranking_temas": [],
                "ranking_sentimientos": [],
                "desglose_diario": [
                    {"fecha": label, "feedback": 0, "pendientes": 0}
                    for label in labels
                ],
                "rrhh_conversaciones": rrhh_conversaciones,
                "votos": {"si": 0, "no": 0},
            },
            "updated_at": current_time.isoformat(timespec="seconds"),
        }

    feedback_records = [doc.to_dict() for doc in db.collection("feedback_respuestas").stream()]
    pendientes_records = [doc.to_dict() for doc in db.collection("consultas_pendientes").stream()]
    if not rrhh_records:
        rrhh_records = [doc.to_dict() for doc in db.collection("rrhh_handoffs").stream()]
    return build_statistics_from_records(
        feedback_records=feedback_records,
        pendientes_records=pendientes_records,
        rrhh_records=rrhh_records,
        now=now,
        days=days,
    )

