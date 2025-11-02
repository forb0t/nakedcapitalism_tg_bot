"""
Конвертер статей в формат Teletype
"""

import re
import html
from datetime import datetime
from urllib.parse import urlparse
import sqlite3

class TeletypeConverter:
    def __init__(self):
        self.setup_database()
    
    def setup_database(self):
        """Подключение к базе данных статей"""
        self.conn = sqlite3.connect('articles.db')
    
    def clean_text(self, text):
        """Очистка текста от HTML тегов и специальных символов"""
        if not text:
            return ""
        
        # Декодирование HTML entities
        text = html.unescape(text)
        
        # Удаление HTML тегов
        text = re.sub(r'<[^>]+>', '', text)
        
        # Удаление лишних пробелов и переносов строк
        text = re.sub(r'\s+', ' ', text)
        
        # Удаление специальных символов
        text = re.sub(r'[^\w\s\-.,!?():;"\'@#$%&*+=<>/\\|~`]', '', text)
        
        return text.strip()
    
    def format_date(self, date_str):
        """Форматирование даты для Teletype"""
        try:
            # Парсинг различных форматов дат
            if isinstance(date_str, str):
                # Попытка распарсить дату
                for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%B %d, %Y']:
                    try:
                        dt = datetime.strptime(date_str, fmt)
                        return dt.strftime('%Y-%m-%d')
                    except ValueError:
                        continue
            return str(date_str)
        except:
            return datetime.now().strftime('%Y-%m-%d')
    
    def extract_domain(self, url):
        """Извлечение домена из URL"""
        try:
            parsed = urlparse(url)
            return parsed.netloc
        except:
            return "nakedcapitalism.com"
    
    def format_teletype_post(self, article):
        """Форматирование статьи в формат Teletype"""
        
        # Очистка и форматирование данных
        title = self.clean_text(article.get('title', ''))
        author = self.clean_text(article.get('author', 'Unknown'))
        date_posted = self.format_date(article.get('date_posted', ''))
        url = article.get('url', '')
        domain = self.extract_domain(url)
        
        # Создание метаданных для Teletype
        metadata = {
            'title': title,
            'author': author,
            'date': date_posted,
            'source': domain,
            'url': url,
            'tags': self.generate_tags(title, author),
            'category': self.categorize_article(title),
            'word_count': len(title.split()),
            'created_at': datetime.now().isoformat()
        }
        
        # Форматирование контента
        content = self.create_teletype_content(metadata, article)
        
        return {
            'metadata': metadata,
            'content': content,
            'teletype_format': self.create_teletype_format(metadata, content)
        }
    
    def generate_tags(self, title, author):
        """Генерация тегов на основе заголовка и автора"""
        tags = []
        
        # Базовые теги
        tags.extend(['naked-capitalism', 'finance', 'economics'])
        
        # Теги на основе ключевых слов в заголовке
        title_lower = title.lower()
        
        keyword_tags = {
            'trump': 'politics',
            'economy': 'economics',
            'finance': 'finance',
            'bank': 'banking',
            'market': 'markets',
            'ai': 'technology',
            'tech': 'technology',
            'climate': 'environment',
            'green': 'environment',
            'health': 'healthcare',
            'medical': 'healthcare',
            'china': 'geopolitics',
            'russia': 'geopolitics',
            'war': 'geopolitics',
            'military': 'geopolitics',
            'housing': 'real-estate',
            'real estate': 'real-estate',
            'commodities': 'commodities',
            'oil': 'energy',
            'energy': 'energy',
            'crypto': 'cryptocurrency',
            'bitcoin': 'cryptocurrency',
            'inflation': 'macro-economics',
            'fed': 'federal-reserve',
            'federal reserve': 'federal-reserve'
        }
        
        for keyword, tag in keyword_tags.items():
            if keyword in title_lower:
                tags.append(tag)
        
        # Уникальные теги
        return list(set(tags))[:10]  # Максимум 10 тегов
    
    def categorize_article(self, title):
        """Категоризация статьи на основе заголовка"""
        title_lower = title.lower()
        
        if any(word in title_lower for word in ['links', 'daily', 'roundup']):
            return 'daily-links'
        elif any(word in title_lower for word in ['analysis', 'report', 'study']):
            return 'analysis'
        elif any(word in title_lower for word in ['opinion', 'commentary', 'view']):
            return 'opinion'
        elif any(word in title_lower for word in ['news', 'breaking', 'update']):
            return 'news'
        elif any(word in title_lower for word in ['interview', 'talk', 'discussion']):
            return 'interview'
        else:
            return 'general'
    
    def create_teletype_content(self, metadata, article):
        """Создание контента для Teletype"""
        
        content_parts = []
        
        # Заголовок
        content_parts.append(f"# {metadata['title']}")
        content_parts.append("")
        
        # Метаданные
        content_parts.append("## Article Information")
        content_parts.append(f"**Author:** {metadata['author']}")
        content_parts.append(f"**Date:** {metadata['date']}")
        content_parts.append(f"**Source:** {metadata['source']}")
        content_parts.append(f"**Category:** {metadata['category']}")
        content_parts.append(f"**Tags:** {', '.join(metadata['tags'])}")
        content_parts.append("")
        
        # Ссылка на оригинал
        content_parts.append("## Original Article")
        content_parts.append(f"[Read full article on {metadata['source']}]({metadata['url']})")
        content_parts.append("")
        
        # Сводка (заглушка для будущего контента)
        content_parts.append("## Summary")
        content_parts.append(f"*This article from {metadata['source']} discusses {self.generate_summary(metadata['title'])}*")
        content_parts.append("")
        
        # Теги в формате Teletype
        content_parts.append("## Tags")
        for tag in metadata['tags']:
            content_parts.append(f"#{tag}")
        content_parts.append("")
        
        # Метаданные для поиска
        content_parts.append("---")
        content_parts.append(f"**Original URL:** {metadata['url']}")
        content_parts.append(f"**Converted:** {metadata['created_at']}")
        content_parts.append(f"**Word Count:** {metadata['word_count']}")
        
        return "\n".join(content_parts)
    
    def generate_summary(self, title):
        """Генерация краткого описания на основе заголовка"""
        # Простая генерация описания на основе ключевых слов
        title_lower = title.lower()
        
        if 'trump' in title_lower:
            return "political developments and policy implications"
        elif any(word in title_lower for word in ['economy', 'economic', 'finance']):
            return "economic trends and financial analysis"
        elif any(word in title_lower for word in ['market', 'trading', 'investment']):
            return "market analysis and investment insights"
        elif any(word in title_lower for word in ['ai', 'tech', 'technology']):
            return "technological developments and their implications"
        elif any(word in title_lower for word in ['climate', 'environment']):
            return "environmental issues and climate policy"
        elif any(word in title_lower for word in ['health', 'medical']):
            return "healthcare and medical industry developments"
        else:
            return "current events and analysis"
    
    def create_teletype_format(self, metadata, content):
        """Создание полного формата Teletype"""
        
        teletype_post = {
            'id': f"nakedcap_{hash(metadata['url']) % 1000000}",
            'title': metadata['title'],
            'author': {
                'name': metadata['author'],
                'username': metadata['author'].lower().replace(' ', '_'),
                'avatar': None
            },
            'content': content,
            'tags': metadata['tags'],
            'category': metadata['category'],
            'metadata': {
                'source': metadata['source'],
                'original_url': metadata['url'],
                'published_date': metadata['date'],
                'word_count': metadata['word_count'],
                'converted_at': metadata['created_at']
            },
            'stats': {
                'views': 0,
                'likes': 0,
                'comments': 0,
                'shares': 0
            },
            'format': 'markdown',
            'visibility': 'public',
            'featured': False
        }
        
        return teletype_post
    
    def convert_article_by_id(self, article_id):
        """Конвертация конкретной статьи по ID"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT title, url, author, date_posted
            FROM articles 
            WHERE id = ?
        ''', (article_id,))
        
        article_data = cursor.fetchone()
        if not article_data:
            return None
        
        article = {
            'title': article_data[0],
            'url': article_data[1],
            'author': article_data[2],
            'date_posted': article_data[3]
        }
        
        return self.format_teletype_post(article)
    
    def convert_latest_articles(self, limit=5):
        """Конвертация последних статей"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT title, url, author, date_posted
            FROM articles 
            ORDER BY created_at DESC
            LIMIT ?
        ''', (limit,))
        
        articles_data = cursor.fetchall()
        converted_articles = []
        
        for article_data in articles_data:
            article = {
                'title': article_data[0],
                'url': article_data[1],
                'author': article_data[2],
                'date_posted': article_data[3]
            }
            
            converted = self.format_teletype_post(article)
            converted_articles.append(converted)
        
        return converted_articles
    
    def convert_articles_by_category(self, category, limit=10):
        """Конвертация статей по категории"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT title, url, author, date_posted
            FROM articles 
            ORDER BY created_at DESC
            LIMIT ?
        ''', (limit,))
        
        articles_data = cursor.fetchall()
        converted_articles = []
        
        for article_data in articles_data:
            article = {
                'title': article_data[0],
                'url': article_data[1],
                'author': article_data[2],
                'date_posted': article_data[3]
            }
            
            converted = self.format_teletype_post(article)
            
            # Фильтрация по категории
            if converted['metadata']['category'] == category:
                converted_articles.append(converted)
        
        return converted_articles
    
    def export_to_teletype_format(self, articles, filename='teletype_export.json'):
        """Экспорт статей в JSON формат для Teletype"""
        import json
        
        export_data = {
            'export_info': {
                'created_at': datetime.now().isoformat(),
                'source': 'naked-capitalism',
                'total_articles': len(articles),
                'format_version': '1.0'
            },
            'articles': articles
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        return filename
    
    def close(self):
        """Закрытие соединения с базой данных"""
        self.conn.close()

def main():
    """Демонстрация работы конвертера"""
    converter = TeletypeConverter()
    
    print("🔄 Конвертация статей в формат Teletype")
    print("=" * 50)
    
    # Конвертация последних 3 статей
    articles = converter.convert_latest_articles(3)
    
    print(f"✅ Конвертировано {len(articles)} статей")
    
    for i, article in enumerate(articles, 1):
        print(f"\n📰 Статья {i}:")
        print(f"   Заголовок: {article['metadata']['title']}")
        print(f"   Автор: {article['metadata']['author']}")
        print(f"   Категория: {article['metadata']['category']}")
        print(f"   Теги: {', '.join(article['metadata']['tags'][:5])}")
        print(f"   URL: {article['metadata']['url']}")
    
    # Экспорт в файл
    filename = converter.export_to_teletype_format(articles)
    print(f"\n💾 Статьи экспортированы в файл: {filename}")
    
    # Показать пример контента
    if articles:
        print(f"\n📝 Пример контента первой статьи:")
        print("-" * 40)
        print(articles[0]['content'][:500] + "...")
    
    converter.close()
    print("\n✅ Конвертация завершена!")

if __name__ == "__main__":
    main()
