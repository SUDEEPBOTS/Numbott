import os
import asyncio
import time
import zipfile
import re
from telethon import events, Button, TelegramClient, types
from telethon.errors import (
    MessageNotModifiedError, PhoneNumberInvalidError, PhoneNumberOccupiedError,
    PhoneCodeInvalidError, PhoneCodeExpiredError,
    FreshChangePhoneForbiddenError, FloodWaitError
)
from telethon.tl.functions.account import SendChangePhoneCodeRequest, ChangePhoneRequest
from database import cur, db, get_flag_by_country_name, get_bot_mode, get_panel_price, get_lzt_key
from config import (
    PE_LOCATION, PE_GIFT, PE_LIGHTNING, PE_CHECK, P_MONEY, P_PKG, P_CARD, P_WARN,
    P_NO, P_YES, P_INR, P_TIME, P_FLAG, P_OTP, P_2FA, P_PHONE, AUTO_CANCEL_SECONDS,
    OTP_REGEX, bot, logger, API_ID, API_HASH
)
from utils.keyboards import style_btn
from utils.states import active_orders, session_buy_state, get_user_lock
from utils.lzt import lzt_client, COUNTRY_TO_LZT

search_state = {}
change_number_state = {}

def get_active_order_card(order, phone, is_admin_user=False):
    msg = (f"<blockquote expandable>{PE_LIGHTNING} <b>𝐎ʀᴅᴇʀ 𝐀ᴄᴛɪᴠᴇ!</b>\n\n"
           f"{P_PHONE} <b>𝐏ʜᴏɴᴇ:</b> <code>+{phone}</code>\n"
           f"{P_FLAG} <b>𝐂ᴏᴜɴᴛʀʏ:</b> {order['c_icon']} {order['country']}\n"
           f"🔐 <b>2𝐅𝐀 𝐏ᴀssᴡᴏʀᴅ:</b> <code>{order['twofa']}</code>\n\n"
           f"🔻 <b>𝐈ɴsᴛʀᴜᴄᴛɪᴏɴs:</b>\n"
           f"1. 𝐎ᴘᴇɴ 𝐓ᴇʟᴇɢʀᴀᴍ & 𝐀ᴅᴅ 𝐀ᴄᴄᴏᴜɴᴛ (<code>+{phone}</code>).\n"
           f"2. ⏳ <b>𝐏ʟᴇᴀsᴇ ᴡᴀɪᴛ!</b> 𝐓ʜᴇ ʙᴏᴛ ɪs ᴀᴄᴛɪᴠᴇʟʏ ʟɪsᴛᴇɴɪɴɢ ғᴏʀ ʏᴏᴜʀ 𝐎𝐓𝐏.\n\n"
           f"<i>💡 𝐘ᴏᴜ ᴄᴀɴ ᴀʟsᴏ ᴛᴀᴘ '🔄 𝐂ʜᴀɴɢᴇ ᴛᴏ 𝐌ʏ 𝐍ᴜᴍʙᴇʀ' ᴛᴏ ᴍɪɢʀᴀᴛᴇ ᴛʜɪs ᴀᴄᴄᴏᴜɴᴛ ᴅɪʀᴇᴄᴛʟʏ ᴛᴏ ʏᴏᴜʀ ᴘᴇʀsᴏɴᴀʟ ɴᴜᴍʙᴇʀ!</i></blockquote>")
    
    btns = [
        [style_btn("🔄 𝐂ʜᴀɴɢᴇ ᴛᴏ 𝐌ʏ 𝐍ᴜᴍʙᴇʀ", f"chg_num|{phone}", "success", icon=5409320020058584473)],
        [
            style_btn("🔄 𝐆ᴇᴛ 𝐎𝐓𝐏 𝐀ɢᴀɪɴ", f"get_otp_again|{phone}", "primary", icon=5408995930416362034),
            style_btn("✅ 𝐅ɪɴɪsʜ 𝐎ʀᴅᴇʀ", f"finish_order|{phone}", "primary", icon=5409320020058584473)
        ]
    ]
    if is_admin_user:
        btns.append([style_btn("❌ [Admin] Cancel & Refund", f"cancel_order|{phone}", "danger", icon=6129888444245089008)])
    return msg, btns

async def get_countries_list():
    """Retrieve available countries based on bot_mode."""
    bot_mode = get_bot_mode()
    
    # 1. Manual Mode: only local stock
    if bot_mode == 'manual':
        rows = cur.execute("SELECT country_name, COUNT(*) FROM stock WHERE available=1 GROUP BY country_name").fetchall()
        return sorted(rows, key=lambda x: x[0])

    # 2. Panel Mode: all supported countries from catalog
    if bot_mode == 'panel':
        all_c = set(COUNTRY_TO_LZT.keys())
        try:
            customs = cur.execute("SELECT name FROM custom_countries").fetchall()
            for (c,) in customs: all_c.add(c)
        except: pass
        return sorted([(c_name, '40+') for c_name in all_c], key=lambda x: x[0])

    # 3. Hybrid Mode: local stock with count + other catalog countries
    all_c = set(COUNTRY_TO_LZT.keys())
    try:
        customs = cur.execute("SELECT name FROM custom_countries").fetchall()
        for (c,) in customs: all_c.add(c)
    except: pass
    
    country_dict = {c_name: '40+' for c_name in all_c}
    local_rows = cur.execute("SELECT country_name, COUNT(*) FROM stock WHERE available=1 GROUP BY country_name").fetchall()
    for c_name, count in local_rows:
        country_dict[c_name] = count

    return sorted(country_dict.items(), key=lambda x: x[0])

YEAR_BADGES = {
    2026: "✨ 2026 (Fresh)",
    2025: "🥉 2025 (1 Year Old)",
    2024: "🥈 2024 (2 Years Old)",
    2023: "🥇 2023 (3 Years Old)",
    2022: "💎 2022 (4 Years Old)",
    2021: "👑 2021 (5 Years Old)",
    2020: "🔥 2020 (6 Years Old)",
    2019: "⚡ 2019 & Older (Vintage)"
}

search_state = {}

async def search_countries_matching(query):
    import html
    from database import COUNTRY_CODES, get_flag_by_country_name
    from utils.lzt import get_lzt_code
    query_clean = query.strip().lower()
    dial_code = re.sub(r'[^\d]', '', query_clean)
    all_countries = await get_countries_list()
    
    matches = []
    for c_name, count in all_countries:
        if query_clean in c_name.lower():
            matches.append((c_name, count))
            continue
        if dial_code:
            for code, (name, _) in COUNTRY_CODES.items():
                if name == c_name and dial_code == code:
                    matches.append((c_name, count))
        lzt_code = get_lzt_code(c_name)
        if lzt_code and query_clean == lzt_code.lower():
            matches.append((c_name, count))
            continue
    return matches

FILTERS_LIST = [
    ("stars", "⭐ 𝐓ᴇʟᴇɢʀᴀᴍ 𝐒ᴛᴀʀs (𝐁ᴀʟᴀɴᴄᴇ)", 5409320020058584473),
    ("premium", "👑 𝐓ᴇʟᴇɢʀᴀᴍ 𝐏ʀᴇᴍɪᴜᴍ", 5408995930416362034),
    ("no_email", "🚫 𝐍ᴏ 𝐄ᴍᴀɪʟ 𝐁ᴏᴜɴᴅ (𝐃ɪʀᴇᴄᴛ 𝐎𝐓𝐏)", 5409320020058584473),
    ("with_email", "📧 𝐄ᴍᴀɪʟ 𝐁ᴏᴜɴᴅ (𝐖ɪᴛʜ 𝐌ᴀɪʟ)", 5408995930416362034),
    ("no_2fa", "🔓 𝐍ᴏ 2𝐅𝐀 (1-𝐂ʟɪᴄᴋ 𝐋ᴏɢɪɴ)", 5409320020058584473),
    ("with_2fa", "🔒 2𝐅𝐀 𝐄ɴᴀʙʟᴇᴅ (𝐏ᴀss 𝐈ɴᴄʟᴜᴅᴇᴅ)", 5408995930416362034),
    ("dc5", "🌐 𝐃𝐂 5 (𝐀sɪᴀ / 𝐈ɴᴅɪᴀ 𝐏ɪɴɢ)", 5409320020058584473),
    ("aged", "🏛️ 𝐀ɢᴇᴅ / 𝐎ʟᴅ 𝐀ᴄᴄᴏᴜɴᴛs", 5408995930416362034),
]

