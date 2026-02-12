import os
import unittest
from unittest.mock import patch

import firebase_config


class FirebaseConfigTests(unittest.TestCase):
    def test_obtener_ruta_credenciales_default(self):
        with patch.dict(os.environ, {}, clear=True):
            ruta = firebase_config.obtener_ruta_credenciales()
            self.assertEqual(ruta, "claves.json")

    def test_obtener_ruta_credenciales_desde_env(self):
        with patch.dict(os.environ, {"FIREBASE_CREDENTIALS": "claves-bacar.json"}):
            ruta = firebase_config.obtener_ruta_credenciales()
            self.assertEqual(ruta, "claves-bacar.json")

    def test_inicializar_firestore_sin_firebase_admin(self):
        with patch.object(firebase_config, "firebase_admin", None):
            db = firebase_config.inicializar_firestore(verbose=False)
            self.assertIsNone(db)


if __name__ == "__main__":
    unittest.main()
