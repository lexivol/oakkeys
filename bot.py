import telebot
import json
import random
import string
import datetime
import os
from flask import Flask, request, jsonify
import threading
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# ========== НАСТРОЙКИ (ЗАМЕНИТЕ НА СВОИ) ==========
BOT_TOKEN = os.environ.get("BOT_TOKEN", "ВАШ_ТОКЕН_БОТА")
MASTER_ADMIN_ID = int(os.environ.get("ADMIN_ID", 123456789))

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# Файлы для хранения
KEYS_FILE = "keys.json"
ADMINS_FILE = "admins.json"

# ========== РАБОТА С ФАЙЛАМИ ==========
def load_keys():
    if os.path.exists(KEYS_FILE):
        with open(KEYS_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_keys(keys):
    with open(KEYS_FILE, 'w') as f:
        json.dump(keys, f, indent=2)

def load_admins():
    if os.path.exists(ADMINS_FILE):
        with open(ADMINS_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_admins(admins):
    with open(ADMINS_FILE, 'w') as f:
        json.dump(admins, f, indent=2)

def is_admin(user_id):
    """Проверяет, является ли пользователь администратором"""
    if user_id == MASTER_ADMIN_ID:
        return True
    admins = load_admins()
    return str(user_id) in admins

def add_admin(user_id, added_by):
    """Добавляет администратора"""
    admins = load_admins()
    admins[str(user_id)] = {
        "added_by": added_by,
        "added_at": datetime.datetime.now().isoformat()
    }
    save_admins(admins)

def remove_admin(user_id):
    """Удаляет администратора"""
    admins = load_admins()
    if str(user_id) in admins:
        del admins[str(user_id)]
        save_admins(admins)
        return True
    return False

def get_user_id_by_username(username):
    """Получает ID пользователя по @username"""
    try:
        username = username.replace('@', '')
        user = bot.get_chat(username)
        return user.id
    except:
        return None

# ========== ГЕНЕРАЦИЯ КЛЮЧЕЙ ==========
def generate_key():
    """Генерирует ключ формата OAK-XXXX-XXXX-XXXX"""
    parts = []
    for _ in range(3):
        part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
        parts.append(part)
    return f"OAK-{'-'.join(parts)}"

def create_key(days_valid):
    """Создаёт ключ на указанное количество дней"""
    key = generate_key()
    keys = load_keys()
    keys[key] = {
        "created_at": datetime.datetime.now().isoformat(),
        "expires_at": (datetime.datetime.now() + datetime.timedelta(days=days_valid)).isoformat(),
        "days_valid": days_valid
    }
    save_keys(keys)
    return key

def is_key_valid(key):
    """Проверяет, действителен ли ключ"""
    keys = load_keys()
    
    if key not in keys:
        return False, "Ключ не найден"
    
    expires_at = datetime.datetime.fromisoformat(keys[key]["expires_at"])
    if datetime.datetime.now() > expires_at:
        return False, "Срок действия истёк"
    
    days_left = (expires_at - datetime.datetime.now()).days
    return True, f"Действителен (осталось {days_left} дн.)"

# ========== КЛАВИАТУРЫ ==========
def main_menu_keyboard():
    """Главное меню с кнопками"""
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("🆕 Сгенерировать ключ", callback_data="gen_key"),
        InlineKeyboardButton("📋 Список ключей", callback_data="list_keys"),
        InlineKeyboardButton("🔍 Проверить ключ", callback_data="check_key"),
        InlineKeyboardButton("🗑️ Удалить ключ", callback_data="del_key"),
        InlineKeyboardButton("📊 Статистика", callback_data="stats"),
        InlineKeyboardButton("👥 Управление админами", callback_data="admin_menu")
    )
    return keyboard

def admin_menu_keyboard():
    """Меню управления админами"""
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("➕ Добавить админа", callback_data="add_admin"),
        InlineKeyboardButton("➖ Удалить админа", callback_data="remove_admin"),
        InlineKeyboardButton("📋 Список админов", callback_data="list_admins"),
        InlineKeyboardButton("◀️ Назад", callback_data="back_to_main")
    )
    return keyboard

