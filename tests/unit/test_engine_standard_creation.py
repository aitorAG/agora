"""Tests de creación standard y persistencia de archivos de partida."""

import src.core.engine as engine_module
from src.core.engine import GameEngine
from src.persistence.json_provider import JsonPersistenceProvider


def _standard_setup():
    return {
        "titulo": "Plantilla estándar",
        "ambientacion": "Roma",
        "contexto_problema": "Intriga",
        "relevancia_jugador": "Clave",
        "player_mission": "Evitar atentado",
        "narrativa_inicial": "Inicio",
        "actors": [
            {
                "name": "Bruto",
                "personality": "Dubitativo",
                "mission": "Elegir bando",
                "background": "Senador",
                "presencia_escena": "Curia",
            }
        ],
    }


def test_create_game_from_setup_persists_standard_files(tmp_path, monkeypatch):
    monkeypatch.setattr(engine_module, "create_character_agent", lambda **_: object())
    monkeypatch.setattr(engine_module, "create_observer_agent", lambda **_: object())
    monkeypatch.setattr(
        engine_module,
        "run_one_step",
        lambda *_args, **_kwargs: {"next_action": "user_input", "game_ended": False, "events": []},
    )

    provider = JsonPersistenceProvider(base_path=tmp_path)
    engine = GameEngine(persistence_provider=provider)
    game_id, setup = engine.create_game_from_setup(
        setup=_standard_setup(),
        username="usuario",
        standard_template_id="rome_caesar_harry",
        template_version="1.0.0",
    )

    assert setup["titulo"] == "Plantilla estándar"
    game = provider.get_game(game_id)
    assert game["game_mode"] == "standard"
    assert game["standard_template_id"] == "rome_caesar_harry"
    assert game["template_version"] == "1.0.0"
    assert game["config_json"]["titulo"] == "Plantilla estándar"
    assert game["state_json"]["turn"] == 0

    game_dir = tmp_path / "custom" / game_id
    assert (game_dir / "config.json").exists()
    assert (game_dir / "context.json").exists()
    assert (game_dir / "characters.json").exists()
    assert (game_dir / "state.json").exists()
    assert (game_dir / "messages.json").exists()