FILTER_BADGES = {
    "stars": "⭐ 𝐓ᴇʟᴇɢʀᴀᴍ 𝐒ᴛᴀʀs",
    "premium": "👑 𝐓ᴇʟᴇɢʀᴀᴍ 𝐏ʀᴇᴍɪᴜᴍ",
    "no_email": "🚫 𝐍ᴏ 𝐄ᴍᴀɪʟ 𝐁ᴏᴜɴᴅ (𝐃ɪʀᴇᴄᴛ 𝐎𝐓𝐏)",
    "with_email": "📧 𝐄ᴍᴀɪʟ 𝐁ᴏᴜɴᴅ (𝐖ɪᴛʜ 𝐌ᴀɪʟ)",
    "nonspam": "🟢 𝐍ᴏɴ-𝐒ᴘᴀᴍ (100% 𝐂ʟᴇᴀɴ)",
    "spam": "🟡 𝐒ᴘᴀᴍ / 𝐔sᴇᴅ (𝐂ʜᴇᴀᴘ)",
    "no_2fa": "🔓 𝐍ᴏ 2𝐅𝐀 (1-𝐂ʟɪᴄᴋ 𝐋ᴏɢɪɴ)",
    "with_2fa": "🔒 2𝐅𝐀 𝐄ɴᴀʙʟᴇᴅ (𝐏ᴀss 𝐈ɴᴄʟᴜᴅᴇᴅ)",
    "dc5": "🌐 𝐃𝐂 5 (𝐀sɪᴀ)",
    "aged": "🏛️ 𝐀ɢᴇᴅ / 𝐎ʟᴅ",
    "bulk": "🌍 𝐒ᴛᴀɴᴅᴀʀᴅ"
}

async def show_filters_catalog(event, page=1):
    limit = 4
    offset = (page - 1) * limit
    items = FILTERS_LIST[offset:offset+limit]
    total = len(FILTERS_LIST)
    total_pages = (total + limit - 1) // limit

    msg = (f"<blockquote>🎯 <b>𝐒ᴇʟᴇᴄᴛ ᴀɴ 𝐀ᴄᴄᴏᴜɴᴛ 𝐅ɪʟᴛᴇʀ:</b> (𝐏ᴀɢᴇ {page}/{total_pages})\n\n"
           f"<i>𝐂ʜᴏᴏsᴇ ᴀ sᴘᴇᴄɪғɪᴄ ᴀᴄᴄᴏᴜɴᴛ ᴛʏᴘᴇ ʙᴇʟᴏᴡ ᴛᴏ ʙʀᴏᴡsᴇ ᴄᴏᴜɴᴛʀɪᴇs:</i></blockquote>")
    
    btns = []
    for f_id, label, icon in items:
        if f_id == "aged":
            btns.append([style_btn(label, b"by_years_menu", "primary", icon=icon)])
        else:
            btns.append([style_btn(label, f"pg_c|{f_id}|1", "primary", icon=icon)])

    nav = []
    if page > 1: nav.append(style_btn("⬅️ 𝐏ʀᴇᴠ", f"pg_filters|{page-1}", "primary", icon=6129627894349045589))
    if offset + limit < total: nav.append(style_btn("𝐍ᴇxᴛ ➡️", f"pg_filters|{page+1}", "primary", icon=6129732880529628243))
    if nav: btns.append(nav)

    btns.append([style_btn("🔙 𝐁ᴀᴄᴋ ᴛᴏ 𝐌ᴇɴᴜ", b"buy_menu_main", "danger", icon=6129812419028982717)])

    if isinstance(event, events.CallbackQuery.Event):
        try: await event.edit(msg, buttons=btns)
        except MessageNotModifiedError: pass
    else:
        await event.respond(msg, buttons=btns)

async def show_buy_menu(event):
    msg = (f"<blockquote>{PE_GIFT} <b>𝐒ᴇʟᴇᴄᴛ 𝐀ᴄᴄᴏᴜɴᴛ 𝐂ᴀᴛᴇɢᴏʀʏ:</b>\n\n"
           f"🔍 <b>𝐒ᴇᴀʀᴄʜ 𝐂ᴏᴜɴᴛʀʏ:</b> 𝐐ᴜɪᴄᴋ ʟᴏᴏᴋᴜᴘ ʙʏ ɴᴀᴍᴇ ᴏʀ ᴅɪᴀʟ ᴄᴏᴅᴇ (+91, +55...)\n"
           f"🟢 <b>𝐍ᴏɴ-𝐒ᴘᴀᴍ / 𝐂ʟᴇᴀɴ:</b> 100% 𝐒ᴘᴀᴍʙʟᴏᴄᴋ-𝐅ʀᴇᴇ (𝐃𝐌 & 𝐏ᴇʀsᴏɴᴀʟ 𝐔sᴇ).\n"
           f"🟡 <b>𝐒ᴘᴀᴍ / 𝐔sᴇᴅ (𝐂ʜᴇᴀᴘ):</b> 𝐁ᴜᴅɢᴇᴛ 𝐀ᴄᴄᴏᴜɴᴛs (𝐂ʜᴀɴɴᴇʟ 𝐉ᴏɪɴᴇʀs & 𝐌ᴇᴍʙᴇʀs).\n"
           f"🎯 <b>𝐌ᴏʀᴇ 𝐅ɪʟᴛᴇʀs:</b> 𝐒ᴛᴀʀs, 𝐄ᴍᴀɪʟ, 2𝐅𝐀, 𝐏ʀᴇᴍɪᴜᴍ, 𝐃𝐂...\n"
           f"🌍 <b>𝐀ʟʟ 𝐂ᴏᴜɴᴛʀɪᴇs:</b> 𝐁ʀᴏᴡsᴇ 50+ ᴄᴏᴜɴᴛʀɪᴇs sᴛᴏᴄᴋ (𝐅ʀᴇsʜ & 𝐀ʟʟ).\n"
           f"🏛️ <b>𝐎ʟᴅ / 𝐀ɢᴇᴅ 𝐀ᴄᴄᴏᴜɴᴛs:</b> 𝐅ɪʟᴛᴇʀ ʙʏ 𝐒ᴘᴇᴄɪғɪᴄ 𝐘ᴇᴀʀ (2025, 2024, 2023...).</blockquote>")
    btns = [
        [style_btn("🔍 𝐒ᴇᴀʀᴄʜ 𝐂ᴏᴜɴᴛʀʏ", b"search_country_btn", "primary", icon=5409098988156629257)],
        [
            style_btn("🟢 𝐍ᴏɴ-𝐒ᴘᴀᴍ / 𝐂ʟᴇᴀɴ", b"pg_c|nonspam|1", "success", icon=5409320020058584473),
            style_btn("🟡 𝐒ᴘᴀᴍ / 𝐔sᴇᴅ (𝐂ʜᴇᴀᴘ)", b"pg_c|spam|1", "primary", icon=5408995930416362034)
        ],
        [style_btn("🎯 𝐌ᴏʀᴇ 𝐀ᴄᴄᴏᴜɴᴛ 𝐅ɪʟᴛᴇʀs (𝐒ᴛᴀʀs/2𝐅𝐀...)", b"pg_filters|1", "success", icon=5409320020058584473)],
        [style_btn("🌍 𝐀ʟʟ 𝐂ᴏᴜɴᴛʀɪᴇs (𝐅ʀᴇsʜ & 𝐀ʟʟ)", b"pg_c|bulk|1", "primary", icon=6154249597532248059)],
        [style_btn("🏛️ 𝐎ʟᴅ / 𝐀ɢᴇᴅ 𝐀ᴄᴄᴏᴜɴᴛs (ʙʏ 𝐘ᴇᴀʀ)", b"by_years_menu", "primary", icon=5408995930416362034)]
    ]
    if isinstance(event, events.CallbackQuery.Event):
        try: await event.edit(msg, buttons=btns)
        except MessageNotModifiedError: pass
    else:
        await event.respond(msg, buttons=btns)

async def show_years_catalog(event):
    msg = (f"<blockquote>🏛️ <b>𝐒ᴇʟᴇᴄᴛ 𝐀ᴄᴄᴏᴜɴᴛ 𝐘ᴇᴀʀ (𝐀ɢᴇ):</b>\n\n"
           f"<i>𝐀ɢᴇᴅ ᴀᴄᴄᴏᴜɴᴛs ʜᴀᴠᴇ ʜɪɢʜᴇʀ ᴛʀᴜsᴛ, ʟᴏᴡᴇʀ ʙᴀɴ ʀᴀᴛᴇs, ᴀɴᴅ ʟᴏɴɢᴇʀ ʜɪsᴛᴏʀʏ!</i></blockquote>")
    btns = []
    for y in [2026, 2025, 2024, 2023, 2022, 2021, 2020, 2019]:
        label = YEAR_BADGES.get(y, f"📅 {y}")
        btns.append([style_btn(label, f"c_by_yr|{y}|1", "primary", icon=5408995930416362034)])
    btns.append([style_btn("🔙 𝐁ᴀᴄᴋ ᴛᴏ 𝐌ᴇɴᴜ", b"buy_menu_main", "danger", icon=6129812419028982717)])
    
    if isinstance(event, events.CallbackQuery.Event):
        try: await event.edit(msg, buttons=btns)
        except MessageNotModifiedError: pass
    else:
        await event.respond(msg, buttons=btns)

