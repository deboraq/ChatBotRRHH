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


if __name__ == "__main__":
    unittest.main()
