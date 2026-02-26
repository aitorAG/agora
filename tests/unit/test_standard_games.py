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


def test_list_standard_templates_reads_manifest_catalog(tmp_path, monkeypatch):
    monkeypatch.setattr(standard_games_module, "PROJECT_ROOT", tmp_path)
    _write_json(
        tmp_path / "game_templates" / "t1" / "manifest.json",
        {
            "id": "t1",
            "titulo": "Plantilla 1",
            "descripcion_breve": "Desc breve",
            "version": "1.2.0",
            "num_personajes": 4,
        },
    )
    _write_json(tmp_path / "game_templates" / "t1" / "config.json", _base_setup())

    templates = list_standard_templates()
    assert len(templates) == 1
    assert templates[0]["id"] == "t1"
    assert templates[0]["titulo"] == "Plantilla 1"
    assert templates[0]["version"] == "1.2.0"


def test_load_standard_template_merges_manifest_metadata(tmp_path, monkeypatch):
    monkeypatch.setattr(standard_games_module, "PROJECT_ROOT", tmp_path)
    _write_json(
        tmp_path / "game_templates" / "t2" / "manifest.json",
        {
            "id": "t2",
            "titulo": "Titulo manifest",
            "descripcion_breve": "Descripcion manifest",
            "version": "2.0.0",
        },
    )
    setup = _base_setup()
    setup.pop("narrativa_inicial")
    setup["narrativa_inicial"] = "Inicio"
    _write_json(tmp_path / "game_templates" / "t2" / "config.json", setup)

    loaded = load_standard_template("t2")
    assert loaded["template_id"] == "t2"
    assert loaded["template_version"] == "2.0.0"
    assert loaded["setup"]["titulo"] == "Titulo manifest"
    assert loaded["setup"]["descripcion_breve"] == "Descripcion manifest"


def test_load_standard_template_rejects_missing_actor_fields(tmp_path, monkeypatch):
    monkeypatch.setattr(standard_games_module, "PROJECT_ROOT", tmp_path)
    _write_json(
        tmp_path / "game_templates" / "t3" / "manifest.json",
        {
            "id": "t3",
            "titulo": "Titulo",
            "descripcion_breve": "Descripcion",
        },
    )
    broken = _base_setup()
    broken["actors"][0].pop("mission")
    _write_json(tmp_path / "game_templates" / "t3" / "config.json", broken)

    with pytest.raises(StandardTemplateError, match="non-empty mission"):
        load_standard_template("t3")
