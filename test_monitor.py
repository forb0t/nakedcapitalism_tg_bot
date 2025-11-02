"""
Тестовый скрипт для проверки мониторинга статей
"""

from article_monitor import NakedCapitalismMonitor
import json

def test_monitor():
    """Тестирование мониторинга статей"""
    print("🧪 Тестирование мониторинга Naked Capitalism")
    print("=" * 50)
    
    monitor = NakedCapitalismMonitor()
    
    # Тест 1: Получение главной страницы
    print("📡 Тест 1: Получение главной страницы...")
    html_content = monitor.get_page_content(monitor.base_url)
    
    if html_content:
        print("✅ Главная страница успешно получена")
        print(f"📏 Размер контента: {len(html_content)} символов")
    else:
        print("❌ Ошибка при получении главной страницы")
        return
    
    # Тест 2: Парсинг статей
    print("\n🔍 Тест 2: Парсинг статей...")
    articles = monitor.parse_articles(html_content)
    
    print(f"📰 Найдено статей: {len(articles)}")
    
    if articles:
        print("\n📋 Первые 5 статей:")
        for i, article in enumerate(articles[:5], 1):
            print(f"{i}. {article['title']}")
            print(f"   Автор: {article['author']}")
            print(f"   URL: {article['url']}")
            print(f"   Дата: {article['date_posted']}")
            print()
    
    # Тест 3: Сохранение в базу данных
    print("💾 Тест 3: Сохранение в базу данных...")
    new_articles = monitor.save_articles(articles)
    
    print(f"💾 Сохранено новых статей: {len(new_articles)}")
    
    # Тест 4: Получение последних статей
    print("\n📚 Тест 4: Получение последних статей...")
    latest = monitor.get_latest_articles(5)
    
    if latest:
        print("📚 Последние статьи в базе:")
        for article in latest:
            print(f"- {article[0]} ({article[2]})")
    
    # Тест 5: Проверка на новые статьи
    print("\n🔄 Тест 5: Полная проверка новых статей...")
    new_articles = monitor.check_for_new_articles()
    
    print(f"🆕 Найдено новых статей: {len(new_articles)}")
    
    # Закрытие соединения с БД
    monitor.conn.close()
    
    print("\n✅ Тестирование завершено!")

def test_single_check():
    """Быстрая проверка новых статей"""
    print("⚡ Быстрая проверка новых статей")
    print("-" * 30)
    
    monitor = NakedCapitalismMonitor()
    new_articles = monitor.check_for_new_articles()
    
    if new_articles:
        print(f"🆕 Найдено {len(new_articles)} новых статей:")
        for article in new_articles:
            print(f"📰 {article['title']} - {article['author']}")
    else:
        print("📝 Новых статей не найдено")
    
    monitor.conn.close()

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "quick":
        test_single_check()
    else:
        test_monitor()