def back_keyboard():
    """Кнопка назад"""
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("◀️ Назад в меню", callback_data="back_to_main"))
    return keyboard

# ========== КОМАНДЫ БОТА ==========
@bot.message_handler(commands=['start'])
def start(message):
    if not is_admin(message.chat.id):
        bot.reply_to(message, "❌ У вас нет доступа к этому боту")
        return
    
    bot.reply_to(
        message,
        "🔑 *OAKLANDS KEY BOT*\n\n"
        "Я помогу вам управлять ключами активации для скрипта Oaklands.\n\n"
        "📋 *Доступные команды:*\n"
        "/gen <дни> - создать ключ\n"
        "/list - список ключей\n"
        "/check <ключ> - проверить ключ\n"
        "/del <ключ> - удалить ключ\n"
        "/stats - статистика\n"
        "/addadmin @user - добавить админа\n"
        "/removeadmin @user - удалить админа\n"
        "/admins - список админов\n\n"
        "👇 *Или используйте кнопки ниже:*",
        parse_mode='Markdown',
        reply_markup=main_menu_keyboard()
    )

@bot.message_handler(commands=['gen'])
def gen_key_command(message):
    if not is_admin(message.chat.id):
        return
    
    parts = message.text.split()
    if len(parts) != 2:
        bot.reply_to(message, "❌ Использование: `/gen 30`", parse_mode='Markdown')
        return
    
    try:
        days = int(parts[1])
        if days < 1 or days > 365:
            bot.reply_to(message, "❌ Дней должно быть от 1 до 365")
            return
    except:
        bot.reply_to(message, "❌ Введите число дней")
        return
    
    key = create_key(days)
    expires = (datetime.datetime.now() + datetime.timedelta(days=days)).strftime("%d.%m.%Y")
    
    bot.reply_to(
        message,
        f"✅ *Ключ создан!*\n\n"
        f"`{key}`\n\n"
        f"📅 Действует: {days} дней (до {expires})\n"
        f"🔄 Без ограничений на количество использований",
        parse_mode='Markdown'
    )

@bot.message_handler(commands=['list'])
def list_keys_command(message):
    if not is_admin(message.chat.id):
        return
    
    keys = load_keys()
    now = datetime.datetime.now()
    active = {k: v for k, v in keys.items() if now < datetime.datetime.fromisoformat(v["expires_at"])}
    
    if not active:
        bot.reply_to(message, "📭 Нет активных ключей")
        return
    
    response = f"🔑 *Активные ключи ({len(active)}):*\n\n"
    for key, data in list(active.items())[:20]:
        expires = datetime.datetime.fromisoformat(data["expires_at"]).strftime("%d.%m.%Y")
        days_left = (datetime.datetime.fromisoformat(data["expires_at"]) - now).days
        response += f"`{key}`\n📅 до {expires} (осталось {days_left} дн.)\n\n"
    
    bot.reply_to(message, response, parse_mode='Markdown')

@bot.message_handler(commands=['check'])
def check_key_command(message):
    if not is_admin(message.chat.id):
        return
    
    parts = message.text.split()
    if len(parts) != 2:
        bot.reply_to(message, "❌ Использование: /check OAK-XXXX-XXXX-XXXX")
        return
    
    valid, msg = is_key_valid(parts[1])
    if valid:
        bot.reply_to(message, f"✅ Ключ `{parts[1]}` {msg}", parse_mode='Markdown')
    else:
        bot.reply_to(message, f"❌ Ключ `{parts[1]}` недействителен\n{msg}", parse_mode='Markdown')

@bot.message_handler(commands=['del'])
def delete_key_command(message):
    if not is_admin(message.chat.id):
        return
    
    parts = message.text.split()
    if len(parts) != 2:
        bot.reply_to(message, "❌ Использование: /del OAK-XXXX-XXXX-XXXX")
        return
    
    keys = load_keys()
    key = parts[1]
    
    if key in keys:
        del keys[key]
        save_keys(keys)
        bot.reply_to(message, f"✅ Ключ `{key}` удалён", parse_mode='Markdown')
    else:
        bot.reply_to(message, "❌ Ключ не найден")

