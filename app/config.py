"""Configuration management and secret sanitation for VibeCheck AI.

Loads settings from environment variables or .env file using pure Python
standard library. Never logs or prints unredacted API credentials.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import urlparse


def load_env_file(dotenv_path: Path) -> Dict[str, str]:
    """Parse a simple .env file without external dependencies."""
    env_vars: Dict[str, str] = {}
    if not dotenv_path.is_file():
        return env_vars

    try:
        with open(dotenv_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip().strip("'\"")
                    if key:
                        env_vars[key] = val
    except Exception:
        pass
    return env_vars


class Config:
    """Application configuration holder."""

    def __init__(self, env_path: Optional[Path] = None):
        base_dir = Path(__file__).resolve().parent.parent
        self.env_path = env_path or (base_dir / ".env")

        # Load .env file into a local dictionary first
        file_env = load_env_file(self.env_path)

        # Environment variables take precedence over .env file
        def get_val(key: str, default: str) -> str:
            return os.environ.get(key, file_env.get(key, default))

        self.ai_base_url = get_val("AI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        self.ai_model = get_val("AI_MODEL", "gpt-4o-mini")
        self.ai_api_key = get_val("AI_API_KEY", "")

        try:
            self.timeout_seconds = int(get_val("AI_TIMEOUT_SECONDS", "20"))
        except ValueError:
            self.timeout_seconds = 20

        try:
            self.max_retries = int(get_val("AI_MAX_RETRIES", "2"))
        except ValueError:
            self.max_retries = 2

        self.prompt_schema_version = get_val("PROMPT_SCHEMA_VERSION", "v1.0.0")
        self.storage_dir = Path(get_val("STORAGE_DIR", str(base_dir / "storage")))
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def validate_url(self) -> bool:
        """Validate base URL scheme and hostname to prevent unintended network calls."""
        if not self.ai_base_url:
            return False
        parsed = urlparse(self.ai_base_url)
        # Enforce HTTPS, or allow HTTP strictly for local testing (localhost / 127.0.0.1)
        if parsed.scheme == "https":
            return bool(parsed.netloc)
        if parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1"}:
            return True
        return False

    @staticmethod
    def redact_secret(secret: str) -> str:
        """Safely mask API keys or tokens for logging and display."""
        if not secret:
            return "(not set)"
        if len(secret) <= 8:
            return "***"
        return f"{secret[:3]}...{secret[-4:]}"

    def get_sanitized_summary(self) -> Dict[str, str]:
        """Return safe-to-display configuration summary without raw credentials."""
        return {
            "AI_BASE_URL": self.ai_base_url,
            "AI_MODEL": self.ai_model,
            "AI_API_KEY": self.redact_secret(self.ai_api_key),
            "TIMEOUT_SECONDS": str(self.timeout_seconds),
            "MAX_RETRIES": str(self.max_retries),
            "PROMPT_SCHEMA_VERSION": self.prompt_schema_version,
            "STORAGE_DIR": str(self.storage_dir),
        }
