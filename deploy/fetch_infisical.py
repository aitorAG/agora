#!/usr/bin/env python3
"""Fetch Infisical secrets and append them to .env.runtime."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def _load_env_file(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not path.is_file():
        return data
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip()
    return data


def main() -> int:
    root_dir = Path(__file__).resolve().parents[1]
    runtime_env = root_dir / ".env.runtime"
    env_map = {**_load_env_file(root_dir / ".env"), **_load_env_file(runtime_env), **os.environ}

    if env_map.get("INFISICAL_ENABLED", "").strip().lower() not in {"1", "true", "yes", "on"}:
        return 0

    sys.path.insert(0, str(root_dir / "engine"))
    from src.config.infisical import fetch_secrets_from_infisical  # noqa: WPS433

    try:
        for key, value in env_map.items():
            os.environ[str(key)] = str(value)
        secrets = fetch_secrets_from_infisical()
    except Exception as exc:
        print(f"Infisical deploy fetch skipped: {exc}")
        return 0

    if not secrets:
        print("Infisical deploy fetch returned no secrets")
        return 0

    existing = _load_env_file(runtime_env)
    merged = {**existing, **secrets}
    lines = [f"{key}={value}" for key, value in merged.items()]
    runtime_env.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Infisical deploy fetch appended {len(secrets)} secrets to {runtime_env}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
