"""Load values straight from the repository's .env file."""

from functools import lru_cache
from pathlib import Path
from typing import Dict

from dotenv import dotenv_values


@lru_cache(maxsize=1)
def _env_values() -> Dict[str, str]:
    """Parse .env once and cache its key/value pairs."""
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        raw = dotenv_values(env_path)
        # Cast None values to empty strings for consistency
        return {k: v or "" for k, v in raw.items() if k is not None}
    return {}


def get_env_value(key: str, default: str = "", *, required: bool = False) -> str:
    """Fetch a value from .env, optionally enforcing its presence."""
    value = _env_values().get(key, default)
    if required and not value:
        raise ValueError(f"{key} not found in .env file")
    return value
