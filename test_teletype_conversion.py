"""
Тестовый скрипт для проверки конвертации статей в формат Teletype
"""

from teletype_converter import TeletypeConverter
from article_processor import ArticleProcessor
import json

def test_basic_conversion():
    """Тест базовой конвертации"""
    print("🧪 Тест базовой конвертации")
    print("-" * 40)
    
    converter = TeletypeConverter()
    
    # Конвертация последних 3 статей
    articles = converter.convert_latest_articles(3)
    
    print(f"✅ Конвертировано {len(articles)} статей")
    
    for i, article in enumerate(articles, 1):
        print(f"\n📰 Статья {i}:")
        print(f"   Заголовок: {article['metadata']['title'][:50]}...")
        print(f"   Автор: {article['metadata']['author']}")
        print(f"   Категория: {article['metadata']['category']}")
        print(f"   Теги: {len(article['metadata']['tags'])} тегов")
        print(f"   URL: {article['metadata']['url']}")
    
    converter.close()
    return articles

def test_enhanced_conversion():
    """Тест расширенной конвертации с полным контентом"""
    print("\n🔬 Тест расширенной конвертации")
    print("-" * 40)
    
    processor = ArticleProcessor()
    
    # Обработка 1 статьи с полным контентом
    print("📡 Получение одной статьи с полным контентом...")
    articles = processor.batch_convert_latest_articles(limit=1, delay=2)
    
    if articles:
        article = articles[0]
        print(f"\n✅ Статья обработана:")
        print(f"   Заголовок: {article['metadata']['title']}")
        print(f"   Полный контент: {'Да' if article['metadata'].get('has_full_content') else 'Нет'}")
        if article['metadata'].get('content_length'):
            print(f"   Длина контента: {article['metadata']['content_length']} символов")
        print(f"   Категория: {article['metadata']['category']}")
        print(f"   Теги: {', '.join(article['metadata']['tags'])}")
        
        # Показать часть контента
        if len(article['content']) > 200:
            print(f"\n📝 Начало контента:")
            print(article['content'][:300] + "...")
    
    processor.close()
    return articles

def test_export_formats():
    """Тест различных форматов экспорта"""
    print("\n📤 Тест экспорта в различные форматы")
    print("-" * 40)
    
    converter = TeletypeConverter()
    
    # Получение статей для экспорта
    articles = converter.convert_latest_articles(2)
    
    if articles:
        # Экспорт в JSON
        json_filename = converter.export_to_teletype_format(articles, 'test_export.json')
        print(f"✅ JSON экспорт: {json_filename}")
        
        # Экспорт в Markdown
        markdown_filename = export_to_markdown(articles, 'test_export.md')
        print(f"✅ Markdown экспорт: {markdown_filename}")
        
        # Экспорт в CSV
        csv_filename = export_to_csv(articles, 'test_export.csv')
        print(f"✅ CSV экспорт: {csv_filename}")
    
    converter.close()

def export_to_markdown(articles, filename):
    """Экспорт статей в Markdown формат"""
    with open(filename, 'w', encoding='utf-8') as f:
        f.write("# Naked Capitalism Articles for Teletype\n\n")
        
        for i, article in enumerate(articles, 1):
            f.write(f"## Article {i}: {article['metadata']['title']}\n\n")
            f.write(f"**Author:** {article['metadata']['author']}\n")
            f.write(f"**Date:** {article['metadata']['date']}\n")
            f.write(f"**Category:** {article['metadata']['category']}\n")
            f.write(f"**Tags:** {', '.join(article['metadata']['tags'])}\n\n")
            f.write(f"**URL:** {article['metadata']['url']}\n\n")
            f.write("---\n\n")
    
    return filename

def export_to_csv(articles, filename):
    """Экспорт статей в CSV формат"""
    import csv
    
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        
        # Заголовки
        writer.writerow([
            'Title', 'Author', 'Date', 'Category', 'Tags', 
            'Source', 'URL', 'Word Count', 'Created At'
        ])
        
        # Данные
        for article in articles:
            writer.writerow([
                article['metadata']['title'],
                article['metadata']['author'],
                article['metadata']['date'],
                article['metadata']['category'],
                '; '.join(article['metadata']['tags']),
                article['metadata']['source'],
                article['metadata']['url'],
                article['metadata']['word_count'],
                article['metadata']['created_at']
            ])
    
    return filename

def analyze_conversion_quality():
    """Анализ качества конвертации"""
    print("\n📊 Анализ качества конвертации")
    print("-" * 40)
    
    converter = TeletypeConverter()
    articles = converter.convert_latest_articles(5)
    
    if articles:
        # Статистика
        total_articles = len(articles)
        categories = {}
        tag_counts = {}
        
        for article in articles:
            # Категории
            category = article['metadata']['category']
            categories[category] = categories.get(category, 0) + 1
            
            # Теги
            for tag in article['metadata']['tags']:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
        
        print(f"📈 Статистика конвертации:")
        print(f"   Всего статей: {total_articles}")
        print(f"   Категории: {len(categories)}")
        print(f"   Уникальных тегов: {len(tag_counts)}")
        
        print(f"\n📂 Распределение по категориям:")
        for category, count in sorted(categories.items(), key=lambda x: x[1], reverse=True):
            print(f"   {category}: {count}")
        
        print(f"\n🏷️ Топ-10 тегов:")
        top_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        for tag, count in top_tags:
            print(f"   #{tag}: {count}")
    
    converter.close()

def main():
    """Основная функция тестирования"""
    print("🧪 ТЕСТИРОВАНИЕ КОНВЕРТАЦИИ В TELETYPE")
    print("=" * 60)
    
    try:
        # Тест 1: Базовая конвертация
        basic_articles = test_basic_conversion()
        
        # Тест 2: Расширенная конвертация
        enhanced_articles = test_enhanced_conversion()
        
        # Тест 3: Экспорт в различные форматы
        test_export_formats()
        
        # Тест 4: Анализ качества
        analyze_conversion_quality()
        
        print("\n" + "=" * 60)
        print("✅ ВСЕ ТЕСТЫ ЗАВЕРШЕНЫ УСПЕШНО!")
        print("\n📁 Созданные файлы:")
        print("   - test_export.json (JSON формат)")
        print("   - test_export.md (Markdown формат)")
        print("   - test_export.csv (CSV формат)")
        
    except Exception as e:
        print(f"\n❌ Ошибка во время тестирования: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
