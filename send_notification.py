"""
Скрипт для отправки уведомлений о новых статьях
"""

import asyncio
from article_monitor import NakedCapitalismMonitor
from telegram import Bot

async def send_article_notification():
    """Отправка уведомления о новых статьях"""
    
    # Токен вашего бота
    BOT_TOKEN = "8114291381:AAFo7jRmm3vD_7o4Cthq8Q9pD31x3_qZWMU"
    
    # ID чата для отправки (замените на ваш ID)
    CHAT_ID = "YOUR_CHAT_ID"  # Замените на ваш chat_id
    
    if CHAT_ID == "YOUR_CHAT_ID":
        print("❌ Необходимо указать CHAT_ID для отправки уведомлений")
        print("📝 Как получить CHAT_ID:")
        print("1. Напишите боту @userinfobot")
        print("2. Скопируйте ваш ID")
        print("3. Замените YOUR_CHAT_ID в файле send_notification.py")
        return
    
    try:
        # Создание бота
        bot = Bot(token=BOT_TOKEN)
        
        # Проверка новых статей
        print("🔍 Проверка новых статей...")
        monitor = NakedCapitalismMonitor()
        new_articles = monitor.check_for_new_articles()
        
        if new_articles:
            print(f"📰 Найдено {len(new_articles)} новых статей")
            
            # Формирование сообщения
            message = f"🆕 **Найдено {len(new_articles)} новых статей с Naked Capitalism!**\n\n"
            
            for i, article in enumerate(new_articles[:5], 1):  # Показываем первые 5
                message += f"**{i}.** {article['title']}\n"
                message += f"👤 {article['author']} | 📅 {article['date_posted']}\n"
                message += f"🔗 [Читать статью]({article['url']})\n\n"
            
            if len(new_articles) > 5:
                message += f"... и еще {len(new_articles) - 5} статей"
            
            # Отправка уведомления
            await bot.send_message(
                chat_id=CHAT_ID,
                text=message,
                parse_mode='Markdown',
                disable_web_page_preview=True
            )
            
            print(f"✅ Уведомление отправлено в чат {CHAT_ID}")
            print(f"📰 Сообщение содержит {len(new_articles)} статей")
            
        else:
            print("📝 Новых статей не найдено")
            
            # Отправка сообщения о том, что новых статей нет
            await bot.send_message(
                chat_id=CHAT_ID,
                text="📝 Новых статей с Naked Capitalism не найдено"
            )
            
            print("✅ Отправлено сообщение о отсутствии новых статей")
        
        monitor.conn.close()
        
    except Exception as e:
        print(f"❌ Ошибка при отправке уведомления: {e}")

async def send_single_article_notification():
    """Отправка уведомления о конкретной статье"""
    
    BOT_TOKEN = "8114291381:AAFo7jRmm3vD_7o4Cthq8Q9pD31x3_qZWMU"
    CHAT_ID = "YOUR_CHAT_ID"  # Замените на ваш chat_id
    
    if CHAT_ID == "YOUR_CHAT_ID":
        print("❌ Необходимо указать CHAT_ID")
        return
    
    try:
        bot = Bot(token=BOT_TOKEN)
        
        # Получение последней статьи
        monitor = NakedCapitalismMonitor()
        latest_articles = monitor.get_latest_articles(1)
        
        if latest_articles:
            title, url, author, date_posted, created_at = latest_articles[0]
            
            message = (
                f"📰 **Новая статья с Naked Capitalism**\n\n"
                f"**{title}**\n\n"
                f"👤 Автор: {author}\n"
                f"📅 Дата: {date_posted}\n"
                f"🔗 [Читать статью]({url})"
            )
            
            await bot.send_message(
                chat_id=CHAT_ID,
                text=message,
                parse_mode='Markdown',
                disable_web_page_preview=True
            )
            
            print(f"✅ Уведомление о статье отправлено: {title}")
        else:
            print("❌ Статьи не найдены")
        
        monitor.conn.close()
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")

def main():
    """Основная функция"""
    print("📢 ОТПРАВКА УВЕДОМЛЕНИЙ О НОВЫХ СТАТЬЯХ")
    print("=" * 50)
    
    print("Выберите тип уведомления:")
    print("1. Проверить и отправить уведомления о новых статьях")
    print("2. Отправить уведомление о последней статье")
    print("3. Только проверить новые статьи (без отправки)")
    
    choice = input("\nВведите номер (1-3): ").strip()
    
    if choice == "1":
        asyncio.run(send_article_notification())
    elif choice == "2":
        asyncio.run(send_single_article_notification())
    elif choice == "3":
        # Только проверка без отправки
        monitor = NakedCapitalismMonitor()
        new_articles = monitor.check_for_new_articles()
        
        if new_articles:
            print(f"\n📰 Найдено {len(new_articles)} новых статей:")
            for i, article in enumerate(new_articles, 1):
                print(f"{i}. {article['title']}")
                print(f"   Автор: {article['author']}")
                print(f"   Дата: {article['date_posted']}")
                print(f"   URL: {article['url']}")
                print()
        else:
            print("📝 Новых статей не найдено")
        
        monitor.conn.close()
    else:
        print("❌ Неверный выбор")

if __name__ == "__main__":
    main()
