"""
Создание полных Teletype версий статей с контентом
"""

from article_processor import ArticleProcessor
import sqlite3
import json
from datetime import datetime
import time

def create_full_teletype_articles():
    """Создание полных Teletype версий всех статей"""
    
    print("🔄 СОЗДАНИЕ ПОЛНЫХ TELETYPE ВЕРСИЙ СТАТЕЙ")
    print("=" * 60)
    
    processor = ArticleProcessor()
    
    # Получение всех статей из базы данных
    cursor = processor.conn.cursor()
    cursor.execute('''
        SELECT id, title, url, author, date_posted, created_at
        FROM articles 
        ORDER BY created_at DESC
    ''')
    
    all_articles_data = cursor.fetchall()
    total_articles = len(all_articles_data)
    
    print(f"📚 Найдено {total_articles} статей в базе данных")
    print(f"🚀 Начинаем создание полных Teletype версий...")
    print(f"⏳ Это может занять несколько минут...")
    
    converted_articles = []
    success_count = 0
    error_count = 0
    
    for i, (article_id, title, url, author, date_posted, created_at) in enumerate(all_articles_data, 1):
        print(f"\n📰 Статья {i}/{total_articles}: {title[:50]}...")
        
        try:
            # Получение полного контента статьи
            full_content = processor.fetch_article_content(url)
            
            if full_content:
                # Создание расширенного контента
                article_data = {
                    'title': title,
                    'url': url,
                    'author': author,
                    'date_posted': date_posted
                }
                
                enhanced_content = processor.create_enhanced_teletype_content(article_data, full_content)
                teletype_post = processor.format_teletype_post(article_data)
                
                # Замена контента на расширенный
                teletype_post['content'] = enhanced_content
                teletype_post['metadata']['has_full_content'] = True
                teletype_post['metadata']['content_length'] = len(full_content)
                teletype_post['metadata']['article_id'] = article_id
                teletype_post['metadata']['original_created_at'] = created_at
                
                converted_articles.append(teletype_post)
                success_count += 1
                
                print(f"   ✅ Полный контент получен ({len(full_content)} символов)")
            else:
                # Базовый пост без полного контента
                article_data = {
                    'title': title,
                    'url': url,
                    'author': author,
                    'date_posted': date_posted
                }
                
                teletype_post = processor.format_teletype_post(article_data)
                teletype_post['metadata']['has_full_content'] = False
                teletype_post['metadata']['article_id'] = article_id
                teletype_post['metadata']['original_created_at'] = created_at
                
                converted_articles.append(teletype_post)
                print(f"   ⚠️ Контент не получен, создан базовый пост")
            
            # Задержка между запросами (защита от блокировки)
            if i < total_articles:
                time.sleep(2)
                
        except Exception as e:
            print(f"   ❌ Ошибка обработки статьи: {e}")
            error_count += 1
            continue
    
    print(f"\n📊 РЕЗУЛЬТАТЫ ОБРАБОТКИ:")
    print(f"   📚 Всего статей: {total_articles}")
    print(f"   ✅ Успешно обработано: {success_count}")
    print(f"   ⚠️ Базовых постов: {len(converted_articles) - success_count}")
    print(f"   ❌ Ошибок: {error_count}")
    
    # Экспорт в различные форматы
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # 1. JSON формат (полная структура Teletype)
    json_filename = f'full_teletype_articles_{timestamp}.json'
    processor.export_to_teletype_format(converted_articles, json_filename)
    print(f"\n💾 Экспорт в JSON: {json_filename}")
    
    # 2. Markdown формат
    md_filename = f'teletype_articles_{timestamp}.md'
    export_to_markdown(converted_articles, md_filename)
    print(f"💾 Экспорт в Markdown: {md_filename}")
    
    # 3. CSV формат для анализа
    csv_filename = f'teletype_articles_{timestamp}.csv'
    export_to_csv(converted_articles, csv_filename)
    print(f"💾 Экспорт в CSV: {csv_filename}")
    
    # 4. Создание сводного отчета
    report_filename = f'conversion_report_{timestamp}.json'
    create_conversion_report(converted_articles, report_filename)
    print(f"📊 Отчет о конвертации: {report_filename}")
    
    processor.conn.close()
    
    print(f"\n✅ СОЗДАНИЕ TELETYPE ВЕРСИЙ ЗАВЕРШЕНО!")
    print(f"📁 Созданные файлы:")
    print(f"   - {json_filename} (JSON)")
    print(f"   - {md_filename} (Markdown)")
    print(f"   - {csv_filename} (CSV)")
    print(f"   - {report_filename} (Отчет)")
    
    return converted_articles

