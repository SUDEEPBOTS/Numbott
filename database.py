import sqlite3
import os
from config import ADMIN_ID

# Initialize DB
db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "otp_bot_final.db")
db = sqlite3.connect(db_path, check_same_thread=False, timeout=20)
db.execute("PRAGMA journal_mode=WAL;")
cur = db.cursor()

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

def get_bot_mode():
    res = cur.execute("SELECT value FROM settings WHERE key='bot_mode'").fetchone()
    if res and res[0] in ('manual', 'panel', 'hybrid'):
        return res[0]
    return os.getenv("BOT_MODE", "manual").strip().lower()

def set_bot_mode(mode):
    cur.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('bot_mode', ?)", (mode,))
    db.commit()

def get_lzt_key():
    res = cur.execute("SELECT value FROM settings WHERE key='lzt_api_key'").fetchone()
    if res and res[0]:
        return res[0].strip()
    return os.getenv("LZT_API_KEY", "").strip()

def set_lzt_key(key):
    cur.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('lzt_api_key', ?)", (key.strip(),))
    db.commit()

def get_rub_rate():
    res = cur.execute("SELECT value FROM settings WHERE key='rub_rate'").fetchone()
    if res and res[0]:
        try: return float(res[0])
        except: pass
    try: return float(os.getenv("RUB_RATE", "1.15"))
    except: return 1.15

def set_rub_rate(rate):
    cur.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('rub_rate', ?)", (str(rate),))
    db.commit()

def get_lzt_margin():
    res = cur.execute("SELECT value FROM settings WHERE key='lzt_margin'").fetchone()
    if res and res[0]:
        try: return float(res[0])
        except: pass
    try: return float(os.getenv("LZT_MARGIN", "25.0"))
    except: return 25.0

def set_lzt_margin(margin):
    cur.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('lzt_margin', ?)", (str(margin),))
    db.commit()

def get_panel_price(country, year, lzt_price_rub=0, mode='bulk'):
    # 1. Check if admin has set explicit custom price in auto_prices table for this specific (country, year)
    row = cur.execute("SELECT price FROM auto_prices WHERE country=? AND year=?", (country, str(year))).fetchone()
    if row and row[0] and row[0] > 0:
        base = int(row[0])
        if mode == 'spam':
            return max(int(base * 0.7), 15)
        return base
    
    # 2. Get base country price (set with year='Common' or 'ALL')
    row_all = cur.execute("SELECT price FROM auto_prices WHERE country=? AND year IN ('Common', 'ALL')", (country,)).fetchone()
    base_price = int(row_all[0]) if (row_all and row_all[0] and row_all[0] > 0) else None

    # Aged year price additions (if no explicit year price is set)
    YEAR_ADDITIONS = {
        2026: 0,
        2025: 25,
        2024: 55,
        2023: 85,
        2022: 125,
        2021: 175,
        2020: 230,
        2019: 290,
        2018: 350,
        2017: 420
    }

    try: y_int = int(year)
    except: y_int = 2026

    if base_price is not None:
        add_amount = YEAR_ADDITIONS.get(y_int, 0 if y_int >= 2026 else (2026 - y_int) * 60)
        total = base_price + add_amount
        if mode == 'spam':
            return max(int(total * 0.7), 15)
        return total
        
    # 3. Dynamic calculation from LZT RUB price if no base price is found
    rub_rate = get_rub_rate()
    margin = get_lzt_margin()
    inr_cost = lzt_price_rub * rub_rate
    calculated = round(inr_cost + margin)
    final_p = max(int(calculated), 25)
    if mode == 'spam':
        return max(int(final_p * 0.7), 15)
    elif mode == 'premium':
        return final_p + 150
    return final_p

def get_fsub_status():
    res = cur.execute("SELECT value FROM settings WHERE key='fsub_status'").fetchone()
    return res[0].strip().lower() if res and res[0] else 'on'

def set_fsub_status(status):
    cur.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('fsub_status', ?)", (str(status).strip().lower(),))
    db.commit()

def get_fsub_channels():
    res = cur.execute("SELECT value FROM settings WHERE key='fsub_channels'").fetchone()
    if res and res[0] is not None:
        val = res[0].strip()
        if not val: return []
        return [c.strip() for c in val.split(",") if c.strip()]
    raw = os.getenv("CHECK_CHANNELS", "")
    return [c.strip() for c in raw.split(",") if c.strip()]

def get_fsub_urls():
    res = cur.execute("SELECT value FROM settings WHERE key='fsub_urls'").fetchone()
    if res and res[0] is not None:
        val = res[0].strip()
        if not val: return []
        return [u.strip() for u in val.split(",") if u.strip()]
    raw = os.getenv("JOIN_URLS", "")
    return [u.strip() for u in raw.split(",") if u.strip()]

def set_fsub_data(channels_list, urls_list):
    ch_str = ",".join([str(c).strip() for c in channels_list if str(c).strip()])
    url_str = ",".join([str(u).strip() for u in urls_list if str(u).strip()])
    cur.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('fsub_channels', ?)", (ch_str,))
    cur.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('fsub_urls', ?)", (url_str,))
    db.commit()

def add_fsub_channel(channel_id, join_url):
    chs = get_fsub_channels()
    urls = get_fsub_urls()
    chs.append(str(channel_id).strip())
    urls.append(str(join_url).strip())
    set_fsub_data(chs, urls)

def remove_fsub_channel(index):
    chs = get_fsub_channels()
    urls = get_fsub_urls()
    if 0 <= index < len(chs):
        chs.pop(index)
        if index < len(urls):
            urls.pop(index)
        set_fsub_data(chs, urls)

def get_log_channels_db():
    res = cur.execute("SELECT value FROM settings WHERE key='log_channels'").fetchone()
    if res and res[0] is not None:
        val = res[0].strip()
        if not val: return []
        out = []
        for c in val.split(","):
            c = c.strip()
            if c:
                try: out.append(int(c))
                except: out.append(c)
        return out
    from config import LOG_CHANNELS
    return LOG_CHANNELS

def set_log_channels_db(channels_list):
    ch_str = ",".join([str(c).strip() for c in channels_list if str(c).strip()])
    cur.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('log_channels', ?)", (ch_str,))
    db.commit()

def add_log_channel_db(channel_id):
    chs = get_log_channels_db()
    c_str = str(channel_id).strip()
    try: val = int(c_str)
    except: val = c_str
    if val not in chs:
        chs.append(val)
        set_log_channels_db(chs)

def remove_log_channel_db(channel_id):
    chs = get_log_channels_db()
    c_str = str(channel_id).strip()
    chs = [c for c in chs if str(c) != c_str]
    set_log_channels_db(chs)


