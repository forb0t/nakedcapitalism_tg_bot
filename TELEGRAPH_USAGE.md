# Telegraph Publisher - Руководство по использованию

Программа для создания статей в Telegraph с использованием официального API.

## Установка

Все необходимые зависимости уже включены в `requirements.txt`:
- `requests` - для HTTP запросов
- `beautifulsoup4` - для парсинга HTML

## Быстрый старт

### 1. Простое использование

```python
from telegraph_publisher import TelegraphPublisher

# Создаем издателя (автоматически создаст аккаунт)
publisher = TelegraphPublisher()

# Создаем аккаунт
account = publisher.create_account(
    short_name="MyBot",
    author_name="Article Publisher"
)

# Создаем статью
page = publisher.create_page(
    title="Моя первая статья",
    content="Это содержимое моей статьи."
)

print(f"Статья создана: {page['url']}")
```

### 2. Использование с существующим токеном

```python
# Если у вас уже есть access_token
publisher = TelegraphPublisher(access_token="your_token_here")

page = publisher.create_page(
    title="Статья с существующим аккаунтом",
    content="Контент статьи"
)
```

### 3. Использование через бота

Все функции доступны через Telegram бота с командами:
- `/publish [id]` - Опубликовать статью
- `/publish_all` - Опубликовать все неопубликованные
- `/telegraph_stats` - Статистика

## Методы API

### `create_account(short_name, author_name=None, author_url=None)`

Создает новый аккаунт Telegraph.

**Параметры:**
- `short_name` (str, 1-32 символа) - обязательное, имя аккаунта
- `author_name` (str, 0-128 символов) - имя автора по умолчанию
- `author_url` (str, 0-512 символов) - URL профиля автора

**Возвращает:** Словарь с информацией об аккаунте, включая `access_token`

### `create_page(title, content, author_name=None, author_url=None, return_content=False)`

Создает новую страницу в Telegraph.

**Параметры:**
- `title` (str, 1-256 символов) - обязательное, заголовок страницы
- `content` - контент страницы:
  - Строка с текстом - будет преобразована в параграфы
  - Строка с HTML - будет преобразована в Node формат
  - Список Node объектов - используется напрямую
- `author_name` (str, 0-128 символов) - имя автора
- `author_url` (str, 0-512 символов) - URL профиля автора
- `return_content` (bool) - вернуть контент в ответе

**Возвращает:** Словарь с информацией о странице, включая `url` и `path`

### `get_page(path, return_content=False)`

Получает информацию о существующей странице.

**Параметры:**
- `path` (str) - путь к странице (например, "Sample-Page-12-15")
- `return_content` (bool) - вернуть контент страницы

### `get_account_info(fields=None)`

Получает информацию о текущем аккаунте.

**Параметры:**
- `fields` (list) - список полей для возврата

## Форматы контента

### 1. Простой текст

```python
content = """
Это первый параграф.

Это второй параграф.

И третий параграф.
"""
```

### 2. HTML контент

```python
html_content = """
<h3>Заголовок</h3>
<p>Параграф с <b>жирным</b> текстом и <i>курсивом</i>.</p>
<p>Также <a href="https://example.com">ссылки</a>.</p>
<ul>
    <li>Элемент 1</li>
    <li>Элемент 2</li>
</ul>
"""
```

### 3. Node объекты (продвинутый формат)

```python
custom_content = [
    {
        "tag": "h3",
        "children": ["Заголовок"]
    },
    {
        "tag": "p",
        "children": [
            "Текст с ",
            {
                "tag": "strong",
                "children": ["жирным"]
            },
            " текстом."
        ]
    },
    {
        "tag": "p",
        "children": [
            "Ссылка на ",
            {
                "tag": "a",
                "attrs": {"href": "https://telegra.ph"},
                "children": ["Telegraph"]
            }
        ]
    }
]
```

## Поддерживаемые HTML теги

При преобразовании HTML поддерживаются следующие теги:
- `p` - параграф
- `h1`, `h2`, `h3`, `h4` - заголовки
- `b`, `strong` - жирный текст
- `em`, `i` - курсив
- `a` - ссылки
- `ul`, `ol`, `li` - списки
- `br` - перенос строки
- `blockquote` - цитаты
- `code`, `pre` - код
- `img` - изображения

## Примеры использования

### Создание статьи из текста

```python
publisher = TelegraphPublisher()
publisher.create_account("MyBot")

text = "Это мой первый текст для Telegraph."
page = publisher.create_page("Моя статья", text)
```

### Создание статьи из HTML

```python
html = "<h3>Заголовок</h3><p>Контент статьи</p>"
page = publisher.create_page("HTML статья", html)
```

### Создание статьи с кастомными Node объектами

```python
nodes = [
    {"tag": "h3", "children": ["Заголовок"]},
    {"tag": "p", "children": ["Контент"]}
]
page = publisher.create_page("Кастомная статья", nodes)
```

## Сохранение токена

**Важно:** Сохраните `access_token` после создания аккаунта!

```python
account = publisher.create_account("MyBot")
token = account['access_token']
print(f"Сохраните этот токен: {token}")

# Использование сохраненного токена позже
publisher2 = TelegraphPublisher(access_token=token)
```

## Обработка ошибок

Все методы могут выбрасывать исключения:

```python
try:
    page = publisher.create_page("Заголовок", "Контент")
except Exception as e:
    print(f"Ошибка: {e}")
```

## Интеграция с существующим проектом

Вы можете интегрировать Telegraph publisher с вашим существующим `ArticleProcessor`:

```python
from telegraph_publisher import TelegraphPublisher
from article_processor import ArticleProcessor

processor = ArticleProcessor()
publisher = TelegraphPublisher(access_token="your_token")

# Получаем контент статьи
content = processor.fetch_article_content("https://example.com/article")

# Публикуем в Telegraph
page = publisher.create_page("Заголовок", content)
```

## Дополнительная информация

- [Официальная документация Telegraph API](https://telegra.ph/api)
- Все запросы используют HTTPS
- Максимальный размер контента: 64 KB
- Статьи автоматически получают Instant View в Telegram

