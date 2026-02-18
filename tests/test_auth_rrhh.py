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

    def test_create_user_creates_and_authenticates(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            users_path = os.path.join(tmpdir, "rrhh_users.json")
            with patch.dict(
                os.environ,
                {
                    "RRHH_USERS_FILE": users_path,
                },
                clear=True,
            ):
                created, user, error = auth_rrhh.create_user(
                    username="nuevo.rrhh",
                    password="secreta123",
                    display_name="Nuevo RRHH",
                    role="rrhh",
                    created_by="admin",
                )
                self.assertTrue(created)
                self.assertEqual(error, "")
                self.assertEqual(user["username"], "nuevo.rrhh")

                users = auth_rrhh.list_file_users()
                self.assertEqual(len(users), 1)
                self.assertEqual(users[0]["display_name"], "Nuevo RRHH")

                ok, payload, _ = auth_rrhh.authenticate("nuevo.rrhh", "secreta123")
                self.assertTrue(ok)
                self.assertEqual(payload["role"], "rrhh")

    def test_create_user_rejects_duplicates(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            users_path = os.path.join(tmpdir, "rrhh_users.json")
            with patch.dict(
                os.environ,
                {
                    "RRHH_USERS_FILE": users_path,
                },
                clear=True,
            ):
                ok1, _, _ = auth_rrhh.create_user("laura", "secreta123")
                ok2, _, err2 = auth_rrhh.create_user("laura", "otra-clave")
                self.assertTrue(ok1)
                self.assertFalse(ok2)
                self.assertIn("existe", err2.lower())

    def test_update_user_role_success(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            users_path = os.path.join(tmpdir, "rrhh_users.json")
            with patch.dict(
                os.environ,
                {
                    "RRHH_USERS_FILE": users_path,
                },
                clear=True,
            ):
                auth_rrhh.create_user("admin", "admin123", role="admin")
                auth_rrhh.create_user("laura", "secreta123", role="rrhh")

                ok, user, error = auth_rrhh.update_user_role(
                    username="laura",
                    role="admin",
                    updated_by="admin",
                )
                self.assertTrue(ok)
                self.assertEqual(error, "")
                self.assertEqual(user["role"], "admin")

    def test_update_user_role_blocks_demoting_last_admin(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            users_path = os.path.join(tmpdir, "rrhh_users.json")
            with patch.dict(
                os.environ,
                {
                    "RRHH_USERS_FILE": users_path,
                },
                clear=True,
            ):
                auth_rrhh.create_user("admin", "admin123", role="admin")
                ok, _, error = auth_rrhh.update_user_role(username="admin", role="rrhh")
                self.assertFalse(ok)
                self.assertIn("al menos un usuario admin", error.lower())


if __name__ == "__main__":
    unittest.main()
