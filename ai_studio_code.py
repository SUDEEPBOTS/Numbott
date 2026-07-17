import os
import sqlite3
import re
import asyncio
import time
import logging
import aiohttp
import csv
import zipfile
import shutil
import html
from datetime import datetime
from urllib.parse import quote

from telethon import TelegramClient, events, Button
from telethon.errors import (
    SessionPasswordNeededError, 
    MessageNotModifiedError,
    UserNotParticipantError,
    ChatAdminRequiredError
)
from telethon.tl.types import ReplyKeyboardMarkup, KeyboardButtonRow, KeyboardButton
from telethon.tl.functions.channels import GetParticipantRequest
from telethon.tl.functions.account import GetPasswordRequest

# ================= CONFIGURATION =================
def load_env_file(path=".env"):
    if not os.path.exists(path):
        return
    try:
        with open(path, encoding="utf-8") as env_file:
            for raw_line in env_file:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                os.environ.setdefault(key, value)
    except Exception as ex:
        print(f"Failed to load {path}: {ex}")


load_env_file()


def env_int(name, default=0):
    raw = os.getenv(name)
    if raw is None or str(raw).strip() == "":
        return default
    return int(str(raw).strip())


def env_list(name, default_csv):
    raw = os.getenv(name, default_csv)
    return [item.strip() for item in raw.split(",") if item.strip()]


API_ID = env_int("API_ID", 32208414)
API_HASH = os.getenv("API_HASH", "628f11c05a44c8dda4b006e66f4bf7df")
BOT_TOKEN = os.getenv("BOT_TOKEN", "8975876483:AAE8vKK4O7OyubHJ1M0AGIcctoqlbB7-9_Q")
ADMIN_ID = env_int("ADMIN_ID", 5298773697)  

# CHANNELS
LOG_CHANNEL_ID = env_int("LOG_CHANNEL_ID", -1004452478102)
CHECK_CHANNELS = env_list("CHECK_CHANNELS", "-1003933313239,-1003964347575")
JOIN_URLS = env_list("JOIN_URLS", "https://t.me/+DE0UFPWq6yowMmQ9,https://t.me/I_VIP_RADHE_II")

# LINKS & MEDIA
TERMS_URL = os.getenv("TERMS_URL", "https://example.com/terms")
CWALLET_QR = os.getenv("CWALLET_QR", "https://example.com/qr.jpg")
CWALLET_ID = os.getenv("CWALLET_ID", "")

# UPI API DETAILS
UPI_MID = os.getenv("UPI_MID", "")
UPI_ID = os.getenv("UPI_ID", "vinit-godara@fam")

OTP_REGEX = r"\b\d{4,8}\b"
AUTO_CANCEL_SECONDS = 600

# ================= PREMIUM EMOJIS =================
USE_PREMIUM_EMOJIS = os.getenv("USE_PREMIUM_EMOJIS", "1").strip().lower() not in {"0", "false", "no", "off"}
PREMIUM_EMOJIS = {
    "heart_fire": "5042225965518816316",
    "lightning": "5042334757040423886",
    "location": "5039775669496579510",
    "flower": "6073117703965511893",
    "check": "6147460667281511517",
    "crown": "6235252066554484059",
    "kiss": "6116282026506065674",
    "skull": "6089128873893563936",
    "xmas": "6267071898702583835",
    "monkey": "6273627839862411998",
    "gift": "5893175870096414393",
    "angel": "5893411041030707544",
    "devil": "5893079628469246474",
}


def tg_emoji(name, fallback):
    emoji_id = PREMIUM_EMOJIS.get(name)
    if USE_PREMIUM_EMOJIS and emoji_id:
        return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'
    return fallback


PE_HEART = tg_emoji("heart_fire", "❤️‍🔥")
PE_LIGHTNING = tg_emoji("lightning", "⚡")
PE_LOCATION = tg_emoji("location", "📍")
PE_FLOWER = tg_emoji("flower", "🌸")
PE_CHECK = tg_emoji("check", "✅")
PE_CROWN = tg_emoji("crown", "👑")
PE_KISS = tg_emoji("kiss", "😘")
PE_SKULL = tg_emoji("skull", "💀")
PE_XMAS = tg_emoji("xmas", "🎄")
PE_MONKEY = tg_emoji("monkey", "🐵")
PE_GIFT = tg_emoji("gift", "🎁")
PE_ANGEL = tg_emoji("angel", "😇")
PE_DEVIL = tg_emoji("devil", "😈")

# ================= UI ICONS =================
P_YES = PE_CHECK
P_NO = '❌'
P_PKG = '📦'
P_MONEY = '💰'
P_USDT = '💲'
P_INR = '₹'
P_TG = '✈️'
P_GIFT = PE_GIFT
P_STATS = '📊'
P_CARD = '💳'
P_USERS = '👥'
P_CAL = '📅'
P_PC = '💻'
P_EYE = '👁️'
P_UPI = '🏦'
P_CW = '👛'
P_ON = '🟢'
P_OFF = '🔴'
P_ID = '🆔'
P_KEY = '⌨️'
P_GLOBE = PE_LOCATION
P_CART = '🛒'
P_STORE = '🏬'
P_OTP = '🔢'
P_2FA = '🔐'
P_FLAG = '🏳️'
P_PHONE = '📱'
P_WAIT = '⏳'
P_TIME = '⏰'
P_WARN = '⚠️'
P_DOC = '📃'
P_SOS = '🆘'
P_ASST = '🤖'
P_ACC = '👤'


def validate_config():
    missing = []
    if API_ID <= 0:
        missing.append("API_ID")
    if not API_HASH:
        missing.append("API_HASH")
    if not BOT_TOKEN or ":" not in BOT_TOKEN:
        missing.append("BOT_TOKEN")
    if ADMIN_ID <= 0:
        missing.append("ADMIN_ID")
    if LOG_CHANNEL_ID == 0:
        missing.append("LOG_CHANNEL_ID")
    if missing:
        raise RuntimeError(
            "Missing/invalid required config: " + ", ".join(missing) +
            ". Set them via environment variables before starting the bot."
        )
    if not CHECK_CHANNELS:
        logger.warning("CHECK_CHANNELS is empty; join verification will be ineffective.")
    if not JOIN_URLS:
        logger.warning("JOIN_URLS is empty; users will not see join buttons.")
    if CHECK_CHANNELS and JOIN_URLS and len(CHECK_CHANNELS) != len(JOIN_URLS):
        logger.warning(
            "CHECK_CHANNELS (%s) and JOIN_URLS (%s) lengths differ.",
            len(CHECK_CHANNELS), len(JOIN_URLS)
        )

# ================= INITIALIZATION =================
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

os.makedirs("sessions", exist_ok=True)

session_name = f"bot_session_{BOT_TOKEN.split(':')[0]}"
bot = TelegramClient(session_name, API_ID, API_HASH)
bot.parse_mode = 'html'

db = sqlite3.connect("otp_bot_final.db", check_same_thread=False, timeout=20)
db.execute("PRAGMA journal_mode=WAL;")
cur = db.cursor()

active_orders = {}      
waiting_proof = {}      
deposit_input = {} 
admin_dep_state = {}    
user_spam_cooldown = {} 
session_buy_state = {}  
custom_dep_amt = {}     

user_locks = {}

def get_user_lock(uid):
    if uid not in user_locks:
        user_locks[uid] = asyncio.Lock()
    return user_locks[uid]

