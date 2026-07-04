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
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфигурация
BOT_TOKEN = "8796023969:AAH_mXDm-I4N_LDc5zgZ_vNzKisY2j-67eg"  # Замените на токен вашего бота
ADMIN_IDS = [7930591505]  # ID администраторов


# Декоратор для проверки прав администратора
def admin_only(func):
    @wraps(func)
    async def wrapped(update, context, *args, **kwargs):
        user_id = update.effective_user.id
        if user_id not in ADMIN_IDS:
            await update.message.reply_text("❌ У вас нет прав для этой команды!")
            return
        return await func(update, context, *args, **kwargs)

    return wrapped


# Инициализация базы данных
def init_db():
    conn = sqlite3.connect('celestine_bot.db')
    cursor = conn.cursor()
    
    # Таблица для предупреждений
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
    
    # Таблица для настроек чата
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


# Функции для работы с БД
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


# Команды бота
async def start(update: Update, context: CallbackContext):
    """Приветственное сообщение"""
    await update.message.reply_text(
        "🌟 *Привет! Я Celestine Bot*\n\n"
        "Я помогаю модерировать чаты и защищать от спама.\n\n"
        "*Доступные команды:*\n"
        "/warn @user [причина] - Выдать предупреждение\n"
        "/warnings @user - Показать предупреждения\n"
        "/clearwarns @user - Очистить предупреждения\n"
        "/kick @user - Кикнуть пользователя\n"
        "/ban @user - Забанить пользователя\n"
        "/unban @user - Разбанить пользователя\n"
        "/mute @user [минуты] - Замутить пользователя\n"
        "/unmute @user - Размутить\n"
        "/settings - Настройки бота\n"
        "/stats - Статистика чата\n\n"
        "*Anti-flood:* автоматически предупреждает за частые сообщения",
        parse_mode='Markdown'
    )


@admin_only
async def warn(update: Update, context: CallbackContext):
    """Выдать предупреждение пользователю"""
    if not context.args:
        await update.message.reply_text("❌ Использование: /warn @user [причина]")
        return
    
    try:
        target_user = await context.bot.get_chat_member(
            update.effective_chat.id,
            context.args[0]
        )
        user_id = target_user.user.id
        
        reason = " ".join(context.args[1:]) if len(context.args) > 1 else "Без причины"
        
        warning_count = add_warning(
            user_id,
            update.effective_chat.id,
            reason,
            update.effective_user.id
        )
        
        await update.message.reply_text(
            f"⚠️ Пользователь {context.args[0]} получил предупреждение #{warning_count}\n"
            f"Причина: {reason}"
        )
        
        # Отправляем предупреждение в ЛС пользователю
        try:
            await context.bot.send_message(
                user_id,
                f"⚠️ Вы получили предупреждение в чате {update.effective_chat.title}\n"
                f"Причина: {reason}\nВсего предупреждений: {warning_count}"
            )
        except:
            pass
        
        # Автоматический бан после 3 предупреждений
        if warning_count >= 3:
            await context.bot.ban_chat_member(update.effective_chat.id, user_id)
            await update.message.reply_text(f"🔨 {context.args[0]} забанен за 3 предупреждения!")
            clear_warnings(user_id, update.effective_chat.id)
            
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")


async def warnings(update: Update, context: CallbackContext):
    """Показать предупреждения пользователя"""
    if not context.args:
        await update.message.reply_text("❌ Использование: /warnings @user")
        return
    
    try:
        target_user = await context.bot.get_chat_member(
            update.effective_chat.id,
            context.args[0]
        )
        user_id = target_user.user.id
        
        warnings_list = get_warnings(user_id, update.effective_chat.id)
        
        if not warnings_list:
            await update.message.reply_text(f"✅ У {context.args[0]} нет предупреждений")
            return
        
        text = f"⚠️ Предупреждения для {context.args[0]}:\n\n"
        for i, (reason, date, warned_by) in enumerate(warnings_list, 1):
            text += f"{i}. Причина: {reason}\n   Дата: {date[:16]}\n\n"
        
        await update.message.reply_text(text)
        
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")


