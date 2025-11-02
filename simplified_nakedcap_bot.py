#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import logging
import sqlite3
from datetime import datetime, timedelta

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

from article_monitor import NakedCapitalismMonitor

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('nakedcap_bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

BOT_TOKEN = "8114291381:AAFo7jRmm3vD_7o4Cthq8Q9pD31x3_qZWMU"

class SimplifiedNakedCapBot:
    def __init__(self):
        self.monitor = NakedCapitalismMonitor()
        self.application = None
        
    def get_total_articles_count(self):
        """Получить общее количество статей"""
        try:
            cursor = self.monitor.conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM articles')
            return cursor.fetchone()[0]
        except Exception as e:
            logger.error(f"Ошибка при получении количества статей: {e}")
            return 0

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик команды /start"""
        user = update.effective_user
        
        keyboard = [
            [InlineKeyboardButton("📰 Проверить статьи", callback_data="check_articles")],
            [InlineKeyboardButton("📚 Последние статьи", callback_data="latest_articles")],
            [InlineKeyboardButton("🔍 Поиск статей", callback_data="search_articles")],
            [InlineKeyboardButton("📊 Статистика", callback_data="stats")],
            [InlineKeyboardButton("❓ Справка", callback_data="help_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        welcome_message = (
            f"Привет, {user.first_name}! 👋\n\n"
            f"🤖 **Бот Naked Capitalism Monitor**\n\n"
            f"📰 **Мониторинг статей**\n"
            f"🔍 **Поиск по базе**\n"
            f"📊 **Статистика**\n\n"
            f"📚 **Статей в базе:** {self.get_total_articles_count()}\n"
            f"⏰ **Последняя проверка:** {datetime.now().strftime('%H:%M:%S')}"
        )
        
        # Проверяем тип обновления
        if update.callback_query:
            await update.callback_query.edit_message_text(
                welcome_message,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                welcome_message,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик команды /help"""
        help_text = (
            "📋 **Доступные команды:**\n\n"
            "🔍 **Мониторинг:**\n"
            "• `/check` - Проверить новые статьи\n"
            "• `/latest` - Последние статьи\n"
            "• `/stats` - Статистика\n"
            "• `/search [запрос]` - Поиск статей\n\n"
            "📚 **Всего статей:** {}".format(
                self.get_total_articles_count()
            )
        )
        
        # Добавляем кнопку назад
        keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if update.callback_query:
            await update.callback_query.edit_message_text(help_text, parse_mode='Markdown', reply_markup=reply_markup)
        else:
            await update.message.reply_text(help_text, parse_mode='Markdown', reply_markup=reply_markup)

    async def check_articles(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Проверка новых статей"""
        try:
            new_articles = self.monitor.check_for_new_articles()
            
            if new_articles:
                response = f"🆕 **Найдено новых статей:** {len(new_articles)}\n\n"
                for i, article in enumerate(new_articles[:5], 1):
                    response += f"{i}. **{article['title']}**\n"
                    response += f"   📅 {article['date']}\n"
                    response += f"   🔗 [Читать]({article['url']})\n\n"
                
                if len(new_articles) > 5:
                    response += f"... и еще {len(new_articles) - 5} статей"
            else:
                response = "✅ Новых статей не найдено"
            
            # Добавляем кнопку назад
            keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="main_menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Проверяем тип обновления
            if update.callback_query:
                await update.callback_query.edit_message_text(response, parse_mode='Markdown', reply_markup=reply_markup)
            else:
                await update.message.reply_text(response, parse_mode='Markdown', reply_markup=reply_markup)
            
        except Exception as e:
            logger.error(f"Ошибка при проверке статей: {e}")
            error_msg = "❌ Произошла ошибка при проверке статей"
            if update.callback_query:
                await update.callback_query.edit_message_text(error_msg)
            else:
                await update.message.reply_text(error_msg)

    async def latest_articles(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Показать последние статьи"""
        try:
            cursor = self.monitor.conn.cursor()
            cursor.execute('''
                SELECT title, url, author, date_posted
                FROM articles 
                ORDER BY created_at DESC 
                LIMIT 10
            ''')
            
            articles = cursor.fetchall()
            
            if articles:
                response = "📚 **Последние статьи:**\n\n"
                for i, (title, url, author, date) in enumerate(articles, 1):
                    response += f"{i}. **{title[:60]}...**\n"
                    response += f"   📅 {date}\n"
                    response += f"   🔗 [Читать]({url})\n\n"
            else:
                response = "❌ Статьи не найдены"
            
            # Добавляем кнопку назад
            keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="main_menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            if update.callback_query:
                await update.callback_query.edit_message_text(response, parse_mode='Markdown', reply_markup=reply_markup)
            else:
                await update.message.reply_text(response, parse_mode='Markdown', reply_markup=reply_markup)
            
        except Exception as e:
            logger.error(f"Ошибка при получении последних статей: {e}")
            error_msg = "❌ Произошла ошибка при получении статей"
            if update.callback_query:
                await update.callback_query.edit_message_text(error_msg)
            else:
                await update.message.reply_text(error_msg)

    async def search_articles(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Поиск статей"""
        if not context.args:
            response = (
                "🔍 **Поиск статей**\n\n"
                "Использование: `/search [запрос]`\n\n"
                "Примеры:\n"
                "• `/search trump`\n"
                "• `/search economics`\n"
                "• `/search politics`"
            )
            
            # Добавляем кнопку назад
            keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="main_menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            if update.callback_query:
                await update.callback_query.edit_message_text(response, parse_mode='Markdown', reply_markup=reply_markup)
            else:
                await update.message.reply_text(response, parse_mode='Markdown', reply_markup=reply_markup)
            return
        
        query = ' '.join(context.args).lower()
        
        try:
            # Поиск в статьях
            cursor = self.monitor.conn.cursor()
            cursor.execute('''
                SELECT title, url, author, date_posted
                FROM articles 
                WHERE LOWER(title) LIKE ? OR LOWER(author) LIKE ?
                ORDER BY created_at DESC
                LIMIT 10
            ''', (f'%{query}%', f'%{query}%'))
            
            results = cursor.fetchall()
            
            response = f"🔍 **Результаты поиска по запросу:** `{query}`\n\n"
            
            if results:
                response += f"📰 **Найдено статей:** {len(results)}\n\n"
                for i, (title, url, author, date) in enumerate(results[:5], 1):
                    response += f"{i}. **{title[:50]}...**\n"
                    response += f"   📅 {date}\n"
                    response += f"   🔗 [Читать]({url})\n\n"
                
                if len(results) > 5:
                    response += f"... и еще {len(results) - 5} статей"
            else:
                response += "❌ Статьи не найдены"
            
            # Добавляем кнопку назад
            keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="main_menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            if update.callback_query:
                await update.callback_query.edit_message_text(response, parse_mode='Markdown', reply_markup=reply_markup)
            else:
                await update.message.reply_text(response, parse_mode='Markdown', reply_markup=reply_markup)
            
        except Exception as e:
            logger.error(f"Ошибка при поиске статей: {e}")
            error_msg = "❌ Произошла ошибка при поиске"
            if update.callback_query:
                await update.callback_query.edit_message_text(error_msg)
            else:
                await update.message.reply_text(error_msg)

    async def stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Показать статистику"""
        try:
            cursor = self.monitor.conn.cursor()
            
            # Общая статистика
            cursor.execute('SELECT COUNT(*) FROM articles')
            total_articles = cursor.fetchone()[0]
            
            # Статьи за последние 7 дней
            week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
            cursor.execute('SELECT COUNT(*) FROM articles WHERE date_posted >= ?', (week_ago,))
            week_articles = cursor.fetchone()[0]
            
            # Статьи за сегодня
            today = datetime.now().strftime('%Y-%m-%d')
            cursor.execute('SELECT COUNT(*) FROM articles WHERE date_posted >= ?', (today,))
            today_articles = cursor.fetchone()[0]
            
            # Топ авторов
            cursor.execute('''
                SELECT author, COUNT(*) as count 
                FROM articles 
                GROUP BY author 
                ORDER BY count DESC 
                LIMIT 5
            ''')
            top_authors = cursor.fetchall()
            
            stats_text = (
                "📊 **Статистика статей**\n\n"
                f"📚 **Всего статей:** {total_articles}\n"
                f"📅 **За последние 7 дней:** {week_articles}\n"
                f"📆 **Сегодня:** {today_articles}\n\n"
            )
            
            if top_authors:
                stats_text += "👥 **Топ авторы:**\n"
                for author, count in top_authors:
                    stats_text += f"   • {author}: {count}\n"
            
            # Добавляем кнопку назад
            keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="main_menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            if update.callback_query:
                await update.callback_query.edit_message_text(stats_text, parse_mode='Markdown', reply_markup=reply_markup)
            else:
                await update.message.reply_text(stats_text, parse_mode='Markdown', reply_markup=reply_markup)
            
        except Exception as e:
            logger.error(f"Ошибка при получении статистики: {e}")
            error_msg = "❌ Произошла ошибка при получении статистики"
            if update.callback_query:
                await update.callback_query.edit_message_text(error_msg)
            else:
                await update.message.reply_text(error_msg)

    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик нажатий squeeze кнопки"""
        query = update.callback_query
        await query.answer()
        
        try:
            if query.data == "check_articles":
                await self.check_articles(update, context)
            elif query.data == "latest_articles":
                await self.latest_articles(update, context)
            elif query.data == "search_articles":
                await self.search_articles(update, context)
            elif query.data == "stats":
                await self.stats(update, context)
            elif query.data == "help_menu":
                await self.help_command(update, context)
            elif query.data == "main_menu":
                await self.start(update, context)
            else:
                await query.edit_message_text(
                    f"❓ Неизвестная команда: {query.data}\n\n"
                    "Используйте /help для получения списка команд."
                )
                
        except Exception as e:
            logger.error(f"Ошибка в button_callback: {e}")
            await query.edit_message_text(
                "❌ Произошла ошибка при обработке команды.\n"
                "Попробуйте еще раз или используйте /help."
            )

    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик ошибок"""
        logger.error(f"Exception while handling an update: {context.error}")

    def run_scheduler(self):
        """Запуск планировщика в отдельном потоке"""
        import schedule
        import time
        
        def check_articles_job():
            try:
                logger.info("🔄 Автоматическая проверка новых статей...")
                new_articles = self.monitor.check_for_new_articles()
                if new_articles:
                    logger.info(f"✅ Найдено {len(new_articles)} новых статей")
                else:
                    logger.info("ℹ️ Новых статей не найдено")
            except Exception as e:
                logger.error(f"Ошибка при автоматической проверке: {e}")
        
        # Планируем проверку каждый час
        schedule.every().hour.do(check_articles_job)
        
        logger.info("📅 Планировщик запущен - проверка каждый час")
        
        while True:
            schedule.run_pending()
            time.sleep(60)

    async def run(self):
        """Запуск бота"""
        if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
            print("❌ ОШИБКА: Необходимо указать токен бота!")
            print("📝 Инструкция:")
            print("1. Найдите @BotFather в Telegram")
            print("2. Отправьте команду /newbot")
            print("3. Следуйте инструкциям для создания бота")
            print("4. Скопируйте полученный токен и замените YOUR_BOT_TOKEN_HERE")
            return

        # Создаем приложение
        self.application = Application.builder().token(BOT_TOKEN).build()

        # Добавляем обработчики
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("check", self.check_articles))
        self.application.add_handler(CommandHandler("latest", self.latest_articles))
        self.application.add_handler(CommandHandler("search", self.search_articles))
        self.application.add_handler(CommandHandler("stats", self.stats))
        self.application.add_handler(CallbackQueryHandler(self.button_callback))

        # Добавляем обработчик ошибок
        self.application.add_error_handler(self.error_handler)

        # Запуск планировщика в фоновом режиме
        import threading
        scheduler_thread = threading.Thread(target=self.run_scheduler, daemon=True)
        scheduler_thread.start()

        logger.info("🚀 Запуск упрощенного бота Naked Capitalism...")
        
        # Инициализация и запуск
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling(allowed_updates=["message", "callback_query"])

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
    bot = SimplifiedNakedCapBot()
    
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        print("\n👋 Бот остановлен пользователем")
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")

if __name__ == "__main__":
    main()
