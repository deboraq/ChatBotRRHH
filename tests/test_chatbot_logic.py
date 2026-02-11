import unittest

import app


class ChatbotLogicTests(unittest.TestCase):
    def setUp(self):
        self.temas_map = {
            "1": "vacaciones",
            "2": "ART",
            "3": "recibo",
            "4": "aguinaldo",
            "5": "fraccionamiento",
        }

    def test_normalizar_texto_remueve_acentos_y_puntuacion(self):
        texto = "¡Quiero mi recibó, por favor!"
        self.assertEqual(app.normalizar_texto(texto), "quiero mi recibo por favor")

    def test_detecta_art_por_sinonimo_aun_con_casing_distinto(self):
        respuesta, tema = app.obtener_respuesta("me lastimé trabajando", self.temas_map)
        self.assertEqual(tema, "ART")
        self.assertIn("accidente laboral", respuesta.lower())

    def test_saludo_con_consulta_devuelve_contexto(self):
        respuesta, tema = app.obtener_respuesta("hola, necesito mi recibo", self.temas_map)
        self.assertEqual(tema, "recibo")
        self.assertTrue(respuesta.startswith("👋 ¡Hola!"))

    def test_contacto_con_rrhh_por_intencion(self):
        respuesta, tema = app.obtener_respuesta(
            "quiero hablar con una persona de RRHH", self.temas_map
        )
        self.assertEqual(tema, "RRHH")
        self.assertIn("interno 104", respuesta.lower())

    def test_sugiere_temas_cuando_hay_error_ortografico(self):
        sugerencias = app.sugerir_temas("vacasiones", self.temas_map)
        self.assertIn("vacaciones", sugerencias)

    def test_detecta_fraccionamiento_por_pregunta_corta(self):
        respuesta, tema = app.obtener_respuesta("y las puedo fraccionar?", self.temas_map)
        self.assertEqual(tema, "fraccionamiento")
        self.assertIn("fraccionar", respuesta.lower())

    def test_responde_cuantos_dias_corresponden_de_vacaciones(self):
        respuesta, tema = app.obtener_respuesta(
            "quiero saber cuánto me corresponde de vacaciones", self.temas_map
        )
        self.assertEqual(tema, "vacaciones")
        self.assertIn("14 días corridos", respuesta.lower())

    def test_feedback_con_pregunta_se_trata_como_consulta(self):
        tipo, texto_norm = app.clasificar_input_feedback("y las puedo fraccionar?")
        self.assertEqual(tipo, "consulta")
        self.assertEqual(texto_norm, "y las puedo fraccionar")

    def test_consulta_desconocida_retorna_none(self):
        respuesta, tema = app.obtener_respuesta("beneficios gym", self.temas_map)
        self.assertIsNone(respuesta)
        self.assertIsNone(tema)


if __name__ == "__main__":
    unittest.main()
