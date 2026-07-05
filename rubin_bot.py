import logging
import sqlite3
import os
from datetime import datetime
from functools import wraps

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackContext,
    filters,
)
from dotenv import load_dotenv

load_dotenv('.env')

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv('BOT_TOKEN')

admin_ids_str = os.getenv('ADMIN_IDS', '')
if admin_ids_str:
    admin_ids_str = admin_ids_str.strip('[]').replace(' ', '')
    ADMIN_IDS = [int(id.strip()) for id in admin_ids_str.split(',') if id.strip()]
else:
    ADMIN_IDS = []

DB_NAME = os.getenv('DB_NAME', 'rubin_bot.db')
FLOOD_LIMIT = int(os.getenv('FLOOD_LIMIT', 5))
FLOOD_TIME = int(os.getenv('FLOOD_TIME', 10))
WARNINGS_BEFORE_BAN = int(os.getenv('WARNINGS_BEFORE_BAN', 3))

print("\n" + "=" * 70)
print("🚀 ЗАПУСК БОТА С ОТЛАДКОЙ")
print(f"BOT_TOKEN: {BOT_TOKEN[:10] if BOT_TOKEN else 'НЕТ'}... (скрыто)")
print(f"ADMIN_IDS: {ADMIN_IDS}")
print(f"DB_NAME: {DB_NAME}")
print(f"FLOOD_LIMIT: {FLOOD_LIMIT}")
print(f"WARNINGS_BEFORE_BAN: {WARNINGS_BEFORE_BAN}")
print("=" * 70 + "\n")

def admin_only(func):
    @wraps(func)
    async def wrapped(update: Update, context: CallbackContext, *args, **kwargs):
        user_id = update.effective_user.id
        user_name = update.effective_user.first_name
        username = update.effective_user.username
        
        is_admin = int(user_id) in [int(admin_id) for admin_id in ADMIN_IDS]
        
        print("\n" + "=" * 60)
        print("🔍 ПРОВЕРКА ПРАВ:")
        print(f"  📱 user_id: {user_id} (тип: {type(user_id).__name__})")
        print(f"  📋 ADMIN_IDS: {ADMIN_IDS}")
        print(f"  🔍 Результат: {is_admin}")
        print("=" * 60 + "\n")
        
        if not is_admin:
            await update.message.reply_text(
                f"❌ *У вас нет прав для этой команды!*\n\n"
                f"📱 *Ваш ID:* `{user_id}`\n"
                f"👤 *Имя:* {user_name}\n"
                f"👤 *Username:* @{username if username else 'Нет'}\n\n"
                f"📋 *ADMIN_IDS из .env:* `{ADMIN_IDS}`\n"
                f"🔍 *Ваш ID в списке:* {'✅ ДА' if is_admin else '❌ НЕТ'}\n\n"
                f"💡 *Чтобы стать админом:*\n"
                f"1. Откройте файл `.env`\n"
                f"2. Добавьте ваш ID в список: `ADMIN_IDS=7930591505`\n"
                f"3. Перезапустите бота",
                parse_mode='Markdown'
            )
            return
        
        print("✅ ПРАВА ПОДТВЕРЖДЕНЫ!")
        return await func(update, context, *args, **kwargs)
    
    return wrapped

