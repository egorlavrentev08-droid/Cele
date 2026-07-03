import logging
import sqlite3
import os
import random
from datetime import datetime, timedelta
from functools import wraps
from typing import Optional, List, Dict
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
ADMIN_IDS = [int(id) for id in os.getenv('ADMIN_IDS', '').split(',') if id]
DB_NAME = os.getenv('DB_NAME', 'celestine_bot.db')
FLOOD_LIMIT = int(os.getenv('FLOOD_LIMIT', 5))
FLOOD_TIME = int(os.getenv('FLOOD_TIME', 10))
WARNINGS_BEFORE_BAN = int(os.getenv('WARNINGS_BEFORE_BAN', 3))

# Проверка наличия токена
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден в .env файле!")

# ============= RP СИСТЕМА =============
# Словарь для хранения состояний RP-взаимодействий
rp_states: Dict[int, Dict] = {}

# Хранилище для временных блокировок RP-команд (anti-spam)
rp_cooldown: Dict[int, datetime] = {}

# Реакции для RP-команд
RP_REACTIONS = {
    'hug': ['обнял(а)', 'прижал(а) к себе', 'нежно обнял(а)', 'крепко обнял(а)'],
    'kiss': ['поцеловал(а)', 'нежно поцеловал(а)', 'чмокнул(а) в щечку', 'страстно поцеловал(а)'],
    'slap': ['дал(а) пощёчину', 'шлёпнул(а)', 'врезал(а) по лицу', 'дал(а) леща'],
    'pat': ['погладил(а) по голове', 'потрепал(а) по волосам', 'нежно погладил(а)'],
    'bite': ['укусил(а)', 'легко укусил(а) за плечо', 'куснул(а) за ухо'],
    'cuddle': ['прижал(а) к себе', 'обнял(а) и прижал(а)', 'заключил(а) в объятия'],
    'tickle': ['пощекотал(а)', 'начал(а) щекотать', 'нежно пощекотал(а)'],
    'punch': ['ударил(а)', 'заехал(а) по морде', 'врезал(а) кулаком'],
    'kick': ['пнул(а)', 'дал(а) пинка', 'ударил(а) ногой'],
    'headpat': ['погладил(а) по голове', 'потрепал(а) по макушке', 'похлопал(а) по плечу'],
    'boop': ['ткнул(а) в нос', 'чмокнул(а) в носик', 'нежно коснулся(лась) носа'],
    'lick': ['облизал(а)', 'провёл(а) языком по', 'лизнул(а)'],
    'whisper': ['прошептал(а) на ухо', 'тихо сказал(а)', 'шепнул(а)'],
    'dance': ['пригласил(а) на танец', 'закружил(а) в танце', 'станцевал(а) с'],
    'sing': ['спел(а) для', 'исполнил(а) песню для', 'запел(а) для'],
    'cry': ['плачет на плече у', 'всхлипывает у', 'роняет слёзы перед'],
    'laugh': ['смеётся над', 'хохочет с', 'улыбается и смеётся с'],
    'blush': ['заливается краской перед', 'краснеет, глядя на', 'стыдливо улыбается'],
    'stare': ['пристально смотрит на', 'не сводит глаз с', 'вглядывается в'],
    'wave': ['машет рукой', 'приветственно машет', 'машет в ответ'],
}

# ============= ДЕКОРАТОРЫ =============
def admin_only(func):
    @wraps(func)
    async def wrapped(update, context, *args, **kwargs):
        user_id = update.effective_user.id
        if user_id not in ADMIN_IDS:
            await update.message.reply_text("❌ У вас нет прав для этой команды!")
            return
        return await func(update, context, *args, **kwargs)
    return wrapped

# ============= БАЗА ДАННЫХ =============
def init_db():
    conn = sqlite3.connect(DB_NAME)
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

