"""
Модуль для конвертации статей Naked Capitalism в Telegraph статьи
"""

import sqlite3
import logging
from typing import Optional, Dict, List, Tuple
from article_processor import ArticleProcessor
from telegraph_publisher import TelegraphPublisher


class TelegraphArticleConverter:
    """Класс для конвертации статей из базы данных в Telegraph"""
    
    def __init__(self, db_path='articles.db', telegraph_token: Optional[str] = None):
        """
        Инициализация конвертера
        
        Args:
            db_path: Путь к базе данных статей
            telegraph_token: Токен Telegraph (если нет, будет создан новый аккаунт)
        """
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.processor = ArticleProcessor(db_path)
        self.publisher = TelegraphPublisher(access_token=telegraph_token)
        
        # Настройка логирования
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
        # Инициализация базы данных
        self.setup_database()
    
    def setup_database(self):
        """Обновление базы данных: добавление поля для Telegraph URL"""
        cursor = self.conn.cursor()
        
        # Проверяем, существует ли колонка telegraph_url
        cursor.execute("PRAGMA table_info(articles)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'telegraph_url' not in columns:
            cursor.execute('ALTER TABLE articles ADD COLUMN telegraph_url TEXT')
            cursor.execute('ALTER TABLE articles ADD COLUMN telegraph_path TEXT')
            cursor.execute('ALTER TABLE articles ADD COLUMN telegraph_published_at TIMESTAMP')
            self.conn.commit()
            self.logger.info("База данных обновлена: добавлены поля для Telegraph")
    
    def ensure_telegraph_account(self):
        """Проверка и создание аккаунта Telegraph при необходимости"""
        if not self.publisher.access_token:
            self.logger.info("Создание нового аккаунта Telegraph...")
            account = self.publisher.create_account(
                short_name="NakedCapitalismBot",
                author_name="Naked Capitalism",
                author_url="https://www.nakedcapitalism.com/"
            )
            self.publisher.access_token = account.get('access_token')
            self.logger.info(f"✓ Аккаунт создан. Token: {account.get('access_token')[:20]}...")
            return account.get('access_token')
        return self.publisher.access_token
    
    def get_article_by_id(self, article_id: int) -> Optional[Tuple]:
        """Получение статьи по ID"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT id, title, url, author, date_posted, telegraph_url
            FROM articles
            WHERE id = ?
        ''', (article_id,))
        return cursor.fetchone()
    
    def get_unpublished_articles(self, limit: Optional[int] = None) -> List[Tuple]:
        """Получение статей, которые еще не опубликованы в Telegraph"""
        cursor = self.conn.cursor()
        query = '''
            SELECT id, title, url, author, date_posted
            FROM articles
            WHERE telegraph_url IS NULL
            ORDER BY created_at DESC
        '''
        if limit:
            query += f' LIMIT {limit}'
        cursor.execute(query)
        return cursor.fetchall()
    
    def get_published_articles(self, limit: Optional[int] = None) -> List[Tuple]:
        """Получение статей, которые уже опубликованы в Telegraph"""
        cursor = self.conn.cursor()
        query = '''
            SELECT id, title, url, author, date_posted, telegraph_url
            FROM articles
            WHERE telegraph_url IS NOT NULL
            ORDER BY telegraph_published_at DESC
        '''
        if limit:
            query += f' LIMIT {limit}'
        cursor.execute(query)
        return cursor.fetchall()
    
    def fetch_article_full_content(self, url: str) -> Optional[str]:
        """Получение полного контента статьи"""
        try:
            # Используем ArticleProcessor для получения контента
            content = self.processor.fetch_article_content(url)
            
            if content:
                # Добавляем информацию об источнике в конец статьи
                source_note = f"\n\n---\n\nИсточник: {url}"
                return content + source_note
            
            return None
        except Exception as e:
            self.logger.error(f"Ошибка при получении контента статьи {url}: {e}")
            return None
    
    def format_article_for_telegraph(self, title: str, content: str, author: str, 
                                     original_url: str) -> List[Dict]:
        """
        Форматирование статьи для публикации в Telegraph
        
        Args:
            title: Заголовок статьи
            content: Контент статьи
            author: Автор статьи
            original_url: Оригинальная ссылка
        
        Returns:
            Список Node объектов для Telegraph
        """
        nodes = []
        
        # Заголовок
        nodes.append({
            "tag": "h3",
            "children": [title]
        })
        
        # Информация об авторе и дате
        author_info = f"Автор: {author}" if author and author != "Unknown" else "Naked Capitalism"
        nodes.append({
            "tag": "p",
            "children": [
                {
                    "tag": "em",
                    "children": [author_info]
                }
            ]
        })
        
        # Разделитель
        nodes.append({"tag": "hr"})
        
        # Контент статьи (разбиваем на параграфы)
        if content:
            paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
            
            for paragraph in paragraphs:
                # Разбиваем параграф на строки
                lines = paragraph.split('\n')
                for line in lines:
                    line = line.strip()
                    if line and len(line) > 5:
                        # Проверяем, не является ли строка ссылкой
                        if line.startswith('http://') or line.startswith('https://'):
                            nodes.append({
                                "tag": "p",
                                "children": [
                                    {
                                        "tag": "a",
                                        "attrs": {"href": line},
                                        "children": [line]
                                    }
                                ]
                            })
                        else:
                            nodes.append({
                                "tag": "p",
                                "children": [line]
                            })
        else:
            # Если контент отсутствует, добавляем сообщение
            nodes.append({
                "tag": "p",
                "children": ["Контент статьи недоступен. Пожалуйста, посетите оригинальную статью по ссылке ниже."]
            })
        
        # Разделитель перед ссылкой на оригинал
        nodes.append({"tag": "hr"})
        
        # Ссылка на оригинальную статью
        nodes.append({
            "tag": "p",
            "children": [
                "📰 ",
                {
                    "tag": "a",
                    "attrs": {"href": original_url},
                    "children": ["Оригинальная статья на Naked Capitalism"]
                }
            ]
        })
        
        return nodes
    
    def publish_article_to_telegraph(self, article_id: int) -> Optional[Dict]:
        """
        Публикация статьи в Telegraph
        
        Args:
            article_id: ID статьи в базе данных
        
        Returns:
            Словарь с информацией о созданной странице Telegraph или None при ошибке
        """
        # Получаем статью из базы
        article = self.get_article_by_id(article_id)
        
        if not article:
            self.logger.error(f"Статья с ID {article_id} не найдена")
            return None
        
        article_id_db, title, url, author, date_posted, telegraph_url = article
        
        # Проверяем, не опубликована ли уже
        if telegraph_url:
            self.logger.warning(f"Статья {article_id} уже опубликована: {telegraph_url}")
            return {"url": telegraph_url}
        
        # Убеждаемся, что есть аккаунт Telegraph
        self.ensure_telegraph_account()
        
        # Получаем контент статьи
        self.logger.info(f"Получение контента статьи: {title}")
        content = self.fetch_article_full_content(url)
        
        if not content or len(content.strip()) < 50:
            self.logger.error(f"Не удалось получить контент статьи {url} или контент слишком короткий")
            return None
        
        # Форматируем для Telegraph
        telegraph_content = self.format_article_for_telegraph(title, content, author, url)
        
        # Публикуем в Telegraph
        try:
            self.logger.info(f"Публикация статьи в Telegraph: {title}")
            page = self.publisher.create_page(
                title=title,
                content=telegraph_content,
                author_name=author if author and author != "Unknown" else "Naked Capitalism",
                author_url=url,
                return_content=False
            )
            
            # Сохраняем ссылку в базу данных
            cursor = self.conn.cursor()
            cursor.execute('''
                UPDATE articles
                SET telegraph_url = ?,
                    telegraph_path = ?,
                    telegraph_published_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (page.get('url'), page.get('path'), article_id))
            self.conn.commit()
            
            self.logger.info(f"✓ Статья опубликована: {page.get('url')}")
            return page
            
        except Exception as e:
            self.logger.error(f"Ошибка при публикации статьи в Telegraph: {e}")
            return None
    
    def publish_multiple_articles(self, article_ids: Optional[List[int]] = None, 
                                  limit: int = 10) -> List[Dict]:
        """
        Публикация нескольких статей
        
        Args:
            article_ids: Список ID статей (если None, берутся неопубликованные)
            limit: Максимальное количество статей для публикации
        
        Returns:
            Список результатов публикации
        """
        results = []
        
        if article_ids:
            # Публикуем указанные статьи
            articles_to_publish = article_ids
        else:
            # Получаем неопубликованные статьи
            unpublished = self.get_unpublished_articles(limit=limit)
            articles_to_publish = [article[0] for article in unpublished]
        
        self.logger.info(f"Начало публикации {len(articles_to_publish)} статей в Telegraph")
        
        for article_id in articles_to_publish:
            try:
                result = self.publish_article_to_telegraph(article_id)
                if result:
                    results.append({
                        "article_id": article_id,
                        "success": True,
                        "telegraph_url": result.get('url')
                    })
                else:
                    results.append({
                        "article_id": article_id,
                        "success": False,
                        "error": "Ошибка публикации"
                    })
            except Exception as e:
                self.logger.error(f"Ошибка при публикации статьи {article_id}: {e}")
                results.append({
                    "article_id": article_id,
                    "success": False,
                    "error": str(e)
                })
        
        self.logger.info(f"Публикация завершена: {sum(1 for r in results if r['success'])}/{len(results)} успешно")
        return results
    
    def get_statistics(self) -> Dict:
        """Получение статистики по публикациям"""
        cursor = self.conn.cursor()
        
        # Всего статей
        cursor.execute("SELECT COUNT(*) FROM articles")
        total = cursor.fetchone()[0]
        
        # Опубликовано в Telegraph
        cursor.execute("SELECT COUNT(*) FROM articles WHERE telegraph_url IS NOT NULL")
        published = cursor.fetchone()[0]
        
        # Не опубликовано
        unpublished = total - published
        
        return {
            "total_articles": total,
            "published_telegraph": published,
            "unpublished": unpublished,
            "publish_percentage": round((published / total * 100) if total > 0 else 0, 2)
        }
    
    def close(self):
        """Закрытие соединений"""
        if self.conn:
            self.conn.close()
        if self.processor:
            self.processor.close()


def main():
    """Пример использования"""
    converter = TelegraphArticleConverter()
    
    try:
        # Получаем статистику
        stats = converter.get_statistics()
        print(f"📊 Статистика:")
        print(f"   Всего статей: {stats['total_articles']}")
        print(f"   Опубликовано в Telegraph: {stats['published_telegraph']}")
        print(f"   Не опубликовано: {stats['unpublished']}")
        print(f"   Процент: {stats['publish_percentage']}%")
        
        # Публикуем первые 5 неопубликованных статей
        print("\n🚀 Публикация статей в Telegraph...")
        results = converter.publish_multiple_articles(limit=5)
        
        print(f"\n✓ Результаты:")
        for result in results:
            if result['success']:
                print(f"   ✓ Статья {result['article_id']}: {result['telegraph_url']}")
            else:
                print(f"   ✗ Статья {result['article_id']}: {result.get('error', 'Ошибка')}")
        
    finally:
        converter.close()


if __name__ == "__main__":
    main()

