from fastapi.testclient import TestClient

from src.api import routes as routes_module
from src.api.app import app
from src.api.schemas import AuthUserResponse
from src.persistence.provider import PersistenceProvider


class _PromptProvider(PersistenceProvider):
    def __init__(self):
        self.runtime_settings: dict[str, dict] = {}

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

    def get_runtime_setting(self, key: str):
        return self.runtime_settings.get(key)

    def set_runtime_setting(self, key: str, value_json: dict):
        self.runtime_settings[key] = dict(value_json)


def _admin_user():
    return AuthUserResponse(
        id="u-admin",
        username="admin",
        is_active=True,
        role="admin",
    )


def test_admin_actor_prompt_get_returns_default_template():
    provider = _PromptProvider()
    app.dependency_overrides[routes_module.require_admin] = _admin_user
    app.dependency_overrides[routes_module.get_persistence_provider] = lambda: provider
    client = TestClient(app)
    try:
        response = client.get("/admin/actor-prompt")
        assert response.status_code == 200
        payload = response.json()
        assert payload["source"] == "default"
        assert "{name}" in payload["template"]
        assert payload["validation"]["valid"] is True
        assert any(item["key"] == "background_block" for item in payload["required_fields"])
        assert any(item["key"] == "player_name" for item in payload["required_fields"])
        assert any(item["key"] == "scene_participants_block" for item in payload["required_fields"])
    finally:
        app.dependency_overrides.clear()


def test_admin_actor_prompt_post_persists_template():
    provider = _PromptProvider()
    app.dependency_overrides[routes_module.require_admin] = _admin_user
    app.dependency_overrides[routes_module.get_persistence_provider] = lambda: provider
    client = TestClient(app)
    template = (
        'Eres {name}. Tu personalidad: {personality}. '
        'Jugador: {player_name}. {scene_participants_block}'
        "{background_block}{mission_block}{extra_system_instruction_block}"
    )
    try:
        response = client.post("/admin/actor-prompt", json={"template": template})
        assert response.status_code == 200
        payload = response.json()
        assert payload["stored"] is True
        assert payload["source"] == "custom"
        assert provider.get_actor_prompt_template() == template
    finally:
        app.dependency_overrides.clear()


def test_admin_actor_prompt_post_validates_required_fields():
    provider = _PromptProvider()
    app.dependency_overrides[routes_module.require_admin] = _admin_user
    app.dependency_overrides[routes_module.get_persistence_provider] = lambda: provider
    client = TestClient(app)
    try:
        response = client.post("/admin/actor-prompt", json={"template": "Hola {name}"})
        assert response.status_code == 422
        detail = response.json()["detail"]
        assert detail["message"] == "El prompt no es válido."
        assert "personality" in detail["validation"]["missing_fields"]
        assert "player_name" in detail["validation"]["missing_fields"]
        assert "scene_participants_block" in detail["validation"]["missing_fields"]
    finally:
        app.dependency_overrides.clear()
