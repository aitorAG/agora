from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _candidate_python(repo_root: Path) -> Path | None:
    candidates = [
        repo_root / "engine" / ".venv" / "Scripts" / "python.exe",
        repo_root / ".venv" / "Scripts" / "python.exe",
        repo_root / "engine" / ".venv" / "bin" / "python",
        repo_root / ".venv" / "bin" / "python",
    ]
    for candidate in candidates:
        if not candidate.is_file():
            continue
        probe = subprocess.run(
            [str(candidate), "-c", "import dotenv"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if probe.returncode == 0:
            return candidate
    return None


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    engine_dir = repo_root / "engine"
    if not engine_dir.is_dir():
        raise SystemExit("No se encontró el directorio 'engine/' en la raíz del repo.")

    engine_python = _candidate_python(repo_root)
    if engine_python is None:
        raise SystemExit(
            "No se encontró un entorno virtual con Python para ejecutar Agora. "
            "Ejecuta 'poetry install' en la raíz o en engine/."
        )

    cmd = [str(engine_python), str(engine_dir / "main.py"), *sys.argv[1:]]
    completed = subprocess.run(cmd, check=False)
    raise SystemExit(completed.returncode)
