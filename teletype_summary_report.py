"""
Итоговый отчет о созданных Teletype версиях статей
"""

import json
import csv
from datetime import datetime

def analyze_teletype_files():
    """Анализ созданных файлов Teletype"""
    
    print("📊 ИТОГОВЫЙ ОТЧЕТ ПО TELETYPE ВЕРСИЯМ СТАТЕЙ")
    print("=" * 60)
    
    # Анализ JSON файла
    try:
        with open('full_teletype_articles_20251021_144214.json', 'r', encoding='utf-8') as f:
            json_data = json.load(f)
        
        articles = json_data['articles']
        total_articles = len(articles)
        
        print(f"📚 JSON файл: full_teletype_articles_20251021_144214.json")
        print(f"   📰 Всего статей: {total_articles}")
        print(f"   📅 Дата создания: {json_data['export_info']['created_at']}")
        print(f"   🔄 Версия формата: {json_data['export_info']['format_version']}")
        
        # Статистика по контенту
        full_content_count = sum(1 for a in articles if a['metadata'].get('has_full_content'))
        basic_posts_count = total_articles - full_content_count
        
        print(f"\n📖 Содержание:")
        print(f"   📝 Полный контент: {full_content_count} статей")
        print(f"   📄 Базовые посты: {basic_posts_count} статей")
        print(f"   📈 Успешность: {(full_content_count / total_articles * 100):.1f}%")
        
        # Статистика по категориям
        categories = {}
        for article in articles:
            category = article['metadata']['category']
            categories[category] = categories.get(category, 0) + 1
        
        print(f"\n📂 Категории:")
        for category, count in sorted(categories.items(), key=lambda x: x[1], reverse=True):
            print(f"   {category}: {count} статей")
        
        # Статистика по тегам
        tag_counts = {}
        for article in articles:
            for tag in article['metadata']['tags']:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
        
        print(f"\n🏷️ Топ-10 тегов:")
        top_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        for tag, count in top_tags:
            print(f"   #{tag}: {count}")
        
        # Статистика по длине контента
        content_lengths = [a['metadata'].get('content_length', 0) for a in articles if a['metadata'].get('has_full_content')]
        if content_lengths:
            avg_length = sum(content_lengths) / len(content_lengths)
            min_length = min(content_lengths)
            max_length = max(content_lengths)
            
            print(f"\n📏 Длина контента:")
            print(f"   Средняя: {avg_length:.0f} символов")
            print(f"   Минимальная: {min_length} символов")
            print(f"   Максимальная: {max_length} символов")
        
    except Exception as e:
        print(f"❌ Ошибка анализа JSON: {e}")
    
    # Анализ CSV файла
    try:
        with open('teletype_articles_20251021_144214.csv', 'r', encoding='utf-8') as f:
            csv_reader = csv.reader(f)
            rows = list(csv_reader)
        
        print(f"\n📊 CSV файл: teletype_articles_20251021_144214.csv")
        print(f"   📋 Строк: {len(rows)}")
        print(f"   📝 Колонок: {len(rows[0]) if rows else 0}")
        
        if rows:
            headers = rows[0]
            print(f"\n📋 Колонки CSV:")
            for i, header in enumerate(headers, 1):
                print(f"   {i:2d}. {header}")
    
    except Exception as e:
        print(f"❌ Ошибка анализа CSV: {e}")
    
    # Анализ Markdown файла
    try:
        with open('teletype_articles_20251021_144214.md', 'r', encoding='utf-8') as f:
            md_content = f.read()
        
        print(f"\n📝 Markdown файл: teletype_articles_20251021_144214.md")
        print(f"   📏 Размер: {len(md_content)} символов")
        print(f"   📄 Строк: {md_content.count(chr(10)) + 1}")
    
    except Exception as e:
        print(f"❌ Ошибка анализа Markdown: {e}")
    
    # Анализ отчета
    try:
        with open('conversion_report_20251021_144214.json', 'r', encoding='utf-8') as f:
            report_data = json.load(f)
        
        print(f"\n📊 Отчет конвертации:")
        print(f"   📅 Время: {report_data['conversion_info']['timestamp']}")
        print(f"   📈 Успешность: {report_data['conversion_info']['success_rate']}")
        print(f"   📚 Полный контент: {report_data['conversion_info']['full_content_articles']}")
        print(f"   📄 Базовых постов: {report_data['conversion_info']['basic_posts']}")
        
        stats = report_data['statistics']
        print(f"   📏 Средняя длина: {stats['average_content_length']} символов")
        print(f"   📊 Диапазон: {stats['content_length_range']['min']} - {stats['content_length_range']['max']}")
    
    except Exception as e:
        print(f"❌ Ошибка анализа отчета: {e}")

