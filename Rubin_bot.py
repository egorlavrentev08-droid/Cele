import logging
import sqlite3
import os
from datetime import datetime, timedelta
from functools import wraps
from dotenv import load_dotenv

from telegram import Update, ChatPermissions
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackContext,
    filters,
)

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфигурация из .env
BOT_TOKEN = os.getenv('BOT_TOKEN')
SUPER_ADMIN_IDS = [int(id) for id in os.getenv('ADMIN_IDS', '').split(',') if id]
DB_NAME = os.getenv('DB_NAME', 'celestine_bot.db')
FLOOD_LIMIT = int(os.getenv('FLOOD_LIMIT', 5))
FLOOD_TIME = int(os.getenv('FLOOD_TIME', 10))
WARNINGS_BEFORE_BAN = int(os.getenv('WARNINGS_BEFORE_BAN', 3))

# Проверка наличия токена
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден в .env файле!")

# Выводим ID админов для отладки
logger.info(f"ADMIN_IDS загружены: {ADMIN_IDS}")


# ============= ИСПРАВЛЕННЫЙ ДЕКОРАТОР =============
def admin_only(func):
    @wraps(func)
    async def wrapped(update: Update, context: CallbackContext, *args, **kwargs):
        user_id = update.effective_user.id
        
        # Проверяем, есть ли пользователь в ADMIN_IDS
        if user_id in ADMIN_IDS:
            return await func(update, context, *args, **kwargs)
        
        # Если нет, проверяем в чате
        try:
            chat_member = await context.bot.get_chat_member(
                update.effective_chat.id,
                user_id
            )
            
            if chat_member.status in ['administrator', 'creator']:
                return await func(update, context, *args, **kwargs)
            else:
                await update.message.reply_text(
                    "❌ У вас нет прав для этой команды!\n"
                    "Требуются права администратора."
                )
                return
                
        except Exception as e:
            logger.error(f"Ошибка проверки прав: {e}")
            await update.message.reply_text(
                "❌ Не удалось проверить ваши права.\n"
                f"Ошибка: {str(e)}"
            )
            return
    
    return wrapped


# ============= ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ ДЛЯ ПОИСКА ПОЛЬЗОВАТЕЛЯ =============
async def get_user_from_text(update: Update, context: CallbackContext, user_text: str):
    """Получить пользователя по тексту (@username, ID или имя)"""
    try:
        # Если это @username
        if user_text.startswith('@'):
            username = user_text[1:]
            try:
                # Пробуем получить напрямую
                chat_member = await context.bot.get_chat_member(
                    update.effective_chat.id,
                    user_text
                )
                return chat_member.user
            except:
                # Ищем среди участников чата
                try:
                    # Получаем список администраторов
                    admins = await context.bot.get_chat_administrators(update.effective_chat.id)
                    for admin in admins:
                        if admin.user.username and admin.user.username.lower() == username.lower():
                            return admin.user
                except:
                    pass
                
                # Если не нашли, пробуем поискать по имени
                try:
                    # Получаем последние сообщения для поиска (только для маленьких чатов)
                    # В противном случае используем другой метод
                    pass
                except:
                    pass
                
                return None
        
        # Если это ID
        elif user_text.isdigit():
            try:
                chat_member = await context.bot.get_chat_member(
                    update.effective_chat.id,
                    int(user_text)
                )
                return chat_member.user
            except:
                return None
        
        # Если это просто имя (пробуем найти среди администраторов)
        else:
            try:
                admins = await context.bot.get_chat_administrators(update.effective_chat.id)
                for admin in admins:
                    if admin.user.first_name and admin.user.first_name.lower() == user_text.lower():
                        return admin.user
                    if admin.user.last_name and admin.user.last_name.lower() == user_text.lower():
                        return admin.user
            except:
                pass
            return None
            
    except Exception as e:
        logger.error(f"Ошибка поиска пользователя: {e}")
        return None


