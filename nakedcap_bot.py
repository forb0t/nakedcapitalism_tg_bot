"""
Telegram бот с мониторингом статей Naked Capitalism
"""

import asyncio
import logging
import schedule
import time
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler
from article_monitor import NakedCapitalismMonitor

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class NakedCapBot:
    def __init__(self, bot_token):
        self.bot_token = bot_token
        self.monitor = NakedCapitalismMonitor()
        self.application = Application.builder().token(bot_token).build()
        self.setup_handlers()
        self.setup_scheduler()
    
    def setup_handlers(self):
        """Настройка обработчиков команд"""
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("check", self.check_articles))
        self.application.add_handler(CommandHandler("latest", self.latest_articles))
        self.application.add_handler(CommandHandler("stats", self.stats))
        self.application.add_handler(CommandHandler("monitor", self.toggle_monitoring))
        self.application.add_handler(CallbackQueryHandler(self.button_callback))
        
        # Обработчик ошибок
        self.application.add_error_handler(self.error_handler)
    
    def setup_scheduler(self):
        """Настройка планировщика для автоматической проверки"""
        schedule.every().hour.do(self.scheduled_check)
        self.monitoring_active = True
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик команды /start"""
        user = update.effective_user
        keyboard = [
            [InlineKeyboardButton("📰 Проверить статьи", callback_data="check_articles")],
            [InlineKeyboardButton("📚 Последние статьи", callback_data="latest_articles")],
            [InlineKeyboardButton("📊 Статистика", callback_data="stats")],
            [InlineKeyboardButton("⚙️ Мониторинг", callback_data="monitor_status")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        welcome_message = (
            f"Привет, {user.first_name}! 👋\n\n"
            f"🤖 Я бот для мониторинга статей с сайта [Naked Capitalism](https://www.nakedcapitalism.com/)\n\n"
            f"📰 Каждый час я проверяю новые статьи и уведомляю вас\n"
            f"🔔 Используйте кнопки ниже или команды для управления\n\n"
            f"📋 Доступные команды:\n"
            f"/check - Проверить новые статьи сейчас\n"
            f"/latest - Показать последние статьи\n"
            f"/stats - Статистика мониторинга\n"
            f"/monitor - Управление мониторингом"
        )
        
        await update.message.reply_text(
            welcome_message, 
            reply_markup=reply_markup,
            parse_mode='Markdown',
            disable_web_page_preview=True
        )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик команды /help"""
        help_text = (
            "📋 Доступные команды:\n\n"
            "🔍 /check - Проверить новые статьи прямо сейчас\n"
            "📚 /latest - Показать последние статьи из базы\n"
            "📊 /stats - Статистика мониторинга\n"
            "⚙️ /monitor - Включить/выключить автоматический мониторинг\n"
            "❓ /help - Показать это сообщение\n\n"
            "🤖 Бот автоматически проверяет новые статьи каждый час\n"
            "📰 Уведомления приходят при обнаружении новых статей"
        )
        await update.message.reply_text(help_text)
    
    async def check_articles(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Проверка новых статей"""
        message = await update.message.reply_text("🔍 Проверяю новые статьи...")
        
        try:
            new_articles = self.monitor.check_for_new_articles()
            
            if new_articles:
                response = f"✅ Найдено {len(new_articles)} новых статей!\n\n"
                for i, article in enumerate(new_articles[:5], 1):  # Показываем только первые 5
                    response += f"{i}. 📰 [{article['title']}]({article['url']})\n"
                    response += f"   👤 Автор: {article['author']}\n"
                    response += f"   📅 Дата: {article['date_posted']}\n\n"
                
                if len(new_articles) > 5:
                    response += f"... и еще {len(new_articles) - 5} статей"
                
                await message.edit_text(
                    response,
                    parse_mode='Markdown',
                    disable_web_page_preview=True
                )
            else:
                await message.edit_text("📝 Новых статей не найдено")
                
        except Exception as e:
            logger.error(f"Ошибка при проверке статей: {e}")
            await message.edit_text("❌ Произошла ошибка при проверке статей")
    
    async def latest_articles(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Показ последних статей"""
        try:
            latest = self.monitor.get_latest_articles(10)
            
            if latest:
                response = "📚 Последние статьи:\n\n"
                for i, article in enumerate(latest, 1):
                    title, url, author, date_posted, created_at = article
                    response += f"{i}. 📰 [{title}]({url})\n"
                    response += f"   👤 {author} | 📅 {date_posted}\n\n"
                
                await update.message.reply_text(
                    response,
                    parse_mode='Markdown',
                    disable_web_page_preview=True
                )
            else:
                await update.message.reply_text("📝 Статей в базе данных нет")
                
        except Exception as e:
            logger.error(f"Ошибка при получении статей: {e}")
            await update.message.reply_text("❌ Произошла ошибка при получении статей")
    
    async def stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Статистика мониторинга"""
        try:
            cursor = self.monitor.conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM articles")
            total_articles = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM articles WHERE created_at >= date('now', '-1 day')")
            today_articles = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM articles WHERE created_at >= date('now', '-7 days')")
            week_articles = cursor.fetchone()[0]
            
            status = "🟢 Активен" if self.monitoring_active else "🔴 Остановлен"
            
            stats_text = (
                f"📊 Статистика мониторинга Naked Capitalism\n\n"
                f"📰 Всего статей в базе: {total_articles}\n"
                f"📅 Статей за сегодня: {today_articles}\n"
                f"📆 Статей за неделю: {week_articles}\n\n"
                f"⚙️ Статус мониторинга: {status}\n"
                f"🕐 Последняя проверка: {datetime.now().strftime('%H:%M:%S')}"
            )
            
            await update.message.reply_text(stats_text)
            
        except Exception as e:
            logger.error(f"Ошибка при получении статистики: {e}")
            await update.message.reply_text("❌ Произошла ошибка при получении статистики")
    
    async def toggle_monitoring(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Переключение мониторинга"""
        self.monitoring_active = not self.monitoring_active
        status = "включен" if self.monitoring_active else "выключен"
        
        message = f"⚙️ Автоматический мониторинг {status}"
        await update.message.reply_text(message)
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик нажатий на кнопки"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "check_articles":
            await self.check_articles(update, context)
        elif query.data == "latest_articles":
            await self.latest_articles(update, context)
        elif query.data == "stats":
            await self.stats(update, context)
        elif query.data == "monitor_status":
            await self.toggle_monitoring(update, context)
    
    async def scheduled_check(self):
        """Планируемая проверка новых статей"""
        if not self.monitoring_active:
            return
        
        try:
            new_articles = self.monitor.check_for_new_articles()
            
            if new_articles:
                # Отправка уведомлений всем пользователям
                await self.notify_users_about_new_articles(new_articles)
                
        except Exception as e:
            logger.error(f"Ошибка в планируемой проверке: {e}")
    
    async def notify_users_about_new_articles(self, articles):
        """Уведомление пользователей о новых статьях"""
        # Здесь можно добавить логику для отправки уведомлений
        # конкретным пользователям или в групповые чаты
        logger.info(f"Обнаружено {len(articles)} новых статей для уведомления")
    
    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик ошибок"""
        logger.error(f"Exception while handling an update: {context.error}")
    
    def run_scheduler(self):
        """Запуск планировщика в отдельном потоке"""
        while True:
            schedule.run_pending()
            time.sleep(60)  # Проверка каждую минуту
    
    async def run(self):
        """Запуск бота"""
        # Запуск планировщика в фоновом режиме
        import threading
        scheduler_thread = threading.Thread(target=self.run_scheduler, daemon=True)
        scheduler_thread.start()
        
        logger.info("🚀 Запуск бота Naked Capitalism Monitor...")
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling(allowed_updates=Update.ALL_TYPES)
        
        # Ожидание завершения
        try:
            await asyncio.Event().wait()
        except KeyboardInterrupt:
            pass
        finally:
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()

def main():
    """Основная функция"""
    # Замените на ваш токен бота
    BOT_TOKEN = ""
    
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌ ОШИБКА: Необходимо указать токен бота!")
        print("📝 Инструкция:")
        print("1. Найдите @BotFather в Telegram")
        print("2. Отправьте команду /newbot")
        print("3. Следуйте инструкциям для создания бота")
        print("4. Скопируйте полученный токен и замените YOUR_BOT_TOKEN_HERE")
        return
    
    bot = NakedCapBot(BOT_TOKEN)
    
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")

if __name__ == "__main__":
    main()
