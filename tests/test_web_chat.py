import json
import os
import tempfile
import unittest
from unittest.mock import patch

import web_chat


class WebChatApiTests(unittest.TestCase):
    def setUp(self):
        web_chat.flask_app.config["TESTING"] = True
        self.client = web_chat.flask_app.test_client()
        web_chat.reset_in_memory_handoffs()

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
        self.assertIn("feedback", body_segunda["reply"].lower())
        self.assertTrue(len(body_segunda["quick_actions"]) > 0)

    def test_feedback_flow_recibo_no_no_cierra_chat(self):
        primera = self.client.post("/api/chat", json={"message": "recibo"})
        self.assertEqual(primera.status_code, 200)
        body_primera = primera.get_json()
        self.assertTrue(body_primera["await_feedback"])

        segunda = self.client.post("/api/chat", json={"message": "no"})
        self.assertEqual(segunda.status_code, 200)
        body_segunda = segunda.get_json()
        self.assertTrue(body_segunda["ok"])
        self.assertFalse(body_segunda["end_session"])
        self.assertIn("feedback", body_segunda["reply"].lower())

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
        self.assertIn("feedback_no_util", body["detail"])
        self.assertIn("no_util_total", body["kpis"])
        self.assertIn("rrhh_abiertas", body["kpis"])
        self.assertIn("rrhh_en_atencion", body["kpis"])
        self.assertIn("rrhh_conversaciones", body["detail"])
        self.assertIn("source_project", body)
        self.assertIn("server_boot_at", body)

    def test_reset_endpoint_includes_quick_actions(self):
        response = self.client.post("/api/reset")
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertTrue(body["ok"])
        self.assertIn("quick_actions", body)
        self.assertTrue(len(body["quick_actions"]) > 0)

    def test_historial_endpoint_registers_colaborador_y_bot(self):
        self.client.post("/api/chat", json={"message": "menu"})
        historial_resp = self.client.get("/api/historial?limit=50")
        self.assertEqual(historial_resp.status_code, 200)
        historial_body = historial_resp.get_json()
        self.assertTrue(historial_body["ok"])
        self.assertGreaterEqual(historial_body["total"], 2)
        remitentes = {item["remitente"] for item in historial_body["items"]}
        self.assertIn("colaborador", remitentes)
        self.assertIn("bot", remitentes)

    def test_historial_endpoint_filter_by_remitente(self):
        self.client.post("/api/chat", json={"message": "menu"})
        only_bot_resp = self.client.get("/api/historial?remitente=bot&limit=20")
        self.assertEqual(only_bot_resp.status_code, 200)
        body = only_bot_resp.get_json()
        self.assertTrue(body["ok"])
        self.assertTrue(all(item["remitente"] == "bot" for item in body["items"]))

    def test_rrhh_handoff_flow(self):
        inicio = self.client.post("/api/chat", json={"message": "quiero hablar con rrhh"})
        self.assertEqual(inicio.status_code, 200)
        body_inicio = inicio.get_json()
        self.assertTrue(body_inicio["ok"])
        self.assertTrue(body_inicio["handoff_active"])

        convs_resp = self.client.get("/api/rrhh/conversaciones")
        self.assertEqual(convs_resp.status_code, 200)
        convs_body = convs_resp.get_json()
        self.assertTrue(convs_body["ok"])
        self.assertTrue(len(convs_body["conversaciones"]) > 0)
        conv_id = convs_body["conversaciones"][0]["conversation_id"]

        tomar_resp = self.client.post(
            f"/api/rrhh/conversaciones/{conv_id}/tomar",
            json={"agente": "Laura"},
        )
        self.assertEqual(tomar_resp.status_code, 200)
        self.assertTrue(tomar_resp.get_json()["ok"])

        msg_resp = self.client.post(
            f"/api/rrhh/conversaciones/{conv_id}/mensajes",
            json={"agente": "Laura", "mensaje": "Hola, te atiende RRHH."},
        )
        self.assertEqual(msg_resp.status_code, 200)
        self.assertTrue(msg_resp.get_json()["ok"])

        poll_resp = self.client.get("/api/chat/poll")
        self.assertEqual(poll_resp.status_code, 200)
        poll_body = poll_resp.get_json()
        self.assertTrue(poll_body["ok"])
        self.assertTrue(poll_body["handoff_active"])
        self.assertTrue(len(poll_body["messages"]) > 0)
        self.assertTrue(any(m["remitente"] in {"rrhh", "sistema"} for m in poll_body["messages"]))

        # Segunda lectura no debe repetir mensajes ya vistos.
        poll_resp_2 = self.client.get("/api/chat/poll")
        self.assertEqual(poll_resp_2.status_code, 200)
        poll_body_2 = poll_resp_2.get_json()
        self.assertTrue(poll_body_2["ok"])
        self.assertEqual(len(poll_body_2["messages"]), 0)

        historial_resp = self.client.get("/api/historial?canal=rrhh&limit=50")
        self.assertEqual(historial_resp.status_code, 200)
        historial_body = historial_resp.get_json()
        self.assertTrue(historial_body["ok"])
        self.assertTrue(any(item["remitente"] == "rrhh" for item in historial_body["items"]))

    def test_stats_reflects_rrhh_handoffs(self):
        self.client.post("/api/chat", json={"message": "quiero hablar con rrhh"})
        stats_resp = self.client.get("/api/stats")
        self.assertEqual(stats_resp.status_code, 200)
        stats_body = stats_resp.get_json()
        self.assertTrue(stats_body["ok"])
        self.assertGreaterEqual(stats_body["kpis"]["rrhh_total"], 1)
        self.assertGreaterEqual(stats_body["kpis"]["rrhh_abiertas"], 1)

    def test_rrhh_endpoints_require_login_when_auth_enabled(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            users_path = os.path.join(tmpdir, "rrhh_users.json")
            with open(users_path, "w", encoding="utf-8") as fh:
                json.dump(
                    {
                        "users": [
                            {
                                "username": "laura",
                                "display_name": "Laura",
                                "password": "secreta123",
                            }
                        ]
                    },
                    fh,
                )

            with patch.dict(
                os.environ,
                {"RRHH_AUTH_ENABLED": "true", "RRHH_USERS_FILE": users_path},
                clear=True,
            ):
                api_resp = self.client.get("/api/rrhh/conversaciones")
                self.assertEqual(api_resp.status_code, 401)
                self.assertFalse(api_resp.get_json()["ok"])

                page_resp = self.client.get("/rrhh")
                self.assertEqual(page_resp.status_code, 302)
                self.assertIn("/login", page_resp.headers.get("Location", ""))

    def test_login_allows_rrhh_access_when_auth_enabled(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            users_path = os.path.join(tmpdir, "rrhh_users.json")
            with open(users_path, "w", encoding="utf-8") as fh:
                json.dump(
                    {
                        "users": [
                            {
                                "username": "laura",
                                "display_name": "Laura",
                                "password": "secreta123",
                            }
                        ]
                    },
                    fh,
                )

            with patch.dict(
                os.environ,
                {"RRHH_AUTH_ENABLED": "true", "RRHH_USERS_FILE": users_path},
                clear=True,
            ):
                login_resp = self.client.post(
                    "/login",
                    data={"username": "laura", "password": "secreta123", "next": "/rrhh"},
                )
                self.assertEqual(login_resp.status_code, 302)

                api_resp = self.client.get("/api/rrhh/conversaciones")
                self.assertEqual(api_resp.status_code, 200)
                body = api_resp.get_json()
                self.assertTrue(body["ok"])
                self.assertEqual(body["agente_actual"], "Laura")

    def test_admin_can_create_rrhh_users_via_api(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            users_path = os.path.join(tmpdir, "rrhh_users.json")
            with open(users_path, "w", encoding="utf-8") as fh:
                json.dump(
                    {
                        "users": [
                            {
                                "username": "admin",
                                "display_name": "Administrador",
                                "password": "admin123",
                                "role": "admin",
                            }
                        ]
                    },
                    fh,
                )

            with patch.dict(
                os.environ,
                {"RRHH_AUTH_ENABLED": "true", "RRHH_USERS_FILE": users_path},
                clear=True,
            ):
                login_resp = self.client.post(
                    "/login",
                    data={"username": "admin", "password": "admin123", "next": "/rrhh"},
                )
                self.assertEqual(login_resp.status_code, 302)

                create_resp = self.client.post(
                    "/api/rrhh/usuarios",
                    json={
                        "username": "analista.rrhh",
                        "display_name": "Analista RRHH",
                        "password": "clave123",
                        "role": "rrhh",
                    },
                )
                self.assertEqual(create_resp.status_code, 200)
                create_body = create_resp.get_json()
                self.assertTrue(create_body["ok"])
                self.assertEqual(create_body["user"]["username"], "analista.rrhh")

                list_resp = self.client.get("/api/rrhh/usuarios")
                self.assertEqual(list_resp.status_code, 200)
                list_body = list_resp.get_json()
                self.assertTrue(list_body["ok"])
                usernames = {item["username"] for item in list_body["users"]}
                self.assertIn("admin", usernames)
                self.assertIn("analista.rrhh", usernames)

    def test_non_admin_cannot_create_rrhh_users(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            users_path = os.path.join(tmpdir, "rrhh_users.json")
            with open(users_path, "w", encoding="utf-8") as fh:
                json.dump(
                    {
                        "users": [
                            {
                                "username": "laura",
                                "display_name": "Laura",
                                "password": "secreta123",
                                "role": "rrhh",
                            }
                        ]
                    },
                    fh,
                )

            with patch.dict(
                os.environ,
                {"RRHH_AUTH_ENABLED": "true", "RRHH_USERS_FILE": users_path},
                clear=True,
            ):
                login_resp = self.client.post(
                    "/login",
                    data={"username": "laura", "password": "secreta123", "next": "/rrhh"},
                )
                self.assertEqual(login_resp.status_code, 302)

                create_resp = self.client.post(
                    "/api/rrhh/usuarios",
                    json={
                        "username": "nuevo",
                        "display_name": "Nuevo",
                        "password": "clave123",
                        "role": "rrhh",
                    },
                )
                self.assertEqual(create_resp.status_code, 403)
                body = create_resp.get_json()
                self.assertFalse(body["ok"])

    def test_admin_can_update_user_role_via_api(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            users_path = os.path.join(tmpdir, "rrhh_users.json")
            with open(users_path, "w", encoding="utf-8") as fh:
                json.dump(
                    {
                        "users": [
                            {
                                "username": "admin",
                                "display_name": "Administrador",
                                "password": "admin123",
                                "role": "admin",
                            },
                            {
                                "username": "laura",
                                "display_name": "Laura",
                                "password": "laura123",
                                "role": "rrhh",
                            },
                        ]
                    },
                    fh,
                )

            with patch.dict(
                os.environ,
                {"RRHH_AUTH_ENABLED": "true", "RRHH_USERS_FILE": users_path},
                clear=True,
            ):
                login_resp = self.client.post(
                    "/login",
                    data={"username": "admin", "password": "admin123", "next": "/rrhh"},
                )
                self.assertEqual(login_resp.status_code, 302)

                update_resp = self.client.post(
                    "/api/rrhh/usuarios/laura/rol",
                    json={"role": "admin"},
                )
                self.assertEqual(update_resp.status_code, 200)
                body = update_resp.get_json()
                self.assertTrue(body["ok"])
                self.assertEqual(body["user"]["role"], "admin")

                list_resp = self.client.get("/api/rrhh/usuarios")
                self.assertEqual(list_resp.status_code, 200)
                listed = {item["username"]: item["role"] for item in list_resp.get_json()["users"]}
                self.assertEqual(listed.get("laura"), "admin")

    def test_non_admin_cannot_update_user_role(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            users_path = os.path.join(tmpdir, "rrhh_users.json")
            with open(users_path, "w", encoding="utf-8") as fh:
                json.dump(
                    {
                        "users": [
                            {
                                "username": "admin",
                                "display_name": "Administrador",
                                "password": "admin123",
                                "role": "admin",
                            },
                            {
                                "username": "laura",
                                "display_name": "Laura",
                                "password": "laura123",
                                "role": "rrhh",
                            },
                        ]
                    },
                    fh,
                )

            with patch.dict(
                os.environ,
                {"RRHH_AUTH_ENABLED": "true", "RRHH_USERS_FILE": users_path},
                clear=True,
            ):
                login_resp = self.client.post(
                    "/login",
                    data={"username": "laura", "password": "laura123", "next": "/rrhh"},
                )
                self.assertEqual(login_resp.status_code, 302)

                update_resp = self.client.post(
                    "/api/rrhh/usuarios/admin/rol",
                    json={"role": "rrhh"},
                )
                self.assertEqual(update_resp.status_code, 403)
                body = update_resp.get_json()
                self.assertFalse(body["ok"])

    def test_cannot_demote_last_admin_via_api(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            users_path = os.path.join(tmpdir, "rrhh_users.json")
            with open(users_path, "w", encoding="utf-8") as fh:
                json.dump(
                    {
                        "users": [
                            {
                                "username": "admin",
                                "display_name": "Administrador",
                                "password": "admin123",
                                "role": "admin",
                            }
                        ]
                    },
                    fh,
                )

            with patch.dict(
                os.environ,
                {"RRHH_AUTH_ENABLED": "true", "RRHH_USERS_FILE": users_path},
                clear=True,
            ):
                login_resp = self.client.post(
                    "/login",
                    data={"username": "admin", "password": "admin123", "next": "/rrhh"},
                )
                self.assertEqual(login_resp.status_code, 302)

                update_resp = self.client.post(
                    "/api/rrhh/usuarios/admin/rol",
                    json={"role": "rrhh"},
                )
                self.assertEqual(update_resp.status_code, 409)
                body = update_resp.get_json()
                self.assertFalse(body["ok"])

    def test_admin_can_create_custom_role_via_api(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            users_path = os.path.join(tmpdir, "rrhh_users.json")
            roles_path = os.path.join(tmpdir, "rrhh_roles.json")
            with open(users_path, "w", encoding="utf-8") as fh:
                json.dump(
                    {
                        "users": [
                            {
                                "username": "admin",
                                "display_name": "Administrador",
                                "password": "admin123",
                                "role": "admin",
                            }
                        ]
                    },
                    fh,
                )

            with patch.dict(
                os.environ,
                {
                    "RRHH_AUTH_ENABLED": "true",
                    "RRHH_USERS_FILE": users_path,
                    "RRHH_ROLES_FILE": roles_path,
                },
                clear=True,
            ):
                self.client.post(
                    "/login",
                    data={"username": "admin", "password": "admin123", "next": "/rrhh"},
                )

                create_role_resp = self.client.post(
                    "/api/rrhh/roles",
                    json={
                        "name": "auditor",
                        "display_name": "Auditor",
                        "permissions": ["historial_ver"],
                    },
                )
                self.assertEqual(create_role_resp.status_code, 200)
                body = create_role_resp.get_json()
                self.assertTrue(body["ok"])
                self.assertEqual(body["role"]["name"], "auditor")

                roles_resp = self.client.get("/api/rrhh/roles")
                self.assertEqual(roles_resp.status_code, 200)
                roles_body = roles_resp.get_json()
                role_names = {item["name"] for item in roles_body["roles"]}
                self.assertIn("auditor", role_names)

    def test_custom_role_permissions_limit_access(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            users_path = os.path.join(tmpdir, "rrhh_users.json")
            roles_path = os.path.join(tmpdir, "rrhh_roles.json")
            with open(users_path, "w", encoding="utf-8") as fh:
                json.dump(
                    {
                        "users": [
                            {
                                "username": "admin",
                                "display_name": "Administrador",
                                "password": "admin123",
                                "role": "admin",
                            },
                            {
                                "username": "auditor1",
                                "display_name": "Auditor",
                                "password": "auditor123",
                                "role": "auditor",
                            },
                        ]
                    },
                    fh,
                )
            with open(roles_path, "w", encoding="utf-8") as fh:
                json.dump(
                    {
                        "roles": [
                            {
                                "name": "auditor",
                                "display_name": "Auditor",
                                "permissions": ["historial_ver"],
                            }
                        ]
                    },
                    fh,
                )

            with patch.dict(
                os.environ,
                {
                    "RRHH_AUTH_ENABLED": "true",
                    "RRHH_USERS_FILE": users_path,
                    "RRHH_ROLES_FILE": roles_path,
                },
                clear=True,
            ):
                self.client.post(
                    "/login",
                    data={"username": "auditor1", "password": "auditor123", "next": "/historial"},
                )

                historial_resp = self.client.get("/api/historial?limit=5")
                self.assertEqual(historial_resp.status_code, 200)

                convs_resp = self.client.get("/api/rrhh/conversaciones")
                self.assertEqual(convs_resp.status_code, 403)
                self.assertFalse(convs_resp.get_json()["ok"])

                users_resp = self.client.get("/api/rrhh/usuarios")
                self.assertEqual(users_resp.status_code, 403)
                self.assertFalse(users_resp.get_json()["ok"])

    def test_logout_clears_session_and_blocks_rrhh_api(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            users_path = os.path.join(tmpdir, "rrhh_users.json")
            with open(users_path, "w", encoding="utf-8") as fh:
                json.dump(
                    {
                        "users": [
                            {
                                "username": "admin",
                                "display_name": "Administrador",
                                "password": "admin123",
                                "role": "admin",
                            }
                        ]
                    },
                    fh,
                )

            with patch.dict(
                os.environ,
                {"RRHH_AUTH_ENABLED": "true", "RRHH_USERS_FILE": users_path},
                clear=True,
            ):
                login_resp = self.client.post(
                    "/login",
                    data={"username": "admin", "password": "admin123", "next": "/rrhh"},
                )
                self.assertEqual(login_resp.status_code, 302)

                api_ok = self.client.get("/api/rrhh/conversaciones")
                self.assertEqual(api_ok.status_code, 200)

                logout_resp = self.client.post("/logout")
                self.assertEqual(logout_resp.status_code, 302)
                self.assertIn("/login", logout_resp.headers.get("Location", ""))

                api_blocked = self.client.get("/api/rrhh/conversaciones")
                self.assertEqual(api_blocked.status_code, 401)


if __name__ == "__main__":
    unittest.main()
