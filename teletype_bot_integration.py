"""
Интеграция конвертера Teletype с Telegram ботом
"""

import asyncio
import json
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler
from teletype_converter import TeletypeConverter
from article_processor import ArticleProcessor

class TeletypeBotIntegration:
    def __init__(self, bot_token):
        self.bot_token = bot_token
        self.converter = TeletypeConverter()
        self.processor = ArticleProcessor()
        self.application = Application.builder().token(bot_token).build()
        self.setup_handlers()
    
    def setup_handlers(self):
        """Настройка обработчиков команд"""
        self.application.add_handler(CommandHandler("convert", self.convert_command))
        self.application.add_handler(CommandHandler("teletype", self.teletype_menu))
        self.application.add_handler(CommandHandler("export", self.export_command))
        self.application.add_handler(CommandHandler("full_convert", self.full_convert_command))
        self.application.add_handler(CallbackQueryHandler(self.button_callback))
        
        # Обработчик ошибок
        self.application.add_error_handler(self.error_handler)
    
    async def teletype_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Главное меню конвертации в Teletype"""
        keyboard = [
            [InlineKeyboardButton("🔄 Быстрая конвертация", callback_data="quick_convert")],
            [InlineKeyboardButton("📖 Полная конвертация", callback_data="full_convert")],
            [InlineKeyboardButton("📤 Экспорт статей", callback_data="export_articles")],
            [InlineKeyboardButton("📊 Статистика конвертации", callback_data="convert_stats")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        menu_text = (
            "🔄 **Конвертация в Teletype**\n\n"
            "Выберите тип конвертации:\n\n"
            "🔄 **Быстрая конвертация** - базовые посты без полного контента\n"
            "📖 **Полная конвертация** - посты с полным контентом статей\n"
            "📤 **Экспорт статей** - экспорт в различные форматы\n"
            "📊 **Статистика** - анализ конвертированных статей"
        )
        
        await update.message.reply_text(
            menu_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def convert_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Команда быстрой конвертации"""
        try:
            limit = 5
            if context.args:
                try:
                    limit = int(context.args[0])
                    limit = min(limit, 20)  # Максимум 20 статей
                except ValueError:
                    limit = 5
            
            message = await update.message.reply_text(f"🔄 Конвертация {limit} статей в формат Teletype...")
            
            # Быстрая конвертация
            articles = self.converter.convert_latest_articles(limit)
            
            if articles:
                response = f"✅ **Конвертировано {len(articles)} статей**\n\n"
                
                for i, article in enumerate(articles[:3], 1):  # Показываем первые 3
                    response += f"**{i}.** {article['metadata']['title'][:60]}...\n"
                    response += f"   👤 {article['metadata']['author']} | 📅 {article['metadata']['date']}\n"
                    response += f"   🏷️ {article['metadata']['category']} | 🔖 {len(article['metadata']['tags'])} тегов\n\n"
                
                if len(articles) > 3:
                    response += f"... и еще {len(articles) - 3} статей"
                
                # Кнопки для действий
                keyboard = [
                    [InlineKeyboardButton("📤 Экспорт в JSON", callback_data=f"export_json_{len(articles)}")],
                    [InlineKeyboardButton("📝 Экспорт в Markdown", callback_data=f"export_md_{len(articles)}")]
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
    
    async def full_convert_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Команда полной конвертации с контентом"""
        try:
            limit = 3
            if context.args:
                try:
                    limit = int(context.args[0])
                    limit = min(limit, 10)  # Максимум 10 статей
                except ValueError:
                    limit = 3
            
            message = await update.message.reply_text(
                f"📖 Полная конвертация {limit} статей с контентом...\n"
                f"⏳ Это может занять несколько минут"
            )
            
            # Полная конвертация
            articles = self.processor.batch_convert_latest_articles(limit=limit, delay=2)
            
            if articles:
                response = f"✅ **Полная конвертация завершена**\n\n"
                
                full_content_count = sum(1 for a in articles if a['metadata'].get('has_full_content'))
                
                response += f"📊 **Статистика:**\n"
                response += f"   📰 Всего статей: {len(articles)}\n"
                response += f"   📖 С полным контентом: {full_content_count}\n"
                response += f"   📝 Базовые посты: {len(articles) - full_content_count}\n\n"
                
                for i, article in enumerate(articles[:2], 1):  # Показываем первые 2
                    content_status = "📖 Полный контент" if article['metadata'].get('has_full_content') else "📝 Базовый пост"
                    response += f"**{i}.** {article['metadata']['title'][:50]}...\n"
                    response += f"   {content_status}\n"
                    if article['metadata'].get('content_length'):
                        response += f"   📏 {article['metadata']['content_length']} символов\n"
                    response += "\n"
                
                if len(articles) > 2:
                    response += f"... и еще {len(articles) - 2} статей"
                
                # Кнопки для действий
                keyboard = [
                    [InlineKeyboardButton("📤 Экспорт полных статей", callback_data=f"export_full_{len(articles)}")],
                    [InlineKeyboardButton("📝 Показать пример", callback_data="show_example")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await message.edit_text(
                    response,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
            else:
                await message.edit_text("❌ Не удалось выполнить полную конвертацию")
                
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка полной конвертации: {str(e)}")
    
    async def export_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Команда экспорта статей"""
        try:
            limit = 5
            format_type = 'json'
            
            if context.args:
                if context.args[0] in ['json', 'md', 'csv']:
                    format_type = context.args[0]
                if len(context.args) > 1:
                    try:
                        limit = int(context.args[1])
                        limit = min(limit, 15)
                    except ValueError:
                        limit = 5
            
            message = await update.message.reply_text(f"📤 Экспорт {limit} статей в формате {format_type.upper()}...")
            
            # Получение статей
            articles = self.converter.convert_latest_articles(limit)
            
            if articles:
                # Экспорт в выбранный формат
                if format_type == 'json':
                    filename = self.converter.export_to_teletype_format(articles, f'export_{datetime.now().strftime("%Y%m%d_%H%M")}.json')
                elif format_type == 'md':
                    filename = self.export_to_markdown(articles, f'export_{datetime.now().strftime("%Y%m%d_%H%M")}.md')
                elif format_type == 'csv':
                    filename = self.export_to_csv(articles, f'export_{datetime.now().strftime("%Y%m%d_%H%M")}.csv')
                
                response = (
                    f"✅ **Экспорт завершен**\n\n"
                    f"📁 **Файл:** {filename}\n"
                    f"📊 **Статей:** {len(articles)}\n"
                    f"📋 **Формат:** {format_type.upper()}\n"
                    f"📅 **Время:** {datetime.now().strftime('%H:%M:%S')}"
                )
                
                await message.edit_text(response, parse_mode='Markdown')
                
                # Отправка файла (если возможно)
                try:
                    with open(filename, 'rb') as f:
                        await update.message.reply_document(
                            document=f,
                            filename=filename,
                            caption=f"📤 Экспорт {len(articles)} статей в формате {format_type.upper()}"
                        )
                except Exception as e:
                    await update.message.reply_text(f"⚠️ Файл создан, но не удалось отправить: {str(e)}")
            else:
                await message.edit_text("❌ Не удалось экспортировать статьи")
                
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка экспорта: {str(e)}")
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик нажатий на кнопки"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "quick_convert":
            await self.convert_command(update, context)
        elif query.data == "full_convert":
            await self.full_convert_command(update, context)
        elif query.data == "export_articles":
            await self.export_command(update, context)
        elif query.data == "convert_stats":
            await self.conversion_stats(update, context)
        elif query.data.startswith("export_json_"):
            await self.handle_export_callback(update, context, "json")
        elif query.data.startswith("export_md_"):
            await self.handle_export_callback(update, context, "md")
        elif query.data.startswith("export_full_"):
            await self.handle_export_callback(update, context, "full")
        elif query.data == "show_example":
            await self.show_conversion_example(update, context)
    
    async def handle_export_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE, export_type: str):
        """Обработка экспорта через кнопки"""
        try:
            query = update.callback_query
            
            if export_type == "full":
                articles = self.processor.batch_convert_latest_articles(limit=3, delay=1)
            else:
                articles = self.converter.convert_latest_articles(5)
            
            if articles:
                if export_type == "json":
                    filename = self.converter.export_to_teletype_format(articles, f'teletype_export_{datetime.now().strftime("%Y%m%d_%H%M")}.json')
                elif export_type == "md":
                    filename = self.export_to_markdown(articles, f'teletype_export_{datetime.now().strftime("%Y%m%d_%H%M")}.md')
                elif export_type == "full":
                    filename = self.converter.export_to_teletype_format(articles, f'full_teletype_export_{datetime.now().strftime("%Y%m%d_%H%M")}.json')
                
                await query.edit_message_text(
                    f"✅ Экспорт завершен!\n📁 Файл: {filename}\n📊 Статей: {len(articles)}",
                    parse_mode='Markdown'
                )
                
                # Отправка файла
                try:
                    with open(filename, 'rb') as f:
                        await context.bot.send_document(
                            chat_id=query.message.chat_id,
                            document=f,
                            filename=filename
                        )
                except Exception as e:
                    await query.message.reply_text(f"⚠️ Файл создан: {filename}")
            else:
                await query.edit_message_text("❌ Не удалось экспортировать статьи")
                
        except Exception as e:
            await query.edit_message_text(f"❌ Ошибка экспорта: {str(e)}")
    
    async def conversion_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Статистика конвертации"""
        try:
            articles = self.converter.convert_latest_articles(10)
            
            if articles:
                # Анализ статистики
                categories = {}
                tag_counts = {}
                
                for article in articles:
                    category = article['metadata']['category']
                    categories[category] = categories.get(category, 0) + 1
                    
                    for tag in article['metadata']['tags']:
                        tag_counts[tag] = tag_counts.get(tag, 0) + 1
                
                stats_text = (
                    f"📊 **Статистика конвертации**\n\n"
                    f"📰 **Всего статей:** {len(articles)}\n"
                    f"📂 **Категорий:** {len(categories)}\n"
                    f"🏷️ **Уникальных тегов:** {len(tag_counts)}\n\n"
                    f"📂 **Категории:**\n"
                )
                
                for category, count in sorted(categories.items(), key=lambda x: x[1], reverse=True):
                    stats_text += f"   {category}: {count}\n"
                
                stats_text += f"\n🏷️ **Топ теги:**\n"
                top_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:5]
                for tag, count in top_tags:
                    stats_text += f"   #{tag}: {count}\n"
                
                await update.callback_query.edit_message_text(stats_text, parse_mode='Markdown')
            else:
                await update.callback_query.edit_message_text("❌ Нет данных для статистики")
                
        except Exception as e:
            await update.callback_query.edit_message_text(f"❌ Ошибка получения статистики: {str(e)}")
    
    async def show_conversion_example(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Показ примера конвертации"""
        try:
            articles = self.converter.convert_latest_articles(1)
            
            if articles:
                article = articles[0]
                example_text = (
                    f"📝 **Пример конвертации:**\n\n"
                    f"**Заголовок:** {article['metadata']['title']}\n"
                    f"**Автор:** {article['metadata']['author']}\n"
                    f"**Категория:** {article['metadata']['category']}\n"
                    f"**Теги:** {', '.join(article['metadata']['tags'])}\n\n"
                    f"**Начало контента:**\n"
                )
                
                content_preview = article['content'][:300] + "..." if len(article['content']) > 300 else article['content']
                example_text += content_preview
                
                await update.callback_query.edit_message_text(example_text, parse_mode='Markdown')
            else:
                await update.callback_query.edit_message_text("❌ Нет примеров для показа")
                
        except Exception as e:
            await update.callback_query.edit_message_text(f"❌ Ошибка показа примера: {str(e)}")
    
    def export_to_markdown(self, articles, filename):
        """Экспорт в Markdown формат"""
        with open(filename, 'w', encoding='utf-8') as f:
            f.write("# Naked Capitalism Articles for Teletype\n\n")
            
            for i, article in enumerate(articles, 1):
                f.write(f"## Article {i}: {article['metadata']['title']}\n\n")
                f.write(f"**Author:** {article['metadata']['author']}\n")
                f.write(f"**Date:** {article['metadata']['date']}\n")
                f.write(f"**Category:** {article['metadata']['category']}\n")
                f.write(f"**Tags:** {', '.join(article['metadata']['tags'])}\n\n")
                f.write(f"**URL:** {article['metadata']['url']}\n\n")
                f.write("---\n\n")
        
        return filename
    
    def export_to_csv(self, articles, filename):
        """Экспорт в CSV формат"""
        import csv
        
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            writer.writerow([
                'Title', 'Author', 'Date', 'Category', 'Tags', 
                'Source', 'URL', 'Word Count', 'Created At'
            ])
            
            for article in articles:
                writer.writerow([
                    article['metadata']['title'],
                    article['metadata']['author'],
                    article['metadata']['date'],
                    article['metadata']['category'],
                    '; '.join(article['metadata']['tags']),
                    article['metadata']['source'],
                    article['metadata']['url'],
                    article['metadata']['word_count'],
                    article['metadata']['created_at']
                ])
        
        return filename
    
    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик ошибок"""
        print(f"Exception while handling an update: {context.error}")
    
    async def run(self):
        """Запуск бота"""
        print("🚀 Запуск Teletype Converter Bot...")
        await self.application.run_polling()

def main():
    """Основная функция"""
    BOT_TOKEN = "8114291381:AAFo7jRmm3vD_7o4Cthq8Q9pD31x3_qZWMU"
    
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌ ОШИБКА: Необходимо указать токен бота!")
        return
    
    bot = TeletypeBotIntegration(BOT_TOKEN)
    
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        print("Бот остановлен пользователем")

if __name__ == "__main__":
    main()