def export_to_markdown(articles, filename):
    """Экспорт статей в Markdown формат"""
    with open(filename, 'w', encoding='utf-8') as f:
        f.write("# Naked Capitalism Articles - Teletype Format\n\n")
        f.write(f"**Всего статей:** {len(articles)}\n")
        f.write(f"**Дата создания:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        full_content_count = sum(1 for a in articles if a['metadata'].get('has_full_content'))
        f.write(f"**С полным контентом:** {full_content_count}\n")
        f.write(f"**Базовых постов:** {len(articles) - full_content_count}\n\n")
        
        f.write("---\n\n")
        
        for i, article in enumerate(articles, 1):
            content_status = "📖 Полный контент" if article['metadata'].get('has_full_content') else "📝 Базовый пост"
            f.write(f"## Article {i}: {article['metadata']['title']}\n\n")
            f.write(f"**Author:** {article['metadata']['author']}\n")
            f.write(f"**Date:** {article['metadata']['date']}\n")
            f.write(f"**Category:** {article['metadata']['category']}\n")
            f.write(f"**Tags:** {', '.join(article['metadata']['tags'])}\n")
            f.write(f"**Status:** {content_status}\n")
            if article['metadata'].get('content_length'):
                f.write(f"**Content Length:** {article['metadata']['content_length']} characters\n")
            f.write(f"**URL:** {article['metadata']['url']}\n\n")
            
            # Показываем начало контента
            content_preview = article['content'][:500] + "..." if len(article['content']) > 500 else article['content']
            f.write(f"**Content Preview:**\n```\n{content_preview}\n```\n\n")
            f.write("---\n\n")

def export_to_csv(articles, filename):
    """Экспорт статей в CSV формат"""
    import csv
    
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        
        # Заголовки
        writer.writerow([
            'Article ID', 'Title', 'Author', 'Date', 'Category', 'Tags',
            'Source', 'URL', 'Has Full Content', 'Content Length',
            'Word Count', 'Created At', 'Original Created At'
        ])
        
        # Данные
        for article in articles:
            writer.writerow([
                article['metadata'].get('article_id', ''),
                article['metadata']['title'],
                article['metadata']['author'],
                article['metadata']['date'],
                article['metadata']['category'],
                '; '.join(article['metadata']['tags']),
                article['metadata']['source'],
                article['metadata']['url'],
                article['metadata'].get('has_full_content', False),
                article['metadata'].get('content_length', 0),
                article['metadata']['word_count'],
                article['metadata']['created_at'],
                article['metadata'].get('original_created_at', '')
            ])

def create_conversion_report(articles, filename):
    """Создание отчета о конвертации"""
    
    # Анализ данных
    total_articles = len(articles)
    full_content_count = sum(1 for a in articles if a['metadata'].get('has_full_content'))
    basic_posts_count = total_articles - full_content_count
    
    # Категории
    categories = {}
    for article in articles:
        category = article['metadata']['category']
        categories[category] = categories.get(category, 0) + 1
    
    # Теги
    tag_counts = {}
    for article in articles:
        for tag in article['metadata']['tags']:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
    
    # Авторы
    authors = {}
    for article in articles:
        author = article['metadata']['author']
        authors[author] = authors.get(author, 0) + 1
    
    # Длина контента
    content_lengths = [a['metadata'].get('content_length', 0) for a in articles if a['metadata'].get('has_full_content')]
    avg_content_length = sum(content_lengths) / len(content_lengths) if content_lengths else 0
    
    report = {
        'conversion_info': {
            'timestamp': datetime.now().isoformat(),
            'total_articles': total_articles,
            'full_content_articles': full_content_count,
            'basic_posts': basic_posts_count,
            'success_rate': f"{(full_content_count / total_articles * 100):.1f}%"
        },
        'statistics': {
            'categories': categories,
            'top_tags': dict(sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:10]),
            'authors': authors,
            'average_content_length': round(avg_content_length),
            'content_length_range': {
                'min': min(content_lengths) if content_lengths else 0,
                'max': max(content_lengths) if content_lengths else 0
            }
        },
        'files_created': {
            'json_export': f'full_teletype_articles_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json',
            'markdown_export': f'teletype_articles_{datetime.now().strftime("%Y%m%d_%H%M%S")}.md',
            'csv_export': f'teletype_articles_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        }
    }
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

def main():
    """Основная функция"""
    print("🚀 ЗАПУСК СОЗДАНИЯ TELETYPE ВЕРСИЙ")
    print("=" * 50)
    
    try:
        articles = create_full_teletype_articles()
        
        print(f"\n🎉 УСПЕШНО СОЗДАНЫ TELETYPE ВЕРСИИ!")
        print(f"📊 Итого обработано: {len(articles)} статей")
        
        # Показать примеры
        if articles:
            print(f"\n📝 Примеры созданных статей:")
            for i, article in enumerate(articles[:3], 1):
                status = "📖 Полный контент" if article['metadata'].get('has_full_content') else "📝 Базовый пост"
                print(f"{i}. {article['metadata']['title'][:60]}...")
                print(f"   {status} | {article['metadata']['category']} | {len(article['metadata']['tags'])} тегов")
        
    except Exception as e:
        print(f"❌ Ошибка при создании Teletype версий: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