# ============= БАЗА ДАННЫХ =============
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
    
    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS chat_settings (
            chat_id INTEGER PRIMARY KEY,
            welcome_enabled INTEGER DEFAULT 1,
            anti_flood_enabled INTEGER DEFAULT 1,
            flood_limit INTEGER DEFAULT {FLOOD_LIMIT},
            flood_time INTEGER DEFAULT {FLOOD_TIME}
        )
    ''')
    
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


def get_warnings(user_id, chat_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    warnings = cursor.execute(
        'SELECT reason, date, warned_by FROM warnings WHERE user_id = ? AND chat_id = ?',
        (user_id, chat_id)
    ).fetchall()
    conn.close()
    return warnings


def clear_warnings(user_id, chat_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        'DELETE FROM warnings WHERE user_id = ? AND chat_id = ?',
        (user_id, chat_id)
    )
    conn.commit()
    conn.close()


def get_chat_setting(chat_id, setting):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        f'SELECT {setting} FROM chat_settings WHERE chat_id = ?',
        (chat_id,)
    )
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None


def set_chat_setting(chat_id, setting, value):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        f'INSERT OR REPLACE INTO chat_settings (chat_id, {setting}) VALUES (?, ?)',
        (chat_id, value)
    )
    conn.commit()
    conn.close()


# ============= КОМАНДЫ БОТА =============
async def start(update: Update, context: CallbackContext):
    """Приветственное сообщение"""
    # Проверяем, является ли пользователь админом
    is_admin = update.effective_user.id in ADMIN_IDS
    admin_status = "✅ (Админ бота)" if is_admin else "❌ (Не админ)"
    
    await update.message.reply_text(
        f"🌟 *Привет! Я Rubin Bot*\n\n"
        f"Ваш статус: {admin_status}\n"
        f"Ваш ID: `{update.effective_user.id}`\n\n"
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
        "/stats - Статистика чата\n"
        "/myid - Показать ваш ID\n\n"
        "*Anti-flood:* автоматически предупреждает за частые сообщения",
        parse_mode='Markdown'
    )


async def myid(update: Update, context: CallbackContext):
    """Показать ID пользователя"""
    await update.message.reply_text(
        f"🆔 Ваш ID: `{update.effective_user.id}`\n"
        f"Ваш username: @{update.effective_user.username if update.effective_user.username else 'Нет'}\n"
        f"Ваше имя: {update.effective_user.first_name}",
        parse_mode='Markdown'
    )


@admin_only
async def warn(update: Update, context: CallbackContext):
    """Выдать предупреждение пользователю"""
    if not context.args:
        await update.message.reply_text(
            "❌ Использование: /warn @user [причина]\n"
            "Пример: /warn @username Спам"
        )
        return
    
    try:
        # Ищем пользователя
        target_user = await get_user_from_text(update, context, context.args[0])
        
        if not target_user:
            await update.message.reply_text(
                f"❌ Пользователь {context.args[0]} не найден!\n"
                "Убедитесь, что правильно указали @username или ID."
            )
            return
        
        user_id = target_user.id
        
        # Проверка на админа
        try:
            target_member = await context.bot.get_chat_member(
                update.effective_chat.id,
                user_id
            )
            if target_member.status in ['administrator', 'creator']:
                await update.message.reply_text("❌ Нельзя выдать предупреждение администратору!")
                return
        except:
            pass
        
        reason = " ".join(context.args[1:]) if len(context.args) > 1 else "Без причины"
        
        warning_count = add_warning(
            user_id,
            update.effective_chat.id,
            reason,
            update.effective_user.id
        )
        
        await update.message.reply_text(
            f"⚠️ Пользователь {target_user.first_name} получил предупреждение #{warning_count}\n"
            f"Причина: {reason}"
        )
        
        # Отправляем предупреждение в ЛС
        try:
            await context.bot.send_message(
                user_id,
                f"⚠️ Вы получили предупреждение в чате {update.effective_chat.title}\n"
                f"Причина: {reason}\nВсего предупреждений: {warning_count}"
            )
        except:
            pass
        
        # Автоматический бан после N предупреждений
        if warning_count >= WARNINGS_BEFORE_BAN:
            await context.bot.ban_chat_member(update.effective_chat.id, user_id)
            await update.message.reply_text(
                f"🔨 {target_user.first_name} забанен за {WARNINGS_BEFORE_BAN} предупреждений!"
            )
            clear_warnings(user_id, update.effective_chat.id)
            
    except Exception as e:
        logger.error(f"Ошибка в warn: {e}")
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")


@admin_only
async def warnings(update: Update, context: CallbackContext):
    """Показать предупреждения пользователя"""
    if not context.args:
        await update.message.reply_text("❌ Использование: /warnings @user")
        return
    
    try:
        target_user = await get_user_from_text(update, context, context.args[0])
        
        if not target_user:
            await update.message.reply_text(f"❌ Пользователь {context.args[0]} не найден!")
            return
        
        user_id = target_user.id
        
        warnings_list = get_warnings(user_id, update.effective_chat.id)
        
        if not warnings_list:
            await update.message.reply_text(f"✅ У {target_user.first_name} нет предупреждений")
            return
        
        text = f"⚠️ Предупреждения для {target_user.first_name}:\n\n"
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
        target_user = await get_user_from_text(update, context, context.args[0])
        
        if not target_user:
            await update.message.reply_text(f"❌ Пользователь {context.args[0]} не найден!")
            return
        
        user_id = target_user.id
        
        clear_warnings(user_id, update.effective_chat.id)
        await update.message.reply_text(f"✅ Очищены все предупреждения для {target_user.first_name}")
        
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")


@admin_only
async def kick(update: Update, context: CallbackContext):
    """Кикнуть пользователя"""
    if not context.args:
        await update.message.reply_text("❌ Использование: /kick @user")
        return
    
    try:
        target_user = await get_user_from_text(update, context, context.args[0])
        
        if not target_user:
            await update.message.reply_text(f"❌ Пользователь {context.args[0]} не найден!")
            return
        
        await context.bot.ban_chat_member(update.effective_chat.id, target_user.id)
        await context.bot.unban_chat_member(update.effective_chat.id, target_user.id)
        await update.message.reply_text(f"👢 {target_user.first_name} был кикнут")
        
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")


@admin_only
async def ban(update: Update, context: CallbackContext):
    """Забанить пользователя"""
    if not context.args:
        await update.message.reply_text("❌ Использование: /ban @user [причина]")
        return
    
    try:
        target_user = await get_user_from_text(update, context, context.args[0])
        
        if not target_user:
            await update.message.reply_text(f"❌ Пользователь {context.args[0]} не найден!")
            return
        
        # Проверка на бана админа
        try:
            target_member = await context.bot.get_chat_member(
                update.effective_chat.id,
                target_user.id
            )
            if target_member.status in ['administrator', 'creator']:
                await update.message.reply_text("❌ Нельзя забанить администратора!")
                return
        except:
            pass
        
        reason = " ".join(context.args[1:]) if len(context.args) > 1 else "Без причины"
        
        await context.bot.ban_chat_member(update.effective_chat.id, target_user.id)
        await update.message.reply_text(
            f"🔨 {target_user.first_name} забанен\nПричина: {reason}"
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
        target_user = await get_user_from_text(update, context, context.args[0])
        
        if not target_user:
            await update.message.reply_text(f"❌ Пользователь {context.args[0]} не найден!")
            return
        
        await context.bot.unban_chat_member(update.effective_chat.id, target_user.id)
        await update.message.reply_text(f"✅ {target_user.first_name} разбанен")
        
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")


@admin_only
async def mute(update: Update, context: CallbackContext):
    """Замутить пользователя"""
    if len(context.args) < 2:
        await update.message.reply_text("❌ Использование: /mute @user [минуты] [причина]")
        return
    
    try:
        target_user = await get_user_from_text(update, context, context.args[0])
        
        if not target_user:
            await update.message.reply_text(f"❌ Пользователь {context.args[0]} не найден!")
            return
        
        # Проверка на мут админа
        try:
            target_member = await context.bot.get_chat_member(
                update.effective_chat.id,
                target_user.id
            )
            if target_member.status in ['administrator', 'creator']:
                await update.message.reply_text("❌ Нельзя замутить администратора!")
                return
        except:
            pass
        
        minutes = int(context.args[1])
        reason = " ".join(context.args[2:]) if len(context.args) > 2 else "Без причины"
        
        until_date = datetime.now() + timedelta(minutes=minutes)
        
        await context.bot.restrict_chat_member(
            update.effective_chat.id,
            target_user.id,
            ChatPermissions(can_send_messages=False),
            until_date=until_date
        )
        
        await update.message.reply_text(
            f"🔇 {target_user.first_name} замучен на {minutes} минут\nПричина: {reason}"
        )
        
    except ValueError:
        await update.message.reply_text("❌ Введите корректное количество минут!")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")


@admin_only
async def unmute(update: Update, context: CallbackContext):
    """Размутить пользователя"""
    if not context.args:
        await update.message.reply_text("❌ Использование: /unmute @user")
        return
    
    try:
        target_user = await get_user_from_text(update, context, context.args[0])
        
        if not target_user:
            await update.message.reply_text(f"❌ Пользователь {context.args[0]} не найден!")
            return
        
        await context.bot.restrict_chat_member(
            update.effective_chat.id,
            target_user.id,
            ChatPermissions(
                can_send_messages=True,
                can_send_media_messages=True,
                can_send_polls=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True
            )
        )
        
        await update.message.reply_text(f"✅ {target_user.first_name} размучен")
        
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


@admin_only
async def set_welcome(update: Update, context: CallbackContext):
    """Включить/выключить приветствия"""
    if not context.args or context.args[0].lower() not in ['on', 'off']:
        await update.message.reply_text("❌ Использование: /set_welcome on/off")
        return
    
    value = 1 if context.args[0].lower() == 'on' else 0
    set_chat_setting(update.effective_chat.id, 'welcome_enabled', value)
    await update.message.reply_text(f"✅ Приветствия {'включены' if value else 'выключены'}")


@admin_only
async def set_antiflood(update: Update, context: CallbackContext):
    """Включить/выключить антифлуд"""
    if not context.args or context.args[0].lower() not in ['on', 'off']:
        await update.message.reply_text("❌ Использование: /set_antiflood on/off")
        return
    
    value = 1 if context.args[0].lower() == 'on' else 0
    set_chat_setting(update.effective_chat.id, 'anti_flood_enabled', value)
    await update.message.reply_text(f"✅ Антифлуд {'включен' if value else 'выключен'}")


@admin_only
async def set_flood(update: Update, context: CallbackContext):
    """Установить настройки антифлуда"""
    if len(context.args) < 2:
        await update.message.reply_text("❌ Использование: /set_flood [лимит] [время_в_секундах]")
        return
    
    try:
        limit = int(context.args[0])
        time = int(context.args[1])
        
        if limit < 1 or time < 1:
            await update.message.reply_text("❌ Значения должны быть больше 0")
            return
        
        set_chat_setting(update.effective_chat.id, 'flood_limit', limit)
        set_chat_setting(update.effective_chat.id, 'flood_time', time)
        await update.message.reply_text(f"✅ Антифлуд настроен: {limit} сообщений за {time} секунд")
        
    except ValueError:
        await update.message.reply_text("❌ Введите числа!")


async def stats(update: Update, context: CallbackContext):
    """Статистика чата"""
    chat_member = await context.bot.get_chat_member(update.effective_chat.id, update.effective_user.id)
    
    conn = sqlite3.connect(DB_NAME)
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


# ============= ОБРАБОТЧИКИ =============
async def welcome_new_members(update: Update, context: CallbackContext):
    """Приветствие новых участников"""
    welcome_enabled = get_chat_setting(update.effective_chat.id, 'welcome_enabled')
    if welcome_enabled == 0:
        return
    
    for new_member in update.message.new_chat_members:
        if new_member.id == context.bot.id:
            continue
        
        welcome_text = (
            f"🌟 Добро пожаловать в {update.effective_chat.title}, {new_member.first_name}! 🌟\n\n"
            f"Пожалуйста, ознакомься с правилами чата и будь вежлив с другими участниками.\n"
            f"Приятного общения! 💫"
        )
        
        await update.message.reply_text(welcome_text)


user_messages = {}

async def anti_flood(update: Update, context: CallbackContext):
    """Защита от флуда"""
    if not update.message or not update.effective_user:
        return
    
    anti_flood_enabled = get_chat_setting(update.effective_chat.id, 'anti_flood_enabled')
    if anti_flood_enabled == 0:
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
    
    flood_limit = get_chat_setting(chat_id, 'flood_limit') or FLOOD_LIMIT
    flood_time = get_chat_setting(chat_id, 'flood_time') or FLOOD_TIME
    
    if user_id not in user_messages:
        user_messages[user_id] = []
    
    user_messages[user_id] = [
        msg_time for msg_time in user_messages[user_id]
        if (current_time - msg_time).seconds < flood_time
    ]
    
    user_messages[user_id].append(current_time)
    
    if len(user_messages[user_id]) > flood_limit:
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
        
        if warning_count >= WARNINGS_BEFORE_BAN:
            await context.bot.ban_chat_member(chat_id, user_id)
            await update.message.reply_text(f"🔨 {update.effective_user.first_name} забанен за флуд!")


# ============= ЗАПУСК БОТА =============
def main():
    """Запуск бота"""
    init_db()
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Регистрируем команды
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("myid", myid))  # Новая команда
    application.add_handler(CommandHandler("warn", warn))
    application.add_handler(CommandHandler("warnings", warnings))
    application.add_handler(CommandHandler("clearwarns", clear_warns))
    application.add_handler(CommandHandler("kick", kick))
    application.add_handler(CommandHandler("ban", ban))
    application.add_handler(CommandHandler("unban", unban))
    application.add_handler(CommandHandler("mute", mute))
    application.add_handler(CommandHandler("unmute", unmute))
    application.add_handler(CommandHandler("settings", settings))
    application.add_handler(CommandHandler("set_welcome", set_welcome))
    application.add_handler(CommandHandler("set_antiflood", set_antiflood))
    application.add_handler(CommandHandler("set_flood", set_flood))
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
    
    print("🤖 Бот Rubin запущен!")
    print(f"👤 Админы бота: {ADMIN_IDS}")
    print("📝 Используйте /myid чтобы узнать свой ID")
    application.run_polling()


if __name__ == '__main__':
    main()
