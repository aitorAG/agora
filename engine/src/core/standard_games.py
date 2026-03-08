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


def _manifest_active(manifest: dict[str, Any]) -> bool:
    value = manifest.get("active")
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


def list_standard_templates() -> list[dict[str, Any]]:
    """Lista templates estándar disponibles usando manifest.json."""
    templates: list[dict[str, Any]] = []
    root = _standard_root()
    if not root.exists() or not root.is_dir():
        return templates
    for child in sorted(root.iterdir(), key=lambda p: p.name):
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
                "active": _manifest_active(manifest),
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
    config = validate_game_setup(
        _read_json(config_path),
        error_factory=StandardTemplateError,
        source_name="config.json",
    )

    setup = dict(config)
    # Garantiza consistencia de los metadatos narrativos usados por UI/listados.
    setup["titulo"] = str(setup.get("titulo") or manifest.get("titulo") or "Plantilla").strip()
    setup["descripcion_breve"] = str(
        setup.get("descripcion_breve") or manifest.get("descripcion_breve") or ""
    ).strip()

    return {
        "template_id": manifest_id,
        "template_version": str(manifest.get("version") or "1.0.0"),
        "setup": setup,
        "manifest": manifest,
    }
