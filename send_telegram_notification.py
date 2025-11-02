"""
Отправка уведомления о новой статье через Telegram API
"""

import requests
import json
from datetime import datetime
from article_monitor import NakedCapitalismMonitor

def send_telegram_notification():
    """Отправка уведомления через Telegram API"""
    
    # Настройки бота
    BOT_TOKEN = "8114291381:AAFo7jRmm3vD_7o4Cthq8Q9pD31x3_qZWMU"
    
    # Для получения Chat ID:
    # 1. Напишите боту @userinfobot
    # 2. Или добавьте бота в группу и напишите /start
    # 3. Скопируйте ID из логов или используйте getUpdates API
    
    CHAT_ID = "YOUR_CHAT_ID"  # Замените на ваш Chat ID
    
    if CHAT_ID == "YOUR_CHAT_ID":
        print("❌ Необходимо указать CHAT_ID")
        print("\n📝 Как получить Chat ID:")
        print("1. Напишите боту @userinfobot")
        print("2. Или используйте команду: py get_chat_id.py")
        return False
    
    try:
        # Получение последней статьи
        monitor = NakedCapitalismMonitor()
        latest_articles = monitor.get_latest_articles(1)
        
        if not latest_articles:
            print("❌ Статьи не найдены")
            return False
        
        title, url, author, date_posted, created_at = latest_articles[0]
        
        # Формирование сообщения
        message = (
            f"🆕 **Новая статья с Naked Capitalism!**\n\n"
            f"📰 **{title}**\n\n"
            f"👤 **Автор:** {author}\n"
            f"📅 **Дата:** {date_posted}\n"
            f"🔗 **Ссылка:** [Читать статью]({url})\n\n"
            f"💡 *Статья добавлена в базу данных*"
        )
        
        # URL для отправки сообщения
        url_api = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        
        # Данные для отправки
        data = {
            "chat_id": CHAT_ID,
            "text": message,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True
        }
        
        print("📤 Отправка уведомления...")
        print(f"   Получатель: {CHAT_ID}")
        print(f"   Статья: {title}")
        
        # Отправка запроса
        response = requests.post(url_api, json=data, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            if result.get("ok"):
                print("✅ Уведомление успешно отправлено!")
                print(f"   Message ID: {result['result']['message_id']}")
                
                # Сохранение информации об отправке
                notification_log = {
                    "timestamp": datetime.now().isoformat(),
                    "chat_id": CHAT_ID,
                    "article": {
                        "title": title,
                        "url": url,
                        "author": author,
                        "date": date_posted
                    },
                    "message_id": result['result']['message_id'],
                    "status": "sent"
                }
                
                log_filename = f"notification_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                with open(log_filename, 'w', encoding='utf-8') as f:
                    json.dump(notification_log, f, indent=2, ensure_ascii=False)
                
                print(f"📝 Лог сохранен в: {log_filename}")
                return True
            else:
                print(f"❌ Ошибка API: {result.get('description', 'Unknown error')}")
                return False
        else:
            print(f"❌ HTTP ошибка: {response.status_code}")
            print(f"   Ответ: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка при отправке: {e}")
        return False
    finally:
        monitor.conn.close()

def get_chat_id():
    """Получение Chat ID через getUpdates API"""
    
    BOT_TOKEN = "8114291381:AAFo7jRmm3vD_7o4Cthq8Q9pD31x3_qZWMU"
    
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
        response = requests.get(url, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("ok"):
                updates = data.get("result", [])
                
                if updates:
                    print("📋 Найденные чаты:")
                    chat_ids = set()
                    
                    for update in updates[-10:]:  # Последние 10 обновлений
                        message = update.get("message", {})
                        chat = message.get("chat", {})
                        chat_id = chat.get("id")
                        chat_type = chat.get("type")
                        chat_title = chat.get("title", chat.get("first_name", "Unknown"))
                        
                        if chat_id:
                            chat_ids.add((chat_id, chat_type, chat_title))
                    
                    for chat_id, chat_type, chat_title in chat_ids:
                        print(f"   ID: {chat_id} | Тип: {chat_type} | Название: {chat_title}")
                    
                    return list(chat_ids)
                else:
                    print("📝 Нет обновлений. Напишите боту /start или любое сообщение")
                    return []
            else:
                print(f"❌ Ошибка API: {data.get('description')}")
                return []
        else:
            print(f"❌ HTTP ошибка: {response.status_code}")
            return []
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return []

def main():
    """Основная функция"""
    print("📢 ОТПРАВКА УВЕДОМЛЕНИЯ ЧЕРЕЗ TELEGRAM API")
    print("=" * 50)
    
    print("Выберите действие:")
    print("1. Получить Chat ID")
    print("2. Отправить уведомление")
    print("3. Проверить новые статьи")
    
    choice = input("\nВведите номер (1-3): ").strip()
    
    if choice == "1":
        print("\n🔍 Получение Chat ID...")
        chats = get_chat_id()
        
        if chats:
            print(f"\n✅ Найдено {len(chats)} чатов")
            print("💡 Скопируйте нужный Chat ID и вставьте в CHAT_ID в коде")
        else:
            print("❌ Чаты не найдены")
    
    elif choice == "2":
        print("\n📤 Отправка уведомления...")
        success = send_telegram_notification()
        
        if success:
            print("\n🎉 Уведомление отправлено успешно!")
        else:
            print("\n❌ Не удалось отправить уведомление")
    
    elif choice == "3":
        print("\n🔍 Проверка новых статей...")
        monitor = NakedCapitalismMonitor()
        new_articles = monitor.check_for_new_articles()
        
        if new_articles:
            print(f"📰 Найдено {len(new_articles)} новых статей:")
            for i, article in enumerate(new_articles, 1):
                print(f"{i}. {article['title']}")
                print(f"   Автор: {article['author']}")
                print(f"   Дата: {article['date_posted']}")
        else:
            print("📝 Новых статей не найдено")
        
        monitor.conn.close()
    
    else:
        print("❌ Неверный выбор")

if __name__ == "__main__":
    main()
