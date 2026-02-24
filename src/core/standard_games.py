"""Gestión de plantillas estándar para creación rápida de partidas."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .game_persistence import ensure_games_structure


class StandardTemplateError(ValueError):
    """Error de validación/carga de plantilla estándar."""


def _standard_root() -> Path:
    return ensure_games_structure() / "standard"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - defensivo
        raise StandardTemplateError(f"Invalid JSON in {path.name}") from exc
    if not isinstance(data, dict):
        raise StandardTemplateError(f"{path.name} must be an object")
    return data


def _validate_setup(config: dict[str, Any]) -> dict[str, Any]:
    required = (
        "ambientacion",
        "contexto_problema",
        "relevancia_jugador",
        "player_mission",
        "narrativa_inicial",
        "actors",
    )
    missing = [k for k in required if k not in config]
    if missing:
        raise StandardTemplateError(f"Missing keys in config.json: {', '.join(missing)}")
    actors = config.get("actors")
    if not isinstance(actors, list) or not actors:
        raise StandardTemplateError("config.json actors must be a non-empty list")
    actor_required = ("name", "personality", "mission", "background", "presencia_escena")
    for actor in actors:
        if not isinstance(actor, dict):
            raise StandardTemplateError("config.json actors must be objects")
        for key in actor_required:
            if not str(actor.get(key, "")).strip():
                raise StandardTemplateError(
                    f"Each actor must have a non-empty {key}"
                )
    return config


def list_standard_templates() -> list[dict[str, Any]]:
    """Lista templates estándar disponibles usando manifest.json."""
    templates: list[dict[str, Any]] = []
    for child in sorted(_standard_root().iterdir(), key=lambda p: p.name):
        if not child.is_dir():
            continue
        manifest_path = child / "manifest.json"
        if not manifest_path.exists():
            continue
        try:
            manifest = _read_json(manifest_path)
        except StandardTemplateError:
            continue
        template_id = str(manifest.get("id") or child.name).strip()
        titulo = str(manifest.get("titulo") or "").strip()
        descripcion = str(manifest.get("descripcion_breve") or "").strip()
        version = str(manifest.get("version") or "1.0.0").strip() or "1.0.0"
        try:
            num_personajes = int(manifest.get("num_personajes", 0) or 0)
        except (TypeError, ValueError):
            num_personajes = 0
        if not template_id or not titulo or not descripcion:
            continue
        templates.append(
            {
                "id": template_id,
                "titulo": titulo,
                "descripcion_breve": descripcion,
                "version": version,
                "num_personajes": max(0, num_personajes),
            }
        )
    return templates


def load_standard_template(template_id: str) -> dict[str, Any]:
    """Carga template por id y devuelve setup + metadatos de manifest."""
    clean_id = str(template_id or "").strip()
    if not clean_id:
        raise StandardTemplateError("template_id is required")
    template_dir = _standard_root() / clean_id
    if not template_dir.exists() or not template_dir.is_dir():
        raise KeyError(clean_id)

    manifest_path = template_dir / "manifest.json"
    config_path = template_dir / "config.json"
    if not manifest_path.exists() or not config_path.exists():
        raise StandardTemplateError("Template is missing manifest.json or config.json")

    manifest = _read_json(manifest_path)
    manifest_id = str(manifest.get("id") or clean_id).strip()
    if not manifest_id:
        raise StandardTemplateError("manifest.json must define a non-empty id")
    if not str(manifest.get("titulo", "")).strip():
        raise StandardTemplateError("manifest.json must define a non-empty titulo")
    if not str(manifest.get("descripcion_breve", "")).strip():
        raise StandardTemplateError(
            "manifest.json must define a non-empty descripcion_breve"
        )
    config = _validate_setup(_read_json(config_path))

    setup = dict(config)
    # Garantiza consistencia de los metadatos narrativos usados por UI/listados.
    setup["titulo"] = str(setup.get("titulo") or manifest.get("titulo") or "Partida estándar").strip()
    setup["descripcion_breve"] = str(
        setup.get("descripcion_breve") or manifest.get("descripcion_breve") or ""
    ).strip()

    return {
        "template_id": manifest_id,
        "template_version": str(manifest.get("version") or "1.0.0"),
        "setup": setup,
        "manifest": manifest,
    }
