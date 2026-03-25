"""
Legajos digitales: metadatos en Firestore (empleados y documentos).
Los archivos viven en Firebase Storage bajo el prefijo legajos_uploads/ (ver web_chat).
"""

from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from typing import Any

LEGAJOS_EMPLEADOS_COLLECTION = "legajos_empleados"
LEGAJOS_DOCUMENTOS_COLLECTION = "legajos_documentos"
LEGAJOS_AUDITORIA_COLLECTION = "legajos_auditoria"

# Acciones registradas en auditoría (campo action)
LEGAJOS_AUDIT_EMPLEADO_CREAR = "empleado_crear"
LEGAJOS_AUDIT_EMPLEADO_EDITAR = "empleado_editar"
LEGAJOS_AUDIT_EMPLEADO_IMPORTAR = "empleado_importar"
LEGAJOS_AUDIT_EMPLEADO_ELIMINAR = "empleado_eliminar"
LEGAJOS_AUDIT_DOCUMENTO_SUBIR = "documento_subir"
LEGAJOS_AUDIT_DOCUMENTO_DESCARGAR = "documento_descargar"
LEGAJOS_AUDIT_DOCUMENTO_ELIMINAR = "documento_eliminar"

LEGAJOS_IMPORT_MAX_ROWS = 500


def _utc_now():
    return datetime.now(timezone.utc)


def normalize_dni(value: str) -> str:
    """Solo dígitos (para ID y validación)."""
    return "".join(c for c in str(value or "") if c.isdigit())


def make_empleado_doc_id(company_id: str, dni_raw: str) -> str | None:
    """
    ID de documento en Firestore: {empresa}_{dni} (ej. bacar_30123456).
    Requiere 6–16 dígitos en el DNI.
    """
    cid = str(company_id or "").strip().lower()
    digits = normalize_dni(dni_raw)
    if len(digits) < 6 or len(digits) > 16:
        return None
    if not cid:
        return None
    return f"{cid}_{digits}"


