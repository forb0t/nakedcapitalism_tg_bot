"""
Интегрированный Telegram бот с поддержкой Teletype версий статей
"""

import asyncio
import logging
import json
import os
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler
from article_monitor import NakedCapitalismMonitor
from teletype_converter import TeletypeConverter
from article_processor import ArticleProcessor

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class IntegratedNakedCapBot:
    def __init__(self, bot_token):
        self.bot_token = bot_token
        self.monitor = NakedCapitalismMonitor()
        self.converter = TeletypeConverter()
        self.processor = ArticleProcessor()
        self.application = Application.builder().token(bot_token).build()
        
        # Загрузка Teletype статей
        self.teletype_articles = self.load_teletype_articles()
        
        self.setup_handlers()
    
    def load_teletype_articles(self):
        """Загрузка Teletype статей из файла"""
        try:
            # Поиск последнего файла с Teletype статьями
            teletype_files = [f for f in os.listdir('.') if f.startswith('full_teletype_articles_') and f.endswith('.json')]
            
            if teletype_files:
                latest_file = sorted(teletype_files)[-1]
                with open(latest_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                articles = data.get('articles', [])
                logger.info(f"✅ Загружено {len(articles)} Teletype статей из {latest_file}")
                return articles
            else:
                logger.warning("⚠️ Файлы Teletype статей не найдены")
                return []
                
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки Teletype статей: {e}")
            return []
    
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
        
        # Teletype функции
        self.application.add_handler(CommandHandler("teletype", self.teletype_menu))
        self.application.add_handler(CommandHandler("convert", self.convert_command))
        self.application.add_handler(CommandHandler("search", self.search_articles))
        self.application.add_handler(CommandHandler("categories", self.show_categories))
        self.application.add_handler(CommandHandler("tags", self.show_tags))
        
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
            [InlineKeyboardButton("🔄 Teletype конвертация", callback_data="teletype_menu")],
            [InlineKeyboardButton("🔍 Поиск статей", callback_data="search_articles")],
            [InlineKeyboardButton("📊 Статистика", callback_data="stats")],
            [InlineKeyboardButton("❓ Справка", callback_data="help_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        welcome_message = (
            f"Привет, {user.first_name}! 👋\n\n"
            f"🤖 **Интегрированный бот Naked Capitalism**\n\n"
            f"📰 **Мониторинг:** Автоматическое отслеживание новых статей\n"
            f"🔄 **Teletype:** Конвертация в формат Teletype\n"
            f"🔍 **Поиск:** Поиск по статьям и тегам\n"
            f"📊 **Аналитика:** Статистика и отчеты\n\n"
            f"💡 **Teletype статей загружено:** {len(self.teletype_articles)}\n"
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
            "🔄 **Teletype функции:**\n"
            "• `/teletype` - Меню конвертации\n"
            "• `/convert [число]` - Конвертировать статьи\n"
            "• `/search [запрос]` - Поиск статей\n"
            "• `/categories` - Показать категории\n"
            "• `/tags` - Показать теги\n\n"
            "💡 **Teletype статей:** {}\n"
            "📚 **Всего статей:** {}".format(
                len(self.teletype_articles),
                self.get_total_articles_count()
            )
        )
        
        # Добавляем кнопку назад
        keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(help_text, parse_mode='Markdown', reply_markup=reply_markup)
    
    async def teletype_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Меню Teletype функций"""
        keyboard = [
            [InlineKeyboardButton("📖 Показать Teletype статьи", callback_data="show_teletype")],
            [InlineKeyboardButton("🔍 Поиск в Teletype", callback_data="search_teletype")],
            [InlineKeyboardButton("📂 По категориям", callback_data="teletype_categories")],
            [InlineKeyboardButton("🏷️ По тегам", callback_data="teletype_tags")],
            [InlineKeyboardButton("🔄 Конвертировать новые", callback_data="convert_new")],
            [InlineKeyboardButton("📤 Экспорт статей", callback_data="export_teletype")],
            [InlineKeyboardButton("⬅️ Назад", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        menu_text = (
            f"🔄 **Teletype функции**\n\n"
            f"📚 **Загружено статей:** {len(self.teletype_articles)}\n"
            f"📊 **Категорий:** {len(set(a['metadata']['category'] for a in self.teletype_articles))}\n"
            f"🏷️ **Уникальных тегов:** {len(set(tag for a in self.teletype_articles for tag in a['metadata']['tags']))}\n\n"
            f"Выберите действие:"
        )
        
        if update.message:
            await update.message.reply_text(menu_text, reply_markup=reply_markup, parse_mode='Markdown')
        else:
            await update.callback_query.edit_message_text(menu_text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def show_teletype_articles(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Показать Teletype статьи"""
        q = update.callback_query
        
        if not self.teletype_articles:
            await q.edit_message_text(
                "❌ Teletype статьи не загружены. Используйте /convert для создания."
            )
            return
        
        # Создаем кнопки для статей
        keyboard = []
        articles_per_page = 5
        page = int(context.user_data.get('teletype_page', 0))
        start_idx = page * articles_per_page
        end_idx = start_idx + articles_per_page
        
        articles = self.teletype_articles[start_idx:end_idx]
        
        for i, article in enumerate(articles):
            title = article['metadata']['title'][:40] + "..." if len(article['metadata']['title']) > 40 else article['metadata']['title']
            callback_data = f"show_article_{start_idx + i}"
            keyboard.append([InlineKeyboardButton(f"📖 {title}", callback_data=callback_data)])
        
        # Навигационные кнопки
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"teletype_page_{page-1}"))
        if end_idx < len(self.teletype_articles):
            nav_buttons.append(InlineKeyboardButton("➡️ Далее", callback_data=f"teletype_page_{page+1}"))
        
        if nav_buttons:
            keyboard.append(nav_buttons)
        
        keyboard.extend([
            [InlineKeyboardButton("🔍 Поиск", callback_data="search_teletype")],
            [InlineKeyboardButton("📂 Категории", callback_data="teletype_categories")],
            [InlineKeyboardButton("⬅️ Назад к меню Teletype", callback_data="teletype_menu")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        response = (
            f"📖 **Teletype статьи** (стр. {page + 1})\n\n"
            f"📚 Показано {len(articles)} из {len(self.teletype_articles)} статей\n"
            f"💡 Нажмите на статью для просмотра полного контента"
        )
        
        await q.edit_message_text(
            response,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def show_article_content(self, update: Update, context: ContextTypes.DEFAULT_TYPE, article_index: int) -> None:
        """Показать полный контент статьи"""
        q = update.callback_query
        
        if article_index >= len(self.teletype_articles):
            await q.answer("❌ Статья не найдена", show_alert=True)
            return
        
        article = self.teletype_articles[article_index]
        
        # Ограничиваем размер сообщения (Telegram лимит ~4000 символов)
        content = article['content']
        if len(content) > 3500:
            content = content[:3500] + "\n\n*[Контент сокращен для отображения в Telegram]*"
        
        # Создаем клавиатуру для навигации
        keyboard = [
            [InlineKeyboardButton("🔗 Открыть оригинал", url=article['metadata']['url'])],
            [InlineKeyboardButton("⬅️ Назад к списку", callback_data="show_teletype")],
            [InlineKeyboardButton("🔍 Поиск", callback_data="search_teletype")],
            [InlineKeyboardButton("⬅️ Меню Teletype", callback_data="teletype_menu")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
        ]
        
        # Добавляем кнопки для соседних статей
        nav_buttons = []
        if article_index > 0:
            nav_buttons.append(InlineKeyboardButton("⬅️ Предыдущая", callback_data=f"show_article_{article_index-1}"))
        if article_index < len(self.teletype_articles) - 1:
            nav_buttons.append(InlineKeyboardButton("➡️ Следующая", callback_data=f"show_article_{article_index+1}"))
        
        if nav_buttons:
            keyboard.insert(1, nav_buttons)
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Отправляем контент
        try:
            await q.edit_message_text(
                content,
                reply_markup=reply_markup,
                parse_mode='Markdown',
                disable_web_page_preview=True
            )
        except Exception as e:
            # Если сообщение слишком длинное, разбиваем на части
            await self.send_article_in_parts(q, article, reply_markup)
    
    async def send_article_in_parts(self, query, article, reply_markup):
        """Отправка статьи по частям"""
        content = article['content']
        max_length = 3000
        
        # Разбиваем контент на части
        parts = []
        while content:
            if len(content) <= max_length:
                parts.append(content)
                break
            else:
                # Находим последний перенос строки в пределах лимита
                split_point = content.rfind('\n', 0, max_length)
                if split_point == -1:
                    split_point = max_length
                
                parts.append(content[:split_point])
                content = content[split_point:].lstrip()
        
        # Отправляем первую часть
        await query.edit_message_text(
            parts[0],
            reply_markup=reply_markup,
            parse_mode='Markdown',
            disable_web_page_preview=True
        )
        
        # Отправляем остальные части как новые сообщения
        for part in parts[1:]:
            await query.message.reply_text(
                part,
                parse_mode='Markdown',
                disable_web_page_preview=True
            )
    
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
        
        # Поиск в Teletype статьях
        teletype_results = []
        for article in self.teletype_articles:
            if (query in article['metadata']['title'].lower() or 
                query in article['metadata']['author'].lower() or
                any(query in tag.lower() for tag in article['metadata']['tags'])):
                teletype_results.append(article)
        
        response = f"🔍 **Результаты поиска по запросу:** `{query}`\n\n"
        
        if regular_results:
            response += f"📰 **Обычные статьи** ({len(regular_results)}):\n"
            for i, (title, url, author, date) in enumerate(regular_results[:5], 1):
                response += f"{i}. {title[:50]}...\n"
                response += f"   👤 {author} | 📅 {date}\n\n"
        
        if teletype_results:
            response += f"📖 **Teletype статьи** ({len(teletype_results)}):\n"
            for i, article in enumerate(teletype_results[:5], 1):
                content_status = "📖" if article['metadata'].get('has_full_content') else "📝"
                response += f"{i}. {content_status} {article['metadata']['title'][:50]}...\n"
                response += f"   🏷️ {article['metadata']['category']} | 📅 {article['metadata']['date']}\n\n"
        
        if not regular_results and not teletype_results:
            response += "❌ Статьи не найдены"
        
        # Добавляем кнопку назад
        keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(response, parse_mode='Markdown', reply_markup=reply_markup)
    
    async def show_categories(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Показать категории статей"""
        # Категории обычных статей
        cursor = self.monitor.conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM articles')
        total_articles = cursor.fetchone()[0]
        
        # Категории Teletype статей
        teletype_categories = {}
        for article in self.teletype_articles:
            category = article['metadata']['category']
            teletype_categories[category] = teletype_categories.get(category, 0) + 1
        
        response = "📂 **Категории статей:**\n\n"
        response += f"📚 **Всего статей в базе:** {total_articles}\n"
        response += f"📖 **Teletype статей:** {len(self.teletype_articles)}\n\n"
        
        if teletype_categories:
            response += "🏷️ **Категории Teletype статей:**\n"
            for category, count in sorted(teletype_categories.items(), key=lambda x: x[1], reverse=True):
                response += f"• **{category}:** {count} статей\n"
        
        # Добавляем кнопку назад
        keyboard = [[InlineKeyboardButton("⬅️ Назад к меню Teletype", callback_data="teletype_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(response, parse_mode='Markdown', reply_markup=reply_markup)
    
    async def show_tags(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Показать теги"""
        # Сбор всех тегов из Teletype статей
        all_tags = {}
        for article in self.teletype_articles:
            for tag in article['metadata']['tags']:
                all_tags[tag] = all_tags.get(tag, 0) + 1
        
        # Топ-15 тегов
        top_tags = sorted(all_tags.items(), key=lambda x: x[1], reverse=True)[:15]
        
        response = f"🏷️ **Топ теги** ({len(all_tags)} уникальных):\n\n"
        
        for tag, count in top_tags:
            response += f"#{tag}: {count}\n"
        
        # Добавляем кнопку назад
        keyboard = [[InlineKeyboardButton("⬅️ Назад к меню Teletype", callback_data="teletype_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(response, parse_mode='Markdown', reply_markup=reply_markup)
    
    async def convert_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Команда конвертации статей"""
        try:
            limit = 5
            if context.args:
                try:
                    limit = int(context.args[0])
                    limit = min(limit, 20)
                except ValueError:
                    limit = 5
            
            message = await update.message.reply_text(f"🔄 Конвертация {limit} статей в Teletype...")
            
            # Конвертация статей
            articles = self.converter.convert_latest_articles(limit)
            
            if articles:
                response = f"✅ **Конвертировано {len(articles)} статей**\n\n"
                
                for i, article in enumerate(articles[:3], 1):
                    response += f"**{i}.** {article['metadata']['title'][:50]}...\n"
                    response += f"   🏷️ {article['metadata']['category']} | 🔖 {len(article['metadata']['tags'])} тегов\n\n"
                
                if len(articles) > 3:
                    response += f"... и еще {len(articles) - 3} статей"
                
                # Обновляем загруженные статьи
                self.teletype_articles.extend(articles)
                
                keyboard = [
                    [InlineKeyboardButton("📖 Показать Teletype", callback_data="show_teletype")],
                    [InlineKeyboardButton("📤 Экспорт", callback_data="export_teletype")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await message.edit_text(
                    response,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
            else:
                await message.edit_text("❌ Не удалось конвертировать статьи")
                
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка конвертации: {str(e)}")
    
    async def check_articles(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Проверка новых статей"""
        message = await update.message.reply_text("🔍 Проверяю новые статьи...")
        
        try:
            new_articles = self.monitor.check_for_new_articles()
            
            if new_articles:
                response = f"✅ **Найдено {len(new_articles)} новых статей!**\n\n"
                for i, article in enumerate(new_articles[:5], 1):
                    response += f"**{i}.** {article['title'][:50]}...\n"
                    response += f"   👤 {article['author']} | 📅 {article['date_posted']}\n\n"
                
                if len(new_articles) > 5:
                    response += f"... и еще {len(new_articles) - 5} статей"
                
                keyboard = [
                    [InlineKeyboardButton("🔄 Конвертировать в Teletype", callback_data="convert_new")],
                    [InlineKeyboardButton("📚 Показать все", callback_data="latest_articles")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await message.edit_text(
                    response,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
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
                response = "📚 **Последние статьи:**\n\n"
                for i, article in enumerate(latest, 1):
                    title, url, author, date_posted, created_at = article
                    response += f"**{i}.** [{title}]({url})\n"
                    response += f"   👤 {author} | 📅 {date_posted}\n\n"
                
                keyboard = [
                    [InlineKeyboardButton("🔄 Конвертировать в Teletype", callback_data="convert_new")],
                    [InlineKeyboardButton("📖 Показать Teletype", callback_data="show_teletype")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                if update.message:
                    await update.message.reply_text(
                        response,
                        reply_markup=reply_markup,
                        parse_mode='Markdown',
                        disable_web_page_preview=True
                    )
                else:
                    await update.callback_query.edit_message_text(
                        response,
                        reply_markup=reply_markup,
                        parse_mode='Markdown',
                        disable_web_page_preview=True
                    )
            else:
                await update.message.reply_text("📝 Статей в базе данных нет")
                
        except Exception as e:
            logger.error(f"Ошибка при получении статей: {e}")
            await update.message.reply_text("❌ Произошла ошибка при получении статей")
    
    async def stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Статистика"""
        try:
            cursor = self.monitor.conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM articles")
            total_articles = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM articles WHERE created_at >= date('now', '-1 day')")
            today_articles = cursor.fetchone()[0]
            
            # Статистика Teletype статей
            teletype_categories = {}
            teletype_tags = {}
            
            for article in self.teletype_articles:
                # Категории
                category = article['metadata']['category']
                teletype_categories[category] = teletype_categories.get(category, 0) + 1
                
                # Теги
                for tag in article['metadata']['tags']:
                    teletype_tags[tag] = teletype_tags.get(tag, 0) + 1
            
            stats_text = (
                f"📊 **Статистика Naked Capitalism Bot**\n\n"
                f"📚 **База данных:**\n"
                f"   • Всего статей: {total_articles}\n"
                f"   • За сегодня: {today_articles}\n\n"
                f"📖 **Teletype статьи:**\n"
                f"   • Конвертировано: {len(self.teletype_articles)}\n"
                f"   • Категорий: {len(teletype_categories)}\n"
                f"   • Уникальных тегов: {len(teletype_tags)}\n\n"
                f"🏷️ **Топ категории Teletype:**\n"
            )
            
            for category, count in sorted(teletype_categories.items(), key=lambda x: x[1], reverse=True)[:5]:
                stats_text += f"   • {category}: {count}\n"
            
            stats_text += f"\n🏷️ **Топ теги:**\n"
            top_tags = sorted(teletype_tags.items(), key=lambda x: x[1], reverse=True)[:5]
            for tag, count in top_tags:
                stats_text += f"   • #{tag}: {count}\n"
            
            await update.message.reply_text(stats_text, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Ошибка при получении статистики: {e}")
            await update.message.reply_text("❌ Произошла ошибка при получении статистики")
    
    async def toggle_monitoring(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Переключение мониторинга"""
        # Здесь можно добавить логику управления мониторингом
        await update.message.reply_text("⚙️ Функция управления мониторингом в разработке")
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик нажатий на кнопки"""
        query = update.callback_query
        await query.answer()
        
        try:
            # Обработка основных команд
            if query.data == "check_articles":
                await self.check_articles(update, context)
            elif query.data == "latest_articles":
                await self.latest_articles(update, context)
            elif query.data == "stats":
                await self.stats(update, context)
            elif query.data == "teletype_menu":
                await self.teletype_menu(update, context)
            elif query.data == "show_teletype":
                await self.show_teletype_articles(update, context)
            elif query.data == "search_teletype":
                await query.edit_message_text(
                    "🔍 **Поиск в Teletype статьях**\n\n"
                    "Используйте команду: `/search [запрос]`\n\n"
                    "Примеры:\n"
                    "• `/search trump`\n"
                    "• `/search economics`\n"
                    "• `/search #technology`",
                    parse_mode='Markdown'
                )
            elif query.data == "teletype_categories":
                await self.show_categories(update, context)
            elif query.data == "teletype_tags":
                await self.show_tags(update, context)
            elif query.data == "convert_new":
                await self.convert_command(update, context)
            elif query.data == "export_teletype":
                await query.edit_message_text(
                    "📤 **Экспорт Teletype статей**\n\n"
                    "Для экспорта используйте:\n"
                    "• `py teletype_converter.py` - экспорт в JSON\n"
                    "• `py create_full_teletype_articles.py` - полный экспорт\n\n"
                    f"📚 **Доступно статей:** {len(self.teletype_articles)}",
                    parse_mode='Markdown'
                )
            elif query.data == "main_menu":
                await self.start(update, context)
            elif query.data == "help_menu":
                await self.help_command(update, context)
            
            # Обработка навигации по страницам Teletype статей
            elif query.data.startswith("teletype_page_"):
                page = int(query.data.split("_")[-1])
                context.user_data['teletype_page'] = page
                await self.show_teletype_articles(update, context)
            
            # Обработка показа конкретной статьи
            elif query.data.startswith("show_article_"):
                article_index = int(query.data.split("_")[-1])
                await self.show_article_content(update, context, article_index)
            
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
