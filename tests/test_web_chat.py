import unittest

import web_chat


class WebChatApiTests(unittest.TestCase):
    def setUp(self):
        web_chat.flask_app.config["TESTING"] = True
        self.client = web_chat.flask_app.test_client()

    def test_menu_endpoint_response(self):
        response = self.client.post("/api/chat", json={"message": "menu"})
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertTrue(body["ok"])
        self.assertIn("Menú de temas disponibles", body["reply"])
        self.assertFalse(body["await_feedback"])
        self.assertIn("quick_actions", body)
        self.assertTrue(len(body["quick_actions"]) > 0)
        self.assertIn("value", body["quick_actions"][0])

    def test_feedback_flow_recibo_si(self):
        primera = self.client.post("/api/chat", json={"message": "recibo"})
        self.assertEqual(primera.status_code, 200)
        body_primera = primera.get_json()
        self.assertTrue(body_primera["ok"])
        self.assertTrue(body_primera["await_feedback"])
        self.assertIn("¿Esta información te fue de utilidad?", body_primera["reply"])
        self.assertTrue(
            any(action["value"] == "si" for action in body_primera["quick_actions"])
        )

        segunda = self.client.post("/api/chat", json={"message": "si"})
        self.assertEqual(segunda.status_code, 200)
        body_segunda = segunda.get_json()
        self.assertTrue(body_segunda["ok"])
        self.assertFalse(body_segunda["await_feedback"])
        self.assertIn("Gracias por tu feedback", body_segunda["reply"])
        self.assertTrue(len(body_segunda["quick_actions"]) > 0)

    def test_pregunta_en_feedback_se_toma_como_consulta(self):
        self.client.post("/api/chat", json={"message": "vacaciones"})
        response = self.client.post(
            "/api/chat", json={"message": "y las puedo fraccionar?"}
        )
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertTrue(body["ok"])
        self.assertIn("fraccionar", body["reply"].lower())

    def test_stats_endpoint_structure(self):
        response = self.client.get("/api/stats")
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertTrue(body["ok"])
        self.assertIn("kpis", body)
        self.assertIn("series_7_dias", body)
        self.assertIn("detail", body)
        self.assertIn("feedback_reciente", body["detail"])

    def test_reset_endpoint_includes_quick_actions(self):
        response = self.client.post("/api/reset")
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertTrue(body["ok"])
        self.assertIn("quick_actions", body)
        self.assertTrue(len(body["quick_actions"]) > 0)


if __name__ == "__main__":
    unittest.main()
