"""
Расширенный процессор статей для извлечения контента и создания полноценных постов Teletype
"""

import requests
import re
from datetime import datetime
from bs4 import BeautifulSoup
from teletype_converter import TeletypeConverter
import time

class ArticleProcessor(TeletypeConverter):
    def __init__(self):
        super().__init__()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
    
    def fetch_article_content(self, url):
        """Получение полного контента статьи"""
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Извлечение основного контента статьи
            content_selectors = [
                'div.entry-content',
                'div.post-content',
                'div.article-content',
                'div.content',
                'article',
                'main'
            ]
            
            article_content = None
            for selector in content_selectors:
                article_content = soup.select_one(selector)
                if article_content:
                    break
            
            if not article_content:
                # Fallback: поиск по классам
                article_content = soup.find('div', class_=re.compile(r'content|entry|post|article'))
            
            if article_content:
                # Очистка контента
                content_text = self.extract_text_content(article_content)
                return content_text
            else:
                return None
                
        except Exception as e:
            print(f"Ошибка при получении контента статьи {url}: {e}")
            return None
    
    def extract_text_content(self, soup_element):
        """Извлечение текстового контента из HTML элемента"""
        # Удаление ненужных элементов
        for element in soup_element.find_all(['script', 'style', 'nav', 'footer', 'header', 'aside']):
            element.decompose()
        
        # Удаление элементов с классами рекламы
        for element in soup_element.find_all(class_=re.compile(r'ads|advertisement|sponsor|promo')):
            element.decompose()
        
        # Извлечение текста
        text_content = soup_element.get_text(separator='\n', strip=True)
        
        # Очистка текста
        lines = text_content.split('\n')
        cleaned_lines = []
        
        for line in lines:
            line = line.strip()
            if line and len(line) > 10:  # Пропускаем короткие строки
                cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines)
    
    def create_full_teletype_post(self, article_id):
        """Создание полноценного поста Teletype с контентом"""
        # Получение базовой информации о статье
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
        
        # Получение полного контента статьи
        print(f"📡 Получение контента статьи: {article['title']}")
        full_content = self.fetch_article_content(article['url'])
        
        if full_content:
            # Создание расширенного контента
            enhanced_content = self.create_enhanced_teletype_content(article, full_content)
            
            # Базовое форматирование
            teletype_post = self.format_teletype_post(article)
            
            # Замена контента на расширенный
            teletype_post['content'] = enhanced_content
            teletype_post['metadata']['has_full_content'] = True
            teletype_post['metadata']['content_length'] = len(full_content)
            
            return teletype_post
        else:
            # Возврат базового поста без полного контента
            teletype_post = self.format_teletype_post(article)
            teletype_post['metadata']['has_full_content'] = False
            return teletype_post
    
    def create_enhanced_teletype_content(self, article, full_content):
        """Создание расширенного контента для Teletype"""
        
        content_parts = []
        
        # Заголовок
        content_parts.append(f"# {article['title']}")
        content_parts.append("")
        
        # Метаданные
        content_parts.append("## 📰 Article Information")
        content_parts.append(f"**Author:** {article['author']}")
        content_parts.append(f"**Date:** {self.format_date(article['date_posted'])}")
        content_parts.append(f"**Source:** {self.extract_domain(article['url'])}")
        content_parts.append("")
        
        # Краткое содержание (первые абзацы)
        summary = self.extract_summary(full_content)
        if summary:
            content_parts.append("## 📝 Summary")
            content_parts.append(summary)
            content_parts.append("")
        
        # Основной контент
        content_parts.append("## 📖 Full Article")
        content_parts.append(self.format_article_content(full_content))
        content_parts.append("")
        
        # Ссылки и дополнительные материалы
        content_parts.append("## 🔗 References")
        content_parts.append(f"[Read original article on {self.extract_domain(article['url'])}]({article['url']})")
        content_parts.append("")
        
        # Теги
        tags = self.generate_tags(article['title'], article['author'])
        content_parts.append("## 🏷️ Tags")
        for tag in tags:
            content_parts.append(f"#{tag}")
        content_parts.append("")
        
        # Метаданные
        content_parts.append("---")
        content_parts.append(f"**Original URL:** {article['url']}")
        content_parts.append(f"**Content Length:** {len(full_content)} characters")
        content_parts.append(f"**Converted:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        return "\n".join(content_parts)
    
    def extract_summary(self, content, max_sentences=3):
        """Извлечение краткого содержания из контента"""
        # Разбиение на предложения
        sentences = re.split(r'[.!?]+', content)
        
        # Фильтрация коротких предложений
        valid_sentences = [s.strip() for s in sentences if len(s.strip()) > 20]
        
        if valid_sentences:
            # Берем первые несколько предложений
            summary_sentences = valid_sentences[:max_sentences]
            return '. '.join(summary_sentences) + '.'
        
        return None
    
    def format_article_content(self, content):
        """Форматирование контента статьи для Teletype"""
        # Разбиение на абзацы
        paragraphs = content.split('\n\n')
        formatted_paragraphs = []
        
        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if len(paragraph) > 50:  # Пропускаем короткие абзацы
                formatted_paragraphs.append(paragraph)
        
        # Ограничение длины контента
        max_length = 5000  # Максимум 5000 символов
        full_content = '\n\n'.join(formatted_paragraphs)
        
        if len(full_content) > max_length:
            full_content = full_content[:max_length] + "\n\n*[Content truncated for brevity]*"
        
        return full_content
    
    def process_multiple_articles(self, article_ids, delay=1):
        """Обработка нескольких статей с задержкой"""
        processed_articles = []
        
        for i, article_id in enumerate(article_ids, 1):
            print(f"🔄 Обработка статьи {i}/{len(article_ids)} (ID: {article_id})")
            
            article = self.create_full_teletype_post(article_id)
            if article:
                processed_articles.append(article)
                print(f"✅ Статья обработана: {article['metadata']['title']}")
            else:
                print(f"❌ Ошибка обработки статьи ID: {article_id}")
            
            # Задержка между запросами
            if i < len(article_ids):
                time.sleep(delay)
        
        return processed_articles
    
    def batch_convert_latest_articles(self, limit=5, delay=2):
        """Пакетная конвертация последних статей"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT id, title, url, author, date_posted
            FROM articles 
            ORDER BY created_at DESC
            LIMIT ?
        ''', (limit,))
        
        articles_data = cursor.fetchall()
        
        print(f"🚀 Начинаем пакетную конвертацию {len(articles_data)} статей")
        
        processed_articles = []
        
        for i, (article_id, title, url, author, date_posted) in enumerate(articles_data, 1):
            print(f"\n📰 Статья {i}/{len(articles_data)}: {title}")
            
            article = {
                'title': title,
                'url': url,
                'author': author,
                'date_posted': date_posted
            }
            
            # Получение контента
            full_content = self.fetch_article_content(url)
            
            if full_content:
                enhanced_content = self.create_enhanced_teletype_content(article, full_content)
                teletype_post = self.format_teletype_post(article)
                teletype_post['content'] = enhanced_content
                teletype_post['metadata']['has_full_content'] = True
                teletype_post['metadata']['content_length'] = len(full_content)
                
                processed_articles.append(teletype_post)
                print(f"✅ Полный контент получен ({len(full_content)} символов)")
            else:
                # Базовый пост без полного контента
                teletype_post = self.format_teletype_post(article)
                teletype_post['metadata']['has_full_content'] = False
                processed_articles.append(teletype_post)
                print(f"⚠️ Контент не получен, создан базовый пост")
            
            # Задержка между запросами
            if i < len(articles_data):
                print(f"⏳ Ожидание {delay} секунд...")
                time.sleep(delay)
        
        return processed_articles

def main():
    """Демонстрация расширенной обработки статей"""
    processor = ArticleProcessor()
    
    print("🔄 Расширенная обработка статей для Teletype")
    print("=" * 60)
    
    # Обработка последних 2 статей с полным контентом
    print("📡 Получение последних статей с полным контентом...")
    articles = processor.batch_convert_latest_articles(limit=2, delay=3)
    
    print(f"\n✅ Обработано {len(articles)} статей")
    
    for i, article in enumerate(articles, 1):
        print(f"\n📰 Статья {i}:")
        print(f"   Заголовок: {article['metadata']['title']}")
        print(f"   Автор: {article['metadata']['author']}")
        print(f"   Полный контент: {'Да' if article['metadata'].get('has_full_content') else 'Нет'}")
        if article['metadata'].get('content_length'):
            print(f"   Длина контента: {article['metadata']['content_length']} символов")
        print(f"   Категория: {article['metadata']['category']}")
        print(f"   Теги: {', '.join(article['metadata']['tags'][:5])}")
    
    # Экспорт в файл
    filename = processor.export_to_teletype_format(articles, 'enhanced_teletype_export.json')
    print(f"\n💾 Статьи экспортированы в файл: {filename}")
    
    # Показать пример контента
    if articles and articles[0]['metadata'].get('has_full_content'):
        print(f"\n📝 Пример контента первой статьи:")
        print("-" * 60)
        content_preview = articles[0]['content'][:800] + "..." if len(articles[0]['content']) > 800 else articles[0]['content']
        print(content_preview)
    
    processor.close()
    print("\n✅ Расширенная обработка завершена!")

if __name__ == "__main__":
    main()