async def show_countries_for_year(event, year, page):
    limit = 10
    offset = (page - 1) * limit
    countries_all = await get_countries_list()
    total = len(countries_all)
    countries = countries_all[offset:offset+limit]
    
    if not countries:
        return await event.respond(f"{P_WARN} 𝐍ᴏ sᴛᴏᴄᴋ ᴀᴠᴀɪʟᴀʙʟᴇ ғᴏʀ {year} ᴀᴛ ᴛʜᴇ ᴍᴏᴍᴇɴᴛ.")

    btns = []
    for c_name, count in countries:
        flag = get_flag_by_country_name(c_name)
        price = get_panel_price(c_name, year)
        btns.append(style_btn(f"{flag} {c_name} — {P_INR}{price}", f"by|bulk|{c_name}|{year}|{price}", "primary", icon=6154249597532248059))
        
    f_btns = [btns[i:i+2] for i in range(0, len(btns), 2)]
    
    nav = []
    if page > 1: nav.append(style_btn("⬅️ 𝐏ʀᴇᴠ", f"c_by_yr|{year}|{page-1}", "primary", icon=6129627894349045589))
    if offset + limit < total: nav.append(style_btn("𝐍ᴇxᴛ ➡️", f"c_by_yr|{year}|{page+1}", "primary", icon=6129732880529628243))
    if nav: f_btns.append(nav)
    
    f_btns.append([style_btn("🔙 𝐁ᴀᴄᴋ ᴛᴏ 𝐘ᴇᴀʀs", b"by_years_menu", "danger", icon=6129812419028982717)])
    
    total_pages = (total + limit - 1) // limit
    msg = f"<blockquote>🏛️ <b>𝐒ᴇʟᴇᴄᴛ 𝐂ᴏᴜɴᴛʀʏ ғᴏʀ {year} 𝐀ᴄᴄᴏᴜɴᴛs:</b> (𝐏ᴀɢᴇ {page}/{total_pages})</blockquote>"
    if isinstance(event, events.CallbackQuery.Event):
        try: await event.edit(msg, buttons=f_btns)
        except MessageNotModifiedError: pass
    else: await event.respond(msg, buttons=f_btns)

async def show_countries(event, mode, page):
    limit = 12
    offset = (page - 1) * limit
    countries_all = await get_countries_list()
    total = len(countries_all)
    countries = countries_all[offset:offset+limit]
    
    if not countries:
        return await event.respond(f"{P_WARN} 𝐍ᴏ sᴛᴏᴄᴋ ᴀᴠᴀɪʟᴀʙʟᴇ ᴀᴛ ᴛʜᴇ ᴍᴏᴍᴇɴᴛ. 𝐏ʟᴇᴀsᴇ ᴄʜᴇᴄᴋ ʙᴀᴄᴋ ʟᴀᴛᴇʀ!")

    btns = []
    for c_name, count in countries:
        flag = get_flag_by_country_name(c_name)
        cnt_str = f"({count})" if count else "(40+)"
        btns.append(style_btn(f"{flag} {c_name} {cnt_str}", f"bc|{mode}|{c_name}", "primary", icon=6154249597532248059))
        
    f_btns = [btns[i:i+2] for i in range(0, len(btns), 2)]
    
    nav = []
    if page > 1: nav.append(style_btn("⬅️ 𝐏ʀᴇᴠ", f"pg_c|{mode}|{page-1}", "primary", icon=6129627894349045589))
    nav.append(style_btn("🔍 𝐒ᴇᴀʀᴄʜ", b"search_country_btn", "primary", icon=5409098988156629257))
    if offset + limit < total: nav.append(style_btn("𝐍ᴇxᴛ ➡️", f"pg_c|{mode}|{page+1}", "primary", icon=6129732880529628243))
    if nav: f_btns.append(nav)
    
    back_row = []
    if mode != 'bulk':
        back_row.append(style_btn("🎯 𝐁ᴀᴄᴋ ᴛᴏ 𝐅ɪʟᴛᴇʀs", b"pg_filters|1", "primary", icon=5409320020058584473))
    back_row.append(style_btn("🔙 𝐁ᴀᴄᴋ ᴛᴏ 𝐌ᴇɴᴜ", b"buy_menu_main", "danger", icon=6129812419028982717))
    f_btns.append(back_row)
    
    total_pages = (total + limit - 1) // limit
    if mode in FILTER_BADGES and mode != 'bulk':
        cat_header = f"🎯 <b>𝐒ᴇʟᴇᴄᴛ 𝐂ᴏᴜɴᴛʀʏ ({FILTER_BADGES[mode]}):</b>"
    else:
        cat_header = f"{PE_LOCATION} <b>𝐒ᴇʟᴇᴄᴛ ᴀ 𝐂ᴏᴜɴᴛʀʏ:</b>"

    msg = f"<blockquote>{cat_header} (𝐏ᴀɢᴇ {page}/{total_pages})</blockquote>"
    if isinstance(event, events.CallbackQuery.Event):
        try: await event.edit(msg, buttons=f_btns)
        except MessageNotModifiedError: pass
    else: await event.respond(msg, buttons=f_btns)

async def show_years(event, mode, country):
    bot_mode = get_bot_mode()
    year_options = []
    
    # 1. Check local stock first
    if bot_mode in ('manual', 'hybrid'):
        if mode == 'spam':
            rows = cur.execute("SELECT account_year, COUNT(*), price FROM stock WHERE country_name=? AND available=1 AND (category='Spam' OR category='spam') GROUP BY account_year, price", (country,)).fetchall()
        elif mode == 'nonspam':
            rows = cur.execute("SELECT account_year, COUNT(*), price FROM stock WHERE country_name=? AND available=1 AND (category!='Spam' AND category!='spam') GROUP BY account_year, price", (country,)).fetchall()
        elif mode == 'no_2fa':
            rows = cur.execute("SELECT account_year, COUNT(*), price FROM stock WHERE country_name=? AND available=1 AND (twofa='None' OR twofa IS NULL OR twofa='') GROUP BY account_year, price", (country,)).fetchall()
        elif mode == 'with_2fa':
            rows = cur.execute("SELECT account_year, COUNT(*), price FROM stock WHERE country_name=? AND available=1 AND (twofa!='None' AND twofa IS NOT NULL AND twofa!='') GROUP BY account_year, price", (country,)).fetchall()
        else:
            rows = cur.execute("SELECT account_year, COUNT(*), price FROM stock WHERE country_name=? AND available=1 GROUP BY account_year, price", (country,)).fetchall()
            
        for y, count, price in rows:
            year_options.append({
                'year': y, 'count': count, 'price': price, 'source': 'local'
            })

    # 2. If panel mode, or hybrid with no local stock
    if (bot_mode == 'panel' or (bot_mode == 'hybrid' and not year_options)) and get_lzt_key():
        try:
            items = await lzt_client.search_items(country, mode=mode)
            # Group by year
            years_grouped = {}
            for itm in items:
                y = itm['year']
                if y not in years_grouped:
                    price = get_panel_price(country, y, itm['price_rub'], mode=mode)
                    years_grouped[y] = {'count': 0, 'price': price}
                years_grouped[y]['count'] += 1
                
            for y, info in sorted(years_grouped.items(), key=lambda x: x[0], reverse=True):
                year_options.append({
                    'year': y, 'count': info['count'], 'price': info['price'], 'source': 'lzt'
                })
        except Exception as e:
            logger.error(f"Error fetching LZT years for {country}: {e}")

    # Fallback to standard aged years if no specific list was grouped
    if not year_options:
        for y in [2026, 2025, 2024, 2023, 2022, 2021]:
            year_options.append({
                'year': y, 'count': '40+', 'price': get_panel_price(country, y, mode=mode), 'source': 'lzt'
            })
    
    flag = get_flag_by_country_name(country)
    btns = []
    for opt in year_options:
        y, count, price = opt['year'], opt['count'], opt['price']
        badge = YEAR_BADGES.get(int(y) if str(y).isdigit() else y, f"📅 {y}")
        cnt_text = f"({count} left)" if isinstance(count, int) else f"({count})"
        btns.append([style_btn(f"{badge} — {P_INR}{price} {cnt_text}", f"by|{mode}|{country}|{y}|{price}", "primary", icon=5408995930416362034)])
    
    if mode != 'bulk':
        btns.append([style_btn("🔙 𝐁ᴀᴄᴋ ᴛᴏ 𝐂ᴏᴜɴᴛʀɪᴇs", f"pg_c|{mode}|1", "danger", icon=6129812419028982717)])
    else:
        btns.append([style_btn("🔙 𝐁ᴀᴄᴋ ᴛᴏ 𝐂ᴏᴜɴᴛʀɪᴇs", "pg_c|bulk|1", "danger", icon=6129812419028982717)])
    
    if mode in FILTER_BADGES and mode != 'bulk':
        cat_label = f" ({FILTER_BADGES[mode]})"
    else:
        cat_label = ""
    
    await event.edit(f"<blockquote>{flag} <b>𝐒ᴇʟᴇᴄᴛ 𝐘ᴇᴀʀ & 𝐏ʀɪᴄᴇ ғᴏʀ {country}{cat_label}:</b></blockquote>", buttons=btns)

