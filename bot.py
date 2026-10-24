"""
Telegram-бот, присылающий новые статьи из RSS-лент.
"""

import asyncio
import html
import logging
import re
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from telegram import (
    BotCommand,
    InlineKeyboardButton as Button,
    InlineKeyboardMarkup,
    LinkPreviewOptions,
    Message,
    Update,
)
from telegram.constants import ChatType, ParseMode
from telegram.error import BadRequest, Forbidden, RetryAfter, TelegramError
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    Defaults,
    MessageHandler,
    filters,
)

import bot_config
from bot_config import ConfigError
from feeds import TS_FORMAT, FeedError, discover_feed, fetch_feed
from storage import Storage, data_dir

logger = logging.getLogger(__name__)

PAGE_SIZE = 8
# Сколько новых статей одной ленты показывать в уведомлении
DIGEST_SIZE = 10
# Ручная проверка не чаще раза в минуту, чтобы не долбить сайты
MANUAL_CHECK_COOLDOWN = 60
FETCH_CONCURRENCY = 4

MONTHS = ("янв", "фев", "мар", "апр", "мая", "июн", "июл", "авг", "сен", "окт", "ноя", "дек")
# Ссылка: всё, что начинается с http(s)://, или голый домен вроде habr.com/ru/rss
URL_RE = re.compile(r"^(https?://\S+|[\w.-]+\.[a-z]{2,}(/\S*)?)$", re.IGNORECASE)

# Имя и описания бот выставляет себе сам при каждом запуске — так их не подменить надолго
BOT_NAME = "Naked Capitalism — лента статей"
# Показывается в пустом чате до нажатия «Старт» (до 512 символов)
DESCRIPTION = (
    "📰 Свежие статьи Naked Capitalism и других RSS-лент — прямо в Telegram.\n\n"
    "🔔 Уведомления о новых статьях из лент, на которые вы подписаны\n"
    "🆕 Все свежие статьи в одном списке\n"
    "🔍 Поиск по заголовкам и авторам\n\n"
    "Нажмите «Старт», чтобы подписаться."
)
# Показывается в профиле бота (до 120 символов)
SHORT_DESCRIPTION = "Свежие статьи Naked Capitalism и других RSS-лент с уведомлениями прямо в Telegram"

# Всё остальное делается кнопками меню. /id работает, но в списке не показывается —
# он нужен один раз, чтобы узнать свой ID для ADMIN_IDS
COMMANDS = [BotCommand("start", "Главное меню")]
ADMIN_ACTIONS = {"addfeed", "fen", "fdel", "fdel!"}

Screen = tuple[str, InlineKeyboardMarkup]


def esc(text) -> str:
    return html.escape(str(text or ""), quote=False)


