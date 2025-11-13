"""Deprecated compatibility wrapper.

Все функции перенесены в `nakedcap_bot.py`. Этот модуль сохранён для
обратной совместимости и просто делегирует запуск основному боту.
"""

from nakedcap_bot import main  # noqa: F401

if __name__ == "__main__":
    main()