async def confirm_purchase(event, mode, country, year, price):
    flag = get_flag_by_country_name(country)
    badge = YEAR_BADGES.get(int(year) if str(year).isdigit() else year, f"📅 {year}")
    
    if mode == 'nonspam': cat_badge = "🟢 𝐍ᴏɴ-𝐒ᴘᴀᴍ (100% 𝐂ʟᴇᴀɴ)"
    elif mode == 'spam': cat_badge = "🟡 𝐒ᴘᴀᴍ / 𝐔sᴇᴅ (𝐂ʜᴇᴀᴘ)"
    else: cat_badge = "🌍 𝐒ᴛᴀɴᴅᴀʀᴅ"

    msg = (f"<blockquote>{PE_GIFT} <b>𝐂ᴏɴғɪʀᴍ 𝐏ᴜʀᴄʜᴀsᴇ</b>\n\n"
           f"{P_FLAG} <b>𝐂ᴏᴜɴᴛʀʏ:</b> {flag} {country}\n"
           f"🏷️ <b>𝐂ᴀᴛᴇɢᴏʀʏ:</b> {cat_badge}\n"
           f"📆 <b>𝐘ᴇᴀʀ:</b> {badge}\n"
           f"{P_MONEY} <b>𝐏ʀɪᴄᴇ:</b> {P_INR}{price}\n\n"
           f"<b>𝐀ʀᴇ ʏᴏᴜ sᴜʀᴇ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ ʙᴜʏ?</b></blockquote>")
    btns = [
        [style_btn("✅ 𝐂ᴏɴғɪʀᴍ 𝐁ᴜʏ", f"buy_cf|{mode}|{country}|{year}|{price}", "success", icon=5409320020058584473)],
        [style_btn("❌ 𝐂ᴀɴᴄᴇʟ", "cancel_action", "danger", icon=6129888444245089008)]
    ]
    await event.edit(msg, buttons=btns)

