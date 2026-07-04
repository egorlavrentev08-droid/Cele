import logging
import sqlite3
from datetime import datetime, timedelta
from functools import wraps

from telegram import Update, ChatPermissions
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackContext,
    filters,
)

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG  # Включаем DEBUG для максимальной отладки
)
logger = logging.getLogger(__name__)

# ============= КОНФИГУРАЦИЯ =============
BOT_TOKEN = "8796023969:AAH_mXDm-I4N_LDc5zgZ_vNzKisY2j-67eg"

# ВАЖНО: Убедитесь, что здесь только число без пробелов и кавычек
ADMIN_IDS = [7930591505]  # Ваш ID

print("\n" + "=" * 70)
print("🚀 ЗАПУСК БОТА С ОТЛАДКОЙ")
print(f"ADMIN_IDS: {ADMIN_IDS}")
print(f"Тип ADMIN_IDS: {type(ADMIN_IDS)}")
print(f"Первый элемент: {ADMIN_IDS[0] if ADMIN_IDS else 'Нет'}")
print(f"Тип первого элемента: {type(ADMIN_IDS[0]) if ADMIN_IDS else 'Нет'}")
print("=" * 70 + "\n")


# ============= ДЕКОРАТОР С ПОЛНОЙ ОТЛАДКОЙ =============
def admin_only(func):
    @wraps(func)
    async def wrapped(update: Update, context: CallbackContext, *args, **kwargs):
        user_id = update.effective_user.id
        user_name = update.effective_user.first_name
        username = update.effective_user.username
        
        # ПОДРОБНОЕ ЛОГИРОВАНИЕ
        print("\n" + "=" * 60)
        print("🔍 ПРОВЕРКА ПРАВ:")
        print(f"  📱 user_id: {user_id}")
        print(f"  👤 Имя: {user_name}")
        print(f"  👤 Username: @{username if username else 'Нет'}")
        print(f"  📋 ADMIN_IDS: {ADMIN_IDS}")
        print(f"  🔍 Результат проверки: {user_id in ADMIN_IDS}")
        print("=" * 60 + "\n")
        
        logger.info(f"Проверка прав: user_id={user_id} ({user_name}), ADMIN_IDS={ADMIN_IDS}")
        logger.info(f"Результат: {user_id in ADMIN_IDS}")
        
        # Проверяем с приведением к int (на всякий случай)
        user_id_int = int(user_id)
        admin_ids_int = [int(id) for id in ADMIN_IDS]
        
        print(f"  🔄 user_id как int: {user_id_int}")
        print(f"  🔄 ADMIN_IDS как int: {admin_ids_int}")
        print(f"  🔍 Результат (int): {user_id_int in admin_ids_int}")
        
        if user_id not in ADMIN_IDS:
            # Отправляем подробное сообщение об ошибке
            await update.message.reply_text(
                f"❌ *У вас нет прав для этой команды!*\n\n"
                f"📱 *Ваш ID:* `{user_id}`\n"
                f"👤 *Имя:* {user_name}\n"
                f"👤 *Username:* @{username if username else 'Нет'}\n\n"
                f"📋 *ID админов в коде:* `{ADMIN_IDS}`\n"
                f"🔍 *Ваш ID в списке:* {'✅ ДА' if user_id in ADMIN_IDS else '❌ НЕТ'}\n\n"
                f"💡 *Решение:*\n"
                f"1. Скопируйте ваш ID: `{user_id}`\n"
                f"2. Добавьте его в список ADMIN_IDS\n"
                f"3. Перезапустите бота",
                parse_mode='Markdown'
            )
            return
        
        print("✅ ПРАВА ПОДТВЕРЖДЕНЫ!")
        return await func(update, context, *args, **kwargs)

    return wrapped


# ============= КОМАНДА ДЛЯ ПРОВЕРКИ ID =============
async def myid(update: Update, context: CallbackContext):
    """Показать свой ID с подробной информацией"""
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name
    username = update.effective_user.username
    
    # Проверяем в ADMIN_IDS
    is_admin = user_id in ADMIN_IDS
    
    # Проверяем с int
    is_admin_int = int(user_id) in [int(id) for id in ADMIN_IDS]
    
    await update.message.reply_text(
        f"🆔 *Информация о вас:*\n\n"
        f"📱 *Ваш ID:* `{user_id}`\n"
        f"📱 *ID как int:* `{int(user_id)}`\n"
        f"👤 *Имя:* {user_name}\n"
        f"👤 *Username:* @{username if username else 'Нет'}\n"
        f"🤖 *Статус админа:* {'✅ ДА' if is_admin else '❌ НЕТ'}\n"
        f"🤖 *Статус (int):* {'✅ ДА' if is_admin_int else '❌ НЕТ'}\n\n"
        f"📋 *ADMIN_IDS в коде:* `{ADMIN_IDS}`\n"
        f"📋 *Тип ADMIN_IDS:* {type(ADMIN_IDS)}\n\n"
        f"💡 *Чтобы стать админом:*\n"
        f"1. Скопируйте ваш ID: `{user_id}`\n"
        f"2. Добавьте его в список ADMIN_IDS в коде\n"
        f"3. Перезапустите бота",
        parse_mode='Markdown'
    )


