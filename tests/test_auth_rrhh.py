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
                self.assertIn("permiso", error.lower())

    def test_create_custom_role_and_assign_user(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            users_path = os.path.join(tmpdir, "rrhh_users.json")
            roles_path = os.path.join(tmpdir, "rrhh_roles.json")
            with patch.dict(
                os.environ,
                {
                    "RRHH_USERS_FILE": users_path,
                    "RRHH_ROLES_FILE": roles_path,
                },
                clear=True,
            ):
                ok_role, role, err_role = auth_rrhh.create_role(
                    name="auditor",
                    display_name="Auditor RRHH",
                    permissions=[auth_rrhh.PERM_HISTORY_VIEW],
                )
                self.assertTrue(ok_role)
                self.assertEqual(err_role, "")
                self.assertEqual(role["name"], "auditor")

                ok_user, user, err_user = auth_rrhh.create_user(
                    "auditor1",
                    "auditor123",
                    display_name="Usuario Auditor",
                    role="auditor",
                )
                self.assertTrue(ok_user)
                self.assertEqual(err_user, "")
                self.assertEqual(user["role"], "auditor")
                self.assertEqual(user["permissions"], [auth_rrhh.PERM_HISTORY_VIEW])

    def test_update_role_permissions_success(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            roles_path = os.path.join(tmpdir, "rrhh_roles.json")
            with patch.dict(
                os.environ,
                {
                    "RRHH_ROLES_FILE": roles_path,
                    "RRHH_USERS_FILE": os.path.join(tmpdir, "rrhh_users.json"),
                    "RRHH_ADMIN_USER": "root",
                    "RRHH_ADMIN_PASSWORD": "root123",
                },
                clear=True,
            ):
                ok, role, _ = auth_rrhh.update_role(
                    name="rrhh",
                    display_name="RRHH Operaciones",
                    permissions=[
                        auth_rrhh.PERM_CONVERSATIONS_VIEW,
                        auth_rrhh.PERM_HISTORY_VIEW,
                    ],
                )
                self.assertTrue(ok)
                self.assertEqual(role["display_name"], "RRHH Operaciones")
                self.assertIn(auth_rrhh.PERM_HISTORY_VIEW, role["permissions"])

    def test_update_user_assignments_restricts_company_access(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            users_path = os.path.join(tmpdir, "rrhh_users.json")
            with patch.dict(
                os.environ,
                {
                    "RRHH_USERS_FILE": users_path,
                },
                clear=True,
            ):
                auth_rrhh.create_user("laura", "secreta123", role="rrhh")
                ok, user, error = auth_rrhh.update_user_assignments(
                    username="laura",
                    assignments=[{"company_id": "acme", "branch": "Centro"}],
                )
                self.assertTrue(ok)
                self.assertEqual(error, "")
                self.assertEqual(user["assignments"][0]["company_id"], "acme")
                self.assertTrue(auth_rrhh.user_has_company_access("laura", "acme"))
                self.assertFalse(auth_rrhh.user_has_company_access("laura", "bacar"))

    def test_create_password_reset_token_for_identity(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            users_path = os.path.join(tmpdir, "rrhh_users.json")
            with patch.dict(
                os.environ,
                {
                    "RRHH_USERS_FILE": users_path,
                },
                clear=True,
            ):
                ok_create, _, _ = auth_rrhh.create_user(
                    "laura",
                    "secreta123",
                    role="rrhh",
                    email="laura@empresa.com",
                )
                self.assertTrue(ok_create)

                ok_reset, payload, error = auth_rrhh.create_password_reset_token_for_identity(
                    username="laura",
                    email="laura@empresa.com",
                )
                self.assertTrue(ok_reset)
                self.assertEqual(error, "")
                self.assertEqual(payload["email"], "laura@empresa.com")
                self.assertTrue(len(payload["token"]) > 20)

                bad_ok, _, bad_error = auth_rrhh.create_password_reset_token_for_identity(
                    username="laura",
                    email="otro@empresa.com",
                )
                self.assertFalse(bad_ok)
                self.assertIn("inválido", bad_error.lower())

    def test_delete_role_blocked_when_assigned_to_user(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            users_path = os.path.join(tmpdir, "rrhh_users.json")
            roles_path = os.path.join(tmpdir, "rrhh_roles.json")
            with patch.dict(
                os.environ,
                {
                    "RRHH_USERS_FILE": users_path,
                    "RRHH_ROLES_FILE": roles_path,
                },
                clear=True,
            ):
                auth_rrhh.create_role(
                    name="auditor",
                    display_name="Auditor",
                    permissions=[auth_rrhh.PERM_HISTORY_VIEW],
                )
                auth_rrhh.create_user("aud1", "auditor123", role="auditor")
                ok, error = auth_rrhh.delete_role("auditor")
                self.assertFalse(ok)
                self.assertIn("asignado", error.lower())


if __name__ == "__main__":
    unittest.main()