async def process_purchase(event, mode, country, year, price_str):
    uid, price = event.sender_id, int(price_str)
    bot_mode = get_bot_mode()
    
    async with get_user_lock(uid):
        disc_row = cur.execute("SELECT discount, balance FROM users WHERE user_id=?", (uid,)).fetchone()
        if not disc_row: return await event.answer("❌ User not found!", alert=True)
        discount, balance = disc_row[0], disc_row[1]
        final_price = price if discount == 0 else int(price * (100 - discount) / 100)
        
        if balance < final_price:
            return await event.answer("❌ Insufficient Balance!", alert=True)

        # Check local stock first
        if mode == 'spam':
            local_row = cur.execute("SELECT phone, session_file, twofa FROM stock WHERE country_name=? AND account_year=? AND available=1 AND (category='Spam' OR category='spam') LIMIT 1", (country, int(year))).fetchone()
        elif mode == 'nonspam':
            local_row = cur.execute("SELECT phone, session_file, twofa FROM stock WHERE country_name=? AND account_year=? AND available=1 AND (category!='Spam' AND category!='spam') LIMIT 1", (country, int(year))).fetchone()
        elif mode == 'no_2fa':
            local_row = cur.execute("SELECT phone, session_file, twofa FROM stock WHERE country_name=? AND account_year=? AND available=1 AND (twofa='None' OR twofa IS NULL OR twofa='') LIMIT 1", (country, int(year))).fetchone()
        elif mode == 'with_2fa':
            local_row = cur.execute("SELECT phone, session_file, twofa FROM stock WHERE country_name=? AND account_year=? AND available=1 AND (twofa!='None' AND twofa IS NOT NULL AND twofa!='') LIMIT 1", (country, int(year))).fetchone()
        else:
            local_row = cur.execute("SELECT phone, session_file, twofa FROM stock WHERE country_name=? AND account_year=? AND available=1 LIMIT 1", (country, int(year))).fetchone()
        
        is_local = (bot_mode in ('manual', 'hybrid')) and (local_row is not None)
        
        if not is_local and bot_mode == 'manual':
            return await event.answer("❌ Out of stock!", alert=True)

        if is_local:
            phone, sess, twofa_pass = local_row
            cur.execute("UPDATE users SET balance = balance - ? WHERE user_id=? AND balance >= ?", (final_price, uid, final_price))
            if cur.rowcount == 0: return await event.answer("❌ Insufficient Balance!", alert=True)
            cur.execute("UPDATE stock SET available=0 WHERE phone=?", (phone,))
            db.commit()
        else:
            # Panel / LZT order: reserve balance first
            cur.execute("UPDATE users SET balance = balance - ? WHERE user_id=? AND balance >= ?", (final_price, uid, final_price))
            if cur.rowcount == 0: return await event.answer("❌ Insufficient Balance!", alert=True)
            db.commit()

    c_icon = get_flag_by_country_name(country)
    actual_year = int(year)

    if is_local:
        # Local session processing
        await event.edit(f"{PE_LIGHTNING} <b>𝐏ʀᴏᴄᴇssɪɴɢ ʏᴏᴜʀ ᴏʀᴅᴇʀ...</b>\n𝐏ʟᴇᴀsᴇ ᴡᴀɪᴛ ᴡʜɪʟᴇ ᴡᴇ ɪɴɪᴛɪᴀʟɪᴢᴇ ᴛʜᴇ sᴇssɪᴏɴ.")
        
        client = TelegramClient(sess, API_ID, API_HASH)
        try:
            await client.connect()
            if not await client.is_user_authorized():
                raise Exception("Session expired or not authorized")
        except Exception as e:
            logger.error(f"Client init error: {e}")
            try: await client.disconnect()
            except: pass
            async with get_user_lock(uid):
                cur.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (final_price, uid))
                cur.execute("DELETE FROM stock WHERE phone=?", (phone,))
                db.commit()
            return await event.edit(f"{P_NO} <b>Error initializing account. (Session Dead)</b> Money refunded.")

        from database import is_admin
        temp_order = {'c_icon': c_icon, 'country': country, 'twofa': twofa_pass}
        msg, active_btns = get_active_order_card(temp_order, phone, is_admin(uid))
        sent_msg = await event.edit(msg, buttons=active_btns)
        
        active_orders[phone] = {
            'uid': uid, 'client': client, 'sess': sess, 'start_time': time.time(), 
            'paid': False, 'price': final_price, 'country': country, 'year': actual_year, 
            'c_icon': c_icon, 'twofa': twofa_pass, 'msg_id': sent_msg.id, 'is_lzt': False
        }
        asyncio.create_task(auto_otp_task(phone))
    else:
        # LZT Panel Purchase Flow
        await event.edit(f"{PE_LIGHTNING} <b>𝐏ʀᴏᴄᴇssɪɴɢ ʏᴏᴜʀ ᴏʀᴅᴇʀ...</b>\n𝐏ʟᴇᴀsᴇ ᴡᴀɪᴛ ᴡʜɪʟᴇ ᴡᴇ ɪɴɪᴛɪᴀʟɪᴢᴇ ᴛʜᴇ sᴇssɪᴏɴ.")
        try:
            items = await lzt_client.search_items(country, actual_year, mode=mode)
            if not items:
                items = await lzt_client.search_items(country, mode=mode)
            
            if not items:
                async with get_user_lock(uid):
                    cur.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (final_price, uid))
                    db.commit()
                return await event.edit(f"<blockquote>{P_NO} <b>❌ 𝐎ᴜᴛ ᴏғ 𝐒ᴛᴏᴄᴋ!</b>\n\n𝐍ᴏ ᴀᴄᴄᴏᴜɴᴛs ᴀʀᴇ ᴄᴜʀʀᴇɴᴛʟʏ ᴀᴠᴀɪʟᴀʙʟᴇ ғᴏʀ <b>{c_icon} {country}</b>.\n𝐘ᴏᴜʀ ᴍᴏɴᴇʏ (<b>{P_INR}{final_price}</b>) ʜᴀs ʙᴇᴇɴ <b>ɪɴsᴛᴀɴᴛʟʏ ʀᴇғᴜɴᴅᴇᴅ</b>.</blockquote>", buttons=[[style_btn("🛒 𝐁ᴜʏ 𝐀ɴᴏᴛʜᴇʀ 𝐂ᴏᴜɴᴛʀʏ", "buy_menu_main", "primary", icon=5408995930416362034)]])

            buy_success = False
            bought_info = None
            client = None
            phone = None
            last_err = ""

            for itm in items[:5]:
                item_id = itm['item_id']
                price_str = itm.get('price_str', str(itm.get('price_usd', '0.1')))
                balance_id = itm.get('balance_id')
                ok, buy_result = await lzt_client.fast_buy(item_id, price_str, balance_id)
                if ok:
                    str_sess = buy_result.get("string_session")
                    if str_sess:
                        try:
                            from telethon.sessions import StringSession
                            test_client = TelegramClient(StringSession(str_sess), 2040, 'b18441a1ff607e10a989891a5462e627')
                            await test_client.connect()
                            if await test_client.is_user_authorized():
                                me = await test_client.get_me()
                                p = getattr(me, 'phone', None) or buy_result.get("phone") or f"Item-{item_id}"
                                phone = str(p).lstrip('+')
                                client = test_client
                                bought_info = buy_result
                                buy_success = True
                                break
                            else:
                                logger.warning(f"Session for item {item_id} expired on Telegram, trying next...")
                                try: await test_client.disconnect()
                                except: pass
                        except Exception as conn_err:
                            logger.warning(f"Connection error for item {item_id}: {conn_err}, trying next...")
                else:
                    last_err = str(buy_result)
                    logger.warning(f"Fast-buy attempt failed for {item_id}: {last_err}, trying next...")

            if not buy_success or not client:
                async with get_user_lock(uid):
                    cur.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (final_price, uid))
                    db.commit()
                return await event.edit(f"{P_NO} <b>Error initializing account.</b> {last_err or 'Session unavailable.'}\nYour money has been refunded.")

            item_id = bought_info['item_id']
            twofa_pass = bought_info.get("twofa") or "None"
            str_sess = bought_info.get("string_session")

            from database import is_admin
            temp_order = {'c_icon': c_icon, 'country': country, 'twofa': twofa_pass}
            msg, active_btns = get_active_order_card(temp_order, phone, is_admin(uid))
            sent_msg = await event.edit(msg, buttons=active_btns)

            active_orders[phone] = {
                'uid': uid, 'client': client, 'sess': str_sess, 'item_id': item_id,
                'start_time': time.time(), 'paid': False, 'price': final_price,
                'country': country, 'year': actual_year, 'c_icon': c_icon,
                'twofa': twofa_pass, 'msg_id': sent_msg.id, 'is_lzt': True
            }
            asyncio.create_task(auto_otp_task(phone))
        except Exception as e:
            logger.error(f"Purchase flow error: {e}")
            async with get_user_lock(uid):
                cur.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (final_price, uid))
                db.commit()
            return await event.edit(f"{P_NO} <b>Error initializing account.</b> Money refunded.")

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
            try:
                peer = await client.get_input_entity(777000)
            except Exception:
                peer = types.InputPeerUser(user_id=777000, access_hash=0)
            msgs = await client.get_messages(peer, limit=5)
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
                        
                        from config import LOG_CHANNELS, P_YES
                        for log_ch in LOG_CHANNELS:
                            try:
                                await bot.send_message(log_ch, f"{P_YES} <b>ACCOUNT SOLD</b>\n\n👤 <b>User:</b> <code>{uid}</code>\n📱 <b>Phone:</b> <code>{phone}</code>\n💰 <b>Price:</b> ₹{order['price']}\n🌍 <b>Country:</b> {order['country']}")
                            except Exception as log_ex:
                                logger.error(f"Failed to log sale to {log_ch}: {log_ex}")
                
                twofa_text = f"{P_2FA} <b>2FA:</b> <code>{order['twofa']}</code>" if order['twofa'] != "None" else f"🔓 <b>2FA:</b> <code>Disabled (No Password)</code>"
                msg_text = (f"<blockquote>{PE_CHECK} <b>𝐋ᴀᴛᴇsᴛ 𝐎𝐓𝐏 𝐅ᴇᴛᴄʜᴇᴅ!</b>\n\n"
                            f"{P_PHONE} <b>𝐏ʜᴏɴᴇ:</b> <code>{phone}</code>\n"
                            f"{P_FLAG} <b>𝐂ᴏᴜɴᴛʀʏ:</b> {order['c_icon']} {order['country']}\n"
                            f"{P_OTP} <b>𝐎𝐓𝐏:</b> <code><tg-spoiler>{code}</tg-spoiler></code>\n"
                            f"{twofa_text}</blockquote>")
                
                otp_btns = [
                    [style_btn("🔄 𝐆ᴇᴛ 𝐎𝐓𝐏 𝐀ɢᴀɪɴ", f"get_otp_again|{phone}", "primary", icon=5408995930416362034)],
                    [style_btn("✅ 𝐅ɪɴɪsʜ 𝐎ʀᴅᴇʀ", f"finish_order|{phone}", "success", icon=5409320020058584473)]
                ]
                try: await bot.edit_message(uid, msg_id, msg_text, buttons=otp_btns)
                except MessageNotModifiedError: pass
                return 
        except Exception as ex:
            logger.error(f"OTP fetch error for {phone}: {ex}")
        await asyncio.sleep(6) 
        
    if phone in active_orders and not active_orders[phone]['paid']:
        order = active_orders.pop(phone)
        try: await order['client'].disconnect()
        except: pass
        
        # Local manual stock -> refund & restore stock
        if not order.get('is_lzt'):
            async with get_user_lock(uid):
                cur.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (order['price'], uid))
                cur.execute("UPDATE stock SET available=1 WHERE phone=?", (phone,))
                db.commit()
            try: await bot.edit_message(uid, msg_id, f"<blockquote>{P_TIME} <b>𝐎ʀᴅᴇʀ 𝐄xᴘɪʀᴇᴅ!</b>\n\n𝐓ʜᴇ 10-ᴍɪɴᴜᴛᴇ ʟɪᴍɪᴛ ғᴏʀ <code>+{phone}</code> ʀᴀɴ ᴏᴜᴛ. 𝐘ᴏᴜʀ ᴍᴏɴᴇʏ ({P_INR}{order['price']}) ʜᴀs ʙᴇᴇɴ ʀᴇғᴜɴᴅᴇᴅ.</blockquote>")
            except: pass
        else:
            # LZT Panel purchased accounts -> do not auto-refund to prevent wallet drainage exploits
            try: await bot.edit_message(uid, msg_id, f"<blockquote>{P_TIME} <b>𝐒ᴇssɪᴏɴ 𝐓ɪᴍᴇᴏᴜᴛ</b>\n\n𝐓ʜᴇ 10-ᴍɪɴᴜᴛᴇ ʟɪsᴛᴇɴᴇʀ ғᴏʀ <code>+{phone}</code> ʜᴀs ᴇɴᴅᴇᴅ.\n𝐈ғ ʏᴏᴜ ɴᴇᴇᴅ ᴀssɪsᴛᴀɴᴄᴇ, ᴘʟᴇᴀsᴇ ᴄᴏɴᴛᴀᴄᴛ 𝐒ᴜᴘᴘᴏʀᴛ.</blockquote>")
            except: pass

