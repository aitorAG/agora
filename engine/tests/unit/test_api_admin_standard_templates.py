from fastapi.testclient import TestClient

from src.api import routes as routes_module
from src.api.app import app
from src.api.schemas import AuthUserResponse
from src.persistence.provider import PersistenceProvider


class _TemplateProvider(PersistenceProvider):
    def __init__(self):
        self.templates = {
            "rome_caesar_harry": {
                "id": "rome_caesar_harry",
                "version": "1.0.0",
                "active": True,
                "titulo": "Las Idus del Oraculo Carmesi",
                "descripcion_breve": "Roma y magia.",
                "num_personajes": 2,
                "config_json": {
                    "id": "rome_caesar_harry",
                    "version": "1.0.0",
                    "active": True,
                    "titulo": "Las Idus del Oraculo Carmesi",
                    "descripcion_breve": "Roma y magia.",
                    "ambientacion": "Roma",
                    "contexto_problema": "Problema",
                    "relevancia_jugador": "Clave",
                    "player_mission": "Salvar a Cesar",
                    "player_public_mission": "Frenar el ritual",
                    "narrativa_inicial": "Inicio",
                    "actors": [
                        {
                            "name": "Harry Potter",
                            "personality": "Impulsivo",
                            "mission": "Ritual",
                            "public_mission": "Evitar una catastrofe",
                            "background": "Mago",
                            "presencia_escena": "Templo",
                        },
                        {
                            "name": "Julio Cesar",
                            "personality": "Ambicioso",
                            "mission": "Sobrevivir",
                            "public_mission": "Mantener el poder",
                            "background": "Dictador",
                            "presencia_escena": "Curia",
                        },
                    ],
                },
            }
        }

    def create_game(self, title, config_json, username=None, game_mode="custom", standard_template_id=None, template_version=None):
        raise NotImplementedError

    def save_game_state(self, game_id, state_json):
        raise NotImplementedError

    def append_message(self, game_id, turn_number, role, content, metadata_json=None):
        raise NotImplementedError

    def get_game(self, game_id):
        raise NotImplementedError

    def get_game_messages(self, game_id):
        raise NotImplementedError

    def list_games_for_user(self, username):
        return []

    def create_feedback(self, game_id, user_id, feedback_text):
        raise NotImplementedError

    def list_feedback(self, limit=500):
        return []

    def list_standard_templates_admin(self):
        return list(self.templates.values())

    def get_standard_template(self, template_id: str):
        if template_id not in self.templates:
            raise KeyError(template_id)
        return self.templates[template_id]

    def upsert_standard_template(self, template_id: str, *, version: str, active: bool, config_json: dict):
        if str(config_json.get("id") or template_id).strip() != template_id:
            raise ValueError("config_json.id must match template_id")
        payload = {
            "id": template_id,
            "version": version,
            "active": active,
            "titulo": str(config_json.get("titulo") or ""),
            "descripcion_breve": str(config_json.get("descripcion_breve") or ""),
            "num_personajes": len(config_json.get("actors") or []),
            "config_json": dict(config_json),
        }
        self.templates[template_id] = payload
        return payload


def _admin_user():
    return AuthUserResponse(
        id="u-admin",
        username="admin",
        is_active=True,
        role="admin",
    )


def test_admin_standard_templates_list_returns_all_templates():
    provider = _TemplateProvider()
    app.dependency_overrides[routes_module.require_admin] = _admin_user
    app.dependency_overrides[routes_module.get_persistence_provider] = lambda: provider
    client = TestClient(app)
    try:
        response = client.get("/admin/standard-templates")
        assert response.status_code == 200
        payload = response.json()
        assert payload["items"][0]["id"] == "rome_caesar_harry"
        assert payload["items"][0]["num_personajes"] == 2
    finally:
        app.dependency_overrides.clear()


def test_admin_standard_templates_get_returns_full_template():
    provider = _TemplateProvider()
    app.dependency_overrides[routes_module.require_admin] = _admin_user
    app.dependency_overrides[routes_module.get_persistence_provider] = lambda: provider
    client = TestClient(app)
    try:
        response = client.get("/admin/standard-templates/rome_caesar_harry")
        assert response.status_code == 200
        payload = response.json()
        assert payload["id"] == "rome_caesar_harry"
        assert payload["active"] is True
        assert payload["config_json"]["actors"][0]["name"] == "Harry Potter"
    finally:
        app.dependency_overrides.clear()


def test_admin_standard_templates_put_updates_template_and_rejects_id_change():
    provider = _TemplateProvider()
    app.dependency_overrides[routes_module.require_admin] = _admin_user
    app.dependency_overrides[routes_module.get_persistence_provider] = lambda: provider
    client = TestClient(app)
    try:
        payload = provider.get_standard_template("rome_caesar_harry")
        config_json = dict(payload["config_json"])
        config_json["titulo"] = "Nuevo titulo"
        response = client.put(
            "/admin/standard-templates/rome_caesar_harry",
            json={
                "version": "1.1.0",
                "active": False,
                "config_json": config_json,
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["version"] == "1.1.0"
        assert body["active"] is False
        assert body["config_json"]["titulo"] == "Nuevo titulo"

        config_json["id"] = "otro_id"
        invalid = client.put(
            "/admin/standard-templates/rome_caesar_harry",
            json={
                "version": "1.1.0",
                "active": True,
                "config_json": config_json,
            },
        )
        assert invalid.status_code == 422
        assert invalid.json()["detail"] == "Template id is immutable"
    finally:
        app.dependency_overrides.clear()
