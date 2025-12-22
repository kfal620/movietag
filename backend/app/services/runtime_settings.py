from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping

from app.core.settings import ENV_FILE_PATH


def _parse_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    values: dict[str, str] = {}
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, raw_value = stripped.split("=", 1)
        values[key.strip()] = raw_value.strip()
    return values


def persist_runtime_settings(updates: Mapping[str, str | None]) -> dict[str, str]:
    """Merge the provided settings into the .env file and OS environment."""
    env_values = _parse_env_file(ENV_FILE_PATH)

    for key, value in updates.items():
        if value is None:
            env_values.pop(key, None)
            os.environ.pop(key, None)
        else:
            env_values[key] = value
            os.environ[key] = value

    serialized = "\n".join(f"{key}={value}" for key, value in env_values.items())
    ENV_FILE_PATH.write_text(f"{serialized}\n" if serialized else "")
    return env_values