def register_buy(bot):
    @bot.on(events.NewMessage(pattern=r"(?i)^(🛒 𝐁ᴜʏ 𝐀ᴄᴄᴏᴜɴᴛ|🛒 Buy Account|📁 Buy Sessions)$"))
    async def msg_buy(e):
        await show_buy_menu(e)

    @bot.on(events.CallbackQuery(pattern=b"^buy_menu_main$"))
    async def cb_buy_menu_main(e):
        await show_buy_menu(e)

    @bot.on(events.CallbackQuery(pattern=b"^by_years_menu$"))
    async def cb_by_years_menu(e):
        await show_years_catalog(e)

    @bot.on(events.CallbackQuery(pattern=r"^pg_filters\|(\d+)$"))
    async def cb_pg_filters(e):
        p = e.pattern_match
        page = int(p.group(1).decode())
        await show_filters_catalog(e, page)

    @bot.on(events.CallbackQuery(pattern=r"^c_by_yr\|(\d+)\|(\d+)$"))
    async def cb_c_by_yr(e):
        p = e.pattern_match
        year = int(p.group(1).decode())
        page = int(p.group(2).decode())
        await show_countries_for_year(e, year, page)

    @bot.on(events.CallbackQuery(pattern=r"^bc\|(.+)\|(.+)$"))
    async def cb_bc(e):
        p = e.pattern_match
        await show_years(e, p.group(1).decode(), p.group(2).decode())

    @bot.on(events.CallbackQuery(pattern=r"^pg_c\|(.+)\|(\d+)$"))
    async def cb_pg_c(e):
        p = e.pattern_match
        await show_countries(e, p.group(1).decode(), int(p.group(2).decode()))

    @bot.on(events.CallbackQuery(pattern=r"^by\|(.+)\|(.+)\|(\d+)\|(\d+)$"))
    async def cb_by_single(e):
        p = e.pattern_match
        await confirm_purchase(e, p.group(1).decode(), p.group(2).decode(), p.group(3).decode(), p.group(4).decode())
        
    @bot.on(events.CallbackQuery(pattern=r"^buy_cf\|(.+)\|(.+)\|(\d+)\|(\d+)$"))
    async def cb_buy_cf_4(e):
        p = e.pattern_match
        await process_purchase(e, p.group(1).decode(), p.group(2).decode(), p.group(3).decode(), p.group(4).decode())

    @bot.on(events.CallbackQuery(pattern=r"^buy_cf\|(.+)\|(\d+)\|(\d+)$"))
    async def cb_buy_cf_3(e):
        p = e.pattern_match
        await process_purchase(e, "bulk", p.group(1).decode(), p.group(2).decode(), p.group(3).decode())

    @bot.on(events.CallbackQuery(pattern=r"^cancel_order\|(.+)$"))
    async def cb_cancel_order(e):
        phone = e.pattern_match.group(1).decode()
        uid = e.sender_id
        from database import is_admin
        if not is_admin(uid):
            return await e.answer("🚫 Cancellation is disabled for members. Please complete your login or contact Support.", alert=True)
            
        if phone not in active_orders:
            return await e.answer("⚠️ Order already completed or expired.", alert=True)
            
        order = active_orders[phone]
        if order.get('paid'):
            return await e.answer("⚠️ OTP was already sent! Order is completed.", alert=True)
            
        # Admin cancel & refund
        active_orders.pop(phone)
        refund_amt = order['price']
        
        try:
            if 'client' in order and order['client']:
                await order['client'].disconnect()
        except: pass
            
        async with get_user_lock(order['uid']):
            cur.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (refund_amt, order['uid']))
            if not order.get('is_lzt'):
                cur.execute("UPDATE stock SET available=1 WHERE phone=?", (phone,))
            db.commit()
            
        msg = f"<blockquote>{P_NO} <b>❌ 𝐎ʀᴅᴇʀ 𝐂ᴀɴᴄᴇʟʟᴇᴅ!</b>\n\n𝐘ᴏᴜʀ ᴍᴏɴᴇʏ (<b>{P_INR}{refund_amt}</b>) ʜᴀs ʙᴇᴇɴ <b>ɪɴsᴛᴀɴᴛʟʏ ʀᴇғᴜɴᴅᴇᴅ</b> ᴛᴏ ʏᴏᴜʀ ʙᴀʟᴀɴᴄᴇ.</blockquote>"
        await e.edit(msg, buttons=[[style_btn("🛒 𝐁ᴜʏ 𝐀ɢᴀɪɴ", "buy_menu_main", "primary", icon=5408995930416362034)]])
        await e.answer("✅ Order Cancelled & Refunded!", alert=True)

    @bot.on(events.CallbackQuery(pattern=r"^get_otp_again\|(.+)$"))
    async def cb_get_otp_again(e):
        phone = e.pattern_match.group(1).decode()
        if phone not in active_orders: return await e.answer("⚠️ Session expired.", alert=True)
        await e.answer("🔄 Fetching latest OTP...")
        order = active_orders[phone]
        uid = order['uid']
        msg_id = order['msg_id']
        client = order.get('client')

        if not client:
            return await e.answer("⚠️ Client disconnected.", alert=True)

        try:
            try:
                peer = await client.get_input_entity(777000)
            except Exception:
                peer = types.InputPeerUser(user_id=777000, access_hash=0)
            msgs = await client.get_messages(peer, limit=5)
            code = None
            for m in msgs:
                if m.date.timestamp() > order['start_time'] - 10:
                    if m.message and re.search(OTP_REGEX, m.message) and "Login detected" not in m.message:
                        code = re.search(OTP_REGEX, m.message).group()
                        break
            if code:
                if not order['paid']:
                    order['paid'] = True
                    async with get_user_lock(uid):
                        cur.execute("INSERT INTO orders (user_id, country, year, price, phone, otp) VALUES (?,?,?,?,?,?)", (uid, order['country'], order['year'], order['price'], phone, code))
                        if not order.get('is_lzt'):
                            cur.execute("DELETE FROM stock WHERE phone=?", (phone,))
                        db.commit()
                twofa_text = f"{P_2FA} <b>2FA:</b> <code>{order['twofa']}</code>" if order['twofa'] != "None" else f"🔓 <b>2FA:</b> <code>Disabled (No Password)</code>"
                msg_text = (f"<blockquote>{PE_CHECK} <b>𝐋ᴀᴛᴇsᴛ 𝐎𝐓𝐏 𝐅ᴇᴛᴄʜᴇᴅ!</b>\n\n"
                            f"{P_PHONE} <b>𝐏ʜᴏɴᴇ:</b> <code>+{phone}</code>\n"
                            f"{P_FLAG} <b>𝐂ᴏᴜɴᴛʀʏ:</b> {order['c_icon']} {order['country']}\n"
                            f"{P_OTP} <b>𝐎𝐓𝐏:</b> <code><tg-spoiler>{code}</tg-spoiler></code>\n"
                            f"{twofa_text}</blockquote>")
                otp_btns = [
                    [style_btn("🔄 𝐆ᴇᴛ 𝐎𝐓𝐏 𝐀ɢᴀɪɴ", f"get_otp_again|{phone}", "primary", icon=5408995930416362034)],
                    [style_btn("✅ 𝐅ɪɴɪsʜ 𝐎ʀᴅᴇʀ", f"finish_order|{phone}", "success", icon=5409320020058584473)]
                ]
                try: await bot.edit_message(uid, msg_id, msg_text, buttons=otp_btns)
                except MessageNotModifiedError: pass
            else:
                await e.answer("⚠️ No new OTP found yet. Make sure you tapped Send Code in Telegram!", alert=True)
        except Exception as ex:
            logger.error(f"OTP fetch error for {phone}: {ex}")
            await e.answer("❌ Error fetching OTP.", alert=True)
        
    @bot.on(events.CallbackQuery(pattern=r"^(finish_order|logout_bot)\|(.+)$"))
    async def cb_finish_order(e):
        phone = e.pattern_match.group(2).decode()
        if phone in active_orders:
            order = active_orders.pop(phone)
            if 'client' in order and order['client']:
                try: await order['client'].disconnect()
                except: pass
            if not order.get('is_lzt') and 'sess' in order:
                for ext in ['.session', '.session-wal', '.session-shm', '.session-journal']:
                    if os.path.exists(order['sess'] + ext): os.remove(order['sess'] + ext)
            msg = f"<blockquote>{PE_CHECK} <b>🎉 𝐎ʀᴅᴇʀ 𝐂ᴏᴍᴘʟᴇᴛᴇᴅ!</b>\n\n𝐓ʜᴀɴᴋ ʏᴏᴜ ғᴏʀ ʏᴏᴜʀ ᴘᴜʀᴄʜᴀsᴇ. 𝐘ᴏᴜʀ ᴀᴄᴄᴏᴜɴᴛ ɪs ʀᴇᴀᴅʏ ᴛᴏ ᴜsᴇ!</blockquote>"
            await e.edit(msg, buttons=[[style_btn("🛒 𝐁ᴜʏ 𝐀ɴᴏᴛʜᴇʀ 𝐀ᴄᴄᴏᴜɴᴛ", "buy_menu_main", "primary", icon=5408995930416362034)]])
        else:
            await e.answer("✅ Order already completed.", alert=True)

    @bot.on(events.CallbackQuery(pattern=b"^search_country_btn$"))
    async def cb_search_country_btn(e):
        uid = e.sender_id
        search_state[uid] = True
        msg = (f"<blockquote>🔍 <b>𝐒ᴇᴀʀᴄʜ 𝐂ᴏᴜɴᴛʀʏ:</b>\n\n"
               f"𝐏ʟᴇᴀsᴇ ᴛʏᴘᴇ ᴛʜᴇ <b>𝐂ᴏᴜɴᴛʀʏ 𝐍ᴀᴍᴇ</b> (ᴇ.ɢ. <i>India, Brazil, Russia, France</i>) ᴏʀ <b>𝐃ɪᴀʟɪɴɢ 𝐂ᴏᴅᴇ</b> (ᴇ.ɢ. <i>+91, +55, +7</i>) ʙᴇʟᴏᴡ:</blockquote>")
        btns = [[style_btn("🔙 𝐁ᴀᴄᴋ ᴛᴏ 𝐌ᴇɴᴜ", b"buy_menu_main", "danger", icon=6129812419028982717)]]
        try: await e.edit(msg, buttons=btns)
        except MessageNotModifiedError: pass

    @bot.on(events.NewMessage(func=lambda e: e.sender_id in search_state and not e.text.startswith('/')))
    async def msg_search_country(e):
        import html
        uid = e.sender_id
        search_state.pop(uid, None)
        query = (e.text or "").strip()
        if not query: return
        
        matches = await search_countries_matching(query)
        if matches:
            btns = []
            for c_name, count in matches[:12]:
                flag = get_flag_by_country_name(c_name)
                cnt_str = f"({count})" if count else "(40+)"
                btns.append(style_btn(f"{flag} {c_name} {cnt_str}", f"bc|bulk|{c_name}", "primary", icon=6154249597532248059))
            
            f_btns = [btns[i:i+2] for i in range(0, len(btns), 2)]
            f_btns.append([
                style_btn("🔍 𝐒ᴇᴀʀᴄʜ 𝐀ɢᴀɪɴ", b"search_country_btn", "primary", icon=5409098988156629257),
                style_btn("🔙 𝐁ᴀᴄᴋ ᴛᴏ 𝐌ᴇɴᴜ", b"buy_menu_main", "danger", icon=6129812419028982717)
            ])
            msg = (f"<blockquote>🔍 <b>𝐒ᴇᴀʀᴄʜ 𝐑ᴇsᴜʟᴛs ғᴏʀ:</b> <code>{html.escape(query)}</code>\n\n"
                   f"𝐅ᴏᴜɴᴅ <b>{len(matches)}</b> ᴍᴀᴛᴄʜɪɴɢ ᴄᴏᴜɴᴛʀɪᴇs:</blockquote>")
            await e.reply(msg, buttons=f_btns)
        else:
            f_btns = [
                [style_btn("🔍 𝐒ᴇᴀʀᴄʜ 𝐀ɢᴀɪɴ", b"search_country_btn", "primary", icon=5409098988156629257)],
                [style_btn("🌍 𝐀ʟʟ 𝐂ᴏᴜɴᴛʀɪᴇs", b"pg_c|bulk|1", "primary", icon=6154249597532248059)],
                [style_btn("🔙 𝐁ᴀᴄᴋ ᴛᴏ 𝐌ᴇɴᴜ", b"buy_menu_main", "danger", icon=6129812419028982717)]
            ]
            msg = (f"<blockquote>❌ <b>𝐍ᴏ ᴄᴏᴜɴᴛʀɪᴇs ғᴏᴜɴᴅ ᴍᴀᴛᴄʜɪɴɢ:</b> <code>{html.escape(query)}</code>\n\n"
                   f"𝐏ʟᴇᴀsᴇ ᴄʜᴇᴄᴋ ᴛʜᴇ sᴘᴇʟʟɪɴɢ ᴏʀ ʙʀᴏᴡsᴇ <b>𝐀ʟʟ 𝐂ᴏᴜɴᴛʀɪᴇs</b>.</blockquote>")
            await e.reply(msg, buttons=f_btns)

    @bot.on(events.CallbackQuery(pattern=r"^chg_num\|(.+)$"))
    async def cb_chg_num(e):
        phone = e.pattern_match.group(1).decode()
        uid = e.sender_id
        if phone not in active_orders:
            return await e.answer("⚠️ Order expired or completed.", alert=True)
        order = active_orders[phone]
        if order['uid'] != uid:
            return await e.answer("🚫 Not your order!", alert=True)
        
        change_number_state[uid] = {'stage': 'await_new_phone', 'phone': phone}
        msg = (f"<blockquote>🔄 <b>𝐂ʜᴀɴɢᴇ 𝐀ᴄᴄᴏᴜɴᴛ 𝐏ʜᴏɴᴇ 𝐍ᴜᴍʙᴇʀ</b>\n\n"
               f"📱 <b>𝐂ᴜʀʀᴇɴᴛ 𝐍ᴜᴍʙᴇʀ:</b> <code>+{phone}</code>\n\n"
               f"🔻 <b>𝐈ɴsᴛʀᴜᴄᴛɪᴏɴs:</b>\n"
               f"𝐏ʟᴇᴀsᴇ sᴇɴᴅ ʏᴏᴜʀ <b>𝐍ᴇᴡ 𝐏ʜᴏɴᴇ 𝐍ᴜᴍʙᴇʀ</b> ɪɴ ɪɴᴛᴇʀɴᴀᴛɪᴏɴᴀʟ ғᴏʀᴍᴀᴛ ʙᴇʟᴏᴡ:\n"
               f"<i>𝐄xᴀᴍᴘʟᴇ: <code>+919876543210</code> ᴏʀ <code>+14155552671</code></i>\n\n"
               f"⚠️ <i>𝐍ᴏᴛᴇ: 𝐌ᴀᴋᴇ sᴜʀᴇ ʏᴏᴜʀ ɴᴇᴡ ɴᴜᴍʙᴇʀ ᴅᴏᴇs ɴᴏᴛ ᴀʟʀᴇᴀᴅʏ ʜᴀᴠᴇ ᴀ 𝐓ᴇʟᴇɢʀᴀᴍ ᴀᴄᴄᴏᴜɴᴛ!</i></blockquote>")
        btns = [[style_btn("🔙 𝐁ᴀᴄᴋ ᴛᴏ 𝐎ʀᴅᴇʀ", f"back_to_order|{phone}", "danger", icon=6129812419028982717)]]
        try: await e.edit(msg, buttons=btns)
        except MessageNotModifiedError: pass

    @bot.on(events.CallbackQuery(pattern=r"^back_to_order\|(.+)$"))
    async def cb_back_to_order(e):
        phone = e.pattern_match.group(1).decode()
        uid = e.sender_id
        change_number_state.pop(uid, None)
        if phone not in active_orders:
            return await e.answer("⚠️ Order expired or completed.", alert=True)
        order = active_orders[phone]
        from database import is_admin
        msg, btns = get_active_order_card(order, phone, is_admin(uid))
        try: await e.edit(msg, buttons=btns)
        except MessageNotModifiedError: pass

    @bot.on(events.NewMessage(func=lambda e: e.sender_id in change_number_state and not e.text.startswith('/')))
    async def msg_change_number(e):
        uid = e.sender_id
        state = change_number_state.get(uid)
        if not state: return
        
        stage = state.get('stage')
        
        if stage == 'await_new_phone':
            orig_phone = state['phone']
            if orig_phone not in active_orders:
                change_number_state.pop(uid, None)
                return await e.reply("⚠️ Order expired or completed.")
                
            new_phone = re.sub(r"[^\d+]", "", (e.text or "").strip())
            if not new_phone.startswith('+'):
                new_phone = '+' + new_phone
                
            if len(new_phone) < 8 or len(new_phone) > 17:
                return await e.reply(f"{P_NO} <b>Invalid phone number format!</b>\nPlease send in international format, e.g. <code>+919876543210</code>")
                
            order = active_orders[orig_phone]
            client = order['client']
            loading = await e.reply("⏳ <i>Sending verification code to your new number...</i>")
            
            try:
                sent_res = await client(SendChangePhoneCodeRequest(phone_number=new_phone))
                change_number_state[uid] = {
                    'stage': 'await_otp',
                    'orig_phone': orig_phone,
                    'new_phone': new_phone,
                    'phone_code_hash': sent_res.phone_code_hash
                }
                msg = (f"<blockquote>📩 <b>𝐕ᴇʀɪғɪᴄᴀᴛɪᴏɴ 𝐂ᴏᴅᴇ 𝐒ᴇɴᴛ!</b>\n\n"
                       f"📱 <b>𝐍ᴇᴡ 𝐍ᴜᴍʙᴇʀ:</b> <code>{new_phone}</code>\n\n"
                       f"<i>𝐀 ᴠᴇʀɪғɪᴄᴀᴛɪᴏɴ ᴄᴏᴅᴇ (𝐎𝐓𝐏) ʜᴀs ʙᴇᴇɴ sᴇɴᴛ ᴛᴏ ʏᴏᴜʀ ɴᴇᴡ ɴᴜᴍʙᴇʀ ᴠɪᴀ 𝐒𝐌𝐒 / 𝐓ᴇʟᴇɢʀᴀᴍ.</i>\n\n"
                       f"👉 <b>𝐏ʟᴇᴀsᴇ ᴛʏᴘᴇ ᴀɴᴅ sᴇɴᴅ ᴛʜᴇ 𝐎𝐓𝐏 ᴄᴏᴅᴇ ʜᴇʀᴇ ɴᴏᴡ:</b></blockquote>")
                btns = [[style_btn("❌ 𝐂ᴀɴᴄᴇʟ 𝐍ᴜᴍʙᴇʀ 𝐂ʜᴀɴɢᴇ", f"back_to_order|{orig_phone}", "danger", icon=6129888444245089008)]]
                await loading.edit(msg, buttons=btns)
            except PhoneNumberOccupiedError:
                await loading.edit(f"<blockquote>{P_NO} <b>❌ 𝐍ᴜᴍʙᴇʀ 𝐀ʟʀᴇᴀᴅʏ 𝐔sᴇᴅ!</b>\n\n𝐓ʜᴇ ɴᴜᴍʙᴇʀ <code>{new_phone}</code> ɪs ᴀʟʀᴇᴀᴅʏ ʀᴇɢɪsᴛᴇʀᴇᴅ ᴏɴ 𝐓ᴇʟᴇɢʀᴀᴍ.\n𝐏ʟᴇᴀsᴇ ᴜsᴇ ᴀ ɴᴜᴍʙᴇʀ ᴛʜᴀᴛ ᴅᴏᴇs ɴᴏᴛ ʜᴀᴠᴇ ᴀ 𝐓ᴇʟᴇɢʀᴀᴍ ᴀᴄᴄᴏᴜɴᴛ, ᴏʀ ᴅᴇʟᴇᴛᴇ ᴛʜᴀᴛ ᴀᴄᴄᴏᴜɴᴛ ғɪʀsᴛ.</blockquote>", buttons=[[style_btn("🔙 𝐁ᴀᴄᴋ ᴛᴏ 𝐎ʀᴅᴇʀ", f"back_to_order|{orig_phone}", "primary", icon=6129812419028982717)]])
            except FreshChangePhoneForbiddenError:
                await loading.edit(f"<blockquote>{P_NO} <b>❌ 𝐂ᴀɴɴᴏᴛ 𝐂ʜᴀɴɢᴇ 𝐍ᴜᴍʙᴇʀ 𝐘ᴇᴛ</b>\n\n𝐓ᴇʟᴇɢʀᴀᴍ sᴇᴄᴜʀɪᴛʏ ʀᴇǫᴜɪʀᴇs ɴᴇᴡ 𝐬𝐞𝐬𝐬𝐢𝐨𝐧𝐬 ᴛᴏ ᴡᴀɪᴛ ʙᴇғᴏʀᴇ ᴄʜᴀɴɢɪɴɢ ɴᴜᴍʙᴇʀs.\n𝐏ʟᴇᴀsᴇ ʟᴏɢɪɴ ᴠɪᴀ ᴛʜᴇ ɴᴏʀᴍᴀʟ 𝐎𝐓𝐏 ғɪʀsᴛ.</blockquote>", buttons=[[style_btn("🔙 𝐁ᴀᴄᴋ ᴛᴏ 𝐎ʀᴅᴇʀ", f"back_to_order|{orig_phone}", "primary", icon=6129812419028982717)]])
            except Exception as ex:
                logger.error(f"SendChangePhoneCode error: {ex}")
                await loading.edit(f"<blockquote>{P_NO} <b>❌ 𝐄ʀʀᴏʀ:</b> {str(ex)}</blockquote>", buttons=[[style_btn("🔙 𝐁ᴀᴄᴋ ᴛᴏ 𝐎ʀᴅᴇʀ", f"back_to_order|{orig_phone}", "primary", icon=6129812419028982717)]])

        elif stage == 'await_otp':
            orig_phone = state['orig_phone']
            new_phone = state['new_phone']
            phone_code_hash = state['phone_code_hash']
            
            if orig_phone not in active_orders:
                change_number_state.pop(uid, None)
                return await e.reply("⚠️ Order expired or completed.")
                
            otp_code = re.sub(r"\D", "", (e.text or "").strip())
            if not otp_code or len(otp_code) < 4:
                return await e.reply(f"{P_NO} <b>Invalid OTP!</b> Please send the numeric code received on your phone.")
                
            order = active_orders[orig_phone]
            client = order['client']
            loading = await e.reply("⏳ <i>Verifying code and changing phone number...</i>")
            
            try:
                await client(ChangePhoneRequest(
                    phone_number=new_phone,
                    phone_code_hash=phone_code_hash,
                    phone_code=otp_code
                ))
                
                change_number_state.pop(uid, None)
                order['paid'] = True
                
                async with get_user_lock(uid):
                    cur.execute("INSERT INTO orders (user_id, country, year, price, phone, otp) VALUES (?,?,?,?,?,?)", 
                                (uid, order['country'], order['year'], order['price'], new_phone, f"Migrated from {orig_phone}"))
                    cur.execute("DELETE FROM stock WHERE phone=?", (orig_phone,))
                    db.commit()
                    
                    from config import LOG_CHANNELS
                    for ch in LOG_CHANNELS:
                        try:
                            admin_log = (f"<blockquote><b>🛍️ 𝐍ᴇᴡ 𝐏ᴜʀᴄʜᴀsᴇ (𝐍ᴜᴍʙᴇʀ 𝐌ɪɢʀᴀᴛᴇᴅ)</b>\n\n"
                                         f"👤 <b>𝐔sᴇᴅ 𝐁ʏ:</b> <code>{uid}</code>\n"
                                         f"📱 <b>𝐎ʀɪɢɪɴᴀʟ:</b> <code>+{orig_phone}</code>\n"
                                         f"🔄 <b>𝐍ᴇᴡ 𝐍ᴜᴍʙᴇʀ:</b> <code>{new_phone}</code>\n"
                                         f"{P_FLAG} <b>𝐂ᴏᴜɴᴛʀʏ:</b> {order['c_icon']} {order['country']}\n"
                                         f"{P_MONEY} <b>𝐏ʀɪᴄᴇ:</b> {P_INR}{order['price']}</blockquote>")
                            await bot.send_message(ch, admin_log)
                        except: pass
                
                try: await client.disconnect()
                except: pass
                active_orders.pop(orig_phone, None)
                
                success_msg = (
                    f"<blockquote>{PE_GIFT} <b>🎉 𝐏ʜᴏɴᴇ 𝐍ᴜᴍʙᴇʀ 𝐂ʜᴀɴɢᴇᴅ 𝐒ᴜᴄᴄᴇssғᴜʟʟʏ!</b>\n\n"
                    f"📱 <b>𝐍ᴇᴡ 𝐏ʜᴏɴᴇ:</b> <code>{new_phone}</code>\n"
                    f"{P_FLAG} <b>𝐂ᴏᴜɴᴛʀʏ:</b> {order['c_icon']} {order['country']}\n"
                    f"📆 <b>𝐀ᴄᴄᴏᴜɴᴛ 𝐘ᴇᴀʀ:</b> <b>{order['year']}</b>\n"
                    f"🔐 <b>2𝐅𝐀 𝐏ᴀssᴡᴏʀᴅ:</b> <code>{order['twofa']}</code>\n\n"
                    f"✅ <b>𝐓ʜᴇ ᴀᴄᴄᴏᴜɴᴛ ɪs ɴᴏᴡ 100% ᴍɪɢʀᴀᴛᴇᴅ ᴛᴏ ʏᴏᴜʀ ɴᴇᴡ ɴᴜᴍʙᴇʀ!</b>\n"
                    f"𝐘ᴏᴜ ᴄᴀɴ ɴᴏᴡ ʟᴏɢɪɴ ᴅɪʀᴇᴄᴛʟʏ ᴜsɪɴɢ ʏᴏᴜʀ ᴏᴡɴ ɴᴜᴍʙᴇʀ (<code>{new_phone}</code>).</blockquote>"
                )
                await loading.edit(success_msg, buttons=[[style_btn("🛒 𝐁ᴜʏ 𝐀ɴᴏᴛʜᴇʀ 𝐀ᴄᴄᴏᴜɴᴛ", "buy_menu_main", "primary", icon=5408995930416362034)]])
            except PhoneCodeInvalidError:
                await loading.edit(f"<blockquote>{P_NO} <b>❌ 𝐈ɴᴠᴀʟɪᴅ 𝐎𝐓𝐏 𝐂ᴏᴅᴇ!</b>\n𝐏ʟᴇᴀsᴇ ᴄʜᴇᴄᴋ ᴛʜᴇ ᴄᴏᴅᴇ ᴀɴᴅ sᴇɴᴅ ɪᴛ ᴀɢᴀɪɴ.</blockquote>")
            except PhoneCodeExpiredError:
                change_number_state.pop(uid, None)
                await loading.edit(f"<blockquote>{P_NO} <b>❌ 𝐎𝐓𝐏 𝐄xᴘɪʀᴇᴅ!</b>\n𝐏ʟᴇᴀsᴇ ʀᴇᴛʀʏ ᴄʜᴀɴɢɪɴɢ ɴᴜᴍʙᴇʀ.</blockquote>", buttons=[[style_btn("🔙 𝐁ᴀᴄᴋ ᴛᴏ 𝐎ʀᴅᴇʀ", f"back_to_order|{orig_phone}", "primary", icon=6129812419028982717)]])
            except Exception as ex:
                logger.error(f"ChangePhone error: {ex}")
                await loading.edit(f"<blockquote>{P_NO} <b>❌ 𝐄ʀʀᴏʀ:</b> {str(ex)}</blockquote>", buttons=[[style_btn("🔙 𝐁ᴀᴄᴋ ᴛᴏ 𝐎ʀᴅᴇʀ", f"back_to_order|{orig_phone}", "primary", icon=6129812419028982717)]])
