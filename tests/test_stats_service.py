import unittest
from datetime import datetime, timedelta

import stats_service


class StatsServiceTests(unittest.TestCase):
    def test_build_statistics_from_records(self):
        now = datetime(2026, 2, 12, 12, 0, 0)
        feedback = [
            {"tema": "vacaciones", "fue_util": "si", "fecha": now - timedelta(days=1)},
            {"tema": "vacaciones", "fue_util": "no", "fecha": now - timedelta(days=1)},
            {"tema": "recibo", "fue_util": "si", "fecha": now - timedelta(days=3)},
        ]
        pendientes = [
            {"sentimiento": "neutral", "fecha": now - timedelta(days=1)},
            {"sentimiento": "negativo/enojado", "fecha": now - timedelta(days=2)},
            {"sentimiento": "neutral", "fecha": now - timedelta(days=2)},
        ]

        result = stats_service.build_statistics_from_records(
            feedback_records=feedback,
            pendientes_records=pendientes,
            now=now,
            days=7,
        )

        self.assertTrue(result["available"])
        self.assertEqual(result["kpis"]["total_feedback"], 3)
        self.assertEqual(result["kpis"]["votos_si"], 2)
        self.assertEqual(result["kpis"]["votos_no"], 1)
        self.assertEqual(result["kpis"]["total_pendientes"], 3)
        self.assertAlmostEqual(result["kpis"]["utilidad_pct"], 66.67, places=2)
        self.assertEqual(result["top_temas"][0]["tema"], "vacaciones")
        self.assertEqual(result["top_temas"][0]["cantidad"], 2)
        self.assertEqual(result["pendientes_por_sentimiento"][0]["sentimiento"], "neutral")
        self.assertEqual(result["series_7_dias"]["labels"][-1], "2026-02-12")
        self.assertEqual(len(result["series_7_dias"]["feedback"]), 7)
        self.assertEqual(len(result["series_7_dias"]["pendientes"]), 7)
        self.assertIn("detail", result)
        self.assertIn("feedback_reciente", result["detail"])
        self.assertIn("pendientes_recientes", result["detail"])
        self.assertIn("ranking_temas", result["detail"])
        self.assertIn("desglose_diario", result["detail"])
        self.assertTrue(len(result["detail"]["feedback_reciente"]) > 0)
        self.assertEqual(len(result["detail"]["desglose_diario"]), 7)

    def test_obtener_estadisticas_sin_db(self):
        result = stats_service.obtener_estadisticas(None, now=datetime(2026, 2, 12), days=7)
        self.assertFalse(result["available"])
        self.assertEqual(result["kpis"]["total_feedback"], 0)
        self.assertEqual(result["kpis"]["total_pendientes"], 0)
        self.assertEqual(len(result["series_7_dias"]["labels"]), 7)
        self.assertIn("detail", result)
        self.assertEqual(result["detail"]["feedback_reciente"], [])


if __name__ == "__main__":
    unittest.main()
