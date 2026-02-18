import os
import unittest
from unittest.mock import Mock, patch

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

    def test_inicializar_firestore_usa_adc_si_no_hay_archivo_local(self):
        fake_admin = Mock()
        fake_admin._apps = []
        fake_firestore = Mock()
        fake_firestore.client.return_value = "db-adc"

        with (
            patch.object(firebase_config, "firebase_admin", fake_admin),
            patch.object(firebase_config, "credentials", Mock()),
            patch.object(firebase_config, "firestore", fake_firestore),
            patch.dict(os.environ, {}, clear=True),
            patch("os.path.exists", return_value=False),
        ):
            db = firebase_config.inicializar_firestore(verbose=False)

        self.assertEqual(db, "db-adc")
        fake_admin.initialize_app.assert_called_once_with()
        fake_firestore.client.assert_called_once()

    def test_inicializar_firestore_prioriza_archivo_si_existe(self):
        fake_admin = Mock()
        fake_admin._apps = []
        fake_credentials = Mock()
        fake_credentials.Certificate.return_value = "cred-obj"
        fake_firestore = Mock()
        fake_firestore.client.return_value = "db-file"

        with (
            patch.object(firebase_config, "firebase_admin", fake_admin),
            patch.object(firebase_config, "credentials", fake_credentials),
            patch.object(firebase_config, "firestore", fake_firestore),
            patch.dict(os.environ, {}, clear=True),
            patch("os.path.exists", return_value=True),
        ):
            db = firebase_config.inicializar_firestore(credentials_path="mi-clave.json", verbose=False)

        self.assertEqual(db, "db-file")
        fake_credentials.Certificate.assert_called_once_with("mi-clave.json")
        fake_admin.initialize_app.assert_called_once_with("cred-obj")
        fake_firestore.client.assert_called_once()

    def test_inicializar_firestore_si_falla_archivo_hace_fallback_adc(self):
        fake_admin = Mock()
        fake_admin._apps = []
        fake_credentials = Mock()
        fake_credentials.Certificate.side_effect = RuntimeError("credencial inválida")
        fake_firestore = Mock()
        fake_firestore.client.return_value = "db-fallback"

        with (
            patch.object(firebase_config, "firebase_admin", fake_admin),
            patch.object(firebase_config, "credentials", fake_credentials),
            patch.object(firebase_config, "firestore", fake_firestore),
            patch.dict(os.environ, {"FIREBASE_CREDENTIALS": "/tmp/cred.json"}, clear=True),
            patch("os.path.exists", return_value=True),
        ):
            db = firebase_config.inicializar_firestore(verbose=False)

        self.assertEqual(db, "db-fallback")
        fake_credentials.Certificate.assert_called_once_with("/tmp/cred.json")
        fake_admin.initialize_app.assert_called_once_with()
        fake_firestore.client.assert_called_once()


if __name__ == "__main__":
    unittest.main()
