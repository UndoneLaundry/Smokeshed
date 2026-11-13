"""Load API keys for the Smokeshed pipeline.

Keys come from environment variables. For local development they are read
from a `.env` file at the repo root (see `.env.example` and docs/API_SETUP.md).
In GitHub Actions they come from repository secrets.

Key values are never printed or logged by this module.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent

# Real environment variables (e.g. GitHub Secrets) take precedence over .env.
load_dotenv(REPO_ROOT / ".env", override=False)


class MissingAPIKeyError(RuntimeError):
    """Raised when a required API key is not set."""


def _get(name: str) -> str | None:
    value = os.getenv(name, "").strip()
    return value or None


def get_firms_map_key() -> str:
    """Return the NASA FIRMS MAP_KEY, or raise a clear error if it is missing."""
    key = _get("FIRMS_MAP_KEY")
    if key is None:
        raise MissingAPIKeyError(
            "FIRMS_MAP_KEY is not set. Copy .env.example to .env and add your "
            "NASA FIRMS key (free: https://firms.modaps.eosdis.nasa.gov/api/map_key/). "
            "In GitHub Actions, add it as a repository secret named FIRMS_MAP_KEY. "
            "See docs/API_SETUP.md."
        )
    return key


def get_datagovsg_api_key() -> str | None:
    """Return the optional data.gov.sg API key, or None if not set."""
    return _get("DATAGOVSG_API_KEY")