# ============= КОМАНДА ДЛЯ ТЕСТА =============
async def test(update: Update, context: CallbackContext):
    """Тестовая команда без проверки прав"""
    user_id = update.effective_user.id
    
    await update.message.reply_text(
        f"✅ Тестовая команда работает!\n"
        f"Ваш ID: `{user_id}`\n"
        f"ADMIN_IDS: `{ADMIN_IDS}`",
        parse_mode='Markdown'
    )


# ============= ОСТАЛЬНЫЕ КОМАНДЫ =============
async def start(update: Update, context: CallbackContext):
    """Приветственное сообщение"""
    user_id = update.effective_user.id
    is_admin = user_id in ADMIN_IDS
    
    await update.message.reply_text(
        f"🌟 *Привет! Я Celestine Bot*\n\n"
        f"Ваш ID: `{user_id}`\n"
        f"Статус: {'✅ Админ' if is_admin else '❌ НЕ админ'}\n\n"
        "📝 *Доступные команды:*\n"
        "/myid - Проверить ваш ID и статус\n"
        "/test - Тестовая команда (без проверки прав)\n"
        "/warn @user - Выдать предупреждение (только админ)\n"
        "/ban @user - Забанить (только админ)\n"
        "/mute @user - Замутить (только админ)\n\n"
        "⚠️ Если вы админ, но команды не работают:\n"
        "1. Используйте /myid\n"
        "2. Скопируйте ваш ID\n"
        "3. Добавьте в ADMIN_IDS в коде",
        parse_mode='Markdown'
    )


@admin_only
async def warn(update: Update, context: CallbackContext):
    """Выдать предупреждение пользователю (ТОЛЬКО ДЛЯ АДМИНОВ)"""
    print("⚠️ ВЫЗВАНА КОМАНДА WARN")
    
    if not context.args:
        await update.message.reply_text("❌ Использование: /warn @user [причина]")
        return
    
    try:
        # Пытаемся получить пользователя
        user_input = context.args[0]
        target_user = None
        
        print(f"Поиск пользователя: {user_input}")
        
        if user_input.startswith('@'):
            try:
                chat_member = await context.bot.get_chat_member(
                    update.effective_chat.id,
                    user_input
                )
                target_user = chat_member.user
                print(f"Найден по @username: {target_user.id}")
            except Exception as e:
                print(f"Ошибка поиска по @username: {e}")
                # Ищем среди администраторов
                admins = await context.bot.get_chat_administrators(update.effective_chat.id)
                username = user_input[1:].lower()
                for admin in admins:
                    if admin.user.username and admin.user.username.lower() == username:
                        target_user = admin.user
                        print(f"Найден среди админов: {target_user.id}")
                        break
        
        elif user_input.isdigit():
            try:
                chat_member = await context.bot.get_chat_member(
                    update.effective_chat.id,
                    int(user_input)
                )
                target_user = chat_member.user
                print(f"Найден по ID: {target_user.id}")
            except Exception as e:
                print(f"Ошибка поиска по ID: {e}")
        
        if not target_user:
            await update.message.reply_text(f"❌ Пользователь {user_input} не найден!")
            return
        
        # Выдаем предупреждение
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
        
        # Бан после 3 предупреждений
        if warning_count >= 3:
            await context.bot.ban_chat_member(update.effective_chat.id, target_user.id)
            await update.message.reply_text(f"🔨 {target_user.first_name} забанен!")
            clear_warnings(target_user.id, update.effective_chat.id)
            
    except Exception as e:
        print(f"❌ ОШИБКА В WARN: {e}")
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")


# ============= ОСТАЛЬНЫЕ ФУНКЦИИ БД =============
def init_db():
    conn = sqlite3.connect('celestine_bot.db')
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
            flood_limit INTEGER DEFAULT 5,
            flood_time INTEGER DEFAULT 10
        )
    ''')
    
    conn.commit()
    conn.close()


def add_warning(user_id, chat_id, reason, warned_by):
    conn = sqlite3.connect('celestine_bot.db')
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


def get_warnings(user_id, chat_id):
    conn = sqlite3.connect('celestine_bot.db')
    cursor = conn.cursor()
    warnings = cursor.execute(
        'SELECT reason, date, warned_by FROM warnings WHERE user_id = ? AND chat_id = ?',
        (user_id, chat_id)
    ).fetchall()
    conn.close()
    return warnings


def clear_warnings(user_id, chat_id):
    conn = sqlite3.connect('celestine_bot.db')
    cursor = conn.cursor()
    cursor.execute(
        'DELETE FROM warnings WHERE user_id = ? AND chat_id = ?',
        (user_id, chat_id)
    )
    conn.commit()
    conn.close()


# ============= ОБРАБОТЧИКИ =============
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
        if (current_time - msg_time).seconds < 10
    ]
    
    user_messages[user_id].append(current_time)
    
    if len(user_messages[user_id]) > 5:
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
        
        if warning_count >= 3:
            await context.bot.ban_chat_member(chat_id, user_id)


# ============= ЗАПУСК =============
def main():
    """Запуск бота"""
    print("\n" + "=" * 70)
    print("🚀 ЗАПУСК БОТА")
    print(f"ADMIN_IDS: {ADMIN_IDS}")
    print("=" * 70 + "\n")
    
    init_db()
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Регистрируем команды
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("myid", myid))
    application.add_handler(CommandHandler("test", test))  # Тестовая команда
    application.add_handler(CommandHandler("warn", warn))
    # Добавьте остальные команды по аналогии...
    
    # Обработчики
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