# ================= DATABASE SCHEMA =================
def setup_db():
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        balance INTEGER DEFAULT 0,
        referred_by INTEGER,
        total_deposited INTEGER DEFAULT 0,
        joined_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        banned INTEGER DEFAULT 0,
        discount INTEGER DEFAULT 0,
        terms_accepted INTEGER DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
    CREATE TABLE IF NOT EXISTS stock (
        phone TEXT PRIMARY KEY,
        session_file TEXT,
        country_name TEXT,
        country_icon TEXT DEFAULT '🌍',
        account_year INTEGER,
        category TEXT DEFAULT 'Good',
        price INTEGER,
        available INTEGER DEFAULT 1,
        twofa TEXT DEFAULT 'None',
        added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS auto_prices (
        country TEXT,
        year TEXT,
        price INTEGER,
        PRIMARY KEY (country, year)
    );
    CREATE TABLE IF NOT EXISTS deposits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount INTEGER,
        method_name TEXT,
        status TEXT, 
        date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS upi_orders (
        order_id TEXT PRIMARY KEY,
        user_id INTEGER,
        amount INTEGER,
        status TEXT,
        date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        country TEXT,
        year INTEGER,
        price INTEGER,
        phone TEXT,
        otp TEXT,
        date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS custom_payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        caption TEXT,
        qr_file_id TEXT
    );
    CREATE TABLE IF NOT EXISTS admins (
        user_id INTEGER PRIMARY KEY,
        p_add_stock INTEGER DEFAULT 0,
        p_manage_stock INTEGER DEFAULT 0,
        p_stats INTEGER DEFAULT 0,
        p_bal INTEGER DEFAULT 0,
        p_settings INTEGER DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS custom_countries (
        code TEXT PRIMARY KEY,
        name TEXT,
        flag TEXT
    );
    """)
    db.commit()

setup_db()

# ================= HELPER FUNCTIONS =================
def is_bot_online():
    res = cur.execute("SELECT value FROM settings WHERE key='bot_status'").fetchone()
    return res[0] == 'on' if res else True

def is_admin(uid):
    if uid == ADMIN_ID: return True
    row = cur.execute("SELECT user_id FROM admins WHERE user_id=?", (uid,)).fetchone()
    return bool(row)

def has_perm(uid, perm):
    if uid == ADMIN_ID: return True
    row = cur.execute(f"SELECT {perm} FROM admins WHERE user_id=?", (uid,)).fetchone()
    return bool(row and row[0] == 1)

def ensure_user(uid):
    cur.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (uid,))
    db.commit()

def get_usdt_rate():
    res = cur.execute("SELECT value FROM settings WHERE key='usdt_rate'").fetchone()
    try: return float(res[0]) if res else 94.0
    except: return 94.0

def get_support_url():
    res = cur.execute("SELECT value FROM settings WHERE key='support_url'").fetchone()
    url = res[0] if res and res[0] else "https://t.me/tgtelehelpbot"
    if not url.startswith("http"): url = "https://" + url.replace("@", "t.me/")
    return url

def to_usd(inr):
    return round(inr / get_usdt_rate(), 2)

def is_user_banned(uid):
    res = cur.execute("SELECT banned FROM users WHERE user_id=?", (uid,)).fetchone()
    return res and res[0] == 1

def update_balance(uid, amount):
    cur.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (amount, uid))
    db.commit()

def delete_session_files(session_path):
    base = session_path if not session_path.endswith('.session') else session_path[:-8]
    for ext in ['.session', '.session-wal', '.session-shm', '.session-journal']:
        try:
            if os.path.exists(base + ext): os.remove(base + ext)
        except: pass


# [FIXED] Force join channel logic properly implemented here
async def check_channel_joined(uid):
    if is_admin(uid): return True
    for ch in CHECK_CHANNELS:
        try:
            # Convert string channel ID to integer safely to avoid ValueError
            ch_id = int(ch.strip()) if str(ch).strip().lstrip('-').isdigit() else ch.strip()
            
            try:
                # Direct check via Telethon function
                await bot(GetParticipantRequest(channel=ch_id, participant=uid))
            except ValueError:
                # If ValueError occurs, resolve entity first then check again
                entity = await bot.get_entity(ch_id)
                await bot(GetParticipantRequest(channel=entity, participant=uid))
                
        except UserNotParticipantError:
            return False
        except ChatAdminRequiredError:
            logger.error(f"Bot is not admin in channel: {ch}")
            return False
        except Exception as e:
            logger.error(f"Channel Check Error for {ch}: {e}")
            return False
    return True


COUNTRY_CODES = {
    '1': ('USA/Canada', '🇺🇸'), '7': ('Russia', '🇷🇺'), '20': ('Egypt', '🇪🇬'),
    '27': ('South Africa', '🇿🇦'), '31': ('Netherlands', '🇳🇱'), '32': ('Belgium', '🇧🇪'),
    '33': ('France', '🇫🇷'), '34': ('Spain', '🇪🇸'), '39': ('Italy', '🇮🇹'), 
    '44': ('UK', '🇬🇧'), '46': ('Sweden', '🇸🇪'), '48': ('Poland', '🇵🇱'),
    '49': ('Germany', '🇩🇪'), '51': ('Peru', '🇵🇪'), '52': ('Mexico', '🇲🇽'),
    '54': ('Argentina', '🇦🇷'), '55': ('Brazil', '🇧🇷'), '56': ('Chile', '🇨🇱'),
    '57': ('Colombia', '🇨🇴'), '58': ('Venezuela', '🇻🇪'), '60': ('Malaysia', '🇲🇾'),
    '61': ('Australia', '🇦🇺'), '62': ('Indonesia', '🇮🇩'), '63': ('Philippines', '🇵🇭'), 
    '66': ('Thailand', '🇹🇭'), '84': ('Vietnam', '🇻🇳'), '86': ('China', '🇨🇳'), 
    '90': ('Turkey', '🇹🇷'), '91': ('India', '🇮🇳'), '92': ('Pakistan', '🇵🇰'), 
    '93': ('Afghanistan', '🇦🇫'), '94': ('Sri Lanka', '🇱🇰'), '95': ('Myanmar', '🇲🇲'),
    '98': ('Iran', '🇮🇷'), '212': ('Morocco', '🇲🇦'), '213': ('Algeria', '🇩🇿'),
    '234': ('Nigeria', '🇳🇬'), '254': ('Kenya', '🇰🇪'), '255': ('Tanzania', '🇹🇿'),
    '380': ('Ukraine', '🇺🇦'), '880': ('Bangladesh', '🇧🇩'), '964': ('Iraq', '🇮🇶'),
    '966': ('Saudi Arabia', '🇸🇦'), '971': ('UAE', '🇦🇪'), '998': ('Uzbekistan', '🇺🇿')
}

def get_flag_by_country_name(name):
    for code, (c_name, c_flag) in COUNTRY_CODES.items():
        if c_name == name: return c_flag
    try:
        row = cur.execute("SELECT flag FROM custom_countries WHERE name=?", (name,)).fetchone()
        if row: return row[0]
    except: pass
    return "🌍"

def get_country_info(phone):
    phone = str(phone).replace(' ', '').replace('+', '')
    if not phone: return "Unknown", "🌍"
    
    try:
        customs = cur.execute("SELECT code, name, flag FROM custom_countries").fetchall()
        customs.sort(key=lambda x: len(x[0]), reverse=True)
        for code, name, flag in customs:
            if phone.startswith(code): return name, flag
    except: pass

    for length in (3, 2, 1):
        prefix = phone[:length]
        if prefix in COUNTRY_CODES: return COUNTRY_CODES[prefix]
    return "Unknown", "🌍"

async def detect_account_year(client):
    year = 2024
    try:
        try: await client.delete_dialog('TGDNAbot')
        except: pass
        await client.send_message('TGDNAbot', '/start')
        me = await client.get_me()
        await asyncio.sleep(1)
        await client.send_message('TGDNAbot', str(me.id)) 
        for _ in range(8):
            await asyncio.sleep(1.5)
            msgs = await client.get_messages('TGDNAbot', limit=3)
            for m in msgs:
                if m.text and ('Created:' in m.text or 'Age:' in m.text or 'Registration' in m.text):
                    match = re.search(r'(?:Created|Age|Registration)[^\d]*(\d{4})', m.text, re.IGNORECASE)
                    if match: return int(match.group(1))
    except Exception: pass
    return year

# ================= LOGGING LOGIC =================
async def process_referral_bonus(uid, amount):
    row = cur.execute("SELECT referred_by FROM users WHERE user_id=?", (uid,)).fetchone()
    ref = row[0] if row else None
    if ref:
        pct_row = cur.execute("SELECT value FROM settings WHERE key='ref_percent'").fetchone()
        pct = float(pct_row[0]) if pct_row else 3.0
        if pct > 0:
            bonus = int(amount * (pct / 100))
            if bonus > 0:
                update_balance(ref, bonus)
                try:
                    await bot.send_message(
                        ref,
                        f"{PE_GIFT} <b>Referral Bonus Unlocked!</b>\n"
                        f"{PE_HEART} Your referral <code>{uid}</code> deposited {P_INR}{amount}.\n"
                        f"{PE_CHECK} You earned <b>{P_INR}{bonus}</b>!"
                    )
                except:
                    pass

async def log_primary_deposit(uid, amt, method):
    try:
        try:
            user = await bot.get_entity(int(uid))
            username = html.escape(user.username) if user.username else "NoUsername"
        except:
            username = "NoUsername"
        t = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        msg = (f"{PE_GIFT} <b>NEW DEPOSIT SUCCESSFUL</b>\n\n"
               f"{P_ACC} Uꜱᴇʀ ID: <code>{uid}</code>\n"
               f"👤 Uꜱᴇʀɴᴀᴍᴇ: @{username}\n"
               f"{P_MONEY} Aᴍᴏᴜɴᴛ: {P_INR}{amt}\n"
               f"{P_CARD} Mᴇᴛʜᴏᴅ: {method}\n"
               f"{P_TIME} Tɪᴍᴇ: {t}\n\n"
               f"<i>{PE_HEART} Thanks for depositing in Fresh Tg!</i>")
        try: await bot.send_message(LOG_CHANNEL_ID, msg)
        except Exception as e: logger.error(f"Failed Log: {e}")
    except Exception as e: logger.error(f"Global Dep Log Err: {e}")

async def log_primary_purchase(uid, country, price, amount, year, qty):
    try:
        t = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        msg = (f"{PE_LIGHTNING} <b>NEW PURCHASE SUCCESSFUL</b>\n\n"
               f"{P_ID} Uꜱᴇʀ Iᴅ: <code>{uid}</code>\n"
               f"{P_GLOBE} Cᴏᴜɴᴛʀʏ: {country}\n"
               f"{P_MONEY} Pʀɪᴄᴇ: {P_INR}{price}\n"
               f"{P_CARD} Tᴏᴛᴀʟ Pᴀɪᴅ: {P_INR}{amount}\n"
               f"{P_CAL} Yᴇᴀʀ: {year}\n"
               f"{P_PKG} Qᴜᴀɴᴛɪᴛʏ: {qty}\n"
               f"{P_TIME} Tɪᴍᴇ: {t}")
        try: await bot.send_message(LOG_CHANNEL_ID, msg)
        except: pass
    except Exception as e: logger.error(f"Pur Log Err: {e}")

# ================= MENU HELPERS =================
def get_persistent_menu(uid):
    rows = [
        [KeyboardButton("🛒 Buy Account"), KeyboardButton("👤 My Profile")],
        [KeyboardButton("📁 Buy Sessions")],
        [KeyboardButton("💰 Deposit"), KeyboardButton("📊 My Stats")],
        [KeyboardButton("📞 Support")]
    ]
    if is_admin(uid): rows.append([KeyboardButton("🔐 Admin Panel")])
    return ReplyKeyboardMarkup([KeyboardButtonRow(r) for r in rows], resize=True)


def get_terms_buttons():
    return [
        [Button.url("📜 Read Terms & Conditions", TERMS_URL)],
        [Button.inline("✅ Accept", "tc_accept"), Button.inline("❌ Reject", "tc_reject")]
    ]


def get_support_buttons():
    buttons = [
        [Button.url("📩 Support", get_support_url())],
        [Button.url("📜 Terms & Conditions", TERMS_URL)]
    ]
    if JOIN_URLS:
        buttons.append([Button.url("📢 Channel", JOIN_URLS[0])])
    return buttons


def get_join_buttons():
    buttons = [[Button.url(f"📢 Join Channel {i+1}", link)] for i, link in enumerate(JOIN_URLS) if link]
    buttons.append([Button.inline("✅ Verify Joined", "verify_join")])
    return buttons

async def send_main_menu(event, uid):
    me = await bot.get_me()
    pct_row = cur.execute("SELECT value FROM settings WHERE key='ref_percent'").fetchone()
    pct = pct_row[0] if pct_row else "3"
    bot_username = me.username or ""
    ref_line = (
        f"{P_GLOBE} <code>https://t.me/{bot_username}?start=ref_{uid}</code>"
        if bot_username else
        f"{P_GLOBE} <i>Set a public bot username to enable referral links.</i>"
    )
    msg = (f"{PE_HEART} <b>Welcome to Fresh Tg Store!</b>\n\n"
           f"{PE_GIFT} <b>Premium services:</b> Buy accounts, sessions, and top up instantly.\n"
           f"{P_GIFT} <b>Refer & Earn:</b>\nInvite friends and earn {pct}% of their deposits!\n"
           f"{ref_line}\n\n"
           f"👨‍💻 <b>Developer:</b> @I_VIP_RADHE_II")
    
    if isinstance(event, events.CallbackQuery.Event):
        try: await event.delete()
        except: pass
        await bot.send_message(uid, msg, buttons=get_persistent_menu(uid))
    else:
        await event.respond(msg, buttons=get_persistent_menu(uid))

# ================= DEPOSIT HANDLERS =================
def format_payment_buttons(buttons):
    n = len(buttons)
    res = []
    for i in range(0, n, 2): res.append(buttons[i:i+2])
    return res

async def deposit_menu(event):
    msg = f"{P_CARD} <b>Select Payment Method:</b>\n\n{PE_LIGHTNING} Choose Automatic for instant credit.\n{P_WAIT} Choose Manual for other methods."
    flat_buttons = [
        Button.inline("⚡ UPI Automatic", "dep_upi"),
        Button.inline("👛 Cwallet ( +5% )", "depm_Cwallet")
    ]
    customs = cur.execute("SELECT name FROM custom_payments").fetchall()
    for c in customs:
        flat_buttons.append(Button.inline(f"💳 {c[0]}", f"depm_{c[0]}"))
    
    btns = format_payment_buttons(flat_buttons)
    await bot.send_message(event.chat_id, msg, buttons=btns)

def get_keypad():
    return [
        [Button.inline("1", "kp_1"), Button.inline("2", "kp_2"), Button.inline("3", "kp_3")],
        [Button.inline("4", "kp_4"), Button.inline("5", "kp_5"), Button.inline("6", "kp_6")],
        [Button.inline("7", "kp_7"), Button.inline("8", "kp_8"), Button.inline("9", "kp_9")],
        [Button.inline("🔙 Del", "kp_del"), Button.inline("0", "kp_0"), Button.inline("✅ Confirm", "kp_done")],
        [Button.inline("❌ Cancel", "cancel_action")]
    ]

def get_admin_custom_keypad(dep_id):
    return [
        [Button.inline("1", f"dkp|{dep_id}|1"), Button.inline("2", f"dkp|{dep_id}|2"), Button.inline("3", f"dkp|{dep_id}|3")],
        [Button.inline("4", f"dkp|{dep_id}|4"), Button.inline("5", f"dkp|{dep_id}|5"), Button.inline("6", f"dkp|{dep_id}|6")],
        [Button.inline("7", f"dkp|{dep_id}|7"), Button.inline("8", f"dkp|{dep_id}|8"), Button.inline("9", f"dkp|{dep_id}|9")],
        [Button.inline("🔙 Del", f"dkp|{dep_id}|del"), Button.inline("0", f"dkp|{dep_id}|0"), Button.inline("✅ Confirm", f"dkp|{dep_id}|conf")],
        [Button.inline("❌ Cancel", f"dkp|{dep_id}|cancel")]
    ]

async def manual_deposit_init(event, method):
    uid = event.sender_id
    deposit_input[uid] = {'step': 'wait_amt', 'method': method}
    await event.edit(f"{P_CARD} <b>{method} Deposit</b>\n\n👇 Reply to this message with the <b>AMOUNT</b> in ₹ (INR) you want to deposit.", buttons=[[Button.inline("❌ Cancel", "cancel_action")]])

async def init_upi_keypad(event):
    uid = event.sender_id
    deposit_input[uid] = {'step': 'upi_keypad', 'val': '0'}
    await event.edit(f"{P_KEY} <b>ENTER AMOUNT IN INR (Min ₹1)</b>\n\n{P_MONEY} <code>₹0</code>", buttons=get_keypad())

async def keypad_logic(event):
    uid = event.sender_id
    action = event.data.decode().replace("kp_", "")
    curr = deposit_input.get(uid, {}).get('val', "0")

    if action.isdigit():
        if curr == "0": curr = action
        else: curr += action
        if len(curr) > 5: curr = curr[:5]
    elif action == "del": curr = curr[:-1] or "0"
    elif action == "done":
        amt = int(curr)
        if amt < 1: return await event.answer("⚠️ Minimum Deposit is ₹1", alert=True)
        return await show_upi_qr(event, amt)
    
    deposit_input[uid] = {'step': 'upi_keypad', 'val': curr}
    await event.edit(f"{P_KEY} <b>ENTER AMOUNT IN INR</b>\n\n{P_MONEY} <code>₹{curr}</code>", buttons=get_keypad())

async def show_upi_qr(event, amount):
    uid = event.sender_id
    order_id = f"ORDER_{uid}_{int(time.time())}"
    await event.edit(f"{P_WAIT} Generating Payment QR...")
    
    upi_url = f"upi://pay?pa={UPI_ID}&pn=FreshTgStore&am={amount}&cu=INR"
    encoded_upi = quote(upi_url)
    qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=400x400&data={encoded_upi}"
    
    try:
        cur.execute("INSERT INTO upi_orders (order_id, user_id, amount, status) VALUES (?,?,?,?)", (order_id, uid, amount, "pending"))
        db.commit()
        
        msg = (f"{PE_LIGHTNING} <b>AUTOMATIC UPI PAYMENT</b>\n\n"
               f"{P_MONEY} Amount: <code>₹{amount}</code>\n"
               f"{P_ID} Order ID: <code>{order_id}</code>\n\n"
               f"👇 <b>Scan the QR below or Pay to:</b>\n<code>{UPI_ID}</code>\n\n"
               f"⚠️ <b>AFTER PAYING:</b> Tap the button below to submit your 12-Digit UTR/Reference Number.")
        
        await event.delete()
        await bot.send_file(uid, qr_url, caption=msg, buttons=[
            [Button.inline("✅ Submit UTR (12 Digit)", f"submit_utr_{order_id}")], 
            [Button.inline("❌ Cancel", "cancel_action")]
        ])
    except Exception as e: 
        await bot.send_message(uid, f"{P_NO} Error: {str(e)}")

async def auto_check_upi_task(uid, order_id, msg_to_edit):
    pass 

async def verify_upi_payment(event, order_id):
    uid = event.sender_id
    row = cur.execute("SELECT amount, status FROM upi_orders WHERE order_id=?", (order_id,)).fetchone()
    if not row: return await event.answer("❌ Order not found.", alert=True)
    if row[1] == 'success': return await event.answer("✅ Already credited!", alert=True)

    chat = event.chat_id
    await event.delete()
    
    async with bot.conversation(chat, timeout=120) as conv:
        try:
            await conv.send_message("👇 <b>Please enter the 12-Digit UTR / Reference Number of your payment:</b>\n\n<i>(Type /cancel to abort)</i>")
            resp = await conv.get_response()
            utr_number = resp.text.strip()
            
            if utr_number == "/cancel":
                return await conv.send_message("❌ Cancelled.")
            if len(utr_number) < 8:
                return await conv.send_message("❌ Invalid UTR. Please try again.")
            
            await conv.send_message(f"⏳ Verifying UTR: <code>{utr_number}</code>...\n<i>Please wait...</i>")
            
            amt = int(row[0])
            
            cur.execute("INSERT INTO deposits (user_id, amount, method_name, status) VALUES (?,?,?,?)", (uid, amt, f"UPI (UTR: {utr_number})", "pending"))
            db.commit()
            dep_id = cur.lastrowid
            
            cap = (f"{PE_LIGHTNING} <b>NEW UPI DEPOSIT (Needs Approval)</b>\n"
                   f"{P_ACC} User: <code>{uid}</code>\n"
                   f"{P_MONEY} Amount: <b>₹{amt}</b>\n"
                   f"🧾 UTR Submitted: <code>{utr_number}</code>\n"
                   f"Please verify this UTR in your FamPay app.")
            
            btns = [
                [Button.inline(f"✅ Accept (₹{amt})", f"dep_acc|{dep_id}|{uid}|UPI|exact|{amt}"), 
                 Button.inline("❌ Reject", f"dep_rej|{dep_id}|{uid}")]
            ]
            
            try:
                await bot.send_message(LOG_CHANNEL_ID, cap, buttons=btns)
            except Exception as log_err:
                try:
                    await bot.send_message(ADMIN_ID, f"⚠️ <b>LOG CHANNEL ERROR</b>\n\n{cap}", buttons=btns)
                except Exception as admin_err:
                    print(f"Failed to log UPI deposit: {admin_err}")
                
            await conv.send_message("✅ <b>UTR Submitted successfully!</b>\nAmount will be added to your balance as soon as our system/admin verifies the payment.")
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            await conv.send_message(f"❌ Time out or Error: {e}")

# ================= BUYING FLOW =================
async def show_countries(event, flow, page=1):
    limit = 10
    offset = (page - 1) * limit
    
    total_row = cur.execute("SELECT COUNT(DISTINCT country_name) FROM stock WHERE available=1").fetchone()
    total = total_row[0] if total_row else 0
    rows = cur.execute("SELECT country_icon, country_name, COUNT(*) FROM stock WHERE available=1 GROUP BY country_name ORDER BY country_name ASC LIMIT ? OFFSET ?", (limit, offset)).fetchall()
        
    if not rows and page == 1: 
        err_msg = f"{P_NO} <b>Stock is Empty right now. Check back later!</b>"
        if isinstance(event, events.CallbackQuery.Event): return await event.edit(err_msg)
        else: return await event.respond(err_msg)
    
    title = f"{PE_LIGHTNING} <b>Bulk Sessions Menu</b>" if flow == 'bulk' else f"{PE_HEART} <b>Single Account Menu</b>"
    msg = f"{title}\n\n{P_GLOBE} <b>Select a region below to view available numbers (Page {page}).</b>\n{P_USDT} Rate: 1 USDT = {P_INR}{get_usdt_rate()}\n\n"
    
    btns = []
    for (i, n, c) in rows:
        btns.append([Button.inline(f"{i} {n} ({c})", f"bc|{flow}|{n[:20]}")])

    nav = []
    if page > 1: nav.append(Button.inline("Prev", f"pg_c|{flow}|{page-1}"))
    if offset + limit < total: nav.append(Button.inline("Next", f"pg_c|{flow}|{page+1}"))
    if nav: btns.append(nav)
    btns.append([Button.inline("Cancel", "cancel_action")])
    
    if isinstance(event, events.CallbackQuery.Event): await event.edit(msg, buttons=btns)
    else: await event.respond(msg, buttons=btns)

async def show_years(event, flow, country):
    rows = cur.execute("SELECT account_year, price, COUNT(*) FROM stock WHERE available=1 AND country_name LIKE ? GROUP BY account_year, price ORDER BY account_year DESC", (f"{country}%",)).fetchall()
    if not rows: return await event.answer("❌ Out of stock for this country.", alert=True)

    uid = event.sender_id
    disc_row = cur.execute("SELECT discount FROM users WHERE user_id=?", (uid,)).fetchone()
    discount = disc_row[0] if disc_row else 0

    msg = f"{PE_FLOWER} <b>Select Account Year</b>\n{P_GLOBE} Country: <b>{country}</b>\n\n"
    btns = []
    
    for (y, p, c) in rows:
        disp_p = p if discount == 0 else int(p * (100 - discount) / 100)
        disc_text = f" (-{discount}%)" if discount > 0 else ""
        btns.append([Button.inline(f"{y} | ₹{disp_p}{disc_text} | {c}", f"by|{flow}|{country}|{y}|{p}")])

    btns.append([Button.inline("Back to Countries", f"pg_c|{flow}|1")])
    await event.edit(msg, buttons=btns)

async def confirm_purchase(event, country, year, price_str):
    uid = event.sender_id
    base_price = int(price_str)
    
    bal_row = cur.execute("SELECT balance FROM users WHERE user_id=?", (uid,)).fetchone()
    bal = bal_row[0] if bal_row else 0
    disc_row = cur.execute("SELECT discount FROM users WHERE user_id=?", (uid,)).fetchone()
    discount = disc_row[0] if disc_row else 0
    final_price = base_price if discount == 0 else int(base_price * (100 - discount) / 100)

    msg = (f"{PE_CHECK} <b>Confirm Your Purchase</b>\n\n"
           f"{P_FLAG} <b>Country:</b> {country}\n"
           f"{P_CAL} <b>Year:</b> {year}\n"
           f"{P_MONEY} <b>Final Price:</b> {P_INR}{final_price}\n\n"
           f"{P_CARD} <b>Your Balance:</b> {P_INR}{bal}\n\n"
           f"❓ Do you want to proceed with this purchase?")
    
    btns = [
        [Button.inline("Yes, Buy Now", f"buy_cf|{country}|{year}|{base_price}")],
        [Button.inline("No, Cancel", "cancel_action")]
    ]
    await event.edit(msg, buttons=btns)

async def process_purchase(event, country, year_str, price_str):
    uid, base_price = event.sender_id, int(price_str)

    disc_row = cur.execute("SELECT discount FROM users WHERE user_id=?", (uid,)).fetchone()
    discount = disc_row[0] if disc_row else 0
    final_price = base_price if discount == 0 else int(base_price * (100 - discount) / 100)

    async with get_user_lock(uid):
        row = cur.execute("SELECT phone, session_file, country_icon, account_year, twofa FROM stock WHERE country_name LIKE ? AND account_year=? AND price=? AND available=1 LIMIT 1", (f"{country}%", int(year_str), base_price)).fetchone()

        if not row:
            return await event.answer("❌ Sold out! Another user just bought this account.", alert=True)
        
        phone, sess, c_icon, actual_year, twofa_pass = row

        cur.execute("UPDATE users SET balance = balance - ? WHERE user_id=? AND balance >= ?", (final_price, uid, final_price))
        if cur.rowcount == 0:
            return await event.answer(f"❌ Insufficient Balance! Need ₹{final_price}", alert=True)

        cur.execute("UPDATE stock SET available=0 WHERE phone=?", (phone,))
        db.commit()

    await event.edit(f"{PE_LIGHTNING} <b>Fetching Number (+{phone})...</b>")
    clean_sess = sess if not sess.endswith(".session") else sess[:-8]
    client = TelegramClient(clean_sess, API_ID, API_HASH)
    
    try:
        await client.connect()
        if not await client.is_user_authorized(): raise Exception("Session dead")
    except Exception:
        async with get_user_lock(uid):
            cur.execute("DELETE FROM stock WHERE phone=?", (phone,))
            cur.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (final_price, uid))
            db.commit()
        await client.disconnect()
        delete_session_files(sess)
        return await event.edit(f"{P_NO} <b>Account Invalid.</b> Money refunded. Try buying another.")

    msg = (f"{PE_LIGHTNING} <b>Order Active!</b>\n\n"
           f"{P_PHONE} <b>Phone:</b> <code>{phone}</code>\n"
           f"{P_FLAG} <b>Country:</b> {c_icon} {country}\n\n"
           f"🔻 <b>INSTRUCTIONS:</b>\n"
           f"1. Open Telegram & Add Account\n"
           f"2. Enter the number above.\n"
           f"3. {P_WAIT} <b>Please wait!</b> The bot is actively listening for your OTP and will send it automatically once Telegram delivers it.\n\n"
           f"<i>Note: If no OTP is received within 10 minutes, the bot will auto-cancel and refund your balance automatically.</i>")
    
    sent_msg = await event.edit(msg)
    
    active_orders[phone] = {
        'uid': uid,
        'client': client, 'sess': sess, 'start_time': time.time(), 
        'paid': False, 'price': final_price, 'country': country, 'year': actual_year, 
        'c_icon': c_icon, 'twofa': twofa_pass, 'msg_id': sent_msg.id
    }
    asyncio.create_task(auto_otp_task(phone))

async def auto_otp_task(phone):
    if phone not in active_orders: return
    
    order = active_orders[phone]
    client = order['client']
    start_time = order['start_time']
    uid = order['uid']
    msg_id = order['msg_id']
    
    while time.time() - start_time < AUTO_CANCEL_SECONDS:
        if phone not in active_orders: return 
        try:
            msgs = await client.get_messages(777000, limit=5)
            code = None
            for m in msgs:
                if m.date.timestamp() > start_time - 10: 
                    if m.message and re.search(OTP_REGEX, m.message) and "Login detected" not in m.message:
                        code = re.search(OTP_REGEX, m.message).group()
                        break
            
            if code:
                if not order['paid']:
                    order['paid'] = True
                    async with get_user_lock(uid):
                        cur.execute("INSERT INTO orders (user_id, country, year, price, phone, otp) VALUES (?,?,?,?,?,?)", (uid, order['country'], order['year'], order['price'], phone, code))
                        cur.execute("DELETE FROM stock WHERE phone=?", (phone,))
                        db.commit()
                    
                    await log_primary_purchase(uid, order['country'], order['price'], order['price'], order['year'], 1)
                
                twofa_text = f"{P_2FA} <b>2FA:</b> <code>{order['twofa']}</code>" if order['twofa'] != "None" else f"🔓 <b>2FA:</b> <code>Disabled (No Password)</code>"
                msg_text = (f"{PE_CHECK} <b>Latest OTP Fetched!</b>\n\n"
                            f"{P_PHONE} <b>Phone:</b> <code>{phone}</code>\n"
                            f"{P_FLAG} <b>Country:</b> {order['c_icon']} {order['country']}\n"
                            f"{P_OTP} <b>OTP:</b> <code>{code}</code>\n"
                            f"{twofa_text}")
                
                try: 
                    await bot.edit_message(uid, msg_id, msg_text, buttons=[[Button.inline("🔄 Get OTP Again", f"get_otp_again|{phone}")], [Button.inline("🚪 Finish & Logout", f"logout_bot|{phone}")]])
                except MessageNotModifiedError: pass
                except Exception: 
                    await bot.send_message(uid, msg_text, buttons=[[Button.inline("🔄 Get OTP Again", f"get_otp_again|{phone}")], [Button.inline("🚪 Finish & Logout", f"logout_bot|{phone}")]])
                return 
        except Exception: pass
        await asyncio.sleep(6) 
        
    if phone in active_orders and not active_orders[phone]['paid']:
        order = active_orders.pop(phone)
        try: await order['client'].disconnect()
        except: pass
        
        async with get_user_lock(uid):
            cur.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (order['price'], uid))
            cur.execute("UPDATE stock SET available=1 WHERE phone=?", (phone,))
            db.commit()
            
        try: await bot.edit_message(uid, msg_id, f"{P_TIME} <b>Order Expired!</b>\nThe 10-minute limit for <code>{phone}</code> ran out. Your money ({P_INR}{order['price']}) has been automatically refunded.")
        except: pass

async def init_session_purchase(event, country, year, price_str):
    uid, price = event.sender_id, int(price_str)
    stock_row = cur.execute("SELECT COUNT(*) FROM stock WHERE country_name LIKE ? AND account_year=? AND price=? AND available=1", (f"{country}%", int(year), price)).fetchone()
    stock = stock_row[0] if stock_row else 0
    if stock == 0: return await event.answer("❌ Out of stock!", alert=True)
    
    session_buy_state[uid] = {'country': country, 'year': year, 'price': price, 'stock': stock}
    disc_row = cur.execute("SELECT discount FROM users WHERE user_id=?", (uid,)).fetchone()
    discount = disc_row[0] if disc_row else 0
    p_disp = price if discount == 0 else int(price * (100 - discount) / 100)
    
    msg = (f"{PE_GIFT} <b>Buy {country} ({year}) Sessions</b>\n\n"
           f"{P_MONEY} <b>Price per session:</b> {P_INR}{p_disp}\n"
           f"{P_PKG} <b>Available Stock:</b> {stock}\n\n"
           f"👇 <b>Reply to this message</b> with the <b>Number of Sessions</b> you want to buy.")
    await event.edit(msg, buttons=[[Button.inline("Cancel", "cancel_action")]])

async def process_bulk_sessions(event, uid, qty, state, final_cost):
    country, year, price = state['country'], int(state['year']), int(state['price'])
    await event.respond(f"{PE_LIGHTNING} <b>Processing your sessions...</b>")

    async with get_user_lock(uid):
        rows = cur.execute("SELECT phone, session_file, twofa, account_year FROM stock WHERE country_name LIKE ? AND account_year=? AND price=? AND available=1 LIMIT ?", (f"{country}%", year, price, qty)).fetchall()
        if len(rows) < qty:
            return await event.respond(f"{P_NO} Stock changed during processing. Purchase Cancelled.")
        
        cur.execute("UPDATE users SET balance = balance - ? WHERE user_id=? AND balance >= ?", (final_cost, uid, final_cost))
        if cur.rowcount == 0:
            return await event.respond(f"{P_NO} Insufficient Balance! Purchase Cancelled.")

        phones = [r[0] for r in rows]
        placeholders = ",".join("?" for _ in phones)
        cur.execute(f"UPDATE stock SET available=0 WHERE phone IN ({placeholders})", phones)
        
        price_per_acc = final_cost // qty
        for p in phones:
            cur.execute("INSERT INTO orders (user_id, country, price, phone, otp) VALUES (?,?,?,?,?)", (uid, country, price_per_acc, p, "SESSION_FILES"))
        db.commit()

    zip_name = f"sessions_{uid}_{int(time.time())}.zip"
    numbers_txt = ""

    try:
        with zipfile.ZipFile(zip_name, 'w') as zf:
            for phone, sess_file, twofa_pass, y in rows:
                base_s = sess_file if not sess_file.endswith(".session") else sess_file[:-8]
                for ext in ['.session', '.session-wal', '.session-shm', '.session-journal']:
                    src = base_s + ext
                    if os.path.exists(src): zf.write(src, os.path.basename(src))
                
                pass_text = twofa_pass if twofa_pass != "None" else "No_Password"
                numbers_txt += f"+{phone} | pass:{pass_text}\n"
            
            numbers_txt += "\n\nPurchased from @Freshtgsales\n"
            zf.writestr("numbers.txt", numbers_txt)
            
        caption = f"{PE_GIFT} <b>Bulk Purchase Successful!</b>\n\n{P_FLAG} Country: {country}\n{P_PKG} Quantity: {qty}\n{P_CARD} Total Paid: {P_INR}{final_cost}\n\n<i>(Note: Sessions are safely provided, the bot does not keep them active)</i>"
        await bot.send_file(uid, zip_name, caption=caption)
        await log_primary_purchase(uid, country, price, final_cost, year, qty)
    except Exception as e: await event.respond(f"{P_WARN} Error creating zip: {e}")
    finally:
        if os.path.exists(zip_name): os.remove(zip_name)

# ================= STATS & PROFILE FUNCTIONS =================
async def profile_handler(event):
    uid = event.sender_id
    row = cur.execute("SELECT balance, total_deposited, joined_date, discount FROM users WHERE user_id=?", (uid,)).fetchone()
    if not row: return await bot.send_message(event.chat_id, "⚠️ Error: Please type /start to initialize your account.")
    
    bal, dep, date, discount = row
    ref_count_row = cur.execute("SELECT COUNT(*) FROM users WHERE referred_by=?", (uid,)).fetchone()
    ref_count = ref_count_row[0] if ref_count_row else 0
    me = await bot.get_me()
    bot_username = me.username or ""
    ref_link = f"https://t.me/{bot_username}?start=ref_{uid}" if bot_username else None
    disc_msg = f"\n{P_GIFT} Active Discount: <b>{discount}% OFF</b>" if discount > 0 else ""
    ref_block = (f"{P_USERS} <b>Your Referral Link:</b>\n<code>{ref_link}</code>\n\n"
                 if ref_link else
                 f"{P_USERS} <b>Referral Link:</b>\n<i>Set a public bot username to enable referrals.</i>\n\n")
    
    msg = (f"{PE_KISS} <b>USER PROFILE</b>\n\n"
           f"{P_ID} User ID: <code>{uid}</code>\n"
           f"{P_MONEY} Balance: <code>${to_usd(bal):.2f} (₹{bal})</code>\n"
           f"{P_CARD} Deposited: <code>${to_usd(dep):.2f} (₹{dep})</code>{disc_msg}\n"
           f"{P_USERS} Referred Users: <b>{ref_count}</b>\n"
           f"{P_CAL} Joined: {date[:10]}\n\n"
           f"{ref_block}"
           f"<i>(Share this link with your friends to earn bonuses!)</i>")
    await bot.send_message(event.chat_id, msg)

async def stats_handler(event, is_callback=False):
    uid = event.sender_id
    row = cur.execute("SELECT total_deposited FROM users WHERE user_id=?", (uid,)).fetchone()
    if not row: return
    dep = row[0]
    o_row = cur.execute("SELECT COUNT(*), SUM(price) FROM orders WHERE user_id=?", (uid,)).fetchone()
    total_orders = o_row[0] if o_row else 0
    spent = o_row[1] if o_row and o_row[1] else 0
    ref_row = cur.execute("SELECT COUNT(*) FROM users WHERE referred_by=?", (uid,)).fetchone()
    ref_count = ref_row[0] if ref_row else 0
    
    msg = (f"{PE_CROWN} <b>My Statistics</b>\n\n"
           f"{P_CART} <b>Accounts Bought:</b> {total_orders}\n"
           f"{P_USERS} <b>Referrals:</b> {ref_count}\n"
           f"{P_MONEY} <b>Total Spent:</b>\n${to_usd(spent):.2f}\n"
           f"{P_CARD} <b>Total Deposited:</b>\n${to_usd(dep):.2f}")
    
    btns = [[Button.inline("View Purchase Logs", "page_purchases_1")], [Button.inline("Referral Logs", "view_referrals")]]
    if is_callback:
        try: await event.edit(msg, buttons=btns)
        except MessageNotModifiedError: pass
    else: await bot.send_message(event.chat_id, msg, buttons=btns)

async def send_purchase_page(event, uid, page):
    limit = 5
    offset = (page - 1) * limit
    t_row = cur.execute("SELECT COUNT(*) FROM orders WHERE user_id=?", (uid,)).fetchone()
    total = t_row[0] if t_row else 0
    rows = cur.execute("SELECT phone, date FROM orders WHERE user_id=? ORDER BY id DESC LIMIT ? OFFSET ?", (uid, limit, offset)).fetchall()
    
    msg = f"{PE_FLOWER} <b>Purchase History</b>\nPage {page}\n\n"
    if not rows: msg += "No purchases found."
    else:
        for ph, d in rows:
            try:
                dt = datetime.strptime(d, "%Y-%m-%d %H:%M:%S")
                d_str = dt.strftime("%a %b %d %H:%M:%S %Y")
            except:
                d_str = d
            msg += f"{P_PHONE} {ph}\n{P_CAL} {d_str}\n────────────────\n"
            
    nav = []
    if page > 1: nav.append(Button.inline("Prev", f"page_purchases_{page-1}"))
    nav.append(Button.inline("Back", "back_to_stats"))
    if offset + limit < total: nav.append(Button.inline("Next", f"page_purchases_{page+1}"))
    await event.edit(msg, buttons=[nav])

async def view_referrals(event):
    refs = cur.execute("SELECT user_id FROM users WHERE referred_by=?", (event.sender_id,)).fetchall()
    await event.answer(f"👥 You have referred {len(refs)} user(s).", alert=True)

# ================= ADMIN ACTIONS =================
async def admin_panel_handler(event):
    uid = event.sender_id
    if not is_admin(uid): return
    
    status_text = "🟢 Bot is ON" if is_bot_online() else "🔴 Bot is OFF"
    total_users = cur.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    total_stock = cur.execute("SELECT COUNT(*) FROM stock WHERE available=1").fetchone()[0]
    pending_deposits = cur.execute("SELECT COUNT(*) FROM deposits WHERE status='pending'").fetchone()[0]
    btns = []
    
    if uid == ADMIN_ID or has_perm(uid, 'p_settings'):
        btns.append([Button.inline(f"Status: {status_text}", "adm_togglebot")])
        
    r1 = []
    if uid == ADMIN_ID or has_perm(uid, 'p_add_stock'):
        r1.extend([Button.inline("Add Single Acc", "adm_addstock"), Button.inline("Add ZIP", "adm_addzip")])
    if r1: btns.append(r1)

    r2 = []
    if uid == ADMIN_ID or has_perm(uid, 'p_manage_stock'):
        r2.extend([Button.inline("Manage Stock", "adm_managestock"), Button.inline("Auto Price", "adm_autoprice")])
    if r2: btns.append(r2)

    r3 = []
    if uid == ADMIN_ID or has_perm(uid, 'p_stats'):
        r3.extend([Button.inline("Statistics", "adm_stats"), Button.inline("Broadcast", "adm_bcast")])
        r3.append(Button.inline("User Info", "adm_userinfo"))
    if r3: btns.append(r3)

    r4 = []
    if uid == ADMIN_ID or has_perm(uid, 'p_bal'):
        r4.extend([Button.inline("Change Balance", "adm_bal"), Button.inline("Ban User", "adm_ban")])
    if r4: btns.append(r4)

    r5 = []
    if uid == ADMIN_ID or has_perm(uid, 'p_settings'):
        r5.extend([Button.inline("Discount", "adm_discount"), Button.inline("Ref %", "adm_refpct")])
        btns.append(r5)
        btns.append([Button.inline("Support URL", "adm_supporturl"), Button.inline("Payments", "adm_payments")])
        btns.append([Button.inline("Set USDT Rate", "adm_usdtrate")])
        btns.append([Button.inline("Backup Users", "adm_backupusr"), Button.inline("Restore Users", "adm_restoreusr")])

    if uid == ADMIN_ID:
        btns.append([Button.inline("Manage Admins", "adm_manageadmins")])

    header = (f"{PE_CROWN} <b>ADVANCED ADMIN DASHBOARD</b>\n\n"
              f"{P_USERS} Users: <b>{total_users}</b>\n"
              f"{P_PKG} Available Stock: <b>{total_stock}</b>\n"
              f"{P_WAIT} Pending Deposits: <b>{pending_deposits}</b>")
    await bot.send_message(event.chat_id, header, buttons=btns)

async def manage_admins_menu(event):
    rows = cur.execute("SELECT user_id FROM admins").fetchall()
    msg = f"{PE_CROWN} <b>Manage Sub-Admins</b>\n\n"
    for r in rows: msg += f"{P_ACC} <code>{r[0]}</code>\n"
    btns = [[Button.inline("Add Admin", "adm_addadmin"), Button.inline("Edit Admin", "adm_editadminreq")],
            [Button.inline("Back", "adm_adminmain")]]
    await event.edit(msg, buttons=btns)

async def edit_admin_menu(event, target_id):
    row = cur.execute("SELECT p_add_stock, p_manage_stock, p_stats, p_bal, p_settings FROM admins WHERE user_id=?", (target_id,)).fetchone()
    if not row: return await event.answer("Admin not found", alert=True)
    p = ["✅" if x==1 else "❌" for x in row]
    
    btns = [
        [Button.inline(f"Add Stock: {p[0]}", f"adm_tglperm|{target_id}|p_add_stock")],
        [Button.inline(f"Manage Stock: {p[1]}", f"adm_tglperm|{target_id}|p_manage_stock")],
        [Button.inline(f"Stats & Bcast: {p[2]}", f"adm_tglperm|{target_id}|p_stats")],
        [Button.inline(f"Bal & Users: {p[3]}", f"adm_tglperm|{target_id}|p_bal")],
        [Button.inline(f"Settings: {p[4]}", f"adm_tglperm|{target_id}|p_settings")],
        [Button.inline("Remove Admin", f"adm_deladmin|{target_id}")],
        [Button.inline("Back", "adm_manageadmins")]
    ]
    await event.edit(f"✏️ <b>Editing Admin:</b> <code>{target_id}</code>", buttons=btns)

async def send_manage_stock_page(event, page):
    limit = 10
    offset = (page - 1) * limit
    rows = cur.execute("SELECT DISTINCT country_name FROM stock ORDER BY country_name").fetchall()
    total = len(rows)
    countries = rows[offset:offset+limit]
    
    btns = []
    for (c,) in countries: 
        flag = get_flag_by_country_name(c)
        btns.append([Button.inline(f"{flag} {c}", f"adm_msc|{c}")])
    
    nav = []
    if page > 1: nav.append(Button.inline("Prev", f"adm_mspg|{page-1}"))
    if offset + limit < total: nav.append(Button.inline("Next", f"adm_mspg|{page+1}"))
    if nav: btns.append(nav)
    btns.append([Button.inline("Back", "adm_adminmain")])
    await event.edit(f"{PE_LOCATION} <b>Manage Stock</b> (Page {page})\nSelect a country to edit its properties:", buttons=btns)

async def send_manage_stock_country(event, c_name):
    years = cur.execute("SELECT DISTINCT account_year FROM stock WHERE country_name=? ORDER BY account_year DESC", (c_name,)).fetchall()
    flag = get_flag_by_country_name(c_name)
    btns = [
        [Button.inline("Edit Country Name", f"adm_msedit|name|{c_name}"), Button.inline("Edit Flag", f"adm_msedit|flag|{c_name}")],
        [Button.inline("Edit Common Price (All Years)", f"adm_msedit|cprice|{c_name}")]
    ]
    y_btns = []
    for (y,) in years: y_btns.append(Button.inline(f"{y}", f"adm_msedit|yprice|{c_name}|{y}"))
    
    for i in range(0, len(y_btns), 3): btns.append(y_btns[i:i+3])
    btns.append([Button.inline("Back", "adm_mspg|1")])
    await event.edit(f"{flag} <b>Managing: {c_name}</b>\nSelect an option to edit:", buttons=btns)

async def send_autoprice_page(event, page):
    limit = 10
    offset = (page - 1) * limit
    c_list = set([c[0] for c in COUNTRY_CODES.values()])
    db_countries = cur.execute("SELECT DISTINCT country_name FROM stock").fetchall()
    for (c,) in db_countries: c_list.add(c)
    
    custom_countries = cur.execute("SELECT DISTINCT name FROM custom_countries").fetchall()
    for (c,) in custom_countries: c_list.add(c)

    c_list = sorted(list(c_list))
    total = len(c_list)
    countries = c_list[offset:offset+limit]
    
    btns = []
    for c in countries: 
        flag = get_flag_by_country_name(c)
        btns.append([Button.inline(f"{flag} {c}", f"adm_apc|{c}")])
        
    nav = []
    if page > 1: nav.append(Button.inline("Prev", f"adm_appg|{page-1}"))
    if offset + limit < total: nav.append(Button.inline("Next", f"adm_appg|{page+1}"))
    if nav: btns.append(nav)
    btns.append([Button.inline("Add Custom Country", "adm_ap_add_country")])
    btns.append([Button.inline("Back", "adm_adminmain")])
    await event.edit(f"{PE_LIGHTNING} <b>Auto Price Setup</b> (Page {page})\nSelect a country to set fixed prices:", buttons=btns)

async def send_autoprice_country(event, c_name):
    flag = get_flag_by_country_name(c_name)
    btns = [[Button.inline("Set Common Price", f"adm_apset|{c_name}|Common")]]
    y_btns = []
    for y in range(2024, 1999, -1): y_btns.append(Button.inline(f"{y}", f"adm_apset|{c_name}|{y}"))
    for i in range(0, len(y_btns), 4): btns.append(y_btns[i:i+4])
    btns.append([Button.inline("Back", "adm_appg|1")])
    await event.edit(f"{flag} <b>Auto Price: {c_name}</b>\nSelect 'Common' for default price, or specific years:", buttons=btns)

async def admin_actions(event):
    data_full = event.data.decode()
    if not data_full.startswith("adm_"): return
    uid = event.sender_id
    action_data = data_full[4:]
    chat = event.chat_id
    
    if action_data == "adminmain":
        await event.delete()
        class FakeEvent: chat_id = chat; sender_id = uid
        return await admin_panel_handler(FakeEvent())

    if action_data == "togglebot" and has_perm(uid, 'p_settings'):
        new_status = 'off' if is_bot_online() else 'on'
        cur.execute("UPDATE settings SET value=? WHERE key='bot_status'", (new_status,))
        db.commit()
        await event.answer(f"Bot turned {new_status.upper()}", alert=True)
        class FakeEvent: chat_id = chat; sender_id = uid
        await admin_panel_handler(FakeEvent())
        await event.delete()
        return

    elif action_data == "stats" and has_perm(uid, 'p_stats'):
        u_row = cur.execute("SELECT COUNT(*) FROM users").fetchone()
        u = u_row[0] if u_row else 0
        s_row = cur.execute("SELECT COUNT(*) FROM stock WHERE available=1").fetchone()
        s = s_row[0] if s_row else 0
        r_row = cur.execute("SELECT value FROM settings WHERE key='upi_revenue'").fetchone()
        r = r_row[0] if r_row else "0"
        bal_row = cur.execute("SELECT SUM(balance) FROM users").fetchone()
        total_bal = bal_row[0] if bal_row and bal_row[0] else 0
        o_row = cur.execute("SELECT COUNT(*), SUM(price) FROM orders").fetchone()
        total_orders = o_row[0] if o_row else 0
        total_spent = o_row[1] if o_row and o_row[1] else 0
        
        msg = (f"{P_STATS} <b>ADVANCED STATS</b>\n\n{P_USERS} <b>Total Users:</b> {u}\n{P_PKG} <b>Accounts in Stock:</b> {s}\n"
               f"{P_MONEY} <b>Total UPI Revenue:</b> {P_INR}{r}\n\n{P_CARD} <b>Overall Users Balance:</b> {P_INR}{total_bal}\n"
               f"{P_CART} <b>Total Accounts Sold:</b> {total_orders}\n{P_USDT} <b>Overall Sales Amount:</b> {P_INR}{total_spent}")
        return await event.edit(msg, buttons=[[Button.inline("Back", "adm_adminmain")]])

    elif action_data == "payments" and has_perm(uid, 'p_settings'):
        btns = [
            [Button.inline("Add Payment Method", "adm_addpay")],
            [Button.inline("Remove Payment Method", "adm_delpay")],
            [Button.inline("Back to Admin", "adm_adminmain")]
        ]
        return await event.edit(f"{P_CARD} <b>Manage Payment Methods</b>", buttons=btns)

    elif action_data == "manageadmins" and uid == ADMIN_ID:
        return await manage_admins_menu(event)

    elif action_data.startswith("tglperm|") and uid == ADMIN_ID:
        _, t_id, p_name = action_data.split("|")
        cur.execute(f"UPDATE admins SET {p_name} = CASE WHEN {p_name}=1 THEN 0 ELSE 1 END WHERE user_id=?", (t_id,))
        db.commit()
        return await edit_admin_menu(event, t_id)
        
    elif action_data.startswith("deladmin|") and uid == ADMIN_ID:
        t_id = action_data.split("|")[1]
        cur.execute("DELETE FROM admins WHERE user_id=?", (t_id,))
        db.commit()
        await event.answer("✅ Admin Removed", alert=True)
        return await manage_admins_menu(event)

    elif action_data == "managestock" and has_perm(uid, 'p_manage_stock'): return await send_manage_stock_page(event, 1)
    elif action_data.startswith("mspg|") and has_perm(uid, 'p_manage_stock'): return await send_manage_stock_page(event, int(action_data.split("|")[1]))
    elif action_data.startswith("msc|") and has_perm(uid, 'p_manage_stock'): return await send_manage_stock_country(event, action_data.split("|")[1])
    elif action_data == "autoprice" and has_perm(uid, 'p_manage_stock'): return await send_autoprice_page(event, 1)
    elif action_data.startswith("appg|") and has_perm(uid, 'p_manage_stock'): return await send_autoprice_page(event, int(action_data.split("|")[1]))
    elif action_data.startswith("apc|") and has_perm(uid, 'p_manage_stock'): return await send_autoprice_country(event, action_data.split("|")[1])
        
    elif action_data == "backupusr" and has_perm(uid, 'p_settings'):
        cur.execute("SELECT * FROM users")
        with open("users_backup.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f); w.writerow([i[0] for i in cur.description]); w.writerows(cur.fetchall())
        await bot.send_file(chat, "users_backup.csv", caption=f"{P_USERS} <b>Users Backup CSV</b>")
        os.remove("users_backup.csv")
        return await event.answer("✅ Backup Generated!", alert=True)

    async with bot.conversation(chat, timeout=600) as conv:
        async def get_reply(txt):
            await conv.send_message(txt + "\n\n<i>(Type /cancel to abort)</i>")
            resp = await conv.get_response()
            if resp.text == "/cancel": raise ValueError("Cancelled")
            return resp

        try:
            if action_data == "ap_add_country" and has_perm(uid, 'p_manage_stock'):
                code = (await get_reply(f"{P_PHONE} <b>Enter Country Calling Code (without +):</b>\n<i>Example: 91</i>")).text.replace("+", "").strip()
                flag = html.escape((await get_reply(f"{P_FLAG} <b>Enter Country Flag Emoji:</b>\n<i>Example: 🇮🇳</i>")).text.strip())
                name = html.escape((await get_reply(f"{P_GLOBE} <b>Enter Country Name:</b>\n<i>Example: India</i>")).text.strip())
                
                cur.execute("INSERT OR REPLACE INTO custom_countries (code, name, flag) VALUES (?,?,?)", (code, name, flag))
                db.commit()
                await conv.send_message(f"{P_YES} <b>Custom Country Added Successfully!</b>\n{flag} {name} (+{code})\n\n<i>It will now automatically be recognized when adding stock!</i>")

            elif action_data == "userinfo" and has_perm(uid, 'p_stats'):
                t_uid = int((await get_reply(f"{P_ACC} <b>Enter User ID:</b>")).text)
                u_row = cur.execute("SELECT balance, total_deposited, joined_date, banned, discount FROM users WHERE user_id=?", (t_uid,)).fetchone()
                if not u_row: return await conv.send_message(f"{P_NO} User not found.")
                
                o_row = cur.execute("SELECT COUNT(*), SUM(price) FROM orders WHERE user_id=?", (t_uid,)).fetchone()
                up_row = cur.execute("SELECT SUM(amount) FROM upi_orders WHERE user_id=? AND status='success'", (t_uid,)).fetchone()
                
                bal, dep, joined, is_banned, disc = u_row
                o_count = o_row[0] if o_row else 0
                o_spent = o_row[1] if o_row and o_row[1] else 0
                u_upi = up_row[0] if up_row and up_row[0] else 0
                
                msg = (f"{P_ACC} <b>USER INFO:</b> <code>{t_uid}</code>\n\n"
                       f"{P_MONEY} Balance: {P_INR}{bal}\n"
                       f"{P_CARD} Total Deposited: {P_INR}{dep}\n"
                       f"{P_UPI} UPI Deposited: {P_INR}{u_upi}\n"
                       f"{P_CART} Total Orders: {o_count}\n"
                       f"{P_USDT} Total Spent: {P_INR}{o_spent}\n"
                       f"{P_GIFT} Discount: {disc}%\n"
                       f"{P_CAL} Joined: {joined}\n"
                       f"{P_OFF} Banned: {'Yes' if is_banned else 'No'}")
                await conv.send_message(msg)

            elif action_data == "addadmin" and uid == ADMIN_ID:
                new_ad = int((await get_reply(f"{P_ACC} <b>Enter User ID for new Admin:</b>")).text)
                cur.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (new_ad,))
                db.commit()
                await conv.send_message(f"{P_YES} Admin added!")
                class FakeEvent: 
                    async def edit(self, text, buttons): await bot.send_message(chat, text, buttons=buttons)
                    async def answer(self, txt, alert): pass
                await edit_admin_menu(FakeEvent(), new_ad)
                
            elif action_data == "editadminreq" and uid == ADMIN_ID:
                t_id = int((await get_reply(f"{P_ACC} <b>Enter User ID to edit:</b>")).text)
                class FakeEvent: 
                    async def edit(self, text, buttons): await bot.send_message(chat, text, buttons=buttons)
                    async def answer(self, txt, alert): pass
                await edit_admin_menu(FakeEvent(), t_id)

            elif action_data.startswith("msedit|") and has_perm(uid, 'p_manage_stock'):
                parts = action_data.split("|")
                action, c_name = parts[1], parts[2]
                
                if action == "name":
                    new_name = html.escape((await get_reply(f"{P_DOC} <b>Enter NEW Name for {c_name}:</b>")).text)
                    cur.execute("UPDATE stock SET country_name=? WHERE country_name=?", (new_name, c_name))
                    cur.execute("UPDATE auto_prices SET country=? WHERE country=?", (new_name, c_name))
                    db.commit()
                    await conv.send_message(f"{P_YES} Country '{c_name}' successfully renamed to '{new_name}'!")
                    
                elif action == "flag":
                    new_flag = html.escape((await get_reply(f"{P_FLAG} <b>Enter NEW Flag Emoji for {c_name}:</b>")).text)
                    cur.execute("UPDATE stock SET country_icon=? WHERE country_name=?", (new_flag, c_name))
                    db.commit()
                    await conv.send_message(f"{P_YES} Flag updated to {new_flag} for '{c_name}'!")
                    
                elif action == "cprice":
                    new_p = int((await get_reply(f"{P_MONEY} <b>Enter NEW Common Price for all {c_name} accounts:</b>")).text)
                    cur.execute("UPDATE stock SET price=? WHERE country_name=?", (new_p, c_name))
                    db.commit()
                    await conv.send_message(f"{P_YES} All existing '{c_name}' accounts updated to {P_INR}{new_p}!")
                    
                elif action == "yprice":
                    year = parts[3]
                    new_p = int((await get_reply(f"{P_MONEY} <b>Enter NEW Price for {c_name} ({year}):</b>")).text)
                    cur.execute("UPDATE stock SET price=? WHERE country_name=? AND account_year=?", (new_p, c_name, year))
                    db.commit()
                    await conv.send_message(f"{P_YES} All existing '{c_name}' ({year}) accounts updated to {P_INR}{new_p}!")
                    
            elif action_data.startswith("apset|") and has_perm(uid, 'p_manage_stock'):
                parts = action_data.split("|")
                c_name, year = parts[1], parts[2]
                new_p = int((await get_reply(f"{P_ASST} <b>Enter Auto-Price for {c_name} ({year}):</b>\n<i>(Enter 0 to remove this auto-price)</i>")).text)
                if new_p == 0:
                    cur.execute("DELETE FROM auto_prices WHERE country=? AND year=?", (c_name, year))
                    await conv.send_message(f"{P_YES} Auto-Price for {c_name} ({year}) removed!")
                else:
                    cur.execute("INSERT OR REPLACE INTO auto_prices (country, year, price) VALUES (?,?,?)", (c_name, year, new_p))
                    await conv.send_message(f"{P_YES} Auto-Price for {c_name} ({year}) set to {P_INR}{new_p}! Incoming accounts will use this price automatically.")
                db.commit()

            elif action_data == "addpay" and has_perm(uid, 'p_settings'):
                name = html.escape((await get_reply(f"{P_CARD} <b>Enter Payment Method Name:</b>\n<i>(e.g., Binance Pay, TRX)</i>")).text)
                qr_msg = await get_reply(f"📸 <b>Send QR Code Image:</b>\n<i>(Or type <code>skip</code> if no QR needed)</i>")
                qr_path = ""
                if qr_msg.photo:
                    qr_path = f"qr_{int(time.time())}.jpg"
                    await bot.download_media(qr_msg, qr_path)
                
                cap_msg = (await get_reply(f"{P_DOC} <b>Enter Payment Caption:</b>\n<i>(Use <code>text</code> to make wallet IDs or UPI copyable)</i>")).text
                cap_msg = html.escape(cap_msg).replace("&lt;code&gt;", "<code>").replace("&lt;/code&gt;", "</code>")
                cur.execute("INSERT INTO custom_payments (name, caption, qr_file_id) VALUES (?,?,?)", (name, cap_msg, qr_path))
                db.commit()
                await conv.send_message(f"{P_YES} Payment Method '{name}' added successfully!")

            elif action_data == "delpay" and has_perm(uid, 'p_settings'):
                rows = cur.execute("SELECT id, name FROM custom_payments").fetchall()
                if not rows: return await conv.send_message(f"{P_NO} No custom payment methods.")
                msg = f"{P_DOC} <b>Reply with the ID of the method to delete:</b>\n\n"
                for r in rows: msg += f"ID: {r[0]} - {r[1]}\n"
                del_id = (await get_reply(msg)).text
                try:
                    del_id = int(del_id)
                    file_path = cur.execute("SELECT qr_file_id FROM custom_payments WHERE id=?", (del_id,)).fetchone()
                    if file_path and file_path[0] and os.path.exists(file_path[0]): os.remove(file_path[0])
                    cur.execute("DELETE FROM custom_payments WHERE id=?", (del_id,))
                    db.commit()
                    await conv.send_message(f"{P_YES} Deleted!")
                except: await conv.send_message(f"{P_NO} Invalid ID.")

            elif action_data == "addzip" and has_perm(uid, 'p_add_stock'):
                resp = await get_reply(f"{P_PKG} <b>Send the ZIP file containing <code>.session</code> files:</b>")
                if not resp.file or not resp.file.name.endswith('.zip'): return await conv.send_message(f"{P_NO} Invalid file.")
                
                await conv.send_message(f"{P_WAIT} <b>Extracting & Scanning Accounts...</b>")
                zip_path = await bot.download_media(resp, "temp_sessions.zip")
                extracted_dir = f"temp_extracted_{int(time.time())}"
                os.makedirs(extracted_dir, exist_ok=True)
                with zipfile.ZipFile(zip_path, 'r') as zip_ref: zip_ref.extractall(extracted_dir)

                groups = {}
                for file in os.listdir(extracted_dir):
                    if not file.endswith(".session"): continue
                    sess_path = os.path.join(extracted_dir, file)
                    clean_path = sess_path[:-8]
                    try:
                        client = TelegramClient(clean_path, API_ID, API_HASH)
                        await client.connect()
                        if not await client.is_user_authorized(): await client.disconnect(); continue
                        me = await client.get_me()
                        phone = getattr(me, 'phone', None)
                        if not phone: await client.disconnect(); continue
                        
                        c_name, c_icon = get_country_info(phone)
                        pwd = await client(GetPasswordRequest())
                        has_2fa = pwd.has_password
                        year = await detect_account_year(client)
                        await client.disconnect()

                        key = (c_name, year, has_2fa)
                        if key not in groups: groups[key] = []
                        groups[key].append({"phone": phone, "path": clean_path, "c_icon": c_icon})
                    except Exception as e: logger.error(f"Scan error: {e}")

                for key in list(groups.keys()):
                    if key[0] == "Unknown":
                        sample_phone = groups[key][0]["phone"]
                        await conv.send_message(f"{P_WARN} <b>Country not recognized for +{sample_phone}!</b>")
                        new_icon = html.escape((await get_reply(f"{P_FLAG} <b>Enter Country Flag Emoji:</b>\n<i>Example: 🇮🇳</i>")).text)
                        new_name = html.escape((await get_reply(f"{P_GLOBE} <b>Enter Country Name:</b>\n<i>Example: India</i>")).text)
                        new_key = (new_name, key[1], key[2])
                        groups[new_key] = groups.pop(key)
                        for acc in groups[new_key]: acc["c_icon"] = new_icon

                success = 0
                for (c_name, year, has_2fa), accs in groups.items():
                    c_icon = accs[0]["c_icon"]
                    twofa_pass = "None"
                    if has_2fa: twofa_pass = html.escape((await get_reply(f"{P_2FA} <b>Enter 2FA Password for {len(accs)}x {c_name} accounts:</b>")).text)

                    auto_row = cur.execute("SELECT price FROM auto_prices WHERE country=? AND year=?", (c_name, str(year))).fetchone()
                    if not auto_row: auto_row = cur.execute("SELECT price FROM auto_prices WHERE country=? AND year='Common'", (c_name,)).fetchone()

                    if auto_row:
                        price = auto_row[0]
                        await conv.send_message(f"⚡ <b>Auto-Price Applied:</b> {len(accs)}x {c_name} ({year}) at {P_INR}{price}.")
                    else:
                        existing_price = cur.execute("SELECT price FROM stock WHERE country_name=? LIMIT 1", (c_name,)).fetchone()
                        if existing_price:
                            price = existing_price[0]
                            await conv.send_message(f"⚡ <b>Auto-Added:</b> {len(accs)}x {c_name} at {P_INR}{price} (Copied from DB).")
                        else:
                            price = int((await get_reply(f"📌 Found {len(accs)}x {c_name} ({year}).\n{P_MONEY} Enter Price (₹):")).text)

                    for acc in accs:
                        perm_base = f"sessions/{acc['phone']}"
                        for ext in ['.session', '.session-wal', '.session-shm', '.session-journal']:
                            if os.path.exists(acc['path'] + ext): shutil.move(acc['path'] + ext, perm_base + ext)
                        cur.execute("INSERT OR REPLACE INTO stock (phone, session_file, country_name, country_icon, account_year, category, price, available, twofa) VALUES (?,?,?,?,?,?,?,?,?)", 
                                    (acc['phone'], perm_base + ".session", c_name, c_icon, year, 'Good', price, 1, twofa_pass))
                        success += 1
                db.commit()
                os.remove(zip_path); shutil.rmtree(extracted_dir)
                await conv.send_message(f"{P_YES} <b>Bulk Interactive Upload Complete!</b>\n{P_ON} Added: {success}")

            elif action_data == "addstock" and has_perm(uid, 'p_add_stock'):
                phone = (await get_reply(f"{P_PHONE} Enter Phone (+919999...):")).text.replace(" ", "").replace("+", "")
                sp = f"sessions/{phone}"
                client = TelegramClient(sp, API_ID, API_HASH)
                await client.connect()
                sreq = await client.send_code_request(phone)
                
                twofa_pass = "None"
                try: 
                    await client.sign_in(phone, (await get_reply(f"{P_OTP} OTP:")).text, phone_code_hash=sreq.phone_code_hash)
                except SessionPasswordNeededError: 
                    twofa_pass = html.escape((await get_reply(f"{P_2FA} 2FA Pass required. Enter it now:")).text)
                    await client.sign_in(password=twofa_pass)
                
                c_name, c_icon = get_country_info(phone)
                
                if c_name == "Unknown":
                    await conv.send_message(f"{P_WARN} <b>Country not recognized for +{phone}!</b>")
                    c_icon = html.escape((await get_reply(f"{P_FLAG} <b>Enter Country Flag Emoji:</b>\n<i>Example: 🇮🇳</i>")).text)
                    c_name = html.escape((await get_reply(f"{P_GLOBE} <b>Enter Country Name:</b>\n<i>Example: India</i>")).text)
                
                auto_year = await detect_account_year(client)
                await client.disconnect()
                
                year = int((await get_reply(f"{P_CAL} Detected Year: <b>{auto_year}</b>\nReply with Year to confirm or change:")).text)
                auto_row = cur.execute("SELECT price FROM auto_prices WHERE country=? AND year=?", (c_name, str(year))).fetchone()
                if not auto_row: auto_row = cur.execute("SELECT price FROM auto_prices WHERE country=? AND year='Common'", (c_name,)).fetchone()

                if auto_row:
                    price = auto_row[0]
                    await conv.send_message(f"⚡ <b>Auto-Price Applied:</b> {P_INR}{price} for {c_name} ({year})")
                else:
                    existing_price = cur.execute("SELECT price FROM stock WHERE country_name=? LIMIT 1", (c_name,)).fetchone()
                    if existing_price:
                        price = existing_price[0]
                        await conv.send_message(f"⚡ <b>Auto-detected Price:</b> {P_INR}{price} for {c_name}")
                    else: price = int((await get_reply(f"{P_MONEY} Price (₹):")).text)
                
                cur.execute("INSERT OR REPLACE INTO stock (phone, session_file, country_name, country_icon, account_year, category, price, available, twofa) VALUES (?,?,?,?,?,?,?,?,?)", 
                            (phone, sp + ".session", c_name, c_icon, year, 'Good', price, 1, twofa_pass))
                db.commit()
                await conv.send_message(f"{P_YES} Added!")

            elif action_data == "supporturl" and has_perm(uid, 'p_settings'):
                url = (await get_reply("🔗 Enter new Support URL (must start with http:// or https://):")).text
                if not url.startswith("http"): url = "https://" + url.replace("@", "t.me/")
                cur.execute("UPDATE settings SET value=? WHERE key='support_url'", (url,))
                db.commit()
                await conv.send_message(f"{P_YES} Support URL updated.")

            elif action_data == "bcast" and has_perm(uid, 'p_stats'):
                txt = (await get_reply(f"{P_DOC} <b>Message (Supports HTML & tg-emoji tags):</b>")).text
                btn_name = (await get_reply(f"🔘 <b>Button Name (or 'skip'):</b>")).text
                url = (await get_reply("🔗 <b>URL:</b>")).text if btn_name.lower() != 'skip' else None
                btns = [[Button.url(btn_name, url)]] if url else None
                users = cur.execute("SELECT user_id FROM users").fetchall()
                s, f = 0, 0
                await conv.send_message(f"{P_TG} Broadcasting...")
                for (u_id,) in users:
                    try: 
                        await bot.send_message(int(u_id), txt, buttons=btns, parse_mode='html')
                        s += 1
                    except: f += 1
                    await asyncio.sleep(0.1) 
                await conv.send_message(f"{P_YES} Done! Sent: {s} | Failed: {f}")

            elif action_data == "bal" and has_perm(uid, 'p_bal'):
                t_uid = int((await get_reply(f"{P_ACC} <b>User ID:</b>")).text)
                amt = int((await get_reply(f"{P_MONEY} <b>Amount (Negative to deduct):</b>")).text)
                update_balance(t_uid, amt)
                await conv.send_message(f"{P_YES} Added {P_INR}{amt} to {t_uid}.")
                
            elif action_data == "discount" and has_perm(uid, 'p_settings'):
                t_uid = int((await get_reply(f"{P_ACC} <b>User ID:</b>")).text)
                pct = int((await get_reply(f"{P_GIFT} <b>Discount % (0 to remove):</b>")).text)
                cur.execute("UPDATE users SET discount=? WHERE user_id=?", (pct, t_uid))
                db.commit()
                await conv.send_message(f"{P_YES} User {t_uid} has {pct}% discount.")
                
            elif action_data == "refpct" and has_perm(uid, 'p_settings'):
                pct = int((await get_reply(f"{P_USERS} <b>New Referral %:</b>")).text)
                cur.execute("UPDATE settings SET value=? WHERE key='ref_percent'", (str(pct),))
                db.commit()
                await conv.send_message(f"{P_YES} Ref revenue set to {pct}%.")

            elif action_data == "usdtrate" and has_perm(uid, 'p_settings'):
                r = float((await get_reply(f"{P_USDT} <b>New USDT Rate (INR):</b>")).text)
                cur.execute("UPDATE settings SET value=? WHERE key='usdt_rate'", (str(r),))
                db.commit()
                await conv.send_message(f"{P_YES} Rate set to {r}.")

            elif action_data == "restoreusr" and has_perm(uid, 'p_settings'):
                resp = await get_reply(f"📤 <b>Send the <code>users_backup.csv</code> file:</b>")
                if not resp.file or not resp.file.name.endswith('.csv'): return await conv.send_message(f"{P_NO} Invalid file.")
                await bot.download_media(resp, "temp_restore.csv")
                with open("temp_restore.csv", "r", encoding="utf-8") as f:
                    reader = csv.reader(f); next(reader); count = 0
                    for row in reader:
                        try:
                            cur.execute("INSERT OR REPLACE INTO users (user_id, balance, referred_by, total_deposited, joined_date, banned, discount, terms_accepted) VALUES (?,?,?,?,?,?,?,?)", 
                                        (int(row[0]), int(row[1]), row[2] if row[2] else None, int(row[3]), row[4], int(row[5]), int(row[6]), int(row[7])))
                            count += 1
                        except: pass
                db.commit()
                os.remove("temp_restore.csv")
                await conv.send_message(f"{P_YES} Restored {count} users.")

            elif action_data == "ban" and has_perm(uid, 'p_bal'):
                t_uid = int((await get_reply(f"{P_ACC} <b>User ID:</b>")).text)
                is_ban = cur.execute("SELECT banned FROM users WHERE user_id=?", (t_uid,)).fetchone()
                if not is_ban: return await conv.send_message(f"{P_NO} User not found.")
                ns = 0 if is_ban[0] == 1 else 1
                cur.execute("UPDATE users SET banned=? WHERE user_id=?", (ns, t_uid))
                db.commit()
                await conv.send_message(f"User {t_uid} is {'Banned 🚫' if ns == 1 else 'Unbanned ✅'}.")

        except ValueError: await conv.send_message(f"{P_NO} Cancelled.")
        except Exception as e: await conv.send_message(f"{P_NO} Error: {e}")

# ================= CORE EVENT ROUTERS =================
@bot.on(events.NewMessage(pattern=r"(?i)^/start"))
async def handle_start(e):
    try:
        uid = e.sender_id
        if not uid: return
        
        ensure_user(uid)
        if is_user_banned(uid): return

        if not is_bot_online() and not is_admin(uid):
            return await e.respond(f"{P_OFF} <b>Bot is currently under maintenance.</b> Please try again later.")
        
        session_buy_state.pop(uid, None)
        deposit_input.pop(uid, None)

        text = e.text or ''
        if len(text.split()) > 1:
            start_param = text.split()[1]
            if start_param.startswith("ref_"):
                ref = start_param.replace("ref_", "")
                if ref.isdigit() and int(ref) != uid:
                    cur.execute("UPDATE users SET referred_by=? WHERE user_id=? AND referred_by IS NULL", (int(ref), uid))
                    db.commit()

        is_joined = await check_channel_joined(uid)
        if not is_joined:
            msg = f"{PE_FLOWER} <b>You must join our channels first!</b>\n{PE_LOCATION} Join all required channels and then tap <b>Verify Joined</b>."
            return await e.respond(msg, buttons=get_join_buttons())

        row = cur.execute("SELECT terms_accepted FROM users WHERE user_id=?", (uid,)).fetchone()
        terms_acc = row[0] if row else 0
        if not terms_acc:
            msg = f"{PE_FLOWER} <b>TERMS & CONDITIONS</b>\nPlease read and accept our Terms & Conditions before using the bot."
            return await e.respond(msg, buttons=get_terms_buttons())

        await send_main_menu(e, uid)
    except Exception as ex: 
        print(f"Start Error: {ex}")

@bot.on(events.NewMessage())
async def handle_all_messages(e):
    try:
        uid = e.sender_id
        if not uid: return
        if getattr(e, 'text', None) and e.text.startswith('/'): return
        if not is_bot_online() and not is_admin(uid):
            return await e.respond(f"{P_OFF} <b>Bot is currently under maintenance.</b> Please try again later.")
        
        ensure_user(uid)
        if is_user_banned(uid): return

        if uid in waiting_proof and (e.photo or (e.text and "http" in e.text)):
            info = waiting_proof.pop(uid)
            final_amt = info['amount']
            if info['method'] == "Cwallet": final_amt = int(final_amt * 1.05)
            
            cur.execute("INSERT INTO deposits (user_id, amount, method_name, status) VALUES (?,?,?,?)", (uid, final_amt, info['method'], "pending"))
            db.commit()
            dep_id = cur.lastrowid
            await e.reply(f"{PE_GIFT} Deposit request submitted! Please wait for admin approval.")
            cap = f"{PE_LIGHTNING} <b>NEW DEPOSIT REQUEST</b>\n{P_ACC} User: <code>{uid}</code>\n{P_MONEY} Request: <b>{P_INR}{info['amount']}</b>\n{P_CARD} Method: {info['method']}\n{P_ID} Ref: <code>{dep_id}</code>"
            btns = [[Button.inline(f"✅ Accept (₹{final_amt})", f"dep_acc|{dep_id}|{uid}|{info['method']}|exact|{final_amt}"), Button.inline("❌ Reject", f"dep_rej|{dep_id}|{uid}")],
                    [Button.inline("📝 Custom Amount", f"dep_acc|{dep_id}|{uid}|{info['method']}|custom|0")]]
            
            try:
                if e.photo: await bot.send_message(LOG_CHANNEL_ID, cap, file=e.media, buttons=btns)
                else: await bot.send_message(LOG_CHANNEL_ID, cap + f"\n🔗 Hash: {html.escape(e.text)}", buttons=btns)
            except Exception as log_err:
                try:
                    if e.photo: await bot.send_message(ADMIN_ID, f"⚠️ <b>LOG CHANNEL ERROR</b>\n\n{cap}", file=e.media, buttons=btns)
                    else: await bot.send_message(ADMIN_ID, f"⚠️ <b>LOG CHANNEL ERROR</b>\n\n{cap}\n🔗 Hash: {html.escape(e.text)}", buttons=btns)
                except Exception as admin_err:
                    logger.error(f"Failed to log deposit: {admin_err}")
            return

        text = e.text or ""
        if not text: return

        if "Buy Account" in text or "Buy Sessions" in text or "Deposit" in text or "My Profile" in text or "My Stats" in text or "Support" in text or "Admin Panel" in text:
            session_buy_state.pop(uid, None)
            deposit_input.pop(uid, None)
            admin_dep_state.pop(uid, None)

        if is_admin(uid) and uid in admin_dep_state:
            st = admin_dep_state[uid]
            if st['step'] == 'wait_reason':
                t_uid, dep_id, msg_id = st['target_uid'], st['dep_id'], st['msg_id']
                cur.execute("UPDATE deposits SET status='rejected' WHERE id=?", (dep_id,))
                db.commit()
                
                try: await bot.edit_message(LOG_CHANNEL_ID, msg_id, f"{P_NO} <b>REJECTED USER {t_uid}</b>\nReason: {html.escape(text)}")
                except: pass
                
                await bot.send_message(int(t_uid), f"{P_NO} <b>Deposit Rejected!</b>\n📋 Reason: {html.escape(text)}")
                await e.reply(f"{P_YES} Rejection reason sent.")
                admin_dep_state.pop(uid)
                return

        if uid in session_buy_state:
            state = session_buy_state[uid]
            try:
                qty = int(re.sub(r'[^\d]', '', text))
                if qty < 1: raise ValueError
                if qty > state['stock']: return await e.respond(f"{P_WARN} <b>Not enough stock!</b> Max is {state['stock']}.")
                
                disc_row = cur.execute("SELECT discount FROM users WHERE user_id=?", (uid,)).fetchone()
                discount = disc_row[0] if disc_row else 0
                total_cost = qty * state['price']
                if discount > 0: total_cost = int(total_cost * (100 - discount) / 100)
                    
                bal_row = cur.execute("SELECT balance FROM users WHERE user_id=?", (uid,)).fetchone()
                user_bal = bal_row[0] if bal_row else 0
                if user_bal < total_cost: return await e.respond(f"{P_NO} <b>Insufficient Balance!</b>\nYou need {P_INR}{total_cost} to buy {qty} sessions.")

                session_buy_state.pop(uid)
                await process_bulk_sessions(e, uid, qty, state, total_cost)
                return
            except ValueError: return await e.respond(f"{P_NO} Please enter a valid number.")

        if uid in deposit_input and deposit_input[uid]['step'] == 'wait_amt':
            try:
                amt = int(re.sub(r'[^\d]', '', text))
                if amt < 10: return await e.reply(f"{P_WARN} Minimum Deposit is ₹10.")
                method = deposit_input[uid]['method']
                waiting_proof[uid] = {'amount': amt, 'method': method}
                deposit_input.pop(uid)
                
                rate = get_usdt_rate()
                usdt_amt = round(amt / rate, 2)
                rate_text = f"\n\n{P_MONEY} <b>Amount to Pay:</b> {P_INR}{amt} (~{P_USDT}{usdt_amt} USDT)\n💱 <i>Exchange Rate: {P_INR}{rate} = $1</i>"
                
                if method == "Cwallet":
                    msg = (f"{P_CARD} <b>Method:</b> {method}\n\n🚀 <b>Address / ID:</b>\n<code>{CWALLET_ID}</code>"
                           f"{rate_text}\n\n👉 <b>Send Proof:</b>\nPlease send the Transaction Hash (Link) or a Screenshot of the payment now.")
                    try:
                        await bot.send_file(uid, CWALLET_QR, caption=msg, buttons=[[Button.inline("❌ Cancel", "cancel_action")]])
                    except Exception:
                        await bot.send_message(uid, msg + f"\n\n🔗 QR Link: {CWALLET_QR}", buttons=[[Button.inline("❌ Cancel", "cancel_action")]])
                else:
                    row = cur.execute("SELECT caption, qr_file_id FROM custom_payments WHERE name=?", (method,)).fetchone()
                    if row:
                        cap = row[0] + f"{rate_text}\n\n👇 <b>After paying, send a clear Screenshot here:</b>"
                        btns = [[Button.inline("❌ Cancel", "cancel_action")]]
                        if row[1] and os.path.exists(row[1]): 
                            try: await bot.send_file(e.chat_id, row[1], caption=cap, buttons=btns)
                            except: await e.reply(cap, buttons=btns)
                        else: await e.reply(cap, buttons=btns)
                    else: await e.reply(f"{P_CARD} <b>{method} Deposit</b>{rate_text}\n\n👇 Send Screenshot here:", buttons=[[Button.inline("❌ Cancel", "cancel_action")]])
            except ValueError: await e.respond(f"{P_NO} Please enter a valid number in {P_INR} (INR).")
            return

        if "Buy Account" in text: await show_countries(e, 'single', 1)
        elif "Buy Sessions" in text: await show_countries(e, 'bulk', 1)
        elif "Deposit" in text: await deposit_menu(e)
        elif "My Profile" in text: await profile_handler(e)
        elif "My Stats" in text: await stats_handler(e)
        elif "Support" in text: 
            await e.reply(f"{PE_ANGEL} <b>Fresh Tg Support & Relevant Information</b>\n\n{P_WARN} For support contact admin or use the buttons below.", buttons=get_support_buttons())
        elif "Admin Panel" in text: 
            if is_admin(uid): await admin_panel_handler(e)

    except Exception as ex: print(f"Message Error: {ex}")

@bot.on(events.CallbackQuery)
async def handle_callback_query(e):
    try:
        uid = e.sender_id
        if not is_bot_online() and not is_admin(uid):
            return await e.answer("⚙️ Bot is under maintenance.", alert=True)
            
        ensure_user(uid)
        now = time.time()
        if uid in user_spam_cooldown and now - user_spam_cooldown[uid] < 0.5:
            return await e.answer("⚠️ Please slow down! Don't spam buttons.", alert=True)
        user_spam_cooldown[uid] = now

        if is_user_banned(uid): return await e.answer("🚫 BANNED", alert=True)
        data = e.data.decode()

        if data == "verify_join":
            if not await check_channel_joined(uid): return await e.answer("⚠️ You must join the channels first!", alert=True)
            row = cur.execute("SELECT terms_accepted FROM users WHERE user_id=?", (uid,)).fetchone()
            terms = row[0] if row else 0
            if not terms:
                msg = f"{PE_FLOWER} <b>TERMS & CONDITIONS</b>\nPlease read and accept our Terms & Conditions before using the bot."
                try: await e.edit(msg, buttons=get_terms_buttons())
                except MessageNotModifiedError: pass
                return
            await send_main_menu(e, uid)

        elif data == "tc_accept":
            cur.execute("UPDATE users SET terms_accepted=1 WHERE user_id=?", (uid,))
            db.commit()
            await e.answer("✅ Terms Accepted!", alert=True)
            await send_main_menu(e, uid)
            
        elif data == "tc_reject":
            try: await e.edit(f"{P_NO} You cannot use the bot without accepting the terms.")
            except MessageNotModifiedError: pass
            
        elif data == "cancel_action":
            deposit_input.pop(uid, None); waiting_proof.pop(uid, None); session_buy_state.pop(uid, None)
            try: await e.edit(f"{P_NO} <b>Cancelled.</b>")
            except MessageNotModifiedError: pass

        elif data.startswith("pg_c|"): 
            p = data.split("|")
            await show_countries(e, p[1], int(p[2]))

        elif data.startswith("bc|"):
            p = data.split("|")
            await show_years(e, p[1], p[2])

        elif data.startswith("by|"):
            p = data.split("|")
            if p[1] == 'single': await confirm_purchase(e, p[2], p[3], p[4])
            else: await init_session_purchase(e, p[2], p[3], p[4])
            
        elif data.startswith("buy_cf|"):
            p = data.split("|")
            await process_purchase(e, p[1], p[2], p[3])

        elif data.startswith("get_otp_again|"):
            phone = data.split("|")[1]
            if phone not in active_orders:
                return await e.answer("⚠️ Session already logged out or expired.", alert=True)
            
            order = active_orders[phone]
            client = order['client']
            start_time = order['start_time']
            
            await e.answer("🔄 Fetching latest OTP...", alert=False)
            try:
                msgs = await client.get_messages(777000, limit=5)
                latest_code = None
                for m in msgs:
                    if m.date.timestamp() > start_time - 10:
                        if m.message and re.search(OTP_REGEX, m.message) and "Login detected" not in m.message:
                            latest_code = re.search(OTP_REGEX, m.message).group()
                            break
                
                if latest_code:
                    twofa_text = f"{P_2FA} <b>2FA:</b> <code>{order['twofa']}</code>" if order['twofa'] != "None" else f"🔓 <b>2FA:</b> <code>Disabled (No Password)</code>"
                    msg = (f"{P_YES} <b>Latest OTP Fetched!</b>\n\n"
                           f"{P_PHONE} <b>Phone:</b> <code>{phone}</code>\n"
                           f"{P_FLAG} <b>Country:</b> {order['c_icon']} {order['country']}\n"
                           f"{P_OTP} <b>OTP:</b> <code>{latest_code}</code>\n"
                           f"{twofa_text}")
                    try: await e.edit(msg, buttons=[[Button.inline("🔄 Get OTP Again", f"get_otp_again|{phone}")], [Button.inline("🚪 Finish & Logout", f"logout_bot|{phone}")]])
                    except MessageNotModifiedError: pass
                else:
                    await e.answer("⏳ No new OTP found yet. Try again in a few seconds.", alert=True)
            except Exception as ex:
                await e.answer(f"❌ Error fetching OTP.", alert=True)

        elif data.startswith("logout_bot|"):
            phone = data.split("|")[1]
            if phone in active_orders:
                order = active_orders.pop(phone)
                try: await order['client'].log_out()
                except: pass
                try: await order['client'].disconnect()
                except: pass
                delete_session_files(order['sess'])
                await e.edit(f"{P_YES} <b>Session Finished & Logged out successfully.</b>")
            else:
                await e.answer("⚠️ No active order found or already logged out.", alert=True)
        
        elif data.startswith("page_purchases_"): await send_purchase_page(e, uid, int(data.split("_")[2]))
        elif data == "back_to_stats": await stats_handler(e, is_callback=True)
        elif data == "view_referrals": await view_referrals(e)
            
        elif data.startswith("depm_"): await manual_deposit_init(e, data.replace("depm_", ""))
        elif data == "dep_upi": await init_upi_keypad(e)
        elif data.startswith("kp_"): await keypad_logic(e)
        elif data.startswith("submit_utr_"): await verify_upi_payment(e, data.replace("submit_utr_", ""))
        
        elif data.startswith("adm_") and is_admin(uid): await admin_actions(e)
        
        elif data.startswith("dkp|") and has_perm(uid, 'p_bal'):
            _, dep_id, action = data.split("|")
            dep_id = int(dep_id)
            row = cur.execute("SELECT user_id, method_name, status, amount FROM deposits WHERE id=?", (dep_id,)).fetchone()
            if not row or row[2] != 'pending': return await e.edit(f"{P_WARN} Already processed.")
            t_uid, method, orig_amt = row[0], row[1], row[3]
            
            curr = custom_dep_amt.get(dep_id, "0")
            
            if action.isdigit():
                if curr == "0": curr = action
                else: curr += action
                if len(curr) > 7: curr = curr[:7]
            elif action == "del": curr = curr[:-1] or "0"
            elif action == "cancel":
                btns = [[Button.inline(f"✅ Accept (₹{orig_amt})", f"dep_acc|{dep_id}|{t_uid}|{method}|exact|{orig_amt}"), Button.inline("❌ Reject", f"dep_rej|{dep_id}|{t_uid}")],
                        [Button.inline("📝 Custom Amount", f"dep_acc|{dep_id}|{t_uid}|{method}|custom|0")]]
                return await e.edit(f"{PE_LIGHTNING} <b>NEW DEPOSIT REQUEST</b>\n{P_ACC} User: <code>{t_uid}</code>\n{P_MONEY} Request: <b>{P_INR}{orig_amt}</b>\n{P_CARD} Method: {method}\n{P_ID} Ref: <code>{dep_id}</code>", buttons=btns)
            elif action == "conf":
                amt = int(curr)
                if amt <= 0: return await e.answer("Amount must be > 0", alert=True)
                
                async with get_user_lock(t_uid):
                    prev_row = cur.execute("SELECT balance FROM users WHERE user_id=?", (t_uid,)).fetchone()
                    prev_bal = prev_row[0] if prev_row else 0
                    update_balance(t_uid, amt)
                    cur.execute("UPDATE deposits SET status='approved', amount=? WHERE id=?", (amt, dep_id))
                    cur.execute("UPDATE users SET total_deposited = total_deposited + ? WHERE user_id=?", (amt, t_uid))
                    db.commit()
                    
                await process_referral_bonus(t_uid, amt)
                await e.edit(f"{PE_CHECK} <b>APPROVED {P_INR}{amt} TO {t_uid} (Custom Amount)</b>")
                await bot.send_message(int(t_uid), f"{PE_CHECK} <b>Deposit Approved!</b>\n{P_MONEY} Amount Added: {P_INR}{amt}\n📉 Old: {P_INR}{prev_bal} | 📈 New: {P_INR}{prev_bal+amt}")
                return

            custom_dep_amt[dep_id] = curr
            await e.edit(f"{P_KEY} <b>Enter Custom Amount for User {t_uid}:</b>\n\n{P_MONEY} {curr}", buttons=get_admin_custom_keypad(dep_id))

        elif data.startswith("dep_acc|") and has_perm(uid, 'p_bal'):
            p = data.split("|")
            dep_id, t_uid, method, a_type = p[1], int(p[2]), p[3], p[4]
            row = cur.execute("SELECT status FROM deposits WHERE id=?", (dep_id,)).fetchone()
            if not row or row[0] != 'pending': return await e.edit(f"{P_WARN} Already processed.")
            
            if a_type == "exact":
                amt = int(p[5]) 
                async with get_user_lock(t_uid):
                    prev_row = cur.execute("SELECT balance FROM users WHERE user_id=?", (t_uid,)).fetchone()
                    prev_bal = prev_row[0] if prev_row else 0
                    update_balance(t_uid, amt)
                    
                    cur.execute("UPDATE deposits SET status='approved', amount=? WHERE id=?", (amt, dep_id))
                    cur.execute("UPDATE users SET total_deposited = total_deposited + ? WHERE user_id=?", (amt, t_uid))
                    db.commit()
                
                await process_referral_bonus(t_uid, amt)
                
                user_msg = (f"{PE_CHECK} <b>Deposit Approved!</b>\n\n{P_MONEY} <b>Amount Added:</b> ${to_usd(amt):.2f} ({P_INR}{amt})\n"
                            f"📉 <b>Previous Balance:</b> ${to_usd(prev_bal):.2f} ({P_INR}{prev_bal})\n📈 <b>New Balance:</b> ${to_usd(prev_bal+amt):.2f} ({P_INR}{prev_bal+amt})")
                await bot.send_message(int(t_uid), user_msg)
                try: await e.edit(f"{PE_CHECK} <b>INSTANT CREDITED {P_INR}{amt} TO {t_uid}</b>")
                except MessageNotModifiedError: pass
                
            elif a_type == "custom":
                custom_dep_amt[int(dep_id)] = "0"
                await e.edit(f"{P_KEY} <b>Enter Custom Amount for User {t_uid}:</b>\n\n{P_MONEY} 0", buttons=get_admin_custom_keypad(int(dep_id)))
                
        elif data.startswith("dep_rej|") and has_perm(uid, 'p_bal'):
            p = data.split("|")
            dep_id, t_uid = p[1], int(p[2])
            row = cur.execute("SELECT status FROM deposits WHERE id=?", (dep_id,)).fetchone()
            if not row or row[0] != 'pending': return await e.edit(f"{P_WARN} Already processed.")
            admin_dep_state[uid] = {'target_uid': t_uid, 'dep_id': dep_id, 'step': 'wait_reason', 'msg_id': e.message.id}
            await bot.send_message(uid, f"{P_WARN} Reply to this message with the REASON for rejecting user <code>{t_uid}</code>:")
            try: await e.answer("Check your bot PMs to enter the reason.", alert=True)
            except: pass

    except Exception as ex: print(f"Callback Error: {ex}")

async def main():
    print("✅ ULTIMATE ADVANCED HTML BOT STARTED SUCCESSFULLY")
    await bot.run_until_disconnected()

if __name__ == '__main__':
    validate_config()
    bot.start(bot_token=BOT_TOKEN)
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