@admin_only
async def clear_warns(update: Update, context: CallbackContext):
    """Очистить предупреждения пользователя"""
    if not context.args:
        await update.message.reply_text("❌ Использование: /clearwarns @user")
        return
    
    try:
        target_user = await context.bot.get_chat_member(
            update.effective_chat.id,
            context.args[0]
        )
        user_id = target_user.user.id
        
        clear_warnings(user_id, update.effective_chat.id)
        await update.message.reply_text(f"✅ Очищены все предупреждения для {context.args[0]}")
        
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")


@admin_only
async def kick(update: Update, context: CallbackContext):
    """Кикнуть пользователя"""
    if not context.args:
        await update.message.reply_text("❌ Использование: /kick @user")
        return
    
    try:
        target_user = await context.bot.get_chat_member(
            update.effective_chat.id,
            context.args[0]
        )
        await context.bot.ban_chat_member(update.effective_chat.id, target_user.user.id)
        await context.bot.unban_chat_member(update.effective_chat.id, target_user.user.id)
        await update.message.reply_text(f"👢 {context.args[0]} был кикнут")
        
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")


@admin_only
async def ban(update: Update, context: CallbackContext):
    """Забанить пользователя"""
    if not context.args:
        await update.message.reply_text("❌ Использование: /ban @user [причина]")
        return
    
    try:
        target_user = await context.bot.get_chat_member(
            update.effective_chat.id,
            context.args[0]
        )
        reason = " ".join(context.args[1:]) if len(context.args) > 1 else "Без причины"
        
        await context.bot.ban_chat_member(update.effective_chat.id, target_user.user.id)
        await update.message.reply_text(
            f"🔨 {context.args[0]} забанен\nПричина: {reason}"
        )
        
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")


@admin_only
async def unban(update: Update, context: CallbackContext):
    """Разбанить пользователя"""
    if not context.args:
        await update.message.reply_text("❌ Использование: /unban @user")
        return
    
    try:
        target_user = await context.bot.get_chat_member(
            update.effective_chat.id,
            context.args[0]
        )
        await context.bot.unban_chat_member(update.effective_chat.id, target_user.user.id)
        await update.message.reply_text(f"✅ {context.args[0]} разбанен")
        
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")


@admin_only
async def mute(update: Update, context: CallbackContext):
    """Замутить пользователя"""
    if len(context.args) < 2:
        await update.message.reply_text("❌ Использование: /mute @user [минуты] [причина]")
        return
    
    try:
        target_user = await context.bot.get_chat_member(
            update.effective_chat.id,
            context.args[0]
        )
        minutes = int(context.args[1])
        reason = " ".join(context.args[2:]) if len(context.args) > 2 else "Без причины"
        
        until_date = datetime.now() + timedelta(minutes=minutes)
        
        await context.bot.restrict_chat_member(
            update.effective_chat.id,
            target_user.user.id,
            ChatPermissions(can_send_messages=False),
            until_date=until_date
        )
        
        await update.message.reply_text(
            f"🔇 {context.args[0]} замучен на {minutes} минут\nПричина: {reason}"
        )
        
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")


@admin_only
async def unmute(update: Update, context: CallbackContext):
    """Размутить пользователя"""
    if not context.args:
        await update.message.reply_text("❌ Использование: /unmute @user")
        return
    
    try:
        target_user = await context.bot.get_chat_member(
            update.effective_chat.id,
            context.args[0]
        )
        
        await context.bot.restrict_chat_member(
            update.effective_chat.id,
            target_user.user.id,
            ChatPermissions(
                can_send_messages=True,
                can_send_media_messages=True,
                can_send_polls=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True
            )
        )
        
        await update.message.reply_text(f"✅ {context.args[0]} размучен")
        
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")


@admin_only
async def settings(update: Update, context: CallbackContext):
    """Показать настройки бота"""
    await update.message.reply_text(
        "⚙️ *Настройки бота*\n\n"
        "Доступные команды:\n"
        "/set_welcome on/off - Включить/выключить приветствия\n"
        "/set_antiflood on/off - Включить/выключить защиту от спама\n"
        "/set_flood 5 10 - Установить лимит сообщений за секунд",
        parse_mode='Markdown'
    )


