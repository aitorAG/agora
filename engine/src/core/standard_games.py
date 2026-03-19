"""Gestión de plantillas estándar para creación rápida de partidas."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .game_setup_contract import validate_game_setup

PROJECT_ROOT = Path(__file__).resolve().parents[2]

class StandardTemplateError(ValueError):
    """Error de validación/carga de plantilla estándar."""


def _standard_root() -> Path:
    return PROJECT_ROOT / "game_templates"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - defensivo
        raise StandardTemplateError(f"Invalid JSON in {path.name}") from exc
    if not isinstance(data, dict):
        raise StandardTemplateError(f"{path.name} must be an object")
    return data


def _template_active(template_doc: dict[str, Any]) -> bool:
    value = template_doc.get("active")
    if value is None:
        return True
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off"}:
            return False
    return bool(value)


def _load_template_document(template_dir: Path) -> dict[str, Any]:
    config_path = template_dir / "config.json"
    if not config_path.exists():
        raise StandardTemplateError("Template is missing config.json")

    config = _read_json(config_path)
    manifest_path = template_dir / "manifest.json"
    if not manifest_path.exists():
        return config

    # Compatibilidad temporal con el formato legado manifest.json + config.json.
    legacy_manifest = _read_json(manifest_path)
    merged = dict(legacy_manifest)
    merged.update(config)
    return merged


def list_standard_templates() -> list[dict[str, Any]]:
    """Lista templates estándar disponibles usando config.json unificado."""
    templates: list[dict[str, Any]] = []
    root = _standard_root()
    if not root.exists() or not root.is_dir():
        return templates
    for child in sorted(root.iterdir(), key=lambda p: p.name):
        if not child.is_dir():
            continue
        config_path = child / "config.json"
        if not config_path.exists():
            continue
        try:
            template_doc = _load_template_document(child)
        except StandardTemplateError:
            continue
        template_id = str(template_doc.get("id") or child.name).strip()
        titulo = str(template_doc.get("titulo") or "").strip()
        descripcion = str(template_doc.get("descripcion_breve") or "").strip()
        version = str(template_doc.get("version") or "1.0.0").strip() or "1.0.0"
        actors = template_doc.get("actors")
        num_personajes = len(actors) if isinstance(actors, list) else 0
        if not template_id or not titulo or not descripcion:
            continue
        templates.append(
            {
                "id": template_id,
                "titulo": titulo,
                "descripcion_breve": descripcion,
                "version": version,
                "num_personajes": max(0, num_personajes),
                "active": _template_active(template_doc),
            }
        )
    return templates


def load_standard_template(template_id: str) -> dict[str, Any]:
    """Carga template por id y devuelve setup + metadatos de plantilla."""
    clean_id = str(template_id or "").strip()
    if not clean_id:
        raise StandardTemplateError("template_id is required")
    template_dir = _standard_root() / clean_id
    if not template_dir.exists() or not template_dir.is_dir():
        raise KeyError(clean_id)

    template_doc = _load_template_document(template_dir)
    manifest_id = str(template_doc.get("id") or clean_id).strip()
    if not manifest_id:
        raise StandardTemplateError("config.json must define a non-empty id")
    if not str(template_doc.get("titulo", "")).strip():
        raise StandardTemplateError("config.json must define a non-empty titulo")
    if not str(template_doc.get("descripcion_breve", "")).strip():
        raise StandardTemplateError(
            "config.json must define a non-empty descripcion_breve"
        )
    config = validate_game_setup(
        template_doc,
        error_factory=StandardTemplateError,
        source_name="config.json",
    )

    setup = dict(config)
    # Garantiza consistencia de los metadatos narrativos usados por UI/listados.
    setup["titulo"] = str(setup.get("titulo") or template_doc.get("titulo") or "Plantilla").strip()
    setup["descripcion_breve"] = str(
        setup.get("descripcion_breve") or template_doc.get("descripcion_breve") or ""
    ).strip()
    metadata = {
        "id": manifest_id,
        "titulo": setup["titulo"],
        "descripcion_breve": setup["descripcion_breve"],
        "version": str(template_doc.get("version") or "1.0.0"),
        "active": _template_active(template_doc),
    }

    return {
        "template_id": manifest_id,
        "template_version": metadata["version"],
        "active": metadata["active"],
        "setup": setup,
        "manifest": metadata,
    }