def shorten(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def host(url: str | None) -> str:
    netloc = urlparse(url or "").netloc
    return netloc.removeprefix("www.")


def menu_row() -> list[Button]:
    return [Button("🏠 Меню", callback_data="menu")]


def pager(prefix: str, page: int, pages: int) -> list[Button]:
    """Ряд «◀️ 2 / 5 ▶️». prefix — начало callback_data, к нему дописывается номер страницы."""
    if pages <= 1:
        return []
    row = []
    if page > 0:
        row.append(Button("◀️", callback_data=f"{prefix}{page - 1}"))
    row.append(Button(f"{page + 1} / {pages}", callback_data="noop"))
    if page < pages - 1:
        row.append(Button("▶️", callback_data=f"{prefix}{page + 1}"))
    return row


def keyboard(*rows: list[Button]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([row for row in rows if row])


class FeedBot:
    def __init__(self, token: str) -> None:
        self.db = Storage()
        self.admin_ids = bot_config.get_admin_ids()
        self.interval = bot_config.get_check_interval()
        self.tz = bot_config.get_timezone()

        self._check_lock = asyncio.Lock()
        self._last_check_at: float | None = None

        defaults = Defaults(parse_mode=ParseMode.HTML, link_preview_options=LinkPreviewOptions(is_disabled=True))
        self.app = Application.builder().token(token).defaults(defaults).post_init(self._post_init).build()
        self._setup_handlers()

        if not self.admin_ids:
            logger.warning("ADMIN_IDS не задан — добавлять ленты через бота будет некому. Свой ID покажет команда /id")

    # ------------------------------------------------------------------ setup
    def _setup_handlers(self) -> None:
        add = self.app.add_handler
        add(CommandHandler("start", self.cmd_start))
        add(CommandHandler("id", self.cmd_id))
        add(CallbackQueryHandler(self.on_button))
        add(MessageHandler(filters.UpdateType.MESSAGE & filters.TEXT & ~filters.COMMAND, self.on_text))
        self.app.add_error_handler(self.on_error)

    async def _post_init(self, app: Application) -> None:
        bot = app.bot
        try:
            await bot.set_my_commands(COMMANDS)
            # Сравниваем перед записью: у Telegram жёсткие лимиты на смену имени и описаний
            if (await bot.get_my_name()).name != BOT_NAME:
                await bot.set_my_name(BOT_NAME)
            if (await bot.get_my_description()).description != DESCRIPTION:
                await bot.set_my_description(DESCRIPTION)
            if (await bot.get_my_short_description()).short_description != SHORT_DESCRIPTION:
                await bot.set_my_short_description(SHORT_DESCRIPTION)
        except TelegramError as exc:
            logger.warning("Не удалось обновить команды или описание бота: %s", exc)

        app.job_queue.run_repeating(
            self.scheduled_check,
            interval=self.interval * 60,
            first=30,
            name="check_feeds",
            # Если проверку проспали (ноутбук был в спящем режиме), выполнить её сразу после пробуждения,
            # а не ждать следующего интервала
            job_kwargs={"misfire_grace_time": None, "coalesce": True},
        )
        logger.info("Лент: %d, проверка каждые %d мин.", len(self.db.list_feeds()), self.interval)

    def run(self) -> None:
        logger.info("🚀 Запуск бота...")
        # Сообщения, присланные пока бот был выключен, Telegram хранит сутки — обрабатываем их, а не выбрасываем
        self.app.run_polling(allowed_updates=Update.ALL_TYPES)

    # ------------------------------------------------------------------ formatting
    def when(self, ts: str | None) -> str:
        if not ts:
            return ""
        try:
            moment = datetime.strptime(ts, TS_FORMAT).replace(tzinfo=timezone.utc).astimezone(self.tz)
        except ValueError:
            return ""

        today = datetime.now(self.tz).date()
        clock = moment.strftime("%H:%M")
        if moment.date() == today:
            return f"сегодня, {clock}"
        if moment.date() == today - timedelta(days=1):
            return f"вчера, {clock}"
        day = f"{moment.day} {MONTHS[moment.month - 1]}"
        if moment.year != today.year:
            day += f" {moment.year}"
        return f"{day}, {clock}"

    def article(self, num: int, row, show_feed: bool = True) -> str:
        title = esc(shorten(row["title"], 160))
        link = f'<a href="{html.escape(row["url"], quote=True)}">{title}</a>' if row["url"] else title
        meta = [row["feed_title"] if show_feed else None, row["author"], self.when(row["published"])]
        meta_line = " · ".join(esc(part) for part in meta if part)
        return f"<b>{num}.</b> {link}" + (f"\n<i>{meta_line}</i>" if meta_line else "")

    def last_check_text(self) -> str:
        return self.when(self.db.last_check()) or "ещё не было"

    def is_admin(self, update: Update) -> bool:
        return update.effective_user is not None and update.effective_user.id in self.admin_ids

    # ------------------------------------------------------------------ screens
    def screen_menu(self, chat_id: int) -> Screen:
        feeds = self.db.list_feeds(enabled_only=True)
        subscribed = len(self.db.subscribed_feed_ids(chat_id) & {feed["id"] for feed in feeds})

        if subscribed:
            subs_line = f"🔔 Подписок: <b>{subscribed}</b> · всего лент: <b>{len(feeds)}</b>"
        else:
            subs_line = "🔕 Вы пока ни на что не подписаны — загляните в «Ленты»"

        text = "\n".join([
            "📰 <b>Лента статей</b>",
            "",
            "Присылаю свежие статьи из RSS-лент, на которые вы подписаны.",
            "",
            subs_line,
            f"🕐 Проверяю каждые {self.interval} мин · последняя проверка: {self.last_check_text()}",
        ])
        return text, keyboard(
            [Button("🆕 Свежее", callback_data="latest:0"), Button("🔄 Проверить", callback_data="check")],
            [Button("📡 Ленты", callback_data="feeds"), Button("🔍 Поиск", callback_data="search")],
        )

    def screen_latest(self, page: int) -> Screen:
        total = self.db.count_entries()
        if not total:
            return (
                "🆕 <b>Свежие статьи</b>\n\nПока пусто — статьи появятся после первой проверки лент.",
                keyboard([Button("🔄 Проверить", callback_data="check")], menu_row()),
            )

        pages = -(-total // PAGE_SIZE)
        page = min(max(page, 0), pages - 1)
        rows = self.db.latest_entries(PAGE_SIZE, page * PAGE_SIZE)
        lines = [f"🆕 <b>Свежие статьи</b> · стр. {page + 1} из {pages}", ""]
        for num, row in enumerate(rows, page * PAGE_SIZE + 1):
            lines += [self.article(num, row), ""]

        return "\n".join(lines).strip(), keyboard(pager("latest:", page, pages), menu_row())

    def screen_feeds(self, chat_id: int, admin: bool) -> Screen:
        feeds = self.db.list_feeds(enabled_only=not admin)
        subscribed = self.db.subscribed_feed_ids(chat_id)

        lines = ["📡 <b>Ленты</b>", ""]
        if feeds:
            lines.append("Откройте ленту, чтобы посмотреть статьи и подписаться или отписаться.")
            lines += ["", "✅ — вы подписаны   ▫️ — нет"]
            if admin:
                lines.append("⏸ — лента отключена   ⚠️ — ошибка при проверке")
        else:
            lines.append("Лент пока нет.")

        buttons = []
        for feed in feeds:
            if not feed["enabled"]:
                mark = "⏸"
            elif admin and feed["last_error"]:
                mark = "⚠️"
            else:
                mark = "✅" if feed["id"] in subscribed else "▫️"
            label = f"{mark} {shorten(feed['title'], 40)} · {feed['entry_count']}"
            buttons.append([Button(label, callback_data=f"feed:{feed['id']}:0")])

        if admin:
            buttons.append([Button("➕ Добавить ленту", callback_data="addfeed")])
        buttons.append(menu_row())
        return "\n".join(lines), keyboard(*buttons)

    def screen_feed(self, feed_id: int, page: int, chat_id: int, admin: bool) -> Screen | None:
        feed = self.db.get_feed(feed_id)
        if feed is None or (not feed["enabled"] and not admin):
            return None

        subscribed = feed_id in self.db.subscribed_feed_ids(chat_id)
        total = feed["entry_count"]
        pages = max(1, -(-total // PAGE_SIZE))
        page = min(max(page, 0), pages - 1)

        site = feed["site_url"] or feed["url"]
        lines = [
            f"📡 <b>{esc(feed['title'])}</b>",
            f'🌐 <a href="{html.escape(site, quote=True)}">{esc(host(site))}</a> · статей: {total}',
            "🔔 Вы подписаны" if subscribed else "🔕 Вы не подписаны",
        ]
        if admin:
            if not feed["enabled"]:
                lines.append("⏸ Лента отключена — её не проверяют")
            if feed["last_error"]:
                lines.append(f"⚠️ Ошибка при проверке: {esc(feed['last_error'])}")
            lines.append(f"🕐 Последняя проверка: {self.when(feed['checked_at']) or 'ещё не было'}")
        lines.append("")

        rows = self.db.latest_entries(PAGE_SIZE, page * PAGE_SIZE, feed_id=feed_id)
        if rows:
            for num, row in enumerate(rows, page * PAGE_SIZE + 1):
                lines += [self.article(num, row, show_feed=False), ""]
        else:
            lines.append("Статей пока нет.")

        sub_button = (
            Button("🔕 Отписаться", callback_data=f"sub:{feed_id}:{page}") if subscribed
            else Button("🔔 Подписаться", callback_data=f"sub:{feed_id}:{page}")
        )
        admin_row = []
        if admin:
            admin_row = [
                Button("⏸ Отключить" if feed["enabled"] else "▶️ Включить", callback_data=f"fen:{feed_id}:{page}"),
                Button("🗑 Удалить", callback_data=f"fdel:{feed_id}"),
            ]

        return "\n".join(lines).strip(), keyboard(
            pager(f"feed:{feed_id}:", page, pages),
            [sub_button],
            admin_row,
            [Button("⬅️ Ленты", callback_data="feeds"), Button("🏠 Меню", callback_data="menu")],
        )

    def screen_delete_confirm(self, feed_id: int) -> Screen | None:
        feed = self.db.get_feed(feed_id)
        if feed is None:
            return None
        text = (
            f"🗑 <b>Удалить ленту «{esc(feed['title'])}»?</b>\n\n"
            f"Вместе с ней удалятся сохранённые статьи ({feed['entry_count']}) и все подписки на неё."
        )
        return text, keyboard([
            Button("✅ Да, удалить", callback_data=f"fdel!:{feed_id}"),
            Button("❌ Отмена", callback_data=f"feed:{feed_id}:0"),
        ])

    def screen_search_prompt(self) -> Screen:
        text = (
            "🔍 <b>Поиск</b>\n\n"
            "Отправьте слово или фразу — поищу в заголовках и авторах статей.\n\n"
            "<i>Подсказка: в личном чате можно писать запрос сразу, без кнопки.</i>"
        )
        return text, keyboard([Button("❌ Отмена", callback_data="menu")])

    def screen_search(self, query: str) -> Screen:
        query = shorten(query.strip(), 100)
        rows = self.db.search_entries(query)
        lines = [f"🔍 <b>Поиск:</b> «{esc(query)}»", ""]
        if rows:
            for num, row in enumerate(rows, 1):
                lines += [self.article(num, row), ""]
            if len(rows) == 10:
                lines.append("<i>Показаны 10 самых свежих совпадений — уточните запрос, чтобы найти другое.</i>")
        else:
            lines.append("Ничего не нашлось 🤷")
        return "\n".join(lines).strip(), keyboard(
            [Button("🔍 Искать ещё", callback_data="search"), Button("🏠 Меню", callback_data="menu")],
        )

    def screen_add_prompt(self) -> Screen:
        text = (
            "➕ <b>Новая лента</b>\n\n"
            "Пришлите ссылку на RSS/Atom-ленту или просто на сайт — ленту я найду сам.\n\n"
            "Например: <code>https://www.theguardian.com/world/rss</code>"
        )
        return text, keyboard([Button("❌ Отмена", callback_data="feeds")])

    # ------------------------------------------------------------------ message helpers
    async def show(self, update: Update, screen: Screen) -> Message:
        """
        Нажатие кнопки — перерисовываем то же сообщение, иначе — присылаем новое.
        Возвращает сообщение, в котором оказался экран.
        """
        text, markup = screen
        query = update.callback_query
        if query is not None and isinstance(query.message, Message):
            try:
                return await query.edit_message_text(text, reply_markup=markup)
            except BadRequest as exc:
                if "not modified" in str(exc).lower():
                    return query.message
                # Сообщение слишком старое или удалено — пришлём новое
                logger.debug("Не удалось отредактировать сообщение: %s", exc)
        return await update.effective_chat.send_message(text, reply_markup=markup)

    async def ask(self, update: Update, context: ContextTypes.DEFAULT_TYPE, kind: str, screen: Screen) -> None:
        """Показывает приглашение ввести текст и запоминает, чего ждём от пользователя."""
        message = await self.show(update, screen)
        context.chat_data["awaiting"] = {"kind": kind, "message_id": message.message_id}

    # ------------------------------------------------------------------ commands
    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        chat_id = update.effective_chat.id
        context.chat_data.pop("awaiting", None)
        # Новых пользователей сразу подписываем на всё — отписаться можно в «Лентах»
        if self.db.add_chat(chat_id):
            self.db.subscribe_all(chat_id)
        await self.show(update, self.screen_menu(chat_id))

    async def cmd_id(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.effective_user.id
        text = f"🪪 Ваш Telegram ID: <code>{user_id}</code>"
        if not self.is_admin(update):
            text += "\n\nЧтобы управлять лентами, добавьте его в переменную <code>ADMIN_IDS</code> и перезапустите бота."
        await update.effective_message.reply_text(text)

    # ------------------------------------------------------------------ free text
    async def on_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        text = update.effective_message.text.strip()
        awaiting = context.chat_data.pop("awaiting", None)
        private = update.effective_chat.type == ChatType.PRIVATE

        if awaiting is None and not private:
            # В группах реагируем только на ответ на наш вопрос
            return

        if awaiting is not None:
            # Убираем сообщение-приглашение, чтобы в чате не копились старые меню
            try:
                await context.bot.delete_message(update.effective_chat.id, awaiting["message_id"])
            except TelegramError:
                pass

        kind = awaiting["kind"] if awaiting else None
        wants_feed = kind == "add_feed" or (kind is None and self.is_admin(update) and URL_RE.match(text))
        if wants_feed and self.is_admin(update):
            await self.add_feed(update, text.split()[0])
        else:
            await self.show(update, self.screen_search(text))

    # ------------------------------------------------------------------ buttons
    async def on_button(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        action, *args = (query.data or "").split(":")
        chat_id = update.effective_chat.id
        admin = self.is_admin(update)
        context.chat_data.pop("awaiting", None)

        def arg(index: int) -> int:
            try:
                return int(args[index])
            except (IndexError, ValueError):
                return 0

        async def answer(text: str | None = None, alert: bool = False) -> None:
            # Нажатие, сделанное пока бот был выключен, Telegram подтвердить уже не даст — не страшно
            try:
                await query.answer(text, show_alert=alert)
            except BadRequest:
                pass

        if action in ADMIN_ACTIONS and not admin:
            await answer("⛔ Только для администратора", alert=True)
            return

        if action in ("sub", "fen", "fdel", "fdel!", "feed") and self.db.get_feed(arg(0)) is None:
            await answer("Эта лента уже удалена", alert=True)
            await self.show(update, self.screen_feeds(chat_id, admin))
            return

        if action == "sub":
            feed_id = arg(0)
            if feed_id in self.db.subscribed_feed_ids(chat_id):
                self.db.unsubscribe(chat_id, feed_id)
                await answer("🔕 Вы отписались от ленты")
            else:
                self.db.subscribe(chat_id, feed_id)
                await answer("🔔 Подписка оформлена")
            await self.show_feed(update, feed_id, arg(1))
            return

        if action == "fen":
            feed = self.db.get_feed(arg(0))
            self.db.set_feed_enabled(feed["id"], not feed["enabled"])
            await answer("▶️ Лента включена" if not feed["enabled"] else "⏸ Лента отключена")
            await self.show_feed(update, arg(0), arg(1))
            return

        if action == "fdel!":
            feed = self.db.get_feed(arg(0))
            self.db.delete_feed(feed["id"])
            logger.info("Лента удалена: %s", feed["url"])
            await answer(f"🗑 Лента «{shorten(feed['title'], 40)}» удалена")
            await self.show(update, self.screen_feeds(chat_id, admin))
            return

        await answer()

        if action == "menu":
            await self.show(update, self.screen_menu(chat_id))
        elif action == "latest":
            await self.show(update, self.screen_latest(arg(0)))
        elif action == "feeds":
            await self.show(update, self.screen_feeds(chat_id, admin))
        elif action == "feed":
            await self.show_feed(update, arg(0), arg(1))
        elif action == "fdel":
            await self.show(update, self.screen_delete_confirm(arg(0)) or self.screen_feeds(chat_id, admin))
        elif action == "check":
            await self.manual_check(update, context)
        elif action == "search":
            await self.ask(update, context, "search", self.screen_search_prompt())
        elif action == "addfeed":
            await self.ask(update, context, "add_feed", self.screen_add_prompt())
        # noop — индикатор страницы, ничего не делаем

    async def show_feed(self, update: Update, feed_id: int, page: int) -> None:
        chat_id = update.effective_chat.id
        admin = self.is_admin(update)
        await self.show(update, self.screen_feed(feed_id, page, chat_id, admin) or self.screen_feeds(chat_id, admin))

    # ------------------------------------------------------------------ adding feeds
    async def add_feed(self, update: Update, url: str) -> None:
        chat_id = update.effective_chat.id
        status = await update.effective_chat.send_message(f"⏳ Ищу ленту по ссылке {esc(shorten(url, 100))}…")

        try:
            result = await asyncio.to_thread(discover_feed, url)
        except FeedError as exc:
            await status.edit_text(
                f"❌ <b>Не получилось добавить ленту</b>\n\nПричина: {esc(exc)}.\n\n"
                "Проверьте ссылку или пришлите прямую ссылку на RSS.",
                reply_markup=keyboard([Button("🔁 Другая ссылка", callback_data="addfeed")], menu_row()),
            )
            return

        existing = self.db.find_feed(result.url)
        if existing is not None:
            await status.edit_text(
                f"ℹ️ Лента <b>{esc(existing['title'])}</b> уже добавлена.",
                reply_markup=keyboard([Button("📡 Открыть ленту", callback_data=f"feed:{existing['id']}:0")], menu_row()),
            )
            return

        title = result.title or host(result.site_url or result.url)
        feed_id = self.db.add_feed(result.url, title, result.site_url)
        # Текущие статьи ленты запоминаем молча — уведомления пойдут только о новых
        self.db.save_entries(feed_id, result.entries)
        self.db.mark_feed_checked(feed_id, result.etag, result.modified)
        self.db.subscribe(chat_id, feed_id)
        logger.info("Добавлена лента %s (%s)", title, result.url)

        await status.edit_text(
            "\n".join([
                f"✅ <b>Лента «{esc(title)}» добавлена</b>",
                "",
                f"🌐 {esc(host(result.site_url or result.url))}",
                f"📰 Статей сейчас в ленте: {len(result.entries)}",
                "",
                "Вы подписаны — новые статьи будут приходить сюда. "
                "Остальные пользователи увидят ленту в разделе «Ленты».",
            ]),
            reply_markup=keyboard(
                [Button("📡 Открыть ленту", callback_data=f"feed:{feed_id}:0")],
                [Button("➕ Добавить ещё", callback_data="addfeed"), Button("🏠 Меню", callback_data="menu")],
            ),
        )

    # ------------------------------------------------------------------ checking feeds
    async def check_feeds(self) -> tuple[list[tuple], list[tuple], int]:
        """
        Проверяет все включённые ленты.

        Возвращает (новые статьи по лентам, ошибки, сколько лент проверено).
        Первая проверка ленты проходит молча: её текущие статьи просто запоминаются.
        """
        async with self._check_lock:
            feeds = self.db.list_feeds(enabled_only=True)
            semaphore = asyncio.Semaphore(FETCH_CONCURRENCY)

            async def fetch(feed):
                async with semaphore:
                    try:
                        return feed, await asyncio.to_thread(fetch_feed, feed["url"], feed["etag"], feed["modified"]), None
                    except FeedError as exc:
                        return feed, None, str(exc)
                    except Exception:
                        logger.exception("Ошибка при загрузке ленты %s", feed["url"])
                        return feed, None, "внутренняя ошибка"

            fresh, errors = [], []
            for feed, result, error in await asyncio.gather(*(fetch(feed) for feed in feeds)):
                if error:
                    logger.warning("Лента %s: %s", feed["url"], error)
                    self.db.mark_feed_failed(feed["id"], error)
                    errors.append((feed, error))
                    continue

                new = [] if result.not_modified else self.db.save_entries(feed["id"], result.entries)
                self.db.mark_feed_checked(feed["id"], result.etag, result.modified)
                if new and feed["checked_at"] is not None:
                    fresh.append((feed, new))

            self._last_check_at = time.monotonic()
            total_new = sum(len(new) for _, new in fresh)
            logger.info("Проверено лент: %d, новых статей: %d, ошибок: %d", len(feeds), total_new, len(errors))
            return fresh, errors, len(feeds)

    async def manual_check(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        back = keyboard([Button("🆕 Свежее", callback_data="latest:0"), Button("🏠 Меню", callback_data="menu")])

        if self._last_check_at is not None and time.monotonic() - self._last_check_at < MANUAL_CHECK_COOLDOWN:
            await self.show(update, (
                f"🕐 Ленты проверялись меньше минуты назад ({self.last_check_text()}).\n\n"
                "Всё новое уже в разделе «Свежее».",
                back,
            ))
            return

        status = await self.show(update, ("⏳ Проверяю ленты…", keyboard()))
        fresh, errors, checked = await self.check_feeds()

        lines = ["✅ <b>Проверка завершена</b>", f"Лент проверено: {checked} · новых статей: {sum(len(n) for _, n in fresh)}"]
        if errors and self.is_admin(update):
            lines += ["", "⚠️ <b>Не удалось проверить:</b>"]
            lines += [f"• {esc(feed['title'])} — {esc(error)}" for feed, error in errors]

        num, truncated = 0, False
        for feed, new in fresh:
            if truncated:
                break
            lines += ["", f"📡 <b>{esc(feed['title'])}</b>"]
            for row in new[:DIGEST_SIZE]:
                # Лимит сообщения — 4096 символов; остальное есть в «Свежем»
                if len("\n".join(lines)) > 3500:
                    lines.append("…и другие — в разделе «Свежее»")
                    truncated = True
                    break
                num += 1
                lines += [self.article(num, row, show_feed=False), ""]
        if not fresh:
            lines += ["", "Новых статей нет — всё уже в разделе «Свежее»."]

        await status.edit_text("\n".join(lines).strip(), reply_markup=back)

        # Остальные подписчики тоже должны узнать о том, что нашла ручная проверка
        await self.broadcast(context, fresh, skip_chat_id=update.effective_chat.id)

    async def scheduled_check(self, context: ContextTypes.DEFAULT_TYPE) -> None:
        fresh, _errors, _checked = await self.check_feeds()
        await self.broadcast(context, fresh)

    # ------------------------------------------------------------------ notifications
    def digest(self, feed, entries: list[dict]) -> tuple[str, InlineKeyboardMarkup | None, LinkPreviewOptions]:
        if len(entries) == 1 and entries[0]["url"]:
            entry = entries[0]
            meta = " · ".join(esc(part) for part in (entry["author"], self.when(entry["published"])) if part)
            text = (
                f"🆕 <b>{esc(feed['title'])}</b>\n\n"
                f'<b><a href="{html.escape(entry["url"], quote=True)}">{esc(shorten(entry["title"], 200))}</a></b>'
                + (f"\n<i>{meta}</i>" if meta else "")
            )
            markup = keyboard([Button("📖 Читать", url=entry["url"])])
            return text, markup, LinkPreviewOptions(url=entry["url"], prefer_large_media=True)

        lines = [f"🆕 <b>{esc(feed['title'])}</b> · новых статей: {len(entries)}", ""]
        for num, entry in enumerate(entries[:DIGEST_SIZE], 1):
            lines += [self.article(num, entry, show_feed=False), ""]
        if len(entries) > DIGEST_SIZE:
            lines.append(f"…и ещё {len(entries) - DIGEST_SIZE} — в разделе «Свежее»")
        return "\n".join(lines).strip(), None, LinkPreviewOptions(is_disabled=True)

    async def broadcast(self, context: ContextTypes.DEFAULT_TYPE, fresh: list[tuple], skip_chat_id: int | None = None) -> None:
        for feed, entries in fresh:
            text, markup, preview = self.digest(feed, entries)
            subscribers = [chat_id for chat_id in self.db.subscribers(feed["id"]) if chat_id != skip_chat_id]
            logger.info("Лента %s: %d новых статей → %d подписчикам", feed["title"], len(entries), len(subscribers))

            for chat_id in subscribers:
                await self.deliver(context, chat_id, text, markup, preview)
                # Лимит Telegram — около 30 сообщений в секунду
                await asyncio.sleep(0.05)

    async def deliver(self, context, chat_id: int, text: str, markup, preview: LinkPreviewOptions) -> None:
        for _attempt in range(3):
            try:
                await context.bot.send_message(chat_id, text, reply_markup=markup, link_preview_options=preview)
                return
            except RetryAfter as exc:
                await asyncio.sleep(exc.retry_after)
            except Forbidden:
                # Пользователь заблокировал бота или удалил его из группы
                logger.info("Чат %s недоступен — удаляю его подписки", chat_id)
                self.db.remove_chat(chat_id)
                return
            except BadRequest as exc:
                if "chat not found" in str(exc).lower():
                    self.db.remove_chat(chat_id)
                else:
                    logger.warning("Не удалось отправить уведомление в %s: %s", chat_id, exc)
                return
            except TelegramError as exc:
                logger.warning("Не удалось отправить уведомление в %s: %s", chat_id, exc)
                return

    async def on_error(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        logger.error("Ошибка при обработке обновления", exc_info=context.error)


def setup_logging() -> None:
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(data_dir() / "bot.log", encoding="utf-8"),
        ],
    )
    # httpx пишет в лог каждый запрос к Telegram вместе с токеном в адресе
    logging.getLogger("httpx").setLevel(logging.WARNING)


def main() -> None:
    setup_logging()

    try:
        token = bot_config.get_bot_token()
    except (ConfigError, FileNotFoundError) as exc:
        print("❌ ОШИБКА при загрузке токена:")
        print(f"   {exc}")
        print("📝 Подсказка:")
        print("1. Найдите @BotFather в Telegram и получите токен бота")
        print("2. Задайте TELEGRAM_BOT_TOKEN в окружении (Docker / .env)")
        return

    FeedBot(token).run()


if __name__ == "__main__":
    main()