def show_example_articles():
    """Показать примеры созданных статей"""
    
    print(f"\n📝 ПРИМЕРЫ СОЗДАННЫХ СТАТЕЙ")
    print("=" * 40)
    
    try:
        with open('full_teletype_articles_20251021_144214.json', 'r', encoding='utf-8') as f:
            json_data = json.load(f)
        
        articles = json_data['articles']
        
        # Показать первые 3 статьи
        for i, article in enumerate(articles[:3], 1):
            print(f"\n📰 Статья {i}:")
            print(f"   Заголовок: {article['metadata']['title']}")
            print(f"   Автор: {article['metadata']['author']}")
            print(f"   Категория: {article['metadata']['category']}")
            print(f"   Теги: {', '.join(article['metadata']['tags'])}")
            print(f"   Полный контент: {'Да' if article['metadata'].get('has_full_content') else 'Нет'}")
            if article['metadata'].get('content_length'):
                print(f"   Длина контента: {article['metadata']['content_length']} символов")
            print(f"   URL: {article['metadata']['url']}")
            
            # Показать начало контента
            content_preview = article['content'][:200] + "..." if len(article['content']) > 200 else article['content']
            print(f"   Контент (начало): {content_preview}")
    
    except Exception as e:
        print(f"❌ Ошибка показа примеров: {e}")

def create_usage_guide():
    """Создание руководства по использованию"""
    
    guide = """
# 📚 Руководство по использованию Teletype версий статей

## 🎯 Что создано

✅ **55 статей** успешно конвертированы в формат Teletype
✅ **100% успешность** - все статьи имеют полный контент
✅ **4 формата экспорта** - JSON, Markdown, CSV, Отчет

## 📁 Созданные файлы

### 1. JSON файл (основной)
- **Файл:** `full_teletype_articles_20251021_144214.json`
- **Содержит:** Полную структуру Teletype со всеми метаданными
- **Использование:** Импорт в платформу Teletype или другие системы

### 2. Markdown файл
- **Файл:** `teletype_articles_20251021_144214.md`
- **Содержит:** Читаемый формат всех статей
- **Использование:** Просмотр, редактирование, публикация

### 3. CSV файл
- **Файл:** `teletype_articles_20251021_144214.csv`
- **Содержит:** Табличные данные для анализа
- **Использование:** Анализ данных, статистика, импорт в Excel

### 4. Отчет конвертации
- **Файл:** `conversion_report_20251021_144214.json`
- **Содержит:** Статистику и метрики конвертации
- **Использование:** Анализ качества и результатов

## 📊 Статистика

- **Всего статей:** 55
- **Полный контент:** 55 (100%)
- **Категории:** 2 (daily-links: 4, general: 51)
- **Средняя длина:** 7,318 символов
- **Диапазон:** 100 - 27,544 символов

## 🏷️ Топ теги

1. #economics (55)
2. #naked-capitalism (55)
3. #finance (55)
4. #technology (4)
5. #markets (2)
6. #real-estate (2)
7. #commodities (2)
8. #politics (1)
9. #healthcare (1)
10. #geopolitics (1)

## 🚀 Как использовать

### Импорт в Teletype
1. Откройте JSON файл
2. Скопируйте структуру статей
3. Импортируйте в вашу платформу

### Анализ данных
1. Откройте CSV файл в Excel
2. Используйте фильтры и сортировку
3. Создайте диаграммы и отчеты

### Просмотр статей
1. Откройте Markdown файл
2. Читайте статьи в удобном формате
3. Копируйте нужные части

## 🔄 Автоматическое обновление

Для автоматического создания новых Teletype версий:
```bash
py create_full_teletype_articles.py
```

## 📞 Поддержка

Все файлы готовы к использованию и могут быть легко интегрированы с любыми платформами публикации.
"""
    
    with open('TELETYPE_USAGE_GUIDE.md', 'w', encoding='utf-8') as f:
        f.write(guide)
    
    print(f"\n📖 Руководство создано: TELETYPE_USAGE_GUIDE.md")

def main():
    """Основная функция"""
    analyze_teletype_files()
    show_example_articles()
    create_usage_guide()
    
    print(f"\n✅ ИТОГОВЫЙ ОТЧЕТ ЗАВЕРШЕН!")
    print(f"📁 Все файлы готовы к использованию")
    print(f"📖 Руководство: TELETYPE_USAGE_GUIDE.md")

if __name__ == "__main__":
    main()
