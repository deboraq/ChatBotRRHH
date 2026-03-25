import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock

import legajos_service


class FakeSnap:
    def __init__(self, doc_id, data, exists=True):
        self.id = doc_id
        self._data = dict(data)
        self.exists = exists

    def to_dict(self):
        return dict(self._data)


class LegajosServiceTests(unittest.TestCase):
    def test_create_empleado_rejects_duplicate_legajo(self):
        existing = FakeSnap("e1", {"company_id": "bacar", "legajo_numero": "100"})
        col = MagicMock()
        wq = MagicMock()
        wq.stream.return_value = [existing]
        col.where.return_value = wq
        col.document.return_value = MagicMock()

        db = MagicMock()
        db.collection.return_value = col

        ok, row, msg = legajos_service.create_empleado(
            db,
            company_id="bacar",
            dni="30123456",
            legajo_numero="100",
            nombre_completo="Otro",
            created_by="admin",
        )
        self.assertFalse(ok)
        self.assertIsNone(row)
        self.assertIn("legajo", msg.lower())

    def test_list_empleados_filters_search(self):
        snaps = [
            FakeSnap("a", {"company_id": "x", "legajo_numero": "1", "nombre_completo": "Ana López"}),
            FakeSnap("b", {"company_id": "x", "legajo_numero": "2", "nombre_completo": "Benito"}),
        ]
        col = MagicMock()
        wq = MagicMock()
        wq.stream.return_value = snaps
        col.where.return_value = wq
        db = MagicMock()
        db.collection.return_value = col

        out = legajos_service.list_empleados(db, "x", search="ana")
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["id"], "a")

    def test_parse_legajos_import_csv(self):
        raw = "dni,nombre_completo,email\n30111222,Test User,mail@test.com\n".encode("utf-8")
        filas, err = legajos_service.parse_legajos_import_file("colabs.csv", raw)
        self.assertIsNone(err)
        self.assertEqual(len(filas), 1)
        self.assertEqual(filas[0][1].get("dni"), "30111222")
        self.assertEqual(filas[0][1].get("nombre_completo"), "Test User")

    def test_parse_legajos_import_xlsx_roundtrip(self):
        body, err = legajos_service.build_legajos_ejemplo_xlsx_bytes()
        self.assertIsNone(err)
        self.assertIsNotNone(body)
        filas, perr = legajos_service.parse_legajos_import_file("ejemplo.xlsx", body or b"")
        self.assertIsNone(perr)
        self.assertGreaterEqual(len(filas), 2)

    def test_export_xlsx_matches_import_columns(self):
        rows = [
            {
                "dni": "30111222",
                "nombre_completo": "Test",
                "email": "t@test.com",
                "legajo_numero": "1",
                "sucursal": "S",
                "area": "A",
                "notas": "n",
            }
        ]
        raw, err = legajos_service.build_legajos_export_xlsx_bytes(rows)
        self.assertIsNone(err)
        self.assertIsNotNone(raw)
        filas, perr = legajos_service.parse_legajos_import_file("export.xlsx", raw or b"")
        self.assertIsNone(perr)
        self.assertEqual(len(filas), 1)
        leg, nom, suc, area, notas, dni, email = legajos_service._normalize_import_row(filas[0][1])
        self.assertEqual(dni, "30111222")
        self.assertEqual(nom, "Test")
        self.assertEqual(email, "t@test.com")

    def test_normalize_import_row_aliases(self):
        leg, nom, suc, area, notas, dni, email = legajos_service._normalize_import_row(
            {
                "Legajo": "55",
                "Nombre": "Test User",
                "Sucursal": "A",
                "Area": "B",
                "Notas": "x",
                "DNI": "30111222",
                "Mail": "test@ejemplo.com",
            }
        )
        self.assertEqual(leg, "55")
        self.assertEqual(nom, "Test User")
        self.assertEqual(suc, "A")
        self.assertEqual(area, "B")
        self.assertEqual(notas, "x")
        self.assertEqual(dni, "30111222")
        self.assertEqual(email, "test@ejemplo.com")

    def test_list_auditoria_orders_newest_first(self):
        old = FakeSnap(
            "o",
            {
                "company_id": "x",
                "action": "a",
                "details": {},
                "at": datetime(2020, 1, 1, tzinfo=timezone.utc),
            },
        )
        new = FakeSnap(
            "n",
            {
                "company_id": "x",
                "action": "b",
                "details": {},
                "at": datetime(2025, 1, 1, tzinfo=timezone.utc),
            },
        )
        col = MagicMock()
        wq = MagicMock()
        wq.stream.return_value = [old, new]
        col.where.return_value = wq
        db = MagicMock()
        db.collection.return_value = col
        out = legajos_service.list_auditoria(db, "x", limit=10)
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0]["id"], "n")
        self.assertEqual(out[1]["id"], "o")

    def test_list_auditoria_filters_username_action_q(self):
        snaps = [
            FakeSnap(
                "1",
                {
                    "company_id": "x",
                    "username": "admin",
                    "action": "documento_subir",
                    "details": {"filename": "acta.pdf"},
                    "at": datetime(2025, 1, 2, tzinfo=timezone.utc),
                },
            ),
            FakeSnap(
                "2",
                {
                    "company_id": "x",
                    "username": "otro",
                    "action": "empleado_crear",
                    "details": {},
                    "at": datetime(2025, 1, 1, tzinfo=timezone.utc),
                },
            ),
        ]
        col = MagicMock()
        wq = MagicMock()
        wq.stream.return_value = snaps
        col.where.return_value = wq
        db = MagicMock()
        db.collection.return_value = col
        out_u = legajos_service.list_auditoria(db, "x", limit=10, username="adm")
        self.assertEqual(len(out_u), 1)
        self.assertEqual(out_u[0]["id"], "1")
        out_a = legajos_service.list_auditoria(db, "x", limit=10, action="empleado_crear")
        self.assertEqual(len(out_a), 1)
        self.assertEqual(out_a[0]["id"], "2")
        out_q = legajos_service.list_auditoria(db, "x", limit=10, q="acta")
        self.assertEqual(len(out_q), 1)
        self.assertEqual(out_q[0]["id"], "1")

    def test_list_auditoria_filters_by_date_range(self):
        t0 = datetime(2025, 1, 10, 12, 0, 0, tzinfo=timezone.utc)
        t1 = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        t2 = datetime(2025, 1, 20, 12, 0, 0, tzinfo=timezone.utc)
        snaps = [
            FakeSnap("a", {"company_id": "x", "username": "u", "action": "a", "details": {}, "at": t0}),
            FakeSnap("b", {"company_id": "x", "username": "u", "action": "b", "details": {}, "at": t1}),
            FakeSnap("c", {"company_id": "x", "username": "u", "action": "c", "details": {}, "at": t2}),
        ]
        col = MagicMock()
        wq = MagicMock()
        wq.stream.return_value = snaps
        col.where.return_value = wq
        db = MagicMock()
        db.collection.return_value = col
        frm = datetime(2025, 1, 12, 0, 0, 0, tzinfo=timezone.utc)
        to = datetime(2025, 1, 18, 23, 59, 59, tzinfo=timezone.utc)
        out = legajos_service.list_auditoria(db, "x", limit=10, at_from=frm, at_to=to)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["id"], "b")

    def test_build_auditoria_export_xlsx(self):
        evs = [
            {
                "id": "e1",
                "at": "2025-01-01T00:00:00+00:00",
                "username": "admin",
                "action": "documento_subir",
                "details": {"filename": "x.pdf"},
            }
        ]
        raw, err = legajos_service.build_auditoria_export_xlsx_bytes(evs)
        self.assertIsNone(err)
        self.assertIsNotNone(raw)
        self.assertGreater(len(raw or b""), 50)

    def test_list_empleados_search_matches_dni(self):
        snaps = [
            FakeSnap("a", {"company_id": "x", "legajo_numero": "1", "nombre_completo": "Ana", "dni": "28111222"}),
            FakeSnap("b", {"company_id": "x", "legajo_numero": "2", "nombre_completo": "Ben", "dni": "30999888"}),
        ]
        col = MagicMock()
        wq = MagicMock()
        wq.stream.return_value = snaps
        col.where.return_value = wq
        db = MagicMock()
        db.collection.return_value = col
        out = legajos_service.list_empleados(db, "x", search="2811")
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["id"], "a")

    def test_update_empleado_calls_firestore_update(self):
        snap_before = MagicMock()
        snap_before.exists = True
        snap_before.to_dict.return_value = {"company_id": "x", "legajo_numero": "10", "nombre_completo": "Viejo"}
        snap_after = FakeSnap(
            "e1",
            {
                "company_id": "x",
                "legajo_numero": "10",
                "nombre_completo": "Nuevo",
                "dni": "123",
                "email": "nuevo@ejemplo.com",
                "sucursal": "",
                "area": "",
                "notas": "",
            },
        )
        ref = MagicMock()
        ref.get.side_effect = [snap_before, snap_after]
        col = MagicMock()
        col.document.return_value = ref
        wq = MagicMock()
        wq.stream.return_value = []
        col.where.return_value = wq
        db = MagicMock()
        db.collection.return_value = col

        ok, row, msg = legajos_service.update_empleado(
            db,
            empleado_id="e1",
            legajo_numero="10",
            nombre_completo="Nuevo",
            updated_by="admin",
            email="nuevo@ejemplo.com",
        )
        self.assertTrue(ok)
        self.assertEqual((row or {}).get("nombre_completo"), "Nuevo")
        self.assertEqual((row or {}).get("email"), "nuevo@ejemplo.com")
        ref.update.assert_called_once()
        call_kw = ref.update.call_args[0][0]
        self.assertNotIn("dni", call_kw)
        self.assertEqual(call_kw.get("email"), "nuevo@ejemplo.com")

    def test_list_documentos_resumen_tipos(self):
        snaps = [
            FakeSnap("d1", {"company_id": "x", "empleado_id": "e1", "tipo_documento": "dni", "filename": "a.pdf"}),
            FakeSnap("d2", {"company_id": "x", "empleado_id": "e1", "tipo_documento": "dni", "filename": "b.pdf"}),
            FakeSnap("d3", {"company_id": "x", "empleado_id": "e2", "tipo_documento": "contrato", "filename": "c.pdf"}),
        ]
        col = MagicMock()
        wq = MagicMock()
        wq.stream.return_value = snaps
        col.where.return_value = wq
        db = MagicMock()
        db.collection.return_value = col
        out = legajos_service.list_documentos_resumen_tipos(db, "x")
        by_tipo = {r["tipo_documento"]: r["count"] for r in out}
        self.assertEqual(by_tipo.get("contrato"), 1)
        self.assertEqual(by_tipo.get("dni"), 2)

    def test_search_documentos_empresa_by_tipo_and_q(self):
        snaps = [
            FakeSnap("d1", {"company_id": "x", "empleado_id": "e1", "tipo_documento": "dni", "filename": "acta.pdf"}),
            FakeSnap("d2", {"company_id": "x", "empleado_id": "e1", "tipo_documento": "dni", "filename": "otro.pdf"}),
            FakeSnap("d3", {"company_id": "x", "empleado_id": "e1", "tipo_documento": "otro", "filename": "acta2.pdf"}),
        ]
        emp_snap = FakeSnap("e1", {"company_id": "x", "dni": "301", "nombre_completo": "Uno", "legajo_numero": "1"})

        docs_col = MagicMock()
        docs_wq = MagicMock()
        docs_wq.stream.return_value = snaps
        docs_col.where.return_value = docs_wq

        emp_ref = MagicMock()
        emp_ref.get.return_value = emp_snap
        emp_col = MagicMock()
        emp_col.document.return_value = emp_ref

        def collection_side(name):
            if name == legajos_service.LEGAJOS_DOCUMENTOS_COLLECTION:
                return docs_col
            if name == legajos_service.LEGAJOS_EMPLEADOS_COLLECTION:
                return emp_col
            return MagicMock()

        db = MagicMock()
        db.collection.side_effect = collection_side

        only_tipo = legajos_service.search_documentos_empresa(db, "x", "", limit=50, tipo_documento="dni")
        self.assertEqual(len(only_tipo), 2)
        both = legajos_service.search_documentos_empresa(db, "x", "acta", limit=50, tipo_documento="dni")
        self.assertEqual(len(both), 1)
        self.assertEqual(both[0].get("filename"), "acta.pdf")
        self.assertEqual(both[0].get("empleado_nombre"), "Uno")

    def test_search_documentos_por_nombre_colaborador(self):
        snaps = [
            FakeSnap(
                "d1",
                {"company_id": "x", "empleado_id": "e1", "tipo_documento": "dni", "filename": "scan001.pdf"},
            )
        ]
        emp_snap = FakeSnap(
            "e1",
            {
                "company_id": "x",
                "dni": "301",
                "nombre_completo": "Juan Pablo López",
                "legajo_numero": "",
                "email": "",
            },
        )
        docs_col = MagicMock()
        docs_wq = MagicMock()
        docs_wq.stream.return_value = snaps
        docs_col.where.return_value = docs_wq
        emp_ref = MagicMock()
        emp_ref.get.return_value = emp_snap
        emp_col = MagicMock()
        emp_col.document.return_value = emp_ref

        def collection_side(name):
            if name == legajos_service.LEGAJOS_DOCUMENTOS_COLLECTION:
                return docs_col
            if name == legajos_service.LEGAJOS_EMPLEADOS_COLLECTION:
                return emp_col
            return MagicMock()

        db = MagicMock()
        db.collection.side_effect = collection_side
        out = legajos_service.search_documentos_empresa(db, "x", "pablo", limit=50)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].get("filename"), "scan001.pdf")

    def test_search_documentos_solo_empleados_q(self):
        emp_snaps = [
            FakeSnap(
                "e1",
                {
                    "company_id": "x",
                    "nombre_completo": "Ana Torres",
                    "dni": "1",
                    "legajo_numero": "",
                    "email": "",
                },
            ),
            FakeSnap(
                "e2",
                {
                    "company_id": "x",
                    "nombre_completo": "Benito",
                    "dni": "2",
                    "legajo_numero": "",
                    "email": "",
                },
            ),
        ]
        doc_snaps = [
            FakeSnap("d1", {"company_id": "x", "empleado_id": "e1", "tipo_documento": "dni", "filename": "a.pdf"}),
            FakeSnap("d2", {"company_id": "x", "empleado_id": "e2", "tipo_documento": "dni", "filename": "b.pdf"}),
        ]
        emp_wq = MagicMock()
        emp_wq.stream.return_value = emp_snaps
        emp_col = MagicMock()
        emp_col.where.return_value = emp_wq

        def emp_document(eid):
            ref = MagicMock()
            for s in emp_snaps:
                if s.id == eid:
                    ref.get.return_value = s
                    return ref
            ref.get.return_value = FakeSnap(str(eid), {}, exists=False)
            return ref

        emp_col.document.side_effect = emp_document
        docs_col = MagicMock()
        docs_wq = MagicMock()
        docs_wq.stream.return_value = doc_snaps
        docs_col.where.return_value = docs_wq

        def collection_side(name):
            if name == legajos_service.LEGAJOS_DOCUMENTOS_COLLECTION:
                return docs_col
            if name == legajos_service.LEGAJOS_EMPLEADOS_COLLECTION:
                return emp_col
            return MagicMock()

        db = MagicMock()
        db.collection.side_effect = collection_side
        out = legajos_service.search_documentos_empresa(db, "x", "", limit=50, empleados_q="ana")
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].get("filename"), "a.pdf")

    def test_list_documentos_resumen_tipos_con_filtro_colaboradores(self):
        emp_snaps = [
            FakeSnap("e1", {"company_id": "x", "nombre_completo": "Ana López", "dni": "1", "legajo_numero": "", "email": ""}),
            FakeSnap("e2", {"company_id": "x", "nombre_completo": "Ben", "dni": "2", "legajo_numero": "", "email": ""}),
        ]
        doc_snaps = [
            FakeSnap("d1", {"company_id": "x", "empleado_id": "e1", "tipo_documento": "dni", "filename": "a.pdf"}),
            FakeSnap("d2", {"company_id": "x", "empleado_id": "e2", "tipo_documento": "contrato", "filename": "c.pdf"}),
        ]
        emp_wq = MagicMock()
        emp_wq.stream.return_value = emp_snaps
        emp_col = MagicMock()
        emp_col.where.return_value = emp_wq
        docs_col = MagicMock()
        docs_wq = MagicMock()
        docs_wq.stream.return_value = doc_snaps
        docs_col.where.return_value = docs_wq

        def collection_side(name):
            if name == legajos_service.LEGAJOS_DOCUMENTOS_COLLECTION:
                return docs_col
            if name == legajos_service.LEGAJOS_EMPLEADOS_COLLECTION:
                return emp_col
            return MagicMock()

        db = MagicMock()
        db.collection.side_effect = collection_side
        out = legajos_service.list_documentos_resumen_tipos(db, "x", empleados_search="ana")
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["tipo_documento"], "dni")
        self.assertEqual(out[0]["count"], 1)


if __name__ == "__main__":
    unittest.main()
