"""Отправка уведомления о новой статье через Telegram API."""

import json
from datetime import datetime
from typing import Optional, Sequence, Tuple

import requests

from article_monitor import NakedCapitalismMonitor
from bot_config import ConfigError, get_bot_token, get_setting

CHAT_ID_PLACEHOLDER = "YOUR_CHAT_ID"


def _load_chat_id() -> Optional[str]:
    chat_id = get_setting("notification_chat_id") or get_setting("CHAT_ID")
    if not chat_id:
        return None
    chat_id = str(chat_id).strip()
    if chat_id and chat_id != CHAT_ID_PLACEHOLDER:
        return chat_id
    return None


def _chat_id_not_configured() -> None:
    print("❌ Необходимо указать Chat ID.")
    print("📝 Добавьте переменную notification_chat_id в @token.py.")
    print("   Узнать ID можно через @userinfobot или метод getUpdates.")


def send_telegram_notification() -> bool:
    """Отправка уведомления через Telegram API."""
    try:
        bot_token = get_bot_token()
    except ConfigError as exc:
        print(f"❌ Ошибка конфигурации: {exc}")
        return False

    chat_id = _load_chat_id()
    if not chat_id:
        _chat_id_not_configured()
        return False

    try:
        monitor = NakedCapitalismMonitor()
        latest_articles = monitor.get_latest_articles(1)

        if not latest_articles:
            print("❌ Статьи не найдены")
            return False

        title, url, author, date_posted, _created_at = latest_articles[0]
        message = (
            "🆕 **Новая статья с Naked Capitalism!**\n\n"
            f"📰 **{title}**\n\n"
            f"👤 **Автор:** {author}\n"
            f"📅 **Дата:** {date_posted}\n"
            f"🔗 **Ссылка:** [Читать статью]({url})\n\n"
            "💡 *Статья добавлена в базу данных*"
        )

        url_api = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True,
        }

        print("📤 Отправка уведомления...")
        response = requests.post(url_api, json=payload, timeout=30)

        if response.status_code != 200:
            print(f"❌ HTTP ошибка: {response.status_code}")
            print(f"   Ответ: {response.text}")
            return False

        result = response.json()
        if not result.get("ok"):
            print(f"❌ Ошибка API: {result.get('description', 'Unknown error')}")
            return False

        message_id = result["result"]["message_id"]
        print("✅ Уведомление успешно отправлено!")
        print(f"   Message ID: {message_id}")

        notification_log = {
            "timestamp": datetime.now().isoformat(),
            "chat_id": chat_id,
            "article": {
                "title": title,
                "url": url,
                "author": author,
                "date": date_posted,
            },
            "message_id": message_id,
            "status": "sent",
        }

        log_filename = f"notification_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(log_filename, "w", encoding="utf-8") as handle:
            json.dump(notification_log, handle, indent=2, ensure_ascii=False)

        print(f"📝 Лог сохранен в: {log_filename}")
        return True
    except Exception as exc:
        print(f"❌ Ошибка при отправке: {exc}")
        return False
    finally:
        try:
            monitor.conn.close()  # type: ignore[arg-type]
        except Exception:
            pass


def get_chat_id() -> Sequence[Tuple[int, str, str]]:
    """Получение Chat ID через getUpdates API."""
    try:
        bot_token = get_bot_token()
    except ConfigError as exc:
        print(f"❌ Ошибка конфигурации: {exc}")
        return []

    try:
        url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
        response = requests.get(url, timeout=30)

        if response.status_code != 200:
            print(f"❌ HTTP ошибка: {response.status_code}")
            return []

        data = response.json()
        if not data.get("ok"):
            print(f"❌ Ошибка API: {data.get('description')}")
            return []

        updates = data.get("result", [])
        if not updates:
            print("📝 Нет обновлений. Напишите боту /start или любое сообщение.")
            return []

        chats: set[Tuple[int, str, str]] = set()
        for update in updates[-10:]:  # анализируем последние 10 обновлений
            message = update.get("message", {})
            chat = message.get("chat", {})
            chat_id = chat.get("id")
            chat_type = chat.get("type", "unknown")
            chat_title = chat.get("title") or chat.get("first_name") or "Unknown"
            if chat_id:
                chats.add((chat_id, chat_type, chat_title))

        if chats:
            print("📋 Найденные чаты:")
            for cid, ctype, title in chats:
                print(f"   ID: {cid} | Тип: {ctype} | Название: {title}")
        else:
            print("❌ Чаты не найдены")

        return list(chats)
    except Exception as exc:
        print(f"❌ Ошибка: {exc}")
        return []


def main():
    """Основная функция CLI."""
    print("📢 ОТПРАВКА УВЕДОМЛЕНИЯ ЧЕРЕЗ TELEGRAM API")
    print("=" * 50)

    print("Выберите действие:")
    print("1. Получить Chat ID")
    print("2. Отправить уведомление")
    print("3. Проверить новые статьи")

    choice = input("\nВведите номер (1-3): ").strip()

    if choice == "1":
        print("\n🔍 Получение Chat ID...")
        chats = get_chat_id()
        if chats:
            print(f"\n✅ Найдено {len(chats)} чатов.")
            print("💡 Скопируйте нужный Chat ID и добавьте его в @token.py.")
    elif choice == "2":
        print("\n📤 Отправка уведомления...")
        success = send_telegram_notification()
        if success:
            print("\n🎉 Уведомление отправлено успешно!")
        else:
            print("\n❌ Не удалось отправить уведомление.")
    elif choice == "3":
        print("\n🔍 Проверка новых статей...")
        monitor = NakedCapitalismMonitor()
        new_articles = monitor.check_for_new_articles()

        if new_articles:
            print(f"📰 Найдено {len(new_articles)} новых статей:")
            for idx, article in enumerate(new_articles, 1):
                print(f"{idx}. {article['title']}")
                print(f"   Автор: {article['author']}")
                print(f"   Дата: {article['date_posted']}")
        else:
            print("📝 Новых статей не найдено")

        monitor.conn.close()
    else:
        print("❌ Неверный выбор")


if __name__ == "__main__":
    main()
