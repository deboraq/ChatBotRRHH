from collections import Counter
from datetime import date as _date_type, datetime, timedelta, timezone


def _normalizar_texto(valor):
    return str(valor).strip().lower() if valor is not None else ""


def _normalize_company_id(value):
    """Normaliza company_id para comparación (minúsculas, sin espacios)."""
    if value is None:
        return ""
    s = str(value).strip().lower()
    return s[:64] if s else ""


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
    # Manejar fechas guardadas como strings ISO (ej: sent_at de comunicados)
    if isinstance(valor, str) and valor.strip():
        try:
            s = valor.strip().replace("Z", "+00:00")
            dt = datetime.fromisoformat(s)
            if dt.tzinfo is not None:
                dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
            return dt
        except (ValueError, TypeError):
            pass
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
    comunicados_records=None,
    legajos_activos=0,
    legajos_inactivos=0,
    now=None,
    days=7,
    detail_limit=200,
    date_from=None,
    date_to=None,
):
    rrhh_records = rrhh_records or []
    comunicados_records = comunicados_records or []
    now = now or datetime.now(timezone.utc)

    # Filtrar registros por rango de fechas si se especifica
    if date_from or date_to:
        def _in_range(dt):
            if dt is None:
                return False
            d = dt.date() if hasattr(dt, "date") else dt
            if date_from and d < date_from:
                return False
            if date_to and d > date_to:
                return False
            return True
        feedback_records = [r for r in feedback_records if _in_range(_extraer_fecha(r.get("fecha")))]
        pendientes_records = [r for r in pendientes_records if _in_range(_extraer_fecha(r.get("fecha")))]
        comunicados_records = [r for r in comunicados_records if _in_range(
            _extraer_fecha(r.get("sent_at")) or _extraer_fecha(r.get("scheduled_at"))
        )]

    # Etiquetas del gráfico: usar rango seleccionado o últimos N días
    if date_from and date_to:
        delta = (date_to - date_from).days
        days_for_chart = min(delta + 1, 90)
        labels = [(date_from + timedelta(days=i)).isoformat() for i in range(days_for_chart)]
    else:
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

    # Tasa de resolución del bot: % de consultas donde el bot dio alguna respuesta
    total_consultas_bot = total_feedback + total_pendientes
    resolucion_bot_pct = round(total_feedback / total_consultas_bot * 100, 1) if total_consultas_bot > 0 else 0.0

    total_temas = sum(temas_counter.values())
    top_temas_todos = [
        {"tema": tema, "cantidad": cantidad, "pct": round(cantidad / total_temas * 100, 1) if total_temas else 0}
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
    # Preguntas sin respuesta: feedback donde el bot no pudo responder (tema contiene "sin_respuesta")
    sin_respuesta_items = [
        item for item in feedback_reciente_ordenado
        if "sin_respuesta" in (item.get("tema") or "")
    ][:detail_limit]
    sin_respuesta_total = len(sin_respuesta_items)
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
    tiempos_atencion = []
    agentes_stats = {}

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

        # Seguimiento por agente y tiempos de atención
        agente = str(item.get("rrhh_agente") or "sin asignar").strip()
        if agente not in agentes_stats:
            agentes_stats[agente] = {"agente": agente, "total": 0, "cerradas": 0, "tiempos_min": []}
        agentes_stats[agente]["total"] += 1
        if estado == "cerrada":
            agentes_stats[agente]["cerradas"] += 1
            created = _extraer_fecha(item.get("created_at"))
            updated = _extraer_fecha(item.get("updated_at"))
            if created and updated and updated > created:
                mins = (updated - created).total_seconds() / 60
                tiempos_atencion.append(mins)
                agentes_stats[agente]["tiempos_min"].append(mins)

    rrhh_recientes = _ordenar_por_fecha_desc(rrhh_recientes)[:detail_limit]
    rrhh_abiertas = rrhh_pendientes + rrhh_en_atencion
    tiempo_promedio_atencion_min = round(sum(tiempos_atencion) / len(tiempos_atencion), 1) if tiempos_atencion else None
    derivaciones_por_agente = [
        {
            "agente": ad["agente"],
            "total": ad["total"],
            "cerradas": ad["cerradas"],
            "tiempo_promedio_min": round(sum(ad["tiempos_min"]) / len(ad["tiempos_min"]), 1) if ad["tiempos_min"] else None,
        }
        for ad in sorted(agentes_stats.values(), key=lambda x: x["total"], reverse=True)
    ]

    # ── Comunicados ──────────────────────────────────────────────────────────
    com_total = 0
    com_exitosos = 0
    com_fallidos = 0
    com_destinatarios_total = 0
    com_recientes = []
    for item in comunicados_records:
        estado = str(item.get("estado") or "").strip().lower()
        if estado not in ("enviado", "error"):
            continue
        com_total += 1
        result = item.get("result") or {}
        sent = int(result.get("sent") or 0)
        failed = int(result.get("failed") or 0)
        if estado == "enviado":
            com_exitosos += 1
            com_destinatarios_total += sent
        else:
            com_fallidos += 1
        fecha_com = _extraer_fecha(item.get("sent_at")) or _extraer_fecha(item.get("scheduled_at"))
        dest_count = len(item.get("destinatarios") or []) or sent or 0
        com_recientes.append({
            "fecha": _formatear_fecha(fecha_com),
            "fecha_iso": fecha_com.isoformat(timespec="seconds") if fecha_com else "",
            "mensaje": str(item.get("mensaje") or "")[:80],
            "destinatarios": dest_count,
            "enviados": sent,
            "fallidos": failed,
            "estado": estado,
            "creado_por": str(item.get("created_by") or ""),
        })
    com_recientes = _ordenar_por_fecha_desc(com_recientes)[:detail_limit]

    return {
        "available": True,
        "kpis": {
            "total_feedback": total_feedback,
            "votos_si": votos_si,
            "votos_no": votos_no,
            "no_util_total": votos_no,
            "utilidad_pct": utilidad_pct,
            "resolucion_bot_pct": resolucion_bot_pct,
            "sin_respuesta_total": sin_respuesta_total,
            "total_pendientes": total_pendientes,
            "rrhh_total": len(rrhh_records),
            "rrhh_abiertas": rrhh_abiertas,
            "rrhh_pendientes": rrhh_pendientes,
            "rrhh_en_atencion": rrhh_en_atencion,
            "rrhh_cerradas": rrhh_cerradas,
            "tiempo_promedio_atencion_min": tiempo_promedio_atencion_min,
            "comunicados_total": com_total,
            "comunicados_exitosos": com_exitosos,
            "comunicados_fallidos": com_fallidos,
            "comunicados_destinatarios": com_destinatarios_total,
            "legajos_activos": legajos_activos,
            "legajos_inactivos": legajos_inactivos,
            "legajos_total": legajos_activos + legajos_inactivos,
        },
        "top_temas": top_temas_todos[:8],
        "pendientes_por_sentimiento": sentimientos_todos,
        "series_7_dias": serie,
        "detail": {
            "feedback_reciente": feedback_reciente,
            "feedback_no_util": feedback_no_util,
            "feedback_si_util": feedback_si_util,
            "sin_respuesta_items": sin_respuesta_items,
            "pendientes_recientes": pendientes_recientes,
            "ranking_temas": top_temas_todos,
            "ranking_sentimientos": sentimientos_todos,
            "desglose_diario": desglose_diario,
            "rrhh_conversaciones": rrhh_recientes,
            "derivaciones_por_agente": derivaciones_por_agente,
            "votos": {
                "si": votos_si,
                "no": votos_no,
            },
            "comunicados_recientes": com_recientes,
        },
        "updated_at": now.isoformat(timespec="seconds"),
    }


def obtener_estadisticas(db, now=None, days=7, rrhh_records=None, company_id=None, date_from=None, date_to=None):
    rrhh_records = rrhh_records or []
    filter_cid = _normalize_company_id(company_id) if company_id else ""
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
                "comunicados_total": 0,
                "comunicados_exitosos": 0,
                "comunicados_fallidos": 0,
                "comunicados_destinatarios": 0,
                "legajos_activos": 0,
                "legajos_inactivos": 0,
                "legajos_total": 0,
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
                "comunicados_recientes": [],
            },
            "updated_at": current_time.isoformat(timespec="seconds"),
        }

    feedback_records = [doc.to_dict() for doc in db.collection("feedback_respuestas").stream()]
    pendientes_records = [doc.to_dict() for doc in db.collection("consultas_pendientes").stream()]
    comunicados_records = [doc.to_dict() for doc in db.collection("comunicados_programados").stream()]
    if filter_cid:
        feedback_records = [r for r in feedback_records if _normalize_company_id(r.get("company_id")) == filter_cid]
        pendientes_records = [r for r in pendientes_records if _normalize_company_id(r.get("company_id")) == filter_cid]
        comunicados_records = [r for r in comunicados_records if _normalize_company_id(r.get("company_id")) == filter_cid]
    if not rrhh_records:
        rrhh_records = [doc.to_dict() for doc in db.collection("rrhh_handoffs").stream()]
    # Contar colaboradores activos/inactivos
    legajos_activos = 0
    legajos_inactivos = 0
    for doc in db.collection("legajos_empleados").stream():
        data = doc.to_dict()
        if filter_cid and _normalize_company_id(data.get("company_id")) != filter_cid:
            continue
        if data.get("activo", True):
            legajos_activos += 1
        else:
            legajos_inactivos += 1
    return build_statistics_from_records(
        feedback_records=feedback_records,
        pendientes_records=pendientes_records,
        rrhh_records=rrhh_records,
        comunicados_records=comunicados_records,
        legajos_activos=legajos_activos,
        legajos_inactivos=legajos_inactivos,
        now=now,
        days=days,
        date_from=date_from,
        date_to=date_to,
    )