async def stats(update: Update, context: CallbackContext):
    """Статистика чата"""
    chat_member = await context.bot.get_chat_member(update.effective_chat.id, update.effective_user.id)
    
    conn = sqlite3.connect('celestine_bot.db')
    cursor = conn.cursor()
    total_warnings = cursor.execute(
        'SELECT COUNT(*) FROM warnings WHERE chat_id = ?',
        (update.effective_chat.id,)
    ).fetchone()[0]
    conn.close()
    
    await update.message.reply_text(
        f"📊 *Статистика чата*\n\n"
        f"Всего предупреждений: {total_warnings}\n"
        f"Ваш статус: {chat_member.status}\n"
        f"Чат ID: {update.effective_chat.id}",
        parse_mode='Markdown'
    )


# Обработчик новых участников
async def welcome_new_members(update: Update, context: CallbackContext):
    """Приветствие новых участников"""
    for new_member in update.message.new_chat_members:
        if new_member.id == context.bot.id:
            continue
        
        welcome_text = (
            f"🌟 Добро пожаловать в {update.effective_chat.title}, {new_member.first_name}! 🌟\n\n"
            f"Пожалуйста, ознакомься с правилами чата и будь вежлив с другими участниками.\n"
            f"Приятного общения! 💫"
        )
        
        await update.message.reply_text(welcome_text)


# Anti-flood система
user_messages = {}

async def anti_flood(update: Update, context: CallbackContext):
    """Защита от флуда"""
    if not update.message or not update.effective_user:
        return
    
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    current_time = datetime.now()
    
    # Проверяем, не админ ли пользователь
    try:
        chat_member = await context.bot.get_chat_member(chat_id, user_id)
        if chat_member.status in ['administrator', 'creator']:
            return
    except:
        pass
    
    if user_id not in user_messages:
        user_messages[user_id] = []
    
    # Очищаем старые сообщения (старше 10 секунд)
    user_messages[user_id] = [
        msg_time for msg_time in user_messages[user_id]
        if (current_time - msg_time).seconds < 10
    ]
    
    user_messages[user_id].append(current_time)
    
    # Если больше 5 сообщений за 10 секунд - предупреждение
    if len(user_messages[user_id]) > 5:
        warning_count = add_warning(
            user_id,
            chat_id,
            "Флуд (автоматическое предупреждение)",
            context.bot.id
        )
        
        await update.message.delete()
        await update.message.reply_text(
            f"⚠️ {update.effective_user.first_name}, пожалуйста, не флудите!\n"
            f"Предупреждение #{warning_count}"
        )
        
        # Бан за 3 предупреждения от антифлуда
        if warning_count >= 3:
            await context.bot.ban_chat_member(chat_id, user_id)
            await update.message.reply_text(f"🔨 {update.effective_user.first_name} забанен за флуд!")


def main():
    """Запуск бота"""
    # Инициализируем БД
    init_db()
    
    # Создаем приложение
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Регистрируем команды
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("warn", warn))
    application.add_handler(CommandHandler("warnings", warnings))
    application.add_handler(CommandHandler("clearwarns", clear_warns))
    application.add_handler(CommandHandler("kick", kick))
    application.add_handler(CommandHandler("ban", ban))
    application.add_handler(CommandHandler("unban", unban))
    application.add_handler(CommandHandler("mute", mute))
    application.add_handler(CommandHandler("unmute", unmute))
    application.add_handler(CommandHandler("settings", settings))
    application.add_handler(CommandHandler("stats", stats))
    
    # Регистрируем обработчики сообщений
    application.add_handler(MessageHandler(
        filters.StatusUpdate.NEW_CHAT_MEMBERS,
        welcome_new_members
    ))
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        anti_flood
    ))
    
    # Запускаем бота
    print("🤖 Бот Celestine запущен!")
    application.run_polling()


if __name__ == '__main__':
    main()
