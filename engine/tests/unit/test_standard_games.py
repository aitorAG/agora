"""Tests unitarios para templates standard."""

import json

import pytest

from src.core import standard_games as standard_games_module
from src.core.standard_games import (
    StandardTemplateError,
    list_standard_templates,
    load_standard_template,
)


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _base_setup():
    return {
        "id": "template-id",
        "version": "1.0.0",
        "active": True,
        "titulo": "Titulo setup",
        "descripcion_breve": "Descripcion setup",
        "ambientacion": "Roma",
        "contexto_problema": "Intriga política",
        "relevancia_jugador": "Eres clave",
        "player_mission": "Evitar el atentado",
        "narrativa_inicial": "Comienza la historia",
        "actors": [
            {
                "name": "Bruto",
                "personality": "Dubitativo",
                "mission": "Tomar una decisión",
                "background": "Senador",
                "presencia_escena": "Curia",
            }
        ],
    }


def test_list_standard_templates_reads_unified_config_catalog(tmp_path, monkeypatch):
    monkeypatch.setattr(standard_games_module, "PROJECT_ROOT", tmp_path)
    config = _base_setup()
    config.update(
        {
            "id": "t1",
            "titulo": "Plantilla 1",
            "descripcion_breve": "Desc breve",
            "version": "1.2.0",
        }
    )
    config["actors"].append(
        {
            "name": "Casio",
            "personality": "Frio",
            "mission": "Conspirar",
            "background": "Senador",
            "presencia_escena": "Curia",
        }
    )
    _write_json(tmp_path / "game_templates" / "t1" / "config.json", config)

    templates = list_standard_templates()
    assert len(templates) == 1
    assert templates[0]["id"] == "t1"
    assert templates[0]["titulo"] == "Plantilla 1"
    assert templates[0]["version"] == "1.2.0"
    assert templates[0]["num_personajes"] == 2
    assert templates[0]["active"] is True


def test_list_standard_templates_reads_explicit_inactive_flag_from_config(tmp_path, monkeypatch):
    monkeypatch.setattr(standard_games_module, "PROJECT_ROOT", tmp_path)
    config = _base_setup()
    config.update(
        {
            "id": "t_inactive",
            "titulo": "Plantilla inactiva",
            "descripcion_breve": "Desc breve",
            "active": False,
        }
    )
    _write_json(tmp_path / "game_templates" / "t_inactive" / "config.json", config)

    templates = list_standard_templates()

    assert len(templates) == 1
    assert templates[0]["id"] == "t_inactive"
    assert templates[0]["active"] is False


def test_list_standard_templates_keeps_legacy_manifest_compatibility(tmp_path, monkeypatch):
    monkeypatch.setattr(standard_games_module, "PROJECT_ROOT", tmp_path)
    _write_json(
        tmp_path / "game_templates" / "t_legacy" / "manifest.json",
        {
            "id": "t_legacy",
            "titulo": "Plantilla legacy",
            "descripcion_breve": "Desc legacy",
            "version": "3.0.0",
            "active": False,
        },
    )
    config = _base_setup()
    config.pop("id")
    config.pop("version")
    config.pop("active")
    config["titulo"] = "Titulo setup"
    config["descripcion_breve"] = "Descripcion setup"
    _write_json(tmp_path / "game_templates" / "t_legacy" / "config.json", config)

    templates = list_standard_templates()

    assert len(templates) == 1
    assert templates[0]["id"] == "t_legacy"
    assert templates[0]["version"] == "3.0.0"
    assert templates[0]["active"] is False


def test_load_standard_template_reads_unified_config_metadata(tmp_path, monkeypatch):
    monkeypatch.setattr(standard_games_module, "PROJECT_ROOT", tmp_path)
    setup = _base_setup()
    setup.update(
        {
            "id": "t2",
            "titulo": "Titulo config",
            "descripcion_breve": "Descripcion config",
            "version": "2.0.0",
        }
    )
    _write_json(tmp_path / "game_templates" / "t2" / "config.json", setup)

    loaded = load_standard_template("t2")
    assert loaded["template_id"] == "t2"
    assert loaded["template_version"] == "2.0.0"
    assert loaded["setup"]["titulo"] == "Titulo config"
    assert loaded["setup"]["descripcion_breve"] == "Descripcion config"
    assert loaded["manifest"]["id"] == "t2"


def test_load_standard_template_keeps_legacy_manifest_compatibility(tmp_path, monkeypatch):
    monkeypatch.setattr(standard_games_module, "PROJECT_ROOT", tmp_path)
    _write_json(
        tmp_path / "game_templates" / "t2_legacy" / "manifest.json",
        {
            "id": "t2_legacy",
            "titulo": "Titulo manifest",
            "descripcion_breve": "Descripcion manifest",
            "version": "2.0.0",
        },
    )
    setup = _base_setup()
    setup.pop("id")
    setup.pop("version")
    setup.pop("active")
    setup["titulo"] = "Titulo setup"
    setup["descripcion_breve"] = "Descripcion setup"
    _write_json(tmp_path / "game_templates" / "t2_legacy" / "config.json", setup)

    loaded = load_standard_template("t2_legacy")

    assert loaded["template_id"] == "t2_legacy"
    assert loaded["template_version"] == "2.0.0"
    assert loaded["setup"]["titulo"] == "Titulo setup"
    assert loaded["setup"]["descripcion_breve"] == "Descripcion setup"


def test_load_standard_template_rejects_missing_actor_fields(tmp_path, monkeypatch):
    monkeypatch.setattr(standard_games_module, "PROJECT_ROOT", tmp_path)
    broken = _base_setup()
    broken["id"] = "t3"
    broken["titulo"] = "Titulo"
    broken["descripcion_breve"] = "Descripcion"
    broken["actors"][0].pop("mission")
    _write_json(tmp_path / "game_templates" / "t3" / "config.json", broken)

    with pytest.raises(StandardTemplateError, match="actor #1 field 'mission'"):
        load_standard_template("t3")