async def myid(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name
    username = update.effective_user.username
    
    is_admin = int(user_id) in [int(admin_id) for admin_id in ADMIN_IDS]
    
    await update.message.reply_text(
        f"🆔 *Информация о вас:*\n\n"
        f"📱 *Ваш ID:* `{user_id}`\n"
        f"👤 *Имя:* {user_name}\n"
        f"👤 *Username:* @{username if username else 'Нет'}\n"
        f"🤖 *Статус админа:* {'✅ ДА' if is_admin else '❌ НЕТ'}\n\n"
        f"📋 *ADMIN_IDS из .env:* `{ADMIN_IDS}`\n\n"
        f"💡 *Если вы НЕ админ:*\n"
        f"1. Откройте файл `.env`\n"
        f"2. Найдите строку `ADMIN_IDS`\n"
        f"3. Добавьте ваш ID: `ADMIN_IDS=7930591505`\n"
        f"4. Сохраните и перезапустите бота",
        parse_mode='Markdown'
    )

async def test(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    
    await update.message.reply_text(
        f"✅ Тестовая команда работает!\n"
        f"Ваш ID: `{user_id}`\n"
        f"ADMIN_IDS из .env: `{ADMIN_IDS}`",
        parse_mode='Markdown'
    )

async def start(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    is_admin = int(user_id) in [int(admin_id) for admin_id in ADMIN_IDS]
    
    await update.message.reply_text(
        f"🌟 *Привет! Я Celestine Bot*\n\n"
        f"Ваш ID: `{user_id}`\n"
        f"Статус: {'✅ Админ' if is_admin else '❌ НЕ админ'}\n\n"
        "📝 *Доступные команды:*\n"
        "/myid - Проверить ваш ID и статус\n"
        "/test - Тестовая команда (без проверки прав)\n"
        "/warn @user - Выдать предупреждение (только админ)\n\n"
        "⚠️ Если вы админ, но команды не работают:\n"
        "1. Используйте /myid\n"
        "2. Проверьте файл `.env`\n"
        "3. Убедитесь, что ваш ID в списке ADMIN_IDS",
        parse_mode='Markdown'
    )

@admin_only
async def warn(update: Update, context: CallbackContext):
    print("⚠️ ВЫЗВАНА КОМАНДА WARN")
    
    if not context.args:
        await update.message.reply_text("❌ Использование: /warn @user [причина]")
        return
    
    try:
        user_input = context.args[0]
        target_user = None
        
        if user_input.startswith('@'):
            try:
                chat_member = await context.bot.get_chat_member(
                    update.effective_chat.id,
                    user_input
                )
                target_user = chat_member.user
            except Exception as e:
                print(f"Ошибка поиска по @username: {e}")
                admins = await context.bot.get_chat_administrators(update.effective_chat.id)
                username = user_input[1:].lower()
                for admin in admins:
                    if admin.user.username and admin.user.username.lower() == username:
                        target_user = admin.user
                        break
        
        elif user_input.isdigit():
            try:
                chat_member = await context.bot.get_chat_member(
                    update.effective_chat.id,
                    int(user_input)
                )
                target_user = chat_member.user
            except Exception as e:
                print(f"Ошибка поиска по ID: {e}")
        
        if not target_user:
            await update.message.reply_text(f"❌ Пользователь {user_input} не найден!")
            return
        
        reason = " ".join(context.args[1:]) if len(context.args) > 1 else "Без причины"
        
        warning_count = add_warning(
            target_user.id,
            update.effective_chat.id,
            reason,
            update.effective_user.id
        )
        
        await update.message.reply_text(
            f"⚠️ Пользователь {target_user.first_name} получил предупреждение #{warning_count}\n"
            f"Причина: {reason}"
        )
        
        if warning_count >= WARNINGS_BEFORE_BAN:
            await context.bot.ban_chat_member(update.effective_chat.id, target_user.id)
            await update.message.reply_text(f"🔨 {target_user.first_name} забанен!")
            clear_warnings(target_user.id, update.effective_chat.id)
            
    except Exception as e:
        print(f"❌ ОШИБКА В WARN: {e}")
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS warnings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            chat_id INTEGER,
            reason TEXT,
            date TEXT,
            warned_by INTEGER
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_settings (
            chat_id INTEGER PRIMARY KEY,
            welcome_enabled INTEGER DEFAULT 1,
            anti_flood_enabled INTEGER DEFAULT 1,
            flood_limit INTEGER DEFAULT ?,
            flood_time INTEGER DEFAULT ?
        )
    ''', (FLOOD_LIMIT, FLOOD_TIME))
    
    conn.commit()
    conn.close()

def add_warning(user_id, chat_id, reason, warned_by):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO warnings (user_id, chat_id, reason, date, warned_by) VALUES (?, ?, ?, ?, ?)',
        (user_id, chat_id, reason, datetime.now().isoformat(), warned_by)
    )
    conn.commit()
    warning_count = cursor.execute(
        'SELECT COUNT(*) FROM warnings WHERE user_id = ? AND chat_id = ?',
        (user_id, chat_id)
    ).fetchone()[0]
    conn.close()
    return warning_count

def clear_warnings(user_id, chat_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        'DELETE FROM warnings WHERE user_id = ? AND chat_id = ?',
        (user_id, chat_id)
    )
    conn.commit()
    conn.close()

async def welcome_new_members(update: Update, context: CallbackContext):
    for new_member in update.message.new_chat_members:
        if new_member.id == context.bot.id:
            continue
        await update.message.reply_text(
            f"🌟 Добро пожаловать в {update.effective_chat.title}, {new_member.first_name}! 🌟"
        )

user_messages = {}

async def anti_flood(update: Update, context: CallbackContext):
    if not update.message or not update.effective_user:
        return
    
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    current_time = datetime.now()
    
    try:
        chat_member = await context.bot.get_chat_member(chat_id, user_id)
        if chat_member.status in ['administrator', 'creator']:
            return
    except:
        pass
    
    if user_id not in user_messages:
        user_messages[user_id] = []
    
    user_messages[user_id] = [
        msg_time for msg_time in user_messages[user_id]
        if (current_time - msg_time).seconds < FLOOD_TIME
    ]
    
    user_messages[user_id].append(current_time)
    
    if len(user_messages[user_id]) > FLOOD_LIMIT:
        warning_count = add_warning(
            user_id,
            chat_id,
            "Флуд",
            context.bot.id
        )
        await update.message.delete()
        await update.message.reply_text(
            f"⚠️ {update.effective_user.first_name}, не флудите! Предупреждение #{warning_count}"
        )
        
        if warning_count >= WARNINGS_BEFORE_BAN:
            await context.bot.ban_chat_member(chat_id, user_id)

def main():
    print("\n" + "=" * 70)
    print("🚀 ЗАПУСК БОТА")
    print(f"ADMIN_IDS из .env: {ADMIN_IDS}")
    print(f"База данных: {DB_NAME}")
    print("=" * 70 + "\n")
    
    if not BOT_TOKEN:
        print("❌ ОШИБКА: BOT_TOKEN не найден в .env файле!")
        return
    
    init_db()
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("myid", myid))
    application.add_handler(CommandHandler("test", test))
    application.add_handler(CommandHandler("warn", warn))
    
    application.add_handler(MessageHandler(
        filters.StatusUpdate.NEW_CHAT_MEMBERS,
        welcome_new_members
    ))
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        anti_flood
    ))
    
    print("🤖 Бот Celestine запущен!")
    print("📝 Используйте /myid для проверки ID")
    print("📝 Используйте /test для проверки работы бота")
    application.run_polling()

if __name__ == '__main__':
    main()
