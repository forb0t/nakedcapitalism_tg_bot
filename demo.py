"""
Демонстрационный скрипт для показа работы мониторинга
"""

from article_monitor import NakedCapitalismMonitor
import json
from datetime import datetime

def demo_monitoring():
    """Демонстрация работы мониторинга"""
    print("🎯 ДЕМОНСТРАЦИЯ МОНИТОРИНГА NAKED CAPITALISM")
    print("=" * 60)
    
    monitor = NakedCapitalismMonitor()
    
    # Получение и отображение статей
    print("📡 Получение статей с сайта...")
    html_content = monitor.get_page_content(monitor.base_url)
    
    if html_content:
        print("✅ Сайт доступен")
        articles = monitor.parse_articles(html_content)
        
        print(f"\n📰 Найдено {len(articles)} статей:")
        print("-" * 60)
        
        for i, article in enumerate(articles[:10], 1):  # Показываем первые 10
            print(f"{i:2d}. {article['title']}")
            print(f"    👤 Автор: {article['author']}")
            print(f"    📅 Дата: {article['date_posted']}")
            print(f"    🔗 URL: {article['url'][:80]}...")
            print()
        
        if len(articles) > 10:
            print(f"... и еще {len(articles) - 10} статей")
        
        # Проверка новых статей
        print("\n🔍 Проверка новых статей...")
        new_articles = monitor.check_for_new_articles()
        
        if new_articles:
            print(f"\n🆕 Найдено {len(new_articles)} новых статей!")
            print("📋 Последние новые статьи:")
            for article in new_articles[:3]:
                print(f"   📰 {article['title']}")
                print(f"   👤 {article['author']}")
                print()
        else:
            print("📝 Новых статей не найдено (все уже в базе)")
        
        # Статистика
        print("\n📊 СТАТИСТИКА:")
        cursor = monitor.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM articles")
        total = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM articles WHERE created_at >= date('now', '-1 day')")
        today = cursor.fetchone()[0]
        
        print(f"   📚 Всего статей в базе: {total}")
        print(f"   📅 Добавлено сегодня: {today}")
        print(f"   🕐 Время проверки: {datetime.now().strftime('%H:%M:%S')}")
        
    else:
        print("❌ Сайт недоступен")
    
    monitor.conn.close()
    
    print("\n" + "=" * 60)
    print("✅ Демонстрация завершена!")
    print("\n💡 Для запуска полного бота:")
    print("   1. Получите токен у @BotFather")
    print("   2. Замените YOUR_BOT_TOKEN_HERE в nakedcap_bot.py")
    print("   3. Запустите: py nakedcap_bot.py")

if __name__ == "__main__":
    demo_monitoring()
