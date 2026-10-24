"""
Загрузка и разбор RSS/Atom-лент.
"""

import hashlib
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import feedparser
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Формат времени в базе: всегда UTC
TS_FORMAT = "%Y-%m-%d %H:%M:%S"

# Сайты по-разному фильтруют ботов: одни пускают только известные RSS-читалки,
# другие — только браузеры. Начинаем с честного UA библиотеки, при отказе пробуем браузерный.
USER_AGENTS = (
    feedparser.USER_AGENT,
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36",
)
BLOCKED_STATUSES = {401, 403, 406, 419}
FEED_MIME_TYPES = ("application/rss+xml", "application/atom+xml", "application/rdf+xml", "application/xml", "text/xml")
# Где обычно лежит лента, если сайт не указал её в <link rel="alternate">
COMMON_FEED_PATHS = ("/feed", "/rss", "/rss.xml", "/feed.xml", "/atom.xml", "/index.xml")


class FeedError(Exception):
    """Ленту не удалось загрузить или разобрать. Текст пригоден для показа пользователю."""


@dataclass
class Entry:
    guid: str
    title: str
    url: str | None
    author: str | None
    published: str


@dataclass
class FetchResult:
    url: str
    title: str | None = None
    site_url: str | None = None
    etag: str | None = None
    modified: str | None = None
    not_modified: bool = False
    entries: list[Entry] = field(default_factory=list)


def _http_get(url: str, etag: str | None = None, modified: str | None = None) -> requests.Response:
    headers = {"Accept": "application/rss+xml, application/atom+xml, application/xml;q=0.9, text/html;q=0.8, */*;q=0.5"}
    if etag:
        headers["If-None-Match"] = etag
    if modified:
        headers["If-Modified-Since"] = modified

    for user_agent in USER_AGENTS:
        try:
            response = requests.get(url, headers={**headers, "User-Agent": user_agent}, timeout=30)
        except requests.Timeout as exc:
            raise FeedError("сайт не ответил за 30 секунд") from exc
        except requests.RequestException as exc:
            raise FeedError("не удалось подключиться к сайту") from exc
        if response.status_code not in BLOCKED_STATUSES:
            break

    if response.status_code >= 400:
        raise FeedError(f"сайт ответил кодом {response.status_code}")
    return response


def _parse(response: requests.Response):
    """Разбор ответа как ленты. None — если это не RSS/Atom."""
    parsed = feedparser.parse(
        response.content,
        response_headers={
            "content-location": response.url,
            "content-type": response.headers.get("Content-Type", ""),
        },
    )
    if not parsed.version and not parsed.entries:
        return None
    return parsed


def _clean(text: str | None) -> str:
    if not text:
        return ""
    if "<" in text:
        text = BeautifulSoup(text, "html.parser").get_text(" ")
    return re.sub(r"\s+", " ", text).strip()


def _safe_url(url: str | None, base: str) -> str | None:
    """Telegram принимает в ссылках только http(s) — остальное отбрасываем."""
    if not url:
        return None
    url = urljoin(base, url.strip())
    return url if urlparse(url).scheme in ("http", "https") else None


def _published(item) -> str:
    now = datetime.now(timezone.utc)
    for key in ("published_parsed", "updated_parsed", "created_parsed"):
        value = item.get(key)
        if value:
            try:
                # Некоторые ленты ставят даты из будущего — не даём им висеть наверху списка
                return min(datetime(*value[:6], tzinfo=timezone.utc), now).strftime(TS_FORMAT)
            except (TypeError, ValueError):
                continue
    return now.strftime(TS_FORMAT)


def _entries(parsed, base_url: str) -> list[Entry]:
    entries = []
    for item in parsed.entries:
        url = _safe_url(item.get("link"), base_url)
        title = _clean(item.get("title")) or url or "Без названия"
        # Ссылка стабильнее guid: у WordPress guid вида ?p=123, а в старой базе статьи хранились по ссылке
        guid = url or _clean(item.get("id")) or hashlib.md5(title.encode()).hexdigest()
        entries.append(Entry(
            guid=guid,
            title=title[:300],
            url=url,
            author=_clean(item.get("author"))[:100] or None,
            published=_published(item),
        ))
    return entries


def _result(response: requests.Response, parsed) -> FetchResult:
    return FetchResult(
        url=response.url,
        title=_clean(parsed.feed.get("title"))[:100] or None,
        site_url=_safe_url(parsed.feed.get("link"), response.url),
        etag=response.headers.get("ETag"),
        modified=response.headers.get("Last-Modified"),
        entries=_entries(parsed, response.url),
    )


def fetch_feed(url: str, etag: str | None = None, modified: str | None = None) -> FetchResult:
    """Загрузка известной ленты. Если лента не менялась (HTTP 304), not_modified=True."""
    response = _http_get(url, etag, modified)
    if response.status_code == 304:
        return FetchResult(url=url, etag=etag, modified=modified, not_modified=True)

    parsed = _parse(response)
    if parsed is None:
        raise FeedError("по ссылке больше нет RSS/Atom-ленты")
    return _result(response, parsed)


def _feed_candidates(page_url: str, html_text: str) -> list[str]:
    soup = BeautifulSoup(html_text, "html.parser")
    candidates = []
    for link in soup.find_all("link", href=True):
        rel = [value.lower() for value in (link.get("rel") or [])]
        if "alternate" in rel and (link.get("type") or "").lower() in FEED_MIME_TYPES:
            candidates.append(urljoin(page_url, link["href"]))

    root = f"{urlparse(page_url).scheme}://{urlparse(page_url).netloc}"
    candidates.extend(root + path for path in COMMON_FEED_PATHS)
    # Убираем дубли, сохраняя порядок
    return list(dict.fromkeys(candidates))


def discover_feed(url: str) -> FetchResult:
    """
    Поиск ленты по ссылке: подходит как прямая ссылка на RSS/Atom,
    так и ссылка на сайт — тогда лента ищется в <link rel="alternate"> и по типовым адресам.
    """
    url = url.strip()
    if not re.match(r"^https?://", url, re.IGNORECASE):
        url = "https://" + url
    if not urlparse(url).netloc:
        raise FeedError("это не похоже на ссылку")

    response = _http_get(url)
    parsed = _parse(response)
    if parsed is not None:
        return _result(response, parsed)

    for candidate in _feed_candidates(response.url, response.text)[:8]:
        try:
            candidate_response = _http_get(candidate)
        except FeedError:
            continue
        parsed = _parse(candidate_response)
        if parsed is not None and parsed.entries:
            logger.info("Для %s найдена лента %s", url, candidate_response.url)
            return _result(candidate_response, parsed)

    raise FeedError("на этой странице не нашлось RSS/Atom-ленты")
