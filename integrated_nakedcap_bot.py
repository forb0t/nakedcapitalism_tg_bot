"""
Интегрированный Telegram бот для мониторинга статей Naked Capitalism
"""

import asyncio
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler
from article_monitor import NakedCapitalismMonitor
from telegraph_article_converter import TelegraphArticleConverter

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class IntegratedNakedCapBot:
    def __init__(self, bot_token, telegraph_token: str = None, auto_publish: bool = False):
        self.bot_token = bot_token
        self.monitor = NakedCapitalismMonitor()
        self.telegraph_converter = TelegraphArticleConverter(telegraph_token=telegraph_token)
        self.auto_publish = auto_publish  # Автоматическая публикация новых статей
        self.application = Application.builder().token(bot_token).build()
        
        self.setup_handlers()
    
    def setup_handlers(self):
        """Настройка обработчиков команд"""
        # Основные команды
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("help", self.help_command))
        
        # Мониторинг
        self.application.add_handler(CommandHandler("check", self.check_articles))
        self.application.add_handler(CommandHandler("latest", self.latest_articles))
        self.application.add_handler(CommandHandler("stats", self.stats))
        self.application.add_handler(CommandHandler("monitor", self.toggle_monitoring))
        
        # Telegraph команды
        self.application.add_handler(CommandHandler("publish", self.publish_to_telegraph))
        self.application.add_handler(CommandHandler("publish_all", self.publish_all_unpublished))
        self.application.add_handler(CommandHandler("telegraph_stats", self.telegraph_stats))
        self.application.add_handler(CommandHandler("telegraph_latest", self.telegraph_latest))
        
        # Inline кнопки
        self.application.add_handler(CallbackQueryHandler(self.button_callback))
        
        # Обработчик ошибок
        self.application.add_error_handler(self.error_handler)
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик команды /start"""
        user = update.effective_user
        
        keyboard = [
            [InlineKeyboardButton("📰 Проверить статьи", callback_data="check_articles")],
            [InlineKeyboardButton("📚 Последние статьи", callback_data="latest_articles")],
            [InlineKeyboardButton("📊 Статистика", callback_data="stats")],
            [InlineKeyboardButton("❓ Справка", callback_data="help_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        welcome_message = (
            f"Привет, {user.first_name}! 👋\n\n"
            f"🤖 **Интегрированный бот Naked Capitalism**\n\n"
            f"📰 **Мониторинг:** Автоматическое отслеживание новых статей\n"
            f"📊 **Аналитика:** Статистика и отчеты\n\n"
            f"📚 **Статей в базе:** {self.get_total_articles_count()}\n\n"
            f"Используйте кнопки ниже или команды для управления ботом."
        )
        
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
            "• `/monitor` - Управление мониторингом\n\n"
            "📚 **Всего статей:** {}\n\n"
            "📝 **Telegraph команды:**\n"
            "• `/publish [id]` - Опубликовать статью в Telegraph\n"
            "• `/publish_all` - Опубликовать все неопубликованные статьи"
        ).format(
                self.get_total_articles_count()
            )
        
        # Добавляем кнопку назад
        keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(help_text, parse_mode='Markdown', reply_markup=reply_markup)
    
    async def search_articles(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Поиск статей"""
        if not context.args:
            await update.message.reply_text(
                "🔍 **Поиск статей**\n\n"
                "Использование: `/search [запрос]`\n\n"
                "Примеры:\n"
                "• `/search trump`\n"
                "• `/search economics`\n"
                "• `/search #technology`",
                parse_mode='Markdown'
            )
            return
        
        query = ' '.join(context.args).lower()
        
        # Поиск в обычных статьях
        cursor = self.monitor.conn.cursor()
        cursor.execute('''
            SELECT title, url, author, date_posted
            FROM articles 
            WHERE LOWER(title) LIKE ? OR LOWER(author) LIKE ?
            ORDER BY created_at DESC
            LIMIT 10
        ''', (f'%{query}%', f'%{query}%'))
        
        regular_results = cursor.fetchall()
        
        response = f"🔍 **Результаты поиска по запросу:** `{query}`\n\n"
        
        if regular_results:
            response += f"📰 **Найдено статей:** {len(regular_results)}\n\n"
            for i, (title, url, author, date) in enumerate(regular_results[:10], 1):
                response += f"{i}. {title[:50]}...\n"
                response += f"   👤 {author} | 📅 {date}\n\n"
        if not regular_results:
            response += "❌ Статьи не найдены"
        
        # Добавляем кнопку назад
        keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(response, parse_mode='Markdown', reply_markup=reply_markup)
    
    async def check_articles(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Проверка новых статей"""
        if update.message:
            message = await update.message.reply_text("🔍 Проверяю новые статьи...")
        elif update.callback_query:
            await update.callback_query.answer()
            message = await update.callback_query.message.reply_text("🔍 Проверяю новые статьи...")
        else:
            return
        
        try:
            new_articles = self.monitor.check_for_new_articles()
            
            if new_articles:
                response = f"✅ **Найдено {len(new_articles)} новых статей!**\n\n"
                for i, article in enumerate(new_articles[:5], 1):
                    response += f"**{i}.** {article['title'][:50]}...\n"
                    response += f"   👤 {article['author']} | 📅 {article['date_posted']}\n\n"
                
                if len(new_articles) > 5:
                    response += f"... и еще {len(new_articles) - 5} статей\n\n"
                
                # Предложение опубликовать в Telegraph
                response += "💡 Используйте `/publish_all` для автоматической публикации в Telegraph"
                
                keyboard = [
                    [InlineKeyboardButton("📚 Показать все", callback_data="latest_articles")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                # Автоматическая публикация, если включена
                if self.auto_publish and new_articles:
                    await message.edit_text(
                        response + "\n\n⏳ Автоматическая публикация в Telegraph...",
                        reply_markup=reply_markup,
                        parse_mode='Markdown'
                    )
                    # Получаем ID новых статей и публикуем
                    try:
                        cursor = self.monitor.conn.cursor()
                        article_ids = []
                        for article in new_articles:
                            cursor.execute("SELECT id FROM articles WHERE url = ?", (article['url'],))
                            result = cursor.fetchone()
                            if result:
                                article_ids.append(result[0])
                        
                        if article_ids:
                            results = self.telegraph_converter.publish_multiple_articles(article_ids=article_ids)
                            successful = sum(1 for r in results if r['success'])
                            response += f"\n\n✅ Автоматически опубликовано в Telegraph: {successful}/{len(results)}"
                            await message.edit_text(
                                response,
                                reply_markup=reply_markup,
                                parse_mode='Markdown'
                            )
                    except Exception as e:
                        logger.error(f"Ошибка при автоматической публикации: {e}")
                
                if not self.auto_publish:
                    await message.edit_text(
                        response,
                        reply_markup=reply_markup,
                        parse_mode='Markdown'
                    )
            else:
                await message.edit_text("📝 Новых статей не найдено")
                
        except Exception as e:
            logger.error(f"Ошибка при проверке статей: {e}")
            if 'message' in locals():
                await message.edit_text("❌ Произошла ошибка при проверке статей")
            elif update.callback_query:
                await update.callback_query.edit_message_text("❌ Произошла ошибка при проверке статей")
    
    async def latest_articles(self, update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0) -> None:
        """Показ последних статей с пагинацией"""
        try:
            articles_per_page = 10
            offset = page * articles_per_page
            
            latest = self.monitor.get_latest_articles(limit=articles_per_page, offset=offset)
            total_articles = self.monitor.get_total_articles_count()
            total_pages = (total_articles + articles_per_page - 1) // articles_per_page if total_articles > 0 else 1
            
            if latest:
                response = f"📚 **Последние статьи** (Страница {page + 1} из {total_pages}):\n\n"
                
                # Нумерация статей на странице
                start_num = offset + 1
                for i, article in enumerate(latest):
                    article_num = start_num + i
                    # Обработка случая с telegraph_url (может быть или не быть)
                    if len(article) >= 6:
                        title, url, author, date_posted, created_at, telegraph_url = article
                    else:
                        title, url, author, date_posted, created_at = article
                        telegraph_url = None
                    
                    response += f"**{article_num}.** [{title}]({url})\n"
                    response += f"   👤 {author} | 📅 {date_posted}"
                    
                    # Добавляем ссылку на Telegraph версию, если она есть
                    if telegraph_url and telegraph_url.strip():
                        response += f" | [📝 Telegraph]({telegraph_url})"
                    
                    response += "\n\n"
                
                # Создаем кнопки навигации
                keyboard = []
                nav_buttons = []
                
                # Кнопка "Назад"
                if page > 0:
                    nav_buttons.append(InlineKeyboardButton("◀️ Назад", callback_data=f"latest_page_{page - 1}"))
                
                # Индикатор страницы (опционально, можно убрать если не нужен)
                nav_buttons.append(InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="page_info"))
                
                # Кнопка "Вперед"
                if page < total_pages - 1:
                    nav_buttons.append(InlineKeyboardButton("Вперед ▶️", callback_data=f"latest_page_{page + 1}"))
                
                if nav_buttons:
                    keyboard.append(nav_buttons)
                
                # Кнопка "Назад в меню"
                keyboard.append([InlineKeyboardButton("⬅️ Назад в меню", callback_data="main_menu")])
                
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                if update.message:
                    await update.message.reply_text(
                        response,
                        parse_mode='Markdown',
                        disable_web_page_preview=True,
                        reply_markup=reply_markup
                    )
                else:
                    await update.callback_query.edit_message_text(
                        response,
                        parse_mode='Markdown',
                        disable_web_page_preview=True,
                        reply_markup=reply_markup
                    )
            else:
                if update.message:
                    await update.message.reply_text("📝 Статей в базе данных нет")
                else:
                    await update.callback_query.edit_message_text("📝 Статей в базе данных нет")
                
        except Exception as e:
            logger.error(f"Ошибка при получении статей: {e}")
            if update.message:
                await update.message.reply_text("❌ Произошла ошибка при получении статей")
            else:
                await update.callback_query.edit_message_text("❌ Произошла ошибка при получении статей")
    
    async def stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Статистика"""
        try:
            cursor = self.monitor.conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM articles")
            total_articles = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM articles WHERE created_at >= date('now', '-1 day')")
            today_articles = cursor.fetchone()[0]
            
            stats_text = (
                f"📊 **Статистика Naked Capitalism Bot**\n\n"
                f"📚 **База данных:**\n"
                f"   • Всего статей: {total_articles}\n"
                f"   • За сегодня: {today_articles}\n"
            )
            
            if update.message:
                await update.message.reply_text(stats_text, parse_mode='Markdown')
            else:
                await update.callback_query.edit_message_text(stats_text, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Ошибка при получении статистики: {e}")
            if update.message:
                await update.message.reply_text("❌ Произошла ошибка при получении статистики")
            elif update.callback_query:
                await update.callback_query.edit_message_text("❌ Произошла ошибка при получении статистики")
    
    async def toggle_monitoring(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Переключение мониторинга"""
        # Здесь можно добавить логику управления мониторингом
        await update.message.reply_text("⚙️ Функция управления мониторингом в разработке")
    
    async def publish_to_telegraph(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Публикация статьи в Telegraph"""
        if not context.args:
            await update.message.reply_text(
                "📝 **Публикация в Telegraph**\n\n"
                "Использование: `/publish [id]`\n\n"
                "Пример:\n"
                "• `/publish 1` - Опубликовать статью с ID 1\n\n"
                "Используйте `/latest` чтобы узнать ID статей.",
                parse_mode='Markdown'
            )
            return
        
        try:
            article_id = int(context.args[0])
            message = await update.message.reply_text(f"📤 Публикация статьи {article_id} в Telegraph...")
            
            result = self.telegraph_converter.publish_article_to_telegraph(article_id)
            
            if result:
                response = (
                    f"✅ **Статья успешно опубликована!**\n\n"
                    f"📝 Заголовок: {result.get('title', 'N/A')}\n"
                    f"🔗 Telegraph URL: {result.get('url')}\n"
                    f"📊 Просмотров: {result.get('views', 0)}"
                )
                await message.edit_text(response, parse_mode='Markdown')
            else:
                await message.edit_text("❌ Ошибка при публикации статьи. Проверьте ID или попробуйте позже.")
                
        except ValueError:
            await update.message.reply_text("❌ Неверный ID статьи. Используйте число, например: `/publish 1`", parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Ошибка при публикации в Telegraph: {e}")
            await update.message.reply_text(f"❌ Произошла ошибка: {str(e)}")
    
    async def publish_all_unpublished(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Публикация всех неопубликованных статей"""
        limit = 10
        if context.args:
            try:
                limit = int(context.args[0])
            except ValueError:
                pass
        
        message = await update.message.reply_text(f"📤 Публикация до {limit} неопубликованных статей в Telegraph...")
        
        try:
            results = self.telegraph_converter.publish_multiple_articles(limit=limit)
            
            successful = sum(1 for r in results if r['success'])
            failed = len(results) - successful
            
            response = (
                f"📊 **Результаты публикации:**\n\n"
                f"✅ Успешно: {successful}\n"
                f"❌ Ошибок: {failed}\n\n"
            )
            
            if successful > 0:
                response += "**Опубликованные статьи:**\n"
                for result in results[:5]:  # Показываем первые 5
                    if result['success']:
                        response += f"• [{result['article_id']}]({result['telegraph_url']})\n"
            
            await message.edit_text(response, parse_mode='Markdown', disable_web_page_preview=True)
            
        except Exception as e:
            logger.error(f"Ошибка при массовой публикации: {e}")
            await message.edit_text(f"❌ Произошла ошибка: {str(e)}")
    
    async def telegraph_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Статистика публикаций в Telegraph"""
        try:
            stats = self.telegraph_converter.get_statistics()
            
            response = (
                f"📊 **Статистика Telegraph:**\n\n"
                f"📚 Всего статей: {stats['total_articles']}\n"
                f"✅ Опубликовано: {stats['published_telegraph']}\n"
                f"⏳ Не опубликовано: {stats['unpublished']}\n"
                f"📈 Процент: {stats['publish_percentage']}%"
            )
            
            await update.message.reply_text(response, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Ошибка при получении статистики Telegraph: {e}")
            await update.message.reply_text("❌ Произошла ошибка при получении статистики")
    
    async def telegraph_latest(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Последние опубликованные статьи в Telegraph"""
        try:
            limit = 10
            if context.args:
                try:
                    limit = int(context.args[0])
                except ValueError:
                    pass
            
            published = self.telegraph_converter.get_published_articles(limit=limit)
            
            if published:
                response = f"📝 **Последние опубликованные статьи в Telegraph:**\n\n"
                for i, article in enumerate(published, 1):
                    article_id, title, url, author, date_posted, telegraph_url = article
                    response += f"**{i}.** [{title[:50]}...]({telegraph_url})\n"
                    response += f"   👤 {author} | 📅 {date_posted}\n\n"
                
                await update.message.reply_text(
                    response,
                    parse_mode='Markdown',
                    disable_web_page_preview=True
                )
            else:
                await update.message.reply_text("📝 Еще нет опубликованных статей в Telegraph")
                
        except Exception as e:
            logger.error(f"Ошибка при получении опубликованных статей: {e}")
            await update.message.reply_text("❌ Произошла ошибка при получении статей")
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик нажатий на кнопки"""
        query = update.callback_query
        await query.answer()
        
        try:
            # Обработка основных команд
            if query.data == "check_articles":
                await self.check_articles(update, context)
            elif query.data == "latest_articles":
                await self.latest_articles(update, context, page=0)
            elif query.data.startswith("latest_page_"):
                # Обработка переключения страниц
                try:
                    page = int(query.data.split("_")[2])
                    await self.latest_articles(update, context, page=page)
                except (ValueError, IndexError):
                    await query.answer("Ошибка переключения страницы")
            elif query.data == "page_info":
                # Просто ответ на нажатие индикатора страницы
                await query.answer()
            elif query.data == "stats":
                await self.stats(update, context)
            elif query.data == "main_menu":
                await self.start(update, context)
            elif query.data == "help_menu":
                await self.help_command(update, context)
            
            # Обработка поиска статей
            elif query.data == "search_articles":
                await query.edit_message_text(
                    "🔍 **Поиск статей**\n\n"
                    "Используйте команду: `/search [запрос]`\n\n"
                    "Примеры:\n"
                    "• `/search trump`\n"
                    "• `/search economics`\n"
                    "• `/search #technology`",
                    parse_mode='Markdown'
                )
            
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
    
    def get_total_articles_count(self):
        """Получение общего количества статей в базе"""
        try:
            cursor = self.monitor.conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM articles")
            return cursor.fetchone()[0]
        except:
            return 0
    
    async def run(self):
        """Запуск бота"""
        logger.info("🚀 Запуск интегрированного бота Naked Capitalism...")
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
    BOT_TOKEN = "8114291381:AAFo7jRmm3vD_7o4Cthq8Q9pD31x3_qZWMU"
    
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌ ОШИБКА: Необходимо указать токен бота!")
        return
    
    bot = IntegratedNakedCapBot(BOT_TOKEN)
    
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")

if __name__ == "__main__":
    main()