@bot.message_handler(commands=['stats'])
def stats_command(message):
    if not is_admin(message.chat.id):
        return
    
    keys = load_keys()
    now = datetime.datetime.now()
    
    active = sum(1 for k, v in keys.items() if now < datetime.datetime.fromisoformat(v["expires_at"]))
    expired = len(keys) - active
    
    bot.reply_to(
        message,
        f"📊 *Статистика*\n\n"
        f"✅ Активных: {active}\n"
        f"❌ Истекших: {expired}\n"
        f"📦 Всего: {len(keys)}",
        parse_mode='Markdown'
    )

@bot.message_handler(commands=['addadmin'])
def add_admin_command(message):
    if message.chat.id != MASTER_ADMIN_ID:
        bot.reply_to(message, "❌ Только главный администратор может добавлять админов")
        return
    
    parts = message.text.split()
    if len(parts) != 2:
        bot.reply_to(message, "❌ Использование: /addadmin @username\nИли: /addadmin 123456789")
        return
    
    user_input = parts[1]
    user_id = get_user_id_by_username(user_input) if user_input.startswith('@') else int(user_input)
    
    if not user_id:
        bot.reply_to(message, "❌ Пользователь не найден")
        return
    
    if user_id == MASTER_ADMIN_ID:
        bot.reply_to(message, "❌ Это главный администратор")
        return
    
    add_admin(user_id, message.chat.id)
    bot.reply_to(message, f"✅ Пользователь `{user_id}` добавлен в админы", parse_mode='Markdown')

@bot.message_handler(commands=['removeadmin'])
def remove_admin_command(message):
    if message.chat.id != MASTER_ADMIN_ID:
        bot.reply_to(message, "❌ Только главный администратор может удалять админов")
        return
    
    parts = message.text.split()
    if len(parts) != 2:
        bot.reply_to(message, "❌ Использование: /removeadmin @username\nИли: /removeadmin 123456789")
        return
    
    user_input = parts[1]
    user_id = get_user_id_by_username(user_input) if user_input.startswith('@') else int(user_input)
    
    if not user_id:
        bot.reply_to(message, "❌ Пользователь не найден")
        return
    
    if remove_admin(user_id):
        bot.reply_to(message, f"✅ Пользователь `{user_id}` удалён из админов", parse_mode='Markdown')
    else:
        bot.reply_to(message, "❌ Пользователь не был админом")

@bot.message_handler(commands=['admins'])
def admins_list_command(message):
    if not is_admin(message.chat.id):
        return
    
    admins = load_admins()
    if not admins:
        bot.reply_to(message, "📭 Нет дополнительных администраторов\nГлавный админ: `" + str(MASTER_ADMIN_ID) + "`", parse_mode='Markdown')
        return
    
    response = f"👥 *Список администраторов*\n\n"
    response += f"👑 Главный: `{MASTER_ADMIN_ID}`\n\n"
    response += f"➕ Добавленные:\n"
    for admin_id, data in admins.items():
        added_at = datetime.datetime.fromisoformat(data["added_at"]).strftime("%d.%m.%Y")
        response += f"`{admin_id}` (с {added_at})\n"
    
    bot.reply_to(message, response, parse_mode='Markdown')

