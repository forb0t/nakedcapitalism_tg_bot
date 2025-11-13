"""
Telegram бот для мониторинга статей Naked Capitalism.
"""

import asyncio
import logging
import schedule
import time
from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from article_monitor import NakedCapitalismMonitor
from bot_config import ConfigError, get_bot_token

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


class NakedCapBot:
    """Основной класс Telegram-бота."""

    def __init__(self, bot_token: str) -> None:
        self.bot_token = bot_token
        self.monitor = NakedCapitalismMonitor()
        self.application = Application.builder().token(bot_token).build()
        self.monitoring_active = True

        self._setup_handlers()
        self._setup_scheduler()

    # ------------------------------------------------------------------ keyboards & texts
    def _main_menu_keyboard(self) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("📰 Проверить статьи", callback_data="check_articles")],
            [InlineKeyboardButton("📚 Последние статьи", callback_data="latest_articles")],
            [InlineKeyboardButton("🔍 Поиск статей", callback_data="search_articles")],
            [InlineKeyboardButton("📊 Статистика", callback_data="stats")],
            [InlineKeyboardButton("⚙️ Мониторинг", callback_data="monitor_status")],
        ])

    def _back_keyboard(self) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="back_to_menu")]])

    @staticmethod
    def _search_help_text() -> str:
        return (
            "🔍 Поиск статей\n\n"
            "Использование: `/search [запрос]`\n\n"
            "Примеры:\n"
            "• `/search economics`\n"
            "• `/search trump`\n"
            "• `/search #technology`"
        )

    def _welcome_message(self, user) -> str:
        commands = "\n".join([
            "/check - Проверить новые статьи сейчас",
            "/latest - Показать последние статьи",
            "/stats - Статистика мониторинга",
            "/monitor - Управление мониторингом",
            "/search [запрос] - Поиск статей в базе",
        ])

        return (
            f"Привет, {user.first_name}! 👋\n\n"
            f"🤖 Я бот для мониторинга статей с сайта [Naked Capitalism](https://www.nakedcapitalism.com/)\n\n"
            f"📰 Каждый час я проверяю новые статьи и уведомляю вас\n"
            f"🔔 Используйте кнопки ниже или команды для управления\n\n"
            f"📋 Доступные команды:\n{commands}"
        )

    # ------------------------------------------------------------------ setup
    def _setup_handlers(self) -> None:
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("check", self.check_articles))
        self.application.add_handler(CommandHandler("latest", self.latest_articles))
        self.application.add_handler(CommandHandler("stats", self.stats))
        self.application.add_handler(CommandHandler("monitor", self.toggle_monitoring))
        self.application.add_handler(CommandHandler("search", self.search_articles))
        self.application.add_handler(CallbackQueryHandler(self.button_callback))
        self.application.add_error_handler(self.error_handler)

    def _setup_scheduler(self) -> None:
        schedule.every().hour.do(self.scheduled_check)

    # ------------------------------------------------------------------ helpers
    async def _reply_or_send(self, update: Update, text: str, **kwargs):
        message = update.effective_message
        if message is not None:
            return await message.reply_text(text, **kwargs)

        chat = update.effective_chat
        if chat is not None:
            return await chat.send_message(text, **kwargs)

        logger.error("Не удалось определить получателя для отправки сообщения.")
        return None

    # ------------------------------------------------------------------ handlers
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.effective_user
        await self._reply_or_send(
            update,
            self._welcome_message(user),
            reply_markup=self._main_menu_keyboard(),
            parse_mode="Markdown",
            disable_web_page_preview=True,
        )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        help_text = "\n".join([
            "📋 Доступные команды:",
            "",
            "🔍 /check - Проверить новые статьи прямо сейчас",
            "📚 /latest - Показать последние статьи из базы",
            "📊 /stats - Статистика мониторинга",
            "⚙️ /monitor - Включить/выключить автоматический мониторинг",
            "🔎 /search [запрос] - Поиск статей по названию или автору",
            "❓ /help - Показать это сообщение",
            "",
            "🤖 Бот автоматически проверяет новые статьи каждый час",
            "📰 Уведомления приходят при обнаружении новых статей",
        ])
        await self._reply_or_send(update, help_text, reply_markup=self._back_keyboard())

    async def check_articles(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        status_message = await self._reply_or_send(
            update,
            "🔍 Проверяю новые статьи...",
            reply_markup=self._back_keyboard(),
        )
        if status_message is None:
            return

        try:
            new_articles = self.monitor.check_for_new_articles()

            if new_articles:
                response_lines = [f"✅ Найдено {len(new_articles)} новых статей!", ""]
                for idx, article in enumerate(new_articles[:5], 1):
                    response_lines.append(f"{idx}. 📰 [{article['title']}]({article['url']})")
                    response_lines.append(f"   👤 Автор: {article['author']}")
                    response_lines.append(f"   📅 Дата: {article['date_posted']}")
                    response_lines.append("")

                if len(new_articles) > 5:
                    response_lines.append(f"... и еще {len(new_articles) - 5} статей")

                await status_message.edit_text(
                    "\n".join(response_lines).strip(),
                    parse_mode="Markdown",
                    disable_web_page_preview=True,
                    reply_markup=self._back_keyboard(),
                )
            else:
                await status_message.edit_text("📝 Новых статей не найдено", reply_markup=self._back_keyboard())

        except Exception as exc:
            logger.error("Ошибка при проверке статей: %s", exc)
            await status_message.edit_text(
                "❌ Произошла ошибка при проверке статей",
                reply_markup=self._back_keyboard(),
            )

    async def latest_articles(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            latest = self.monitor.get_latest_articles(10)

            if latest:
                response_lines = ["📚 Последние статьи:", ""]
                for idx, article in enumerate(latest, 1):
                    title, url, author, date_posted = article[:4]
                    response_lines.append(f"{idx}. 📰 [{title}]({url})")
                    response_lines.append(f"   👤 {author} | 📅 {date_posted}")
                    response_lines.append("")

                await self._reply_or_send(
                    update,
                    "\n".join(response_lines).strip(),
                    parse_mode="Markdown",
                    disable_web_page_preview=True,
                    reply_markup=self._back_keyboard(),
                )
            else:
                await self._reply_or_send(
                    update,
                    "📝 Статей в базе данных нет",
                    reply_markup=self._back_keyboard(),
                )
        except Exception as exc:
            logger.error("Ошибка при получении статей: %s", exc)
            await self._reply_or_send(
                update,
                "❌ Произошла ошибка при получении статей",
                reply_markup=self._back_keyboard(),
            )

    async def stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            cursor = self.monitor.conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM articles")
            total_articles = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM articles WHERE created_at >= date('now', '-1 day')")
            today_articles = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM articles WHERE created_at >= date('now', '-7 days')")
            week_articles = cursor.fetchone()[0]

            status = "🟢 Активен" if self.monitoring_active else "🔴 Остановлен"

            stats_text = "\n".join([
                "📊 Статистика мониторинга Naked Capitalism",
                "",
                f"📰 Всего статей в базе: {total_articles}",
                f"📅 Статей за сегодня: {today_articles}",
                f"📆 Статей за неделю: {week_articles}",
                "",
                f"⚙️ Статус мониторинга: {status}",
                f"🕐 Последняя проверка: {datetime.now().strftime('%H:%M:%S')}",
            ])

            await self._reply_or_send(update, stats_text, reply_markup=self._back_keyboard())
        except Exception as exc:
            logger.error("Ошибка при получении статистики: %s", exc)
            await self._reply_or_send(
                update,
                "❌ Произошла ошибка при получении статистики",
                reply_markup=self._back_keyboard(),
            )

    async def search_articles(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = " ".join(context.args).strip() if context.args else ""

        if not query:
            await self._reply_or_send(
                update,
                self._search_help_text(),
                parse_mode="Markdown",
                reply_markup=self._back_keyboard(),
            )
            return

        cursor = self.monitor.conn.cursor()
        cursor.execute(
            """
            SELECT title, url, author, date_posted
            FROM articles
            WHERE LOWER(title) LIKE ? OR LOWER(author) LIKE ?
            ORDER BY created_at DESC
            LIMIT 10
            """,
            (f"%{query.lower()}%", f"%{query.lower()}%"),
        )
        results = cursor.fetchall()

        response_lines = [f"🔍 Результаты поиска по запросу: `{query}`", ""]

        if results:
            for idx, (title, url, author, date_posted) in enumerate(results, 1):
                response_lines.append(f"{idx}. 📰 [{title}]({url})")
                response_lines.append(f"   👤 {author} | 📅 {date_posted}")
                response_lines.append("")
        else:
            response_lines.append("❌ Статьи не найдены.")

        await self._reply_or_send(
            update,
            "\n".join(response_lines).strip(),
            parse_mode="Markdown",
            disable_web_page_preview=True,
            reply_markup=self._back_keyboard(),
        )

    async def toggle_monitoring(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        self.monitoring_active = not self.monitoring_active
        status = "включен" if self.monitoring_active else "выключен"
        await self._reply_or_send(
            update,
            f"⚙️ Автоматический мониторинг {status}",
            reply_markup=self._back_keyboard(),
        )

    # ------------------------------------------------------------------ callbacks
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()

        if query.data == "check_articles":
            await self.check_articles(update, context)
        elif query.data == "latest_articles":
            await self.latest_articles(update, context)
        elif query.data == "search_articles":
            await query.edit_message_text(
                self._search_help_text(),
                reply_markup=self._back_keyboard(),
                parse_mode="Markdown",
            )
        elif query.data == "stats":
            await self.stats(update, context)
        elif query.data == "monitor_status":
            await self.toggle_monitoring(update, context)
        elif query.data == "back_to_menu":
            await query.edit_message_text(
                self._welcome_message(query.from_user),
                reply_markup=self._main_menu_keyboard(),
                parse_mode="Markdown",
                disable_web_page_preview=True,
            )

    # ------------------------------------------------------------------ background tasks
    async def scheduled_check(self):
        if not self.monitoring_active:
            return

        try:
            new_articles = self.monitor.check_for_new_articles()
            if new_articles:
                await self.notify_users_about_new_articles(new_articles)
        except Exception as exc:
            logger.error("Ошибка в планируемой проверке: %s", exc)

    async def notify_users_about_new_articles(self, articles):
        """Заглушка для уведомлений пользователей о новых статьях."""
        logger.info("Обнаружено %d новых статей для уведомления", len(articles))

    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        logger.error("Exception while handling an update: %s", context.error)

    # ------------------------------------------------------------------ lifecycle
    def run_scheduler(self) -> None:
        while True:
            schedule.run_pending()
            time.sleep(60)

    async def run(self) -> None:
        import threading

        scheduler_thread = threading.Thread(target=self.run_scheduler, daemon=True)
        scheduler_thread.start()

        logger.info("🚀 Запуск бота Naked Capitalism Monitor...")
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling(allowed_updates=Update.ALL_TYPES)

        try:
            await asyncio.Event().wait()
        except KeyboardInterrupt:
            pass
        finally:
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()


def main():
    try:
        bot_token = get_bot_token()
    except (ConfigError, FileNotFoundError) as exc:
        print("❌ ОШИБКА при загрузке токена:")
        print(f"   {exc}")
        print("📝 Подсказка:")
        print("1. Найдите @BotFather в Telegram")
        print("2. Получите токен вашего бота")
        print("3. Создайте файл @token.py рядом с nakedcap_bot.py")
        print('4. Добавьте строку вида bot_token = "ВАШ_ТОКЕН"')
        return
    except Exception as exc:  # pragma: no cover
        print(f"❌ Непредвиденная ошибка конфигурации: {exc}")
        return

    bot = NakedCapBot(bot_token)

    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")


if __name__ == "__main__":
    main()

