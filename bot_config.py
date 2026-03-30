"""Centralized configuration helpers for the NakedCap project."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from typing import Any, Optional

__all__ = [
    "get_bot_token",
    "get_setting",
    "get_bool",
]

_TOKEN_MODULE_CACHE: Optional[Any] = None


class ConfigError(RuntimeError):
    """Raised when configuration cannot be loaded."""


def _load_token_module() -> Any:
    """Load @token.py once and cache the module object."""
    global _TOKEN_MODULE_CACHE

    if _TOKEN_MODULE_CACHE is not None:
        return _TOKEN_MODULE_CACHE

    token_path = Path(__file__).with_name("@token.py")
    if not token_path.exists():
        raise FileNotFoundError(
            "Файл @token.py не найден. Создайте его рядом с проектом и задайте необходимые переменные."
        )

    spec = importlib.util.spec_from_file_location("nakedcap_tokens", token_path)
    if spec is None or spec.loader is None:
        raise ConfigError("Не удалось подготовить загрузчик для @token.py.")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    _TOKEN_MODULE_CACHE = module
    return module


def get_setting(name: str, default: Any = None) -> Any:
    """
    Получить значение переменной из @token.py.

    Если файл @token.py отсутствует, возвращает default.
    """
    try:
        module = _load_token_module()
    except FileNotFoundError:
        return default
    except ConfigError:
        raise
    except Exception as exc:  # pragma: no cover - непредвиденные ошибки
        raise ConfigError(f"Не удалось загрузить @token.py: {exc}") from exc

    return getattr(module, name, default)


def _normalize_token(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    value = value.strip()
    return value or None


def get_token(
    name: str,
    *,
    placeholder: Optional[str] = None,
    required: bool = True,
) -> Optional[str]:
    """Generic helper to fetch a token from @token.py."""
    value = _normalize_token(get_setting(name))

    if value is None:
        if required:
            raise ConfigError(f"В файле @token.py должна быть указана переменная {name}.")
        return None

    if placeholder and value == placeholder:
        if required:
            raise ConfigError(f"Переменная {name} должна содержать реальный токен, а не плейсхолдер.")
        return None

    return value


def get_bot_token() -> str:
    """
    Получить Telegram токен бота.

    Сначала проверяются переменные окружения TELEGRAM_BOT_TOKEN или BOT_TOKEN,
    затем переменная bot_token в @token.py (локальная разработка).
    """
    env_val = _normalize_token(os.environ.get("TELEGRAM_BOT_TOKEN") or os.environ.get("BOT_TOKEN"))
    if env_val:
        if env_val == "YOUR_BOT_TOKEN_HERE":
            raise ConfigError("TELEGRAM_BOT_TOKEN не должен быть плейсхолдером.")
        return env_val
    return get_token("bot_token", placeholder="YOUR_BOT_TOKEN_HERE", required=True)


def get_bool(name: str, default: bool = False) -> bool:
    """Получить булево значение из @token.py."""
    value = get_setting(name, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off", ""}:
            return False
    return bool(default)