def _serialize_ts(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            return str(value)
    return str(value)


def list_empleados(
    db,
    company_id: str,
    search: str | None = None,
) -> list[dict]:
    """Lista empleados de una empresa. Orden local por legajo y nombre."""
    if not db or not company_id:
        return []
    cid = str(company_id).strip().lower()
    q = (search or "").strip().lower()
    out: list[dict] = []
    try:
        for snap in db.collection(LEGAJOS_EMPLEADOS_COLLECTION).where("company_id", "==", cid).stream():
            row = empleado_from_snap(snap)
            if q:
                leg = (row.get("legajo_numero") or "").lower()
                nom = (row.get("nombre_completo") or "").lower()
                dni_f = (row.get("dni") or "").lower()
                em = (row.get("email") or "").lower()
                if q not in leg and q not in nom and q not in dni_f and q not in em:
                    continue
            out.append(row)
    except Exception:
        return []
    out.sort(
        key=lambda r: (
            str(r.get("legajo_numero") or ""),
            str(r.get("nombre_completo") or "").lower(),
        )
    )
    return out


def empleado_from_snap(doc_snap) -> dict:
    data = doc_snap.to_dict() or {}
    return {
        "id": doc_snap.id,
        "company_id": data.get("company_id") or "",
        "legajo_numero": data.get("legajo_numero") or "",
        "nombre_completo": data.get("nombre_completo") or "",
        "sucursal": data.get("sucursal") or "",
        "area": data.get("area") or "",
        "notas": data.get("notas") or "",
        "dni": data.get("dni") or "",
        "email": data.get("email") or "",
        "created_at": _serialize_ts(data.get("created_at")),
        "created_by": data.get("created_by") or "",
        "updated_at": _serialize_ts(data.get("updated_at")),
        "updated_by": data.get("updated_by") or "",
    }


def get_empleado(db, empleado_id: str) -> dict | None:
    if not db or not empleado_id:
        return None
    try:
        ref = db.collection(LEGAJOS_EMPLEADOS_COLLECTION).document(str(empleado_id))
        snap = ref.get()
        if not snap.exists:
            return None
        return empleado_from_snap(snap)
    except Exception:
        return None


def legajo_numero_exists(db, company_id: str, legajo_numero: str, exclude_id: str | None = None) -> bool:
    if not db or not company_id or not str(legajo_numero or "").strip():
        return False
    cid = str(company_id).strip().lower()
    leg = str(legajo_numero).strip()
    try:
        for snap in db.collection(LEGAJOS_EMPLEADOS_COLLECTION).where("company_id", "==", cid).stream():
            if exclude_id and snap.id == exclude_id:
                continue
            data = snap.to_dict() or {}
            if str(data.get("legajo_numero") or "").strip() == leg:
                return True
    except Exception:
        return False
    return False


def create_empleado(
    db,
    company_id: str,
    dni: str,
    nombre_completo: str,
    created_by: str,
    legajo_numero: str = "",
    sucursal: str = "",
    area: str = "",
    notas: str = "",
    email: str = "",
) -> tuple[bool, dict | None, str]:
    """Crea colaborador. ID en Firestore = {empresa}_{dni}. DNI obligatorio (6–16 dígitos). Legajo opcional."""
    if not db:
        return False, None, "Firestore no disponible."
    cid = str(company_id or "").strip().lower()
    leg = str(legajo_numero or "").strip()
    nom = str(nombre_completo or "").strip()
    dni_digits = normalize_dni(dni)
    if not cid:
        return False, None, "Falta empresa (company_id)."
    if not nom:
        return False, None, "Falta nombre completo."
    if len(dni_digits) < 6 or len(dni_digits) > 16:
        return False, None, "DNI inválido: usá entre 6 y 16 dígitos."
    doc_id = make_empleado_doc_id(cid, dni)
    if not doc_id:
        return False, None, "No se pudo generar el ID del colaborador."
    if leg and legajo_numero_exists(db, cid, leg):
        return False, None, "Ya existe un colaborador con ese legajo en esta empresa."
    now = _utc_now()
    payload = {
        "company_id": cid,
        "legajo_numero": leg,
        "nombre_completo": nom,
        "sucursal": str(sucursal or "").strip(),
        "area": str(area or "").strip(),
        "notas": str(notas or "").strip(),
        "dni": dni_digits,
        "email": str(email or "").strip().lower(),
        "created_at": now,
        "created_by": str(created_by or "").strip(),
        "updated_at": now,
    }
    try:
        ref = db.collection(LEGAJOS_EMPLEADOS_COLLECTION).document(doc_id)
        if ref.get().exists:
            return False, None, "Ya existe un colaborador con ese DNI en esta empresa."
        ref.set(payload)
        snap = ref.get()
        return True, empleado_from_snap(snap), ""
    except Exception as exc:
        return False, None, str(exc)


def update_empleado(
    db,
    empleado_id: str,
    legajo_numero: str,
    nombre_completo: str,
    updated_by: str,
    sucursal: str = "",
    area: str = "",
    notas: str = "",
    email: str = "",
) -> tuple[bool, dict | None, str]:
    """Actualiza datos. El DNI no se modifica (el ID del documento es fijo). Legajo vacío permitido."""
    if not db or not str(empleado_id or "").strip():
        return False, None, "Firestore no disponible o ID inválido."
    eid = str(empleado_id).strip()
    leg = str(legajo_numero or "").strip()
    nom = str(nombre_completo or "").strip()
    if not nom:
        return False, None, "Falta nombre completo."
    try:
        ref = db.collection(LEGAJOS_EMPLEADOS_COLLECTION).document(eid)
        snap = ref.get()
        if not snap.exists:
            return False, None, "Colaborador no encontrado."
        data = snap.to_dict() or {}
        cid = str(data.get("company_id") or "").strip().lower()
        if not cid:
            return False, None, "Registro sin empresa."
        if leg and legajo_numero_exists(db, cid, leg, exclude_id=eid):
            return False, None, "Ya existe otro colaborador con ese legajo en esta empresa."
        now = _utc_now()
        ref.update(
            {
                "legajo_numero": leg,
                "nombre_completo": nom,
                "sucursal": str(sucursal or "").strip(),
                "area": str(area or "").strip(),
                "notas": str(notas or "").strip(),
                "email": str(email or "").strip().lower(),
                "updated_at": now,
                "updated_by": str(updated_by or "").strip(),
            }
        )
        snap = ref.get()
        return True, empleado_from_snap(snap), ""
    except Exception as exc:
        return False, None, str(exc)


def delete_empleado_completo(db, empleado_id: str) -> tuple[bool, list[str], str]:
    """Elimina el colaborador y los metadatos de sus documentos. Devuelve rutas en Storage a borrar."""
    if not db or not str(empleado_id or "").strip():
        return False, [], "ID inválido."
    eid = str(empleado_id).strip()
    paths: list[str] = []
    try:
        for snap in (
            db.collection(LEGAJOS_DOCUMENTOS_COLLECTION).where("empleado_id", "==", eid).stream()
        ):
            doc_id = snap.id
            row = documento_from_snap(snap)
            p = str(row.get("storage_path") or "").strip()
            if p:
                paths.append(p)
            db.collection(LEGAJOS_DOCUMENTOS_COLLECTION).document(doc_id).delete()
        ref = db.collection(LEGAJOS_EMPLEADOS_COLLECTION).document(eid)
        snap_e = ref.get()
        if not snap_e.exists:
            return False, [], "Colaborador no encontrado."
        ref.delete()
        return True, paths, ""
    except Exception as exc:
        return False, [], str(exc)


def list_documentos(db, empleado_id: str) -> list[dict]:
    if not db or not empleado_id:
        return []
    eid = str(empleado_id).strip()
    out: list[dict] = []
    try:
        for snap in (
            db.collection(LEGAJOS_DOCUMENTOS_COLLECTION).where("empleado_id", "==", eid).stream()
        ):
            out.append(documento_from_snap(snap))
    except Exception:
        return []
    out.sort(key=lambda r: str(r.get("uploaded_at") or ""), reverse=True)
    return out


def documento_from_snap(doc_snap) -> dict:
    data = doc_snap.to_dict() or {}
    return {
        "id": doc_snap.id,
        "empleado_id": data.get("empleado_id") or "",
        "company_id": data.get("company_id") or "",
        "tipo_documento": data.get("tipo_documento") or "otro",
        "filename": data.get("filename") or "",
        "storage_path": data.get("storage_path") or "",
        "content_type": data.get("content_type") or "",
        "size_bytes": int(data.get("size_bytes") or 0),
        "uploaded_by": data.get("uploaded_by") or "",
        "uploaded_at": _serialize_ts(data.get("uploaded_at")),
    }


def create_documento(
    db,
    empleado_id: str,
    company_id: str,
    storage_path: str,
    filename: str,
    content_type: str,
    size_bytes: int,
    uploaded_by: str,
    tipo_documento: str = "otro",
) -> tuple[bool, dict | None, str]:
    if not db:
        return False, None, "Firestore no disponible."
    eid = str(empleado_id or "").strip()
    cid = str(company_id or "").strip().lower()
    path = str(storage_path or "").strip()
    if not eid or not cid or not path:
        return False, None, "Datos incompletos para registrar el documento."
    now = _utc_now()
    payload = {
        "empleado_id": eid,
        "company_id": cid,
        "tipo_documento": str(tipo_documento or "otro").strip() or "otro",
        "filename": str(filename or "").strip() or "archivo",
        "storage_path": path,
        "content_type": str(content_type or "").strip(),
        "size_bytes": int(size_bytes or 0),
        "uploaded_by": str(uploaded_by or "").strip(),
        "uploaded_at": now,
    }
    try:
        ref = db.collection(LEGAJOS_DOCUMENTOS_COLLECTION).document()
        ref.set(payload)
        snap = ref.get()
        return True, documento_from_snap(snap), ""
    except Exception as exc:
        return False, None, str(exc)


def get_documento(db, documento_id: str) -> dict | None:
    if not db or not documento_id:
        return None
    try:
        ref = db.collection(LEGAJOS_DOCUMENTOS_COLLECTION).document(str(documento_id))
        snap = ref.get()
        if not snap.exists:
            return None
        return documento_from_snap(snap)
    except Exception:
        return None


def delete_documento_record(db, documento_id: str) -> tuple[bool, dict | None, str]:
    """Elimina solo el documento de Firestore. El blob en Storage lo borra el caller."""
    if not db:
        return False, None, "Firestore no disponible."
    try:
        ref = db.collection(LEGAJOS_DOCUMENTOS_COLLECTION).document(str(documento_id))
        snap = ref.get()
        if not snap.exists:
            return False, None, "Documento no encontrado."
        data = documento_from_snap(snap)
        ref.delete()
        return True, data, ""
    except Exception as exc:
        return False, None, str(exc)


def append_auditoria(
    db,
    company_id: str,
    username: str,
    action: str,
    details: dict | None = None,
) -> None:
    """Registra un evento (best-effort; no lanza)."""
    if not db or not str(company_id or "").strip():
        return
    cid = str(company_id).strip().lower()
    payload = {
        "company_id": cid,
        "username": str(username or "").strip() or "desconocido",
        "action": str(action or "").strip(),
        "details": dict(details) if isinstance(details, dict) else {},
        "at": _utc_now(),
    }
    try:
        db.collection(LEGAJOS_AUDITORIA_COLLECTION).add(payload)
    except Exception:
        pass


def auditoria_from_snap(doc_snap) -> dict:
    data = doc_snap.to_dict() or {}
    det = data.get("details")
    if not isinstance(det, dict):
        det = {}
    return {
        "id": doc_snap.id,
        "company_id": data.get("company_id") or "",
        "username": data.get("username") or "",
        "action": data.get("action") or "",
        "details": det,
        "at": _serialize_ts(data.get("at")),
    }


def list_auditoria(db, company_id: str, limit: int = 80) -> list[dict]:
    """Últimos eventos de una empresa (orden local por fecha, sin índice compuesto)."""
    if not db or not company_id:
        return []
    cid = str(company_id).strip().lower()
    lim = max(1, min(int(limit or 80), 200))
    try:
        snaps = list(
            db.collection(LEGAJOS_AUDITORIA_COLLECTION).where("company_id", "==", cid).stream()
        )
    except Exception:
        return []

    def _sort_key(s):
        d = s.to_dict() or {}
        v = d.get("at")
        if isinstance(v, datetime):
            return v.timestamp()
        if hasattr(v, "timestamp"):
            try:
                return float(v.timestamp())
            except Exception:
                return 0.0
        return 0.0

    try:
        snaps.sort(key=_sort_key, reverse=True)
    except Exception:
        snaps.sort(key=lambda s: s.id, reverse=True)
    return [auditoria_from_snap(s) for s in snaps[:lim]]


def _normalize_import_row(row: dict) -> tuple[str, str, str, str, str, str, str]:
    """Mapea encabezados flexibles a legajo, nombre, sucursal, área, notas, dni, email."""
    m: dict[str, str] = {}
    for k, v in (row or {}).items():
        if k is None:
            continue
        key = str(k).strip().lower().replace(" ", "_")
        m[key] = (str(v).strip() if v is not None else "")
    leg = (
        m.get("legajo_numero")
        or m.get("legajo")
        or m.get("nro_legajo")
        or m.get("numero_legajo")
        or m.get("número_legajo")
        or ""
    )
    nom = (
        m.get("nombre_completo")
        or m.get("nombre")
        or m.get("apellido_y_nombre")
        or m.get("apellido_nombre")
        or ""
    )
    suc = m.get("sucursal") or m.get("branch") or ""
    area = m.get("area") or m.get("área") or ""
    notas = m.get("notas") or m.get("observaciones") or ""
    dni = m.get("dni") or m.get("documento") or m.get("nro_documento") or ""
    email = m.get("email") or m.get("mail") or m.get("correo") or ""
    return leg.strip(), nom.strip(), suc.strip(), area.strip(), notas.strip(), dni.strip(), email.strip()


def parse_legajos_import_file(filename: str, raw: bytes) -> tuple[list[tuple[int, dict]], str | None]:
    """
    Lee CSV (UTF-8) o Excel .xlsx y devuelve filas (nº línea, dict por encabezado)
    en el mismo formato que csv.DictReader, para import_empleados_desde_filas.
    """
    fn = (filename or "").lower().strip()
    if not raw:
        return [], "Archivo vacío."
    if fn.endswith(".csv"):
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            return [], "El CSV debe estar en UTF-8."
        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames:
            return [], "CSV sin encabezados."
        filas: list[tuple[int, dict]] = []
        line_no = 1
        for row in reader:
            line_no += 1
            filas.append((line_no, dict(row or {})))
        return filas, None
    if fn.endswith((".xlsx", ".xlsm")):
        try:
            from openpyxl import load_workbook
        except ImportError:
            return [], "Falta el paquete openpyxl en el servidor para importar Excel."
        try:
            wb = load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
            ws = wb.active
            rows_iter = ws.iter_rows(values_only=True)
            try:
                header_row = next(rows_iter)
            except StopIteration:
                return [], "El Excel está vacío."
            headers: list[str] = []
            for h in header_row:
                if h is None:
                    headers.append("")
                else:
                    headers.append(str(h).strip())
            if not any(x for x in headers if x):
                return [], "Excel sin encabezados en la primera fila."
            filas = []
            line_no = 1
            for row in rows_iter:
                line_no += 1
                d: dict[str, str] = {}
                for i, key in enumerate(headers):
                    if not key:
                        continue
                    val = row[i] if i < len(row) else None
                    if val is None:
                        d[key] = ""
                    elif hasattr(val, "isoformat") and not isinstance(val, str):
                        try:
                            d[key] = val.isoformat()
                        except Exception:
                            d[key] = str(val).strip()
                    else:
                        d[key] = str(val).strip()
                if any(str(v).strip() for v in d.values()):
                    filas.append((line_no, d))
            return filas, None
        except Exception as exc:
            return [], f"No se pudo leer el Excel: {exc}"
    return [], "Formato no soportado. Usá .csv o .xlsx (Excel)."


def build_legajos_ejemplo_xlsx_bytes() -> tuple[bytes | None, str | None]:
    """Genera un .xlsx de ejemplo con columnas separadas (compatible con Excel)."""
    try:
        from openpyxl import Workbook
    except ImportError:
        return None, "openpyxl no instalado."
    wb = Workbook()
    ws = wb.active
    ws.title = "Colaboradores"
    ws.append(
        ["dni", "nombre_completo", "email", "legajo_numero", "sucursal", "area", "notas"]
    )
    ws.append(
        [
            30123456,
            "García Ana María",
            "ana@ejemplo.com",
            "1001",
            "Córdoba",
            "Administración",
            "",
        ]
    )
    ws.append(
        [
            28999111,
            "López Juan Pablo",
            "juan@ejemplo.com",
            "1002",
            "Córdoba",
            "Operaciones",
            "Alta 2025-03",
        ]
    )
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue(), None


def build_legajos_export_xlsx_bytes(items: list[dict]) -> tuple[bytes | None, str | None]:
    """
    Exporta colaboradores a .xlsx con las mismas columnas que el ejemplo de importación
    (dni, nombre_completo, email, legajo_numero, sucursal, area, notas).
    """
    try:
        from openpyxl import Workbook
    except ImportError:
        return None, "openpyxl no instalado."
    wb = Workbook()
    ws = wb.active
    ws.title = "Colaboradores"
    ws.append(
        ["dni", "nombre_completo", "email", "legajo_numero", "sucursal", "area", "notas"]
    )
    for row in items or []:
        ws.append(
            [
                str(row.get("dni") or ""),
                str(row.get("nombre_completo") or ""),
                str(row.get("email") or ""),
                str(row.get("legajo_numero") or ""),
                str(row.get("sucursal") or ""),
                str(row.get("area") or ""),
                str(row.get("notas") or ""),
            ]
        )
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue(), None


def import_empleados_desde_filas(
    db,
    company_id: str,
    filas: list[tuple[int, dict]],
    created_by: str,
) -> dict:
    """
    filas: lista de (número_de_linea, dict como devuelve csv.DictReader).
    Máximo LEGAJOS_IMPORT_MAX_ROWS filas con datos.
    """
    if not db:
        return {"created": 0, "skipped_duplicate": 0, "errors": [{"line": 0, "error": "Firestore no disponible."}]}
    cid = str(company_id or "").strip().lower()
    if not cid:
        return {"created": 0, "skipped_duplicate": 0, "errors": [{"line": 0, "error": "Falta empresa."}]}

    created = 0
    skipped = 0
    errors: list[dict] = []
    processed = 0

    for line_no, raw in filas:
        leg, nom, suc, area, notas, dni, email = _normalize_import_row(raw)
        if not nom and not dni:
            continue
        processed += 1
        if processed > LEGAJOS_IMPORT_MAX_ROWS:
            errors.append({"line": line_no, "error": f"Límite de {LEGAJOS_IMPORT_MAX_ROWS} filas por importación."})
            break
        if not nom or not dni:
            errors.append({"line": line_no, "error": "Falta nombre o DNI."})
            continue
        ok, _, msg = create_empleado(
            db,
            company_id=cid,
            dni=dni,
            nombre_completo=nom,
            created_by=created_by,
            legajo_numero=leg,
            sucursal=suc,
            area=area,
            notas=notas,
            email=email,
        )
        if ok:
            created += 1
        else:
            low = (msg or "").lower()
            if "ya existe" in low:
                skipped += 1
            else:
                errors.append({"line": line_no, "error": msg or "Error al crear."})

    return {"created": created, "skipped_duplicate": skipped, "errors": errors}
