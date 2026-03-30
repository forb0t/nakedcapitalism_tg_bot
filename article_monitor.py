"""
Мониторинг новых статей с сайта Naked Capitalism
"""

import hashlib
import json
import logging
import os
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


def _data_dir() -> Path:
    path = Path(os.environ.get("NAKEDCAP_DATA_DIR", ".")).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


class NakedCapitalismMonitor:
    def __init__(self):
        self._data_dir = _data_dir()
        self.base_url = "https://www.nakedcapitalism.com/"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        self.setup_database()
        self.setup_logging()
    
    def setup_logging(self):
        """Настройка логирования"""
        log_path = self._data_dir / "nakedcap_monitor.log"
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_path, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def setup_database(self):
        """Создание базы данных для хранения статей"""
        self.conn = sqlite3.connect(str(self._data_dir / "articles.db"))
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                url TEXT UNIQUE NOT NULL,
                author TEXT,
                date_posted TEXT,
                content_hash TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self.conn.commit()
    
    def get_page_content(self, url):
        """Получение содержимого страницы"""
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            self.logger.error(f"Ошибка при получении страницы {url}: {e}")
            return None
    
    def parse_articles(self, html_content):
        """Парсинг статей с главной страницы"""
        soup = BeautifulSoup(html_content, 'html.parser')
        articles = []
        
        # Поиск статей в разделе "Recent Items"
        recent_items = soup.find('div', {'id': 'content'}) or soup.find('main')
        if recent_items:
            # Поиск заголовков статей
            article_links = recent_items.find_all('a', href=True)
            
            for link in article_links:
                href = link.get('href')
                title = link.get_text(strip=True)
                
                # Фильтрация только статей (не навигационных ссылок)
                if (href and title and 
                    len(title) > 15 and 
                    not href.startswith('#') and
                    'nakedcapitalism.com' in href and
                    not any(skip in title.lower() for skip in ['comment', 'comments', 'older entries', '←', 'topics:', 'posted by'])):
                    
                    full_url = urljoin(self.base_url, href)
                    
                    # Попытка найти автора и дату
                    author = self.extract_author(link)
                    date_posted = self.extract_date(link)
                    
                    articles.append({
                        'title': title,
                        'url': full_url,
                        'author': author,
                        'date_posted': date_posted,
                        'content_hash': hashlib.md5(title.encode()).hexdigest()
                    })
        
        return articles
    
    def extract_author(self, element):
        """Извлечение автора статьи"""
        # Поиск автора в соседних элементах
        parent = element.parent
        if parent:
            author_elem = parent.find('span', class_='author') or parent.find('em')
            if author_elem:
                return author_elem.get_text(strip=True)
        return "Unknown"
    
    def extract_date(self, element):
        """Извлечение даты статьи"""
        parent = element.parent
        if parent:
            date_elem = parent.find('span', class_='date') or parent.find('time')
            if date_elem:
                return date_elem.get_text(strip=True)
        return datetime.now().strftime('%Y-%m-%d')
    
    def save_articles(self, articles):
        """Сохранение статей в базу данных"""
        cursor = self.conn.cursor()
        new_articles = []
        
        for article in articles:
            try:
                cursor.execute('''
                    INSERT OR IGNORE INTO articles (title, url, author, date_posted, content_hash)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    article['title'],
                    article['url'],
                    article['author'],
                    article['date_posted'],
                    article['content_hash']
                ))
                
                if cursor.rowcount > 0:
                    new_articles.append(article)
                    
            except sqlite3.Error as e:
                self.logger.error(f"Ошибка при сохранении статьи: {e}")
        
        self.conn.commit()
        return new_articles
    
    def check_for_new_articles(self):
        """Проверка новых статей"""
        self.logger.info("Проверка новых статей...")
        
        # Получение главной страницы
        html_content = self.get_page_content(self.base_url)
        if not html_content:
            self.logger.error("Не удалось получить содержимое главной страницы")
            return []
        
        # Парсинг статей
        articles = self.parse_articles(html_content)
        self.logger.info(f"Найдено {len(articles)} статей")
        
        # Сохранение в базу данных
        new_articles = self.save_articles(articles)
        
        if new_articles:
            self.logger.info(f"Обнаружено {len(new_articles)} новых статей:")
            for article in new_articles:
                self.logger.info(f"- {article['title']} by {article['author']}")
        else:
            self.logger.info("Новых статей не найдено")
        
        return new_articles
    
    def get_latest_articles(self, limit=10, offset=0):
        """Получение последних статей из базы данных с поддержкой пагинации"""
        cursor = self.conn.cursor()
        # Проверяем, существует ли колонка telegraph_url
        cursor.execute("PRAGMA table_info(articles)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'telegraph_url' in columns:
            cursor.execute('''
                SELECT title, url, author, date_posted, created_at, telegraph_url
                FROM articles
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            ''', (limit, offset))
        else:
            cursor.execute('''
                SELECT title, url, author, date_posted, created_at, NULL as telegraph_url
                FROM articles
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            ''', (limit, offset))
        
        return cursor.fetchall()
    
    def get_total_articles_count(self):
        """Получение общего количества статей"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM articles")
        return cursor.fetchone()[0]
    
    def run_monitoring(self, interval_hours=1):
        """Запуск мониторинга с заданным интервалом"""
        self.logger.info(f"Запуск мониторинга с интервалом {interval_hours} час(ов)")
        
        try:
            while True:
                new_articles = self.check_for_new_articles()
                
                if new_articles:
                    # Здесь можно добавить отправку уведомлений
                    self.notify_new_articles(new_articles)
                
                # Ожидание до следующей проверки
                sleep_seconds = interval_hours * 3600
                self.logger.info(f"Ожидание {interval_hours} час(ов) до следующей проверки...")
                time.sleep(sleep_seconds)
                
        except KeyboardInterrupt:
            self.logger.info("Мониторинг остановлен пользователем")
        except Exception as e:
            self.logger.error(f"Ошибка в мониторинге: {e}")
        finally:
            self.conn.close()
    
    def notify_new_articles(self, articles):
        """Уведомление о новых статьях (заглушка для интеграции с ботом)"""
        self.logger.info("=== НОВЫЕ СТАТЬИ ===")
        for article in articles:
            self.logger.info(f"📰 {article['title']}")
            self.logger.info(f"👤 Автор: {article['author']}")
            self.logger.info(f"🔗 URL: {article['url']}")
            self.logger.info("-" * 50)

def main():
    """Основная функция для запуска мониторинга"""
    monitor = NakedCapitalismMonitor()
    
    print("🔍 Мониторинг статей Naked Capitalism")
    print("=" * 50)
    
    # Первоначальная проверка
    new_articles = monitor.check_for_new_articles()
    
    if new_articles:
        print(f"\n✅ Найдено {len(new_articles)} новых статей!")
        for article in new_articles:
            print(f"📰 {article['title']} - {article['author']}")
    else:
        print("\n📝 Новых статей не найдено")
    
    # Показ последних статей
    print("\n📚 Последние статьи в базе:")
    latest = monitor.get_latest_articles(5)
    for article in latest:
        print(f"- {article[0]} ({article[2]}) - {article[3]}")
    
    print("\n🚀 Запуск автоматического мониторинга...")
    print("Нажмите Ctrl+C для остановки")
    
    # Запуск мониторинга
    monitor.run_monitoring(interval_hours=1)

if __name__ == "__main__":
    main()