# ========== CALLBACK QUERY HANDLER (КНОПКИ) ==========
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    if not is_admin(call.message.chat.id):
        bot.answer_callback_query(call.id, "Нет доступа")
        return
    
    if call.data == "back_to_main":
        bot.edit_message_text(
            "🔑 *OAKLANDS KEY BOT*\n\n👇 Выберите действие:",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown',
            reply_markup=main_menu_keyboard()
        )
    
    elif call.data == "gen_key":
        bot.edit_message_text(
            "📅 *Создание ключа*\n\nВведите количество дней (1-365):",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown',
            reply_markup=back_keyboard()
        )
        bot.register_next_step_handler(call.message, process_gen_key)
    
    elif call.data == "list_keys":
        keys = load_keys()
        now = datetime.datetime.now()
        active = {k: v for k, v in keys.items() if now < datetime.datetime.fromisoformat(v["expires_at"])}
        
        if not active:
            bot.edit_message_text(
                "📭 Нет активных ключей",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=back_keyboard()
            )
            return
        
        response = f"🔑 *Активные ключи ({len(active)}):*\n\n"
        for key, data in list(active.items())[:20]:
            expires = datetime.datetime.fromisoformat(data["expires_at"]).strftime("%d.%m.%Y")
            days_left = (datetime.datetime.fromisoformat(data["expires_at"]) - now).days
            response += f"`{key}`\n📅 до {expires} (осталось {days_left} дн.)\n\n"
        
        bot.edit_message_text(
            response,
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown',
            reply_markup=back_keyboard()
        )
    
    elif call.data == "check_key":
        bot.edit_message_text(
            "🔍 *Проверка ключа*\n\nВведите ключ (OAK-XXXX-XXXX-XXXX):",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown',
            reply_markup=back_keyboard()
        )
        bot.register_next_step_handler(call.message, process_check_key)
    
    elif call.data == "del_key":
        bot.edit_message_text(
            "🗑️ *Удаление ключа*\n\nВведите ключ для удаления:",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown',
            reply_markup=back_keyboard()
        )
        bot.register_next_step_handler(call.message, process_del_key)
    
    elif call.data == "stats":
        keys = load_keys()
        now = datetime.datetime.now()
        active = sum(1 for k, v in keys.items() if now < datetime.datetime.fromisoformat(v["expires_at"]))
        expired = len(keys) - active
        
        bot.edit_message_text(
            f"📊 *Статистика*\n\n"
            f"✅ Активных: {active}\n"
            f"❌ Истекших: {expired}\n"
            f"📦 Всего: {len(keys)}",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown',
            reply_markup=back_keyboard()
        )
    
    elif call.data == "admin_menu":
        bot.edit_message_text(
            "👥 *Управление администраторами*\n\nВыберите действие:",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown',
            reply_markup=admin_menu_keyboard()
        )
    
    elif call.data == "add_admin":
        if call.message.chat.id != MASTER_ADMIN_ID:
            bot.answer_callback_query(call.id, "Только главный администратор")
            return
        
        bot.edit_message_text(
            "➕ *Добавление администратора*\n\nВведите @username или ID пользователя:",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown',
            reply_markup=back_keyboard()
        )
        bot.register_next_step_handler(call.message, process_add_admin)
    
    elif call.data == "remove_admin":
        if call.message.chat.id != MASTER_ADMIN_ID:
            bot.answer_callback_query(call.id, "Только главный администратор")
            return
        
        bot.edit_message_text(
            "➖ *Удаление администратора*\n\nВведите @username или ID пользователя:",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown',
            reply_markup=back_keyboard()
        )
        bot.register_next_step_handler(call.message, process_remove_admin)
    
    elif call.data == "list_admins":
        admins = load_admins()
        
        response = f"👥 *Список администраторов*\n\n"
        response += f"👑 Главный: `{MASTER_ADMIN_ID}`\n\n"
        
        if admins:
            response += f"➕ Добавленные:\n"
            for admin_id, data in admins.items():
                added_at = datetime.datetime.fromisoformat(data["added_at"]).strftime("%d.%m.%Y")
                response += f"`{admin_id}` (с {added_at})\n"
        else:
            response += "➕ Нет дополнительных администраторов"
        
        bot.edit_message_text(
            response,
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown',
            reply_markup=back_keyboard()
        )

# ========== ОБРАБОТЧИКИ ШАГОВ ==========
def process_gen_key(message):
    if not is_admin(message.chat.id):
        return
    
    try:
        days = int(message.text)
        if days < 1 or days > 365:
            bot.reply_to(message, "❌ Дней должно быть от 1 до 365", reply_markup=back_keyboard())
            return
    except:
        bot.reply_to(message, "❌ Введите число дней", reply_markup=back_keyboard())
        return
    
    key = create_key(days)
    expires = (datetime.datetime.now() + datetime.timedelta(days=days)).strftime("%d.%m.%Y")
    
    bot.reply_to(
        message,
        f"✅ *Ключ создан!*\n\n"
        f"`{key}`\n\n"
        f"📅 Действует: {days} дней (до {expires})\n"
        f"🔄 Без ограничений на количество использований",
        parse_mode='Markdown',
        reply_markup=back_keyboard()
    )

