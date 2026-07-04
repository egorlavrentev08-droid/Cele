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

# ============= КОНФИГУРАЦИЯ =============
BOT_TOKEN = "8796023969:AAH_mXDm-I4N_LDc5zgZ_vNzKisY2j-67eg"
ADMIN_IDS = [7930591505]  # Ваш ID

# ❌ УДАЛИТЕ ЭТУ СТРОКУ!
# ADMIN_USER = [@zaddira]  # ЭТО ВЫЗЫВАЕТ ОШИБКУ!

print(f"🔍 Загружены ADMIN_IDS: {ADMIN_IDS}")
print(f"🔍 Ваш ID должен быть: 7930591505")
print(f"🔍 Проверка: {7930591505 in ADMIN_IDS}")


# ============= ДЕКОРАТОР =============
def admin_only(func):
    @wraps(func)
    async def wrapped(update: Update, context: CallbackContext, *args, **kwargs):
        user_id = update.effective_user.id
        
        # Логируем для отладки
        logger.info(f"Проверка прав: user_id={user_id}, ADMIN_IDS={ADMIN_IDS}")
        
        if user_id not in ADMIN_IDS:
            await update.message.reply_text(
                f"❌ У вас нет прав для этой команды!\n"
                f"Ваш ID: `{user_id}`\n"
                f"ID админов: `{ADMIN_IDS}`",
                parse_mode='Markdown'
            )
            return
        return await func(update, context, *args, **kwargs)

    return wrapped


# ============= КОМАНДА ДЛЯ ПРОВЕРКИ =============
async def myid(update: Update, context: CallbackContext):
    """Показать свой ID"""
    user_id = update.effective_user.id
    is_admin = user_id in ADMIN_IDS
    
    await update.message.reply_text(
        f"🆔 *Ваш ID:* `{user_id}`\n"
        f"👤 *Имя:* {update.effective_user.first_name}\n"
        f"👤 *Username:* @{update.effective_user.username if update.effective_user.username else 'Нет'}\n"
        f"🤖 *Статус админа:* {'✅ ДА' if is_admin else '❌ НЕТ'}\n\n"
        f"📝 *ADMIN_IDS:* `{ADMIN_IDS}`\n"
        f"📝 *Ваш ID в списке:* {'✅ ДА' if is_admin else '❌ НЕТ'}",
        parse_mode='Markdown'
    )


# ============= ФУНКЦИЯ ПОИСКА ПОЛЬЗОВАТЕЛЯ =============
async def find_user(update: Update, context: CallbackContext, user_input: str):
    """Улучшенный поиск пользователя по @username или ID"""
    try:
        # Если это @username
        if user_input.startswith('@'):
            username = user_input[1:]
            logger.info(f"Поиск пользователя по username: {username}")
            
            # Пробуем получить через get_chat_member
            try:
                chat_member = await context.bot.get_chat_member(
                    update.effective_chat.id,
                    user_input
                )
                logger.info(f"Найден через get_chat_member: {chat_member.user.id}")
                return chat_member.user
            except Exception as e:
                logger.warning(f"Не найден через get_chat_member: {e}")
            
            # Ищем среди администраторов
            try:
                admins = await context.bot.get_chat_administrators(update.effective_chat.id)
                for admin in admins:
                    if admin.user.username and admin.user.username.lower() == username.lower():
                        logger.info(f"Найден среди администраторов: {admin.user.id}")
                        return admin.user
            except Exception as e:
                logger.warning(f"Ошибка поиска среди админов: {e}")
            
            # Ищем по имени (первое совпадение)
            try:
                # Получаем список участников (только для маленьких чатов)
                # ВНИМАНИЕ: Это может не работать в больших чатах
                pass
            except:
                pass
            
            return None
        
        # Если это ID
        elif user_input.isdigit():
            user_id = int(user_input)
            logger.info(f"Поиск пользователя по ID: {user_id}")
            try:
                chat_member = await context.bot.get_chat_member(
                    update.effective_chat.id,
                    user_id
                )
                logger.info(f"Найден по ID: {chat_member.user.id}")
                return chat_member.user
            except Exception as e:
                logger.warning(f"Не найден по ID: {e}")
                return None
        
        return None
        
    except Exception as e:
        logger.error(f"Ошибка в find_user: {e}")
        return None


# ============= БАЗА ДАННЫХ =============
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


# ============= КОМАНДЫ БОТА =============
async def start(update: Update, context: CallbackContext):
    """Приветственное сообщение"""
    user_id = update.effective_user.id
    is_admin = user_id in ADMIN_IDS
    
    await update.message.reply_text(
        f"🌟 *Привет! Я Celestine Bot*\n\n"
        f"Ваш ID: `{user_id}`\n"
        f"Статус: {'✅ Админ' if is_admin else '❌ Пользователь'}\n\n"
        "Я помогаю модерировать чаты и защищать от спама.\n\n"
        "*Доступные команды:*\n"
        "/myid - Показать ваш ID\n"
        "/warn @user [причина] - Выдать предупреждение\n"
        "/warnings @user - Показать предупреждения\n"
        "/clearwarns @user - Очистить предупреждения\n"
        "/kick @user - Кикнуть пользователя\n"
        "/ban @user [причина] - Забанить пользователя\n"
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
        # Ищем пользователя
        target_user = await find_user(update, context, context.args[0])
        
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
        
        # Автоматический бан после 3 предупреждений
        if warning_count >= 3:
            await context.bot.ban_chat_member(update.effective_chat.id, user_id)
            await update.message.reply_text(f"🔨 {target_user.first_name} забанен за 3 предупреждения!")
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
        target_user = await find_user(update, context, context.args[0])
        
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
        target_user = await find_user(update, context, context.args[0])
        
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
        target_user = await find_user(update, context, context.args[0])
        
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
        target_user = await find_user(update, context, context.args[0])
        
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
        target_user = await find_user(update, context, context.args[0])
        
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
        target_user = await find_user(update, context, context.args[0])
        
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
        target_user = await find_user(update, context, context.args[0])
        
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


# ============= ОБРАБОТЧИКИ =============
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


user_messages = {}

async def anti_flood(update: Update, context: CallbackContext):
    """Защита от флуда"""
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
            "Флуд (автоматическое предупреждение)",
            context.bot.id
        )
        
        await update.message.delete()
        await update.message.reply_text(
            f"⚠️ {update.effective_user.first_name}, пожалуйста, не флудите!\n"
            f"Предупреждение #{warning_count}"
        )
        
        if warning_count >= 3:
            await context.bot.ban_chat_member(chat_id, user_id)
            await update.message.reply_text(f"🔨 {update.effective_user.first_name} забанен за флуд!")


# ============= ЗАПУСК =============
def main():
    """Запуск бота"""
    print("=" * 50)
    print("🚀 ЗАПУСК БОТА")
    print(f"ADMIN_IDS: {ADMIN_IDS}")
    print(f"Тип ADMIN_IDS: {type(ADMIN_IDS)}")
    print(f"Проверка ID 7930591505: {7930591505 in ADMIN_IDS}")
    print("=" * 50)
    
    init_db()
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Регистрируем команды
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("myid", myid))  # Добавляем команду myid
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
    
    # Регистрируем обработчики
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
    application.run_polling()


if __name__ == '__main__':
    main()
