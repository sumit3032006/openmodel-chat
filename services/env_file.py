"""Optional helper that stores the API key in the local, Git-ignored .env file."""
from __future__ import annotations

import os
from pathlib import Path

VAR = "OPENROUTER_API_KEY"


def _validate(key: str) -> str:
    key = "".join(key.split())
    if not key or any(c in key for c in "\"'=#\\"):
        raise ValueError("The key contains characters that cannot be saved safely.")
    return key


def save_api_key(path: Path, key: str) -> None:
    key = _validate(key)
    path = Path(path)
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    replaced = False
    for i, line in enumerate(lines):
        if line.strip().startswith(f"{VAR}="):
            lines[i] = f"{VAR}={key}"
            replaced = True
            break
    if not replaced:
        lines.append(f"{VAR}={key}")
    tmp = path.with_suffix(".tmp")
    tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def remove_api_key(path: Path) -> None:
    path = Path(path)
    if not path.exists():
        return
    lines = [
        f"{VAR}=" if line.strip().startswith(f"{VAR}=") else line
        for line in path.read_text(encoding="utf-8").splitlines()
    ]
    tmp = path.with_suffix(".tmp")
    tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.replace(tmp, path)