def process_check_key(message):
    if not is_admin(message.chat.id):
        return
    
    valid, msg = is_key_valid(message.text.strip())
    if valid:
        bot.reply_to(message, f"✅ Ключ `{message.text}` {msg}", parse_mode='Markdown', reply_markup=back_keyboard())
    else:
        bot.reply_to(message, f"❌ Ключ `{message.text}` недействителен\n{msg}", parse_mode='Markdown', reply_markup=back_keyboard())

def process_del_key(message):
    if not is_admin(message.chat.id):
        return
    
    keys = load_keys()
    key = message.text.strip()
    
    if key in keys:
        del keys[key]
        save_keys(keys)
        bot.reply_to(message, f"✅ Ключ `{key}` удалён", parse_mode='Markdown', reply_markup=back_keyboard())
    else:
        bot.reply_to(message, "❌ Ключ не найден", reply_markup=back_keyboard())

def process_add_admin(message):
    if message.chat.id != MASTER_ADMIN_ID:
        return
    
    user_input = message.text.strip()
    
    if user_input.startswith('@'):
        user_id = get_user_id_by_username(user_input)
    else:
        try:
            user_id = int(user_input)
        except:
            user_id = None
    
    if not user_id:
        bot.reply_to(message, "❌ Пользователь не найден", reply_markup=back_keyboard())
        return
    
    if user_id == MASTER_ADMIN_ID:
        bot.reply_to(message, "❌ Это главный администратор", reply_markup=back_keyboard())
        return
    
    add_admin(user_id, message.chat.id)
    bot.reply_to(message, f"✅ Пользователь `{user_id}` добавлен в админы", parse_mode='Markdown', reply_markup=back_keyboard())

def process_remove_admin(message):
    if message.chat.id != MASTER_ADMIN_ID:
        return
    
    user_input = message.text.strip()
    
    if user_input.startswith('@'):
        user_id = get_user_id_by_username(user_input)
    else:
        try:
            user_id = int(user_input)
        except:
            user_id = None
    
    if not user_id:
        bot.reply_to(message, "❌ Пользователь не найден", reply_markup=back_keyboard())
        return
    
    if remove_admin(user_id):
        bot.reply_to(message, f"✅ Пользователь `{user_id}` удалён из админов", parse_mode='Markdown', reply_markup=back_keyboard())
    else:
        bot.reply_to(message, "❌ Пользователь не был админом", reply_markup=back_keyboard())

# ========== API ДЛЯ ROBLOX ==========
@app.route('/check_key', methods=['GET'])
def check_key_api():
    key = request.args.get('key')
    username = request.args.get('user', 'unknown')
    
    if not key:
        return jsonify({"valid": False, "reason": "No key provided"})
    
    valid, msg = is_key_valid(key)
    
    if valid:
        for admin_id in load_admins():
            try:
                bot.send_message(
                    int(admin_id),
                    f"🔑 *Активация скрипта*\n\n"
                    f"Ключ: `{key}`\n"
                    f"Игрок: {username}\n"
                    f"Время: {datetime.datetime.now().strftime('%H:%M:%S %d.%m.%Y')}",
                    parse_mode='Markdown'
                )
            except:
                pass
        
        bot.send_message(
            MASTER_ADMIN_ID,
            f"🔑 *Активация скрипта*\n\n"
            f"Ключ: `{key}`\n"
            f"Игрок: {username}\n"
            f"Время: {datetime.datetime.now().strftime('%H:%M:%S %d.%m.%Y')}",
            parse_mode='Markdown'
        )
        return jsonify({"valid": True, "message": msg})
    else:
        return jsonify({"valid": False, "reason": msg})

@app.route('/')
def home():
    return "Oaklands Key Bot is running! 🚀"

@app.route('/health')
def health():
    return "OK"

# ========== ЗАПУСК ==========
if __name__ == '__main__':
    def run_bot():
        print("🤖 Бот запущен!")
        bot.infinity_polling()
    
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    port = int(os.environ.get("PORT", 8080))
    print(f"🌐 API сервер запущен на порту {port}")
    app.run(host='0.0.0.0', port=port)
