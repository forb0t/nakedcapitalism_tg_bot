"""
SQLite-хранилище: ленты, статьи, чаты и подписки.
"""

import logging
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from feeds import TS_FORMAT, Entry

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 2
DEFAULT_FEED = {
    "url": "https://www.nakedcapitalism.com/feed",
    "title": "Naked Capitalism",
    "site_url": "https://www.nakedcapitalism.com/",
}


def data_dir() -> Path:
    path = Path(os.environ.get("NAKEDCAP_DATA_DIR", ".")).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def _now() -> str:
    return datetime.now(timezone.utc).strftime(TS_FORMAT)


def _same_feed_key(url: str) -> str:
    """https://www.site.com/feed/ и http://site.com/feed — одна и та же лента."""
    parts = urlsplit(url.strip())
    netloc = parts.netloc.lower().removeprefix("www.")
    query = f"?{parts.query}" if parts.query else ""
    return f"{netloc}{parts.path.rstrip('/')}{query}"


def _like_pattern(query: str) -> str:
    escaped = query.lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


class Storage:
    def __init__(self, path: Path | str | None = None) -> None:
        self.conn = sqlite3.connect(str(path or data_dir() / "articles.db"))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        # Встроенный LOWER в SQLite понимает только латиницу — для поиска по-русски нужен питоновский
        self.conn.create_function("PYLOWER", 1, lambda s: s.lower() if isinstance(s, str) else s, deterministic=True)
        self._migrate()

    # ------------------------------------------------------------------ schema
    def _migrate(self) -> None:
        version = self.conn.execute("PRAGMA user_version").fetchone()[0]
        if version >= SCHEMA_VERSION:
            return

        with self.conn:
            self.conn.executescript("""
                CREATE TABLE IF NOT EXISTS feeds (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT UNIQUE NOT NULL,
                    title TEXT NOT NULL,
                    site_url TEXT,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    etag TEXT,
                    modified TEXT,
                    checked_at TEXT,
                    last_error TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    feed_id INTEGER NOT NULL REFERENCES feeds(id) ON DELETE CASCADE,
                    guid TEXT NOT NULL,
                    title TEXT NOT NULL,
                    url TEXT,
                    author TEXT,
                    published TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (feed_id, guid)
                );
                CREATE INDEX IF NOT EXISTS entries_published ON entries (published DESC);
                CREATE TABLE IF NOT EXISTS chats (
                    chat_id INTEGER PRIMARY KEY,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS subscriptions (
                    chat_id INTEGER NOT NULL REFERENCES chats(chat_id) ON DELETE CASCADE,
                    feed_id INTEGER NOT NULL REFERENCES feeds(id) ON DELETE CASCADE,
                    PRIMARY KEY (chat_id, feed_id)
                );
            """)

            cursor = self.conn.execute(
                "INSERT OR IGNORE INTO feeds (url, title, site_url) VALUES (:url, :title, :site_url)", DEFAULT_FEED,
            )
            feed_id = cursor.lastrowid if cursor.rowcount else self.find_feed(DEFAULT_FEED["url"])["id"]
            self._import_legacy(feed_id)
            self.conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

    def _import_legacy(self, feed_id: int) -> None:
        """Перенос данных из первой версии бота, которая умела только Naked Capitalism."""
        tables = {row[0] for row in self.conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}

        if "articles" in tables:
            cursor = self.conn.execute("""
                INSERT OR IGNORE INTO entries (feed_id, guid, title, url, author, published, created_at)
                SELECT ?, url, title, url, author,
                       CASE WHEN date_posted GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9] [0-9][0-9]:[0-9][0-9]'
                            THEN date_posted || ':00'
                            ELSE COALESCE(created_at, CURRENT_TIMESTAMP) END,
                       COALESCE(created_at, CURRENT_TIMESTAMP)
                FROM articles
                WHERE url GLOB 'http*://*nakedcapitalism.com/[0-9][0-9][0-9][0-9]/[0-9][0-9]/*.html'
            """, (feed_id,))
            logger.info("Перенесено статей из старой базы: %d", cursor.rowcount)
            self.conn.execute("DROP TABLE articles")

        if "subscribers" in tables:
            self.conn.execute("INSERT OR IGNORE INTO chats (chat_id) SELECT chat_id FROM subscribers")
            self.conn.execute(
                "INSERT OR IGNORE INTO subscriptions (chat_id, feed_id) SELECT chat_id, ? FROM subscribers", (feed_id,),
            )
            self.conn.execute("DROP TABLE subscribers")

    # ------------------------------------------------------------------ feeds
    _FEED_SELECT = """
        SELECT f.*, COUNT(e.id) AS entry_count, MAX(e.published) AS last_published
        FROM feeds f LEFT JOIN entries e ON e.feed_id = f.id
    """

    def list_feeds(self, enabled_only: bool = False) -> list[sqlite3.Row]:
        where = "WHERE f.enabled = 1" if enabled_only else ""
        return self.conn.execute(f"{self._FEED_SELECT} {where} GROUP BY f.id ORDER BY f.id").fetchall()

    def get_feed(self, feed_id: int) -> sqlite3.Row | None:
        return self.conn.execute(f"{self._FEED_SELECT} WHERE f.id = ? GROUP BY f.id", (feed_id,)).fetchone()

    def find_feed(self, url: str) -> sqlite3.Row | None:
        key = _same_feed_key(url)
        for feed in self.conn.execute("SELECT * FROM feeds"):
            if _same_feed_key(feed["url"]) == key:
                return feed
        return None

    def add_feed(self, url: str, title: str, site_url: str | None) -> int:
        with self.conn:
            cursor = self.conn.execute("INSERT INTO feeds (url, title, site_url) VALUES (?, ?, ?)", (url, title, site_url))
        return cursor.lastrowid

    def delete_feed(self, feed_id: int) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM feeds WHERE id = ?", (feed_id,))

    def set_feed_enabled(self, feed_id: int, enabled: bool) -> None:
        with self.conn:
            self.conn.execute("UPDATE feeds SET enabled = ? WHERE id = ?", (int(enabled), feed_id))

    def mark_feed_checked(self, feed_id: int, etag: str | None, modified: str | None) -> None:
        with self.conn:
            self.conn.execute(
                "UPDATE feeds SET checked_at = ?, etag = ?, modified = ?, last_error = NULL WHERE id = ?",
                (_now(), etag, modified, feed_id),
            )

    def mark_feed_failed(self, feed_id: int, error: str) -> None:
        with self.conn:
            self.conn.execute("UPDATE feeds SET last_error = ? WHERE id = ?", (error, feed_id))

    def last_check(self) -> str | None:
        return self.conn.execute("SELECT MAX(checked_at) FROM feeds").fetchone()[0]

    # ------------------------------------------------------------------ entries
    def save_entries(self, feed_id: int, entries: list[Entry]) -> list[dict]:
        """Сохраняет статьи и возвращает только новые — от свежих к старым."""
        new = []
        with self.conn:
            # От старых к новым, чтобы id рос вместе со временем публикации
            for entry in sorted(entries, key=lambda e: e.published):
                cursor = self.conn.execute(
                    "INSERT OR IGNORE INTO entries (feed_id, guid, title, url, author, published) VALUES (?, ?, ?, ?, ?, ?)",
                    (feed_id, entry.guid, entry.title, entry.url, entry.author, entry.published),
                )
                if cursor.rowcount:
                    new.append({"title": entry.title, "url": entry.url, "author": entry.author, "published": entry.published})
        new.reverse()
        return new

    def latest_entries(self, limit: int, offset: int = 0, feed_id: int | None = None) -> list[sqlite3.Row]:
        return self.conn.execute("""
            SELECT e.title, e.url, e.author, e.published, f.title AS feed_title
            FROM entries e JOIN feeds f ON f.id = e.feed_id
            WHERE ? IS NULL OR e.feed_id = ?
            ORDER BY e.published DESC, e.id DESC
            LIMIT ? OFFSET ?
        """, (feed_id, feed_id, limit, offset)).fetchall()

    def count_entries(self, feed_id: int | None = None) -> int:
        return self.conn.execute(
            "SELECT COUNT(*) FROM entries WHERE ? IS NULL OR feed_id = ?", (feed_id, feed_id),
        ).fetchone()[0]

    def search_entries(self, query: str, limit: int = 10) -> list[sqlite3.Row]:
        pattern = _like_pattern(query)
        return self.conn.execute("""
            SELECT e.title, e.url, e.author, e.published, f.title AS feed_title
            FROM entries e JOIN feeds f ON f.id = e.feed_id
            WHERE PYLOWER(e.title) LIKE ? ESCAPE '\\' OR PYLOWER(e.author) LIKE ? ESCAPE '\\'
            ORDER BY e.published DESC, e.id DESC
            LIMIT ?
        """, (pattern, pattern, limit)).fetchall()

    # ------------------------------------------------------------------ chats & subscriptions
    def add_chat(self, chat_id: int) -> bool:
        """Регистрирует чат. True — если чат новый."""
        with self.conn:
            cursor = self.conn.execute("INSERT OR IGNORE INTO chats (chat_id) VALUES (?)", (chat_id,))
        return cursor.rowcount > 0

    def remove_chat(self, chat_id: int) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM chats WHERE chat_id = ?", (chat_id,))

    def subscribe(self, chat_id: int, feed_id: int) -> None:
        self.add_chat(chat_id)
        with self.conn:
            self.conn.execute("INSERT OR IGNORE INTO subscriptions (chat_id, feed_id) VALUES (?, ?)", (chat_id, feed_id))

    def subscribe_all(self, chat_id: int) -> None:
        self.add_chat(chat_id)
        with self.conn:
            self.conn.execute(
                "INSERT OR IGNORE INTO subscriptions (chat_id, feed_id) SELECT ?, id FROM feeds WHERE enabled = 1", (chat_id,),
            )

    def unsubscribe(self, chat_id: int, feed_id: int) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM subscriptions WHERE chat_id = ? AND feed_id = ?", (chat_id, feed_id))

    def subscribed_feed_ids(self, chat_id: int) -> set[int]:
        rows = self.conn.execute("SELECT feed_id FROM subscriptions WHERE chat_id = ?", (chat_id,))
        return {row[0] for row in rows}

    def subscribers(self, feed_id: int) -> list[int]:
        return [row[0] for row in self.conn.execute("SELECT chat_id FROM subscriptions WHERE feed_id = ?", (feed_id,))]
