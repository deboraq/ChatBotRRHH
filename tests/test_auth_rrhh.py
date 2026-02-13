import json
import os
import tempfile
import unittest
from unittest.mock import patch

from werkzeug.security import generate_password_hash

import auth_rrhh


class AuthRrhhTests(unittest.TestCase):
    def test_is_auth_disabled_by_default_without_users(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(auth_rrhh.is_auth_enabled())

    def test_authenticate_admin_user_from_env(self):
        with patch.dict(
            os.environ,
            {
                "RRHH_AUTH_ENABLED": "true",
                "RRHH_ADMIN_USER": "laura",
                "RRHH_ADMIN_PASSWORD": "secreta123",
                "RRHH_ADMIN_DISPLAY_NAME": "Laura RRHH",
            },
            clear=True,
        ):
            self.assertTrue(auth_rrhh.is_auth_enabled())
            ok, user, error = auth_rrhh.authenticate("laura", "secreta123")
            self.assertTrue(ok)
            self.assertEqual(error, "")
            self.assertEqual(user["display_name"], "Laura RRHH")

    def test_authenticate_users_file_with_password_hash(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            users_path = os.path.join(tmpdir, "rrhh_users.json")
            payload = {
                "users": [
                    {
                        "username": "analista",
                        "display_name": "Analista",
                        "password_hash": generate_password_hash("clave-segura"),
                    }
                ]
            }
            with open(users_path, "w", encoding="utf-8") as fh:
                json.dump(payload, fh)

            with patch.dict(
                os.environ,
                {
                    "RRHH_USERS_FILE": users_path,
                },
                clear=True,
            ):
                self.assertTrue(auth_rrhh.is_auth_enabled())
                ok, user, _ = auth_rrhh.authenticate("analista", "clave-segura")
                self.assertTrue(ok)
                self.assertEqual(user["username"], "analista")


if __name__ == "__main__":
    unittest.main()
