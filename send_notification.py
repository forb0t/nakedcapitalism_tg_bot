"""Скрипт для отправки уведомлений о новых статьях."""

import asyncio
from typing import Optional

from telegram import Bot

from article_monitor import NakedCapitalismMonitor
from bot_config import ConfigError, get_bot_token, get_setting

CHAT_ID_PLACEHOLDER = "YOUR_CHAT_ID"


def _load_chat_id() -> Optional[str]:
    """Получить chat_id из @token.py или вернуть None."""
    chat_id = get_setting("notification_chat_id")
    if not chat_id:
        chat_id = get_setting("CHAT_ID")
    if not chat_id:
        return None
    chat_id = str(chat_id).strip()
    if chat_id and chat_id != CHAT_ID_PLACEHOLDER:
        return chat_id
    return None


def _chat_id_not_configured() -> None:
    print("❌ Необходимо указать CHAT_ID для отправки уведомлений.")
    print("📝 Как получить Chat ID:")
    print("1. Напишите боту @userinfobot")
    print("2. Скопируйте ваш ID")
    print("3. Добавьте переменную notification_chat_id в @token.py")


async def send_article_notification():
    """Отправка уведомления о новых статьях."""
    try:
        bot_token = get_bot_token()
    except ConfigError as exc:
        print(f"❌ Ошибка конфигурации: {exc}")
        return

    chat_id = _load_chat_id()
    if not chat_id:
        _chat_id_not_configured()
        return

    try:
        bot = Bot(token=bot_token)
        monitor = NakedCapitalismMonitor()

        print("🔍 Проверка новых статей...")
        new_articles = monitor.check_for_new_articles()

        if new_articles:
            print(f"📰 Найдено {len(new_articles)} новых статей")
            message_lines = [
                f"🆕 **Найдено {len(new_articles)} новых статей с Naked Capitalism!**",
                "",
            ]

            for idx, article in enumerate(new_articles[:5], 1):
                message_lines.append(f"**{idx}.** {article['title']}")
                message_lines.append(f"👤 {article['author']} | 📅 {article['date_posted']}")
                message_lines.append(f"🔗 [Читать статью]({article['url']})")
                message_lines.append("")

            if len(new_articles) > 5:
                message_lines.append(f"... и еще {len(new_articles) - 5} статей")

            await bot.send_message(
                chat_id=chat_id,
                text="\n".join(message_lines).strip(),
                parse_mode='Markdown',
                disable_web_page_preview=True,
            )
            print(f"✅ Уведомление отправлено в чат {chat_id}")
        else:
            print("📝 Новых статей не найдено")
            await bot.send_message(chat_id=chat_id, text="📝 Новых статей с Naked Capitalism не найдено")
            print("✅ Отправлено уведомление об отсутствии новых статей")
    except Exception as exc:
        print(f"❌ Ошибка при отправке уведомления: {exc}")
    finally:
        try:
            monitor.conn.close()  # type: ignore[arg-type]
        except Exception:
            pass


async def send_single_article_notification():
    """Отправка уведомления о последней статье."""
    try:
        bot_token = get_bot_token()
    except ConfigError as exc:
        print(f"❌ Ошибка конфигурации: {exc}")
        return

    chat_id = _load_chat_id()
    if not chat_id:
        _chat_id_not_configured()
        return

    try:
        bot = Bot(token=bot_token)
        monitor = NakedCapitalismMonitor()
        latest_articles = monitor.get_latest_articles(1)

        if not latest_articles:
            print("❌ Статьи не найдены")
            return

        title, url, author, date_posted, _created_at = latest_articles[0]
        message = (
            "📰 **Новая статья с Naked Capitalism**\n\n"
            f"**{title}**\n\n"
            f"👤 Автор: {author}\n"
            f"📅 Дата: {date_posted}\n"
            f"🔗 [Читать статью]({url})"
        )

        await bot.send_message(
            chat_id=chat_id,
            text=message,
            parse_mode='Markdown',
            disable_web_page_preview=True,
        )
        print(f"✅ Уведомление о статье отправлено: {title}")
    except Exception as exc:
        print(f"❌ Ошибка: {exc}")
    finally:
        try:
            monitor.conn.close()  # type: ignore[arg-type]
        except Exception:
            pass


def main():
    """CLI-интерфейс для отправки уведомлений."""
    print("📢 ОТПРАВКА УВЕДОМЛЕНИЙ О НОВЫХ СТАТЬЯХ")
    print("=" * 50)
    print("Выберите тип уведомления:")
    print("1. Проверить и отправить уведомления о новых статьях")
    print("2. Отправить уведомление о последней статье")
    print("3. Только проверить новые статьи (без отправки)")

    choice = input("\nВведите номер (1-3): ").strip()

    if choice == "1":
        asyncio.run(send_article_notification())
    elif choice == "2":
        asyncio.run(send_single_article_notification())
    elif choice == "3":
        monitor = NakedCapitalismMonitor()
        new_articles = monitor.check_for_new_articles()

        if new_articles:
            print(f"\n📰 Найдено {len(new_articles)} новых статей:")
            for idx, article in enumerate(new_articles, 1):
                print(f"{idx}. {article['title']}")
                print(f"   Автор: {article['author']}")
                print(f"   Дата: {article['date_posted']}")
                print(f"   URL: {article['url']}\n")
        else:
            print("📝 Новых статей не найдено")

        monitor.conn.close()
    else:
        print("❌ Неверный выбор")


if __name__ == "__main__":
    main()
