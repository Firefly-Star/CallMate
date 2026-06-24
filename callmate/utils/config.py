"""Configuration loader from .env.

Usage:
    from utils.config import Config
    cfg = Config()
    print(cfg.deepgram.api_key)
"""

import os
from pathlib import Path
from dotenv import load_dotenv


class _DeepgramConfig:
    def __init__(self, api_key: str):
        self.api_key = api_key


class _LLMConfig:
    def __init__(self, anthropic_key: str, openai_key: str):
        self.anthropic_key = anthropic_key
        self.openai_key = openai_key

    @property
    def available(self) -> list[str]:
        providers = []
        if self.anthropic_key:
            providers.append("anthropic")
        if self.openai_key:
            providers.append("openai")
        return providers


class Config:
    """Application configuration loaded from .env file."""

    def __init__(self, env_path: str | None = None):
        if env_path is None:
            env_path = self._find_env_file()

        load_dotenv(env_path)

        self.deepgram = _DeepgramConfig(
            api_key=self._require("DEEPGRAM_API_KEY"),
        )
        self.llm = _LLMConfig(
            anthropic_key=os.getenv("ANTHROPIC_API_KEY", ""),
            openai_key=os.getenv("OPENAI_API_KEY", ""),
        )

        if not self.llm.available:
            raise ValueError(
                "At least one LLM API key is required. "
                "Set ANTHROPIC_API_KEY or OPENAI_API_KEY in .env"
            )

    @staticmethod
    def _find_env_file() -> str:
        """Search for .env in the project directory."""
        candidates = [
            Path.cwd() / ".env",
            Path.cwd().parent / ".env",
            Path.home() / ".callmate" / ".env",
        ]
        for path in candidates:
            if path.exists():
                return str(path)
        raise FileNotFoundError(
            ".env file not found. "
            f"Create one from {Path.cwd() / '.env.template'}"
        )

    @staticmethod
    def _require(key: str) -> str:
        value = os.getenv(key, "")
        if not value:
            raise ValueError(
                f"Missing required config: {key}. "
                "Check your .env file."
            )
        return value
