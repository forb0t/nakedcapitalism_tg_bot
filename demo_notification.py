"""
Демонстрация уведомления о новой статье
"""

from article_monitor import NakedCapitalismMonitor
import json
from datetime import datetime

def demo_notification():
    """Демонстрация уведомления о статье"""
    
    print("📢 ДЕМОНСТРАЦИЯ УВЕДОМЛЕНИЯ О НОВОЙ СТАТЬЕ")
    print("=" * 50)
    
    monitor = NakedCapitalismMonitor()
    
    # Получение последней статьи
    latest_articles = monitor.get_latest_articles(1)
    
    if latest_articles:
        title, url, author, date_posted, created_at = latest_articles[0]
        
        print("📰 Последняя статья в базе данных:")
        print(f"   Заголовок: {title}")
        print(f"   Автор: {author}")
        print(f"   Дата: {date_posted}")
        print(f"   URL: {url}")
        print()
        
        # Формирование сообщения уведомления
        notification_message = (
            f"🆕 **Новая статья с Naked Capitalism!**\n\n"
            f"📰 **{title}**\n\n"
            f"👤 **Автор:** {author}\n"
            f"📅 **Дата:** {date_posted}\n"
            f"🔗 **Ссылка:** [Читать статью]({url})\n\n"
            f"💡 *Статья добавлена в базу данных*"
        )
        
        print("📤 Сообщение уведомления:")
        print("-" * 40)
        print(notification_message)
        print("-" * 40)
        
        # Создание JSON структуры для уведомления
        notification_data = {
            "timestamp": datetime.now().isoformat(),
            "type": "new_article",
            "source": "naked-capitalism",
            "article": {
                "title": title,
                "author": author,
                "date": date_posted,
                "url": url,
                "added_at": created_at
            },
            "message": notification_message,
            "telegram_format": {
                "parse_mode": "Markdown",
                "disable_web_page_preview": True
            }
        }
        
        # Сохранение уведомления в файл
        filename = f"notification_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(notification_data, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Уведомление сохранено в файл: {filename}")
        
        # Статистика
        cursor = monitor.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM articles")
        total_articles = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM articles WHERE created_at >= date('now', '-1 day')")
        today_articles = cursor.fetchone()[0]
        
        print(f"\n📊 Статистика:")
        print(f"   📚 Всего статей в базе: {total_articles}")
        print(f"   📅 Добавлено сегодня: {today_articles}")
        print(f"   🕐 Время проверки: {datetime.now().strftime('%H:%M:%S')}")
        
        # Показать пример отправки через Telegram API
        print(f"\n🤖 Пример отправки через Telegram API:")
        print(f"POST https://api.telegram.org/bot<YOUR_BOT_TOKEN>/sendMessage")
        print(f"Content-Type: application/json")
        print(f"{{")
        print(f'  "chat_id": "YOUR_CHAT_ID",')
        print(f'  "text": "🆕 **Новая статья с Naked Capitalism!**\\n\\n📰 **{title[:50]}...**",')
        print(f'  "parse_mode": "Markdown",')
        print(f'  "disable_web_page_preview": true')
        print(f"}}")
        
    else:
        print("❌ Статьи в базе данных не найдены")
    
    monitor.conn.close()
    
    print(f"\n✅ Демонстрация завершена!")

def create_notification_template():
    """Создание шаблона уведомления"""
    
    template = {
        "notification_types": {
            "new_article": {
                "template": "🆕 **Новая статья с {source}!**\n\n📰 **{title}**\n\n👤 **Автор:** {author}\n📅 **Дата:** {date}\n🔗 **Ссылка:** [Читать статью]({url})",
                "variables": ["source", "title", "author", "date", "url"]
            },
            "multiple_articles": {
                "template": "🆕 **Найдено {count} новых статей с {source}!**\n\n{articles_list}",
                "variables": ["count", "source", "articles_list"]
            },
            "daily_summary": {
                "template": "📊 **Ежедневная сводка {source}**\n\n📰 **Статей за день:** {count}\n📈 **Популярные темы:** {topics}\n🔗 **Последние статьи:** {recent_articles}",
                "variables": ["source", "count", "topics", "recent_articles"]
            }
        },
        "telegram_settings": {
            "parse_mode": "Markdown",
            "disable_web_page_preview": True,
            "disable_notification": False
        }
    }
    
    filename = "notification_templates.json"
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(template, f, indent=2, ensure_ascii=False)
    
    print(f"📝 Шаблоны уведомлений сохранены в: {filename}")

if __name__ == "__main__":
    demo_notification()
    print()
    create_notification_template()