# ============= КОМАНДЫ МОДЕРАЦИИ =============
async def start(update: Update, context: CallbackContext):
    """Приветственное сообщение"""
    await update.message.reply_text(
        "🌟 *Привет! Я Celestine Bot*\n\n"
        "Я помогаю модерировать чаты и защищать от спама, "
        "а также создавать уютную атмосферу с RP-командами!\n\n"
        "*Доступные команды:*\n\n"
        "*📊 Модерация:*\n"
        "/warn @user [причина] - Выдать предупреждение\n"
        "/warnings @user - Показать предупреждения\n"
        "/clearwarns @user - Очистить предупреждения\n"
        "/kick @user - Кикнуть пользователя\n"
        "/ban @user [причина] - Забанить пользователя\n"
        "/unban @user - Разбанить пользователя\n"
        "/mute @user [минуты] - Замутить пользователя\n"
        "/unmute @user - Размутить\n\n"
        "*⚙️ Настройки:*\n"
        "/settings - Настройки бота\n"
        "/stats - Статистика чата\n\n"
        "*🎭 RP-команды (ролевые игры):*\n"
        "/rphelp - Все RP-команды\n"
        "/hug @user - Обнять\n"
        "/kiss @user - Поцеловать\n"
        "/slap @user - Дать пощёчину\n"
        "/cuddle @user - Прижать к себе\n"
        "/randomrp - Случайное действие\n\n"
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
        
        # Автоматический бан после N предупреждений
        if warning_count >= WARNINGS_BEFORE_BAN:
            await context.bot.ban_chat_member(update.effective_chat.id, user_id)
            await update.message.reply_text(f"🔨 {context.args[0]} забанен за {WARNINGS_BEFORE_BAN} предупреждений!")
            clear_warnings(user_id, update.effective_chat.id)
            
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")

@admin_only
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

# ============= RP-КОМАНДЫ =============
async def rp_action(update: Update, context: CallbackContext, action: str):
    """Базовый обработчик RP-действий"""
    if not context.args:
        await update.message.reply_text(
            f"❌ Использование: /{action} @user [текст]"
        )
        return
    
    # Проверка на спам
    user_id = update.effective_user.id
    if user_id in rp_cooldown:
        time_diff = (datetime.now() - rp_cooldown[user_id]).seconds
        if time_diff < 3:
            await update.message.reply_text("⏳ Подождите немного перед следующим RP-действием!")
            return
    
    try:
        # Получаем целевого пользователя
        target_text = context.args[0]
        target_user = None
        
        if target_text.startswith('@'):
            username = target_text[1:]
            # Ищем пользователя в чате
            async for member in context.bot.get_chat_administrators(update.effective_chat.id):
                if member.user.username and member.user.username.lower() == username.lower():
                    target_user = member.user
                    break
            if not target_user:
                try:
                    target_user = await context.bot.get_chat_member(
                        update.effective_chat.id,
                        target_text
                    )
                    target_user = target_user.user
                except:
                    pass
        elif target_text.isdigit():
            try:
                target_user = await context.bot.get_chat_member(
                    update.effective_chat.id,
                    int(target_text)
                )
                target_user = target_user.user
            except:
                pass
        
        # Проверяем, найден ли пользователь
        if not target_user:
            await update.message.reply_text("❌ Пользователь не найден!")
            return
        
        # Проверка на самого себя
        if target_user.id == update.effective_user.id:
            await update.message.reply_text("😅 Нельзя сделать это с самим собой!")
            return
        
        # Проверка на бота
        if target_user.id == context.bot.id:
            responses = [
                f"*{update.effective_user.first_name} пытается {action} меня!* 😅",
                f"*{update.effective_user.first_name} хочет {action} бота!* 🤖",
                f"*{update.effective_user.first_name} {action} бота!* 🌟"
            ]
            await update.message.reply_text(
                random.choice(responses),
                parse_mode='Markdown'
            )
            return
        
        # Получаем дополнительные параметры
        extra_text = " ".join(context.args[1:]) if len(context.args) > 1 else ""
        
        # Выбираем случайную реакцию
        if action in RP_REACTIONS:
            reaction = random.choice(RP_REACTIONS[action])
        else:
            reaction = f"{action}(ет/ит)"
        
        # Формируем ответ
        response = f"*{update.effective_user.first_name}* {reaction} *{target_user.first_name}*"
        if extra_text:
            response += f"\n📝 *Детали:* {extra_text}"
        
        # Добавляем эмодзи
        emojis = {
            'hug': ['🤗', '💕', '🥰'],
            'kiss': ['💋', '😘', '💖'],
            'slap': ['😤', '👋', '💢'],
            'pat': ['👋', '💫', '✨'],
            'bite': ['🦷', '😈', '💢'],
            'cuddle': ['🤗', '💞', '💕'],
            'tickle': ['😂', '😆', '🪶'],
            'punch': ['💥', '👊', '💢'],
            'kick': ['🦵', '💥', '😤'],
            'headpat': ['👋', '✨', '💫'],
            'boop': ['👆', '😊', '💕'],
            'lick': ['😋', '👅', '💕'],
            'whisper': ['🤫', '💬', '🌙'],
            'dance': ['💃', '🕺', '🎵'],
            'sing': ['🎤', '🎵', '🎶'],
            'cry': ['😢', '💧', '🥺'],
            'laugh': ['😂', '🤣', '😄'],
            'blush': ['😊', '🥰', '💕'],
            'stare': ['👀', '😳', '💫'],
            'wave': ['👋', '😊', '✨'],
        }
        
        if action in emojis:
            response += f" {random.choice(emojis[action])}"
        
        bot_name = context.bot.username or "Celestine"
        
        await update.message.reply_text(
            f"*{bot_name}* 📖\n\n{response}",
            parse_mode='Markdown'
        )
        
        rp_cooldown[user_id] = datetime.now()
        
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")

# RP-команды с пользователем
async def hug(update: Update, context: CallbackContext):
    await rp_action(update, context, 'hug')

async def kiss(update: Update, context: CallbackContext):
    await rp_action(update, context, 'kiss')

async def slap(update: Update, context: CallbackContext):
    await rp_action(update, context, 'slap')

async def pat(update: Update, context: CallbackContext):
    await rp_action(update, context, 'pat')

async def bite(update: Update, context: CallbackContext):
    await rp_action(update, context, 'bite')

async def cuddle(update: Update, context: CallbackContext):
    await rp_action(update, context, 'cuddle')

async def tickle(update: Update, context: CallbackContext):
    await rp_action(update, context, 'tickle')

async def punch(update: Update, context: CallbackContext):
    await rp_action(update, context, 'punch')

async def kick_rp(update: Update, context: CallbackContext):
    await rp_action(update, context, 'kick')

async def headpat(update: Update, context: CallbackContext):
    await rp_action(update, context, 'headpat')

async def boop(update: Update, context: CallbackContext):
    await rp_action(update, context, 'boop')

async def lick(update: Update, context: CallbackContext):
    await rp_action(update, context, 'lick')

async def whisper(update: Update, context: CallbackContext):
    await rp_action(update, context, 'whisper')

async def dance(update: Update, context: CallbackContext):
    await rp_action(update, context, 'dance')

async def sing(update: Update, context: CallbackContext):
    await rp_action(update, context, 'sing')

async def cry(update: Update, context: CallbackContext):
    await rp_action(update, context, 'cry')

async def laugh(update: Update, context: CallbackContext):
    await rp_action(update, context, 'laugh')

async def blush(update: Update, context: CallbackContext):
    await rp_action(update, context, 'blush')

async def stare(update: Update, context: CallbackContext):
    await rp_action(update, context, 'stare')

async def wave(update: Update, context: CallbackContext):
    await rp_action(update, context, 'wave')

# RP-команды без пользователя (для себя)
async def rp_self_action(update: Update, context: CallbackContext, action: str):
    """Действие над собой"""
    user_name = update.effective_user.first_name
    
    responses = {
        'cry': [f"*{user_name}* плачет... 😢", f"*{user_name}* грустит... 💧", f"*{user_name}* печален(на)... 🥺"],
        'laugh': [f"*{user_name}* смеётся! 😂", f"*{user_name}* хохочет! 🤣", f"*{user_name}* веселится! 😄"],
        'blush': [f"*{user_name}* краснеет... 😊", f"*{user_name}* смущается... 🥰", f"*{user_name}* заливается краской... 💕"],
        'dance': [f"*{user_name}* танцует! 💃", f"*{user_name}* зажигает на танцполе! 🕺", f"*{user_name}* двигается в ритме! 🎵"],
        'sing': [f"*{user_name}* поёт! 🎤", f"*{user_name}* исполняет песню! 🎵", f"*{user_name}* напевает мелодию! 🎶"],
        'cuddle': [f"*{user_name}* обнимает себя... 🤗", f"*{user_name}* ищет утешения в объятиях... 💕"],
        'stare': [f"*{user_name}* смотрит вдаль... 👀", f"*{user_name}* мечтательно смотрит... 💫"],
        'whisper': [f"*{user_name}* шепчет что-то себе... 🤫", f"*{user_name}* тихо разговаривает... 🌙"],
    }
    
    if action in responses:
        response = random.choice(responses[action])
    else:
        response = f"*{user_name}* {action}(ет/ит) над собой"
    
    bot_name = context.bot.username or "Celestine"
    await update.message.reply_text(
        f"*{bot_name}* 📖\n\n{response}",
        parse_mode='Markdown'
    )

async def cry_self(update: Update, context: CallbackContext):
    await rp_self_action(update, context, 'cry')

async def laugh_self(update: Update, context: CallbackContext):
    await rp_self_action(update, context, 'laugh')

async def dance_self(update: Update, context: CallbackContext):
    await rp_self_action(update, context, 'dance')

async def sing_self(update: Update, context: CallbackContext):
    await rp_self_action(update, context, 'sing')

async def cuddle_self(update: Update, context: CallbackContext):
    await rp_self_action(update, context, 'cuddle')

async def blush_self(update: Update, context: CallbackContext):
    await rp_self_action(update, context, 'blush')

async def stare_self(update: Update, context: CallbackContext):
    await rp_self_action(update, context, 'stare')

async def whisper_self(update: Update, context: CallbackContext):
    await rp_self_action(update, context, 'whisper')

async def hug_self(update: Update, context: CallbackContext):
    await rp_self_action(update, context, 'cuddle')

# Дополнительные RP-команды
async def random_rp(update: Update, context: CallbackContext):
    """Случайное RP-действие"""
    actions = list(RP_REACTIONS.keys())
    action = random.choice(actions)
    
    if context.args:
        await rp_action(update, context, action)
    else:
        await rp_self_action(update, context, action)

async def rp_help(update: Update, context: CallbackContext):
    """Показать все RP-команды"""
    help_text = """
🌟 *Доступные RP-команды:*

*Основные RP-команды (использование: /команда @пользователь):*

🤗 *Обнимашки*
/hug @user - Обнять
/cuddle @user - Прижать к себе

💕 *Нежность*
/kiss @user - Поцеловать
/boop @user - Ткнуть в нос
/headpat @user - Погладить по голове
/pat @user - Погладить

😈 *Шалости*
/bite @user - Укусить
/tickle @user - Пощекотать
/lick @user - Лизнуть
/slap @user - Дать пощёчину

💥 *Боевые*
/punch @user - Ударить
/kick @user - Пнуть

🎭 *Эмоции*
/cry @user - Плакать на плече
/laugh @user - Смеяться с
/blush @user - Краснеть перед
/stare @user - Смотреть на

🎵 *Развлечения*
/dance @user - Пригласить на танец
/sing @user - Спеть для
/whisper @user - Прошептать на ухо

👋 *Другое*
/wave @user - Помахать

*Для себя (без @user):*
/cry - Поплакать
/laugh - Посмеяться
/dance - Потанцевать
/sing - Попеть
/cuddle - Обнять себя
