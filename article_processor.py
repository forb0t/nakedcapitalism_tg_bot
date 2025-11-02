"""
Процессор статей для извлечения контента
"""

import requests
import re
from datetime import datetime
from bs4 import BeautifulSoup
import sqlite3
import time

class ArticleProcessor:
    def __init__(self, db_path='articles.db'):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
    
    def close(self):
        """Закрытие соединения с базой данных"""
        if self.conn:
            self.conn.close()
    
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
