"""Configuration: load .env + a couple of top-level settings."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Config:
    # Empty string means "no explicit choice" — app.py then uses whichever
    # configured provider was found first.
    default_provider: str = ""
    require_confirmation: bool = False
    include_pc_control: bool = True
    max_iterations: int = 12
    temperature: float = 0.7


def load_config(env_path: str | os.PathLike[str] | None = None) -> Config:
    """Load environment from a .env file (if present) and build a Config."""
    try:
        from dotenv import load_dotenv

        if env_path is not None:
            load_dotenv(env_path)
        else:
            # Look for .env in CWD then the repo root.
            for candidate in (Path.cwd() / ".env", Path(__file__).resolve().parents[2] / ".env"):
                if candidate.is_file():
                    load_dotenv(candidate)
                    break
    except ImportError:
        pass  # python-dotenv optional; rely on real environment

    return Config(
        default_provider=os.getenv("JARVIS_DEFAULT_PROVIDER", "").lower(),
        require_confirmation=os.getenv("JARVIS_REQUIRE_CONFIRMATION", "false").lower()
        == "true",
        include_pc_control=os.getenv("JARVIS_INCLUDE_PC_CONTROL", "true").lower()
        != "false",
        max_iterations=int(os.getenv("JARVIS_MAX_ITERATIONS", "12")),
        temperature=float(os.getenv("JARVIS_TEMPERATURE", "0.7")),
    )
