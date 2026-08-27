import re
import html
import asyncio
from telethon import events, Button
from telethon.errors import MessageNotModifiedError
from database import cur, db, is_admin
from utils.states import get_user_lock
from config import P_INR, P_NO, PE_CHECK, PE_GIFT, logger
from utils.keyboards import style_btn
from utils.smm_client import (
    SMM_SERVERS, get_smm_platforms, get_categories_for_platform,
    get_services_for_category, get_smm_service_details, get_service_inr_rate,
    create_smm_order, get_smm_order_status, PLATFORM_ICONS, PLATFORM_PREMIUM_ICONS
)

# User state dictionary for SMM orders
smm_order_state = {}

# ── Step 1: Select Server ──
async def show_smm_servers(event):
    btns = []
    for s_id, s_info in SMM_SERVERS.items():
        p_icon = 5408995930416362034 if s_id == 1 else 5409320020058584473
        btns.append([style_btn(f"{s_info['name']}", f"smm_srv|{s_id}", "primary", icon=p_icon)])
        
    btns.append([style_btn("🔙 𝐁ᴀᴄᴋ ᴛᴏ 𝐃ᴀsʜʙᴏᴀʀᴅ", b"dashboard_main", "danger", icon=6129812419028982717)])
    
    msg = (f"<blockquote>🚀 <b>𝐒ᴏᴄɪᴀʟ 𝐌ᴇᴅɪᴀ 𝐒ᴇʀᴠɪᴄᴇs (𝐒𝐌𝐌)</b>\n\n"
           f"⚡ <b>𝐅ᴀsᴛ & 𝐈ɴsᴛᴀɴᴛ 𝐃ᴇʟɪᴠᴇʀʏ</b> ғᴏʀ ᴀʟʟ ᴍᴀᴊᴏʀ ᴘʟᴀᴛғᴏʀᴍs.\n\n"
           f"👇 <b>𝐏ʟᴇᴀsᴇ sᴇʟᴇᴄᴛ ᴀ 𝐒ᴇʀᴠᴇʀ ʙᴇʟᴏᴡ:</b></blockquote>")
           
    if isinstance(event, events.CallbackQuery.Event):
        try: await event.edit(msg, buttons=btns)
        except MessageNotModifiedError: pass
    else:
        await event.respond(msg, buttons=btns)

# ── Step 2: Select Platform (Telegram, WhatsApp, Instagram, etc.) ──
async def show_smm_platforms_menu(event, server=1):
    srv = SMM_SERVERS.get(server, SMM_SERVERS[1])
    platforms = await get_smm_platforms(server)
    
    btns = []
    plat_row = []
    for p in platforms:
        p_icon = PLATFORM_PREMIUM_ICONS.get(p, 6129399728506412489)
        plat_row.append(style_btn(f"{p}", f"smm_plat|{server}|{p}|1", "primary", icon=p_icon))
        if len(plat_row) == 2:
            btns.append(plat_row)
            plat_row = []
    if plat_row:
        btns.append(plat_row)
        
    btns.append([style_btn("🔙 𝐁ᴀᴄᴋ ᴛᴏ 𝐒ᴇʀᴠᴇʀs", b"smm_menu_main", "danger", icon=6129812419028982717)])
    
    msg = (f"<blockquote>🌐 <b>{srv['name']} — 𝐒ᴇʟᴇᴄᴛ 𝐏ʟᴀᴛғᴏʀᴍ</b>\n\n"
           f"⚡ <b>𝐀ʟʟ 𝐒ᴏᴄɪᴀʟ 𝐌ᴇᴅɪᴀ 𝐏ʟᴀᴛғᴏʀᴍs 𝐀ᴠᴀɪʟᴀʙʟᴇ</b>\n\n"
           f"👇 <b>𝐏ʟᴇᴀsᴇ ᴄʜᴏᴏsᴇ ᴀ ᴘʟᴀᴛғᴏʀᴍ ᴛᴏ ᴄᴏɴᴛɪɴᴜᴇ:</b></blockquote>")
           
    try: await event.edit(msg, buttons=btns)
    except MessageNotModifiedError: pass

# ── Step 3: Select Category (under Platform) with Pagination ──
async def show_platform_categories(event, server, platform, page):
    limit = 6
    offset = (page - 1) * limit
    cats = await get_categories_for_platform(platform, server)
    total = len(cats)
    page_cats = cats[offset:offset+limit]
    
    if not cats:
        return await event.answer("⚠️ No categories found for this platform.", alert=True)
        
    btns = []
    for i, c_data in enumerate(page_cats):
        real_idx = offset + i
        c_name = c_data['name']
        c_count = c_data['count']
        short_name = c_name[:28] + '..' if len(c_name) > 30 else c_name
        btns.append([style_btn(f"📁 {short_name} ({c_count})", f"smm_cat|{server}|{platform}|{real_idx}|1", "primary")])
        
    nav = []
    if page > 1:
        nav.append(style_btn("⬅️ 𝐏ʀᴇᴠ", f"smm_plat|{server}|{platform}|{page-1}", "primary", icon=6129627894349045589))
    if offset + limit < total:
        nav.append(style_btn("𝐍ᴇxᴛ ➡️", f"smm_plat|{server}|{platform}|{page+1}", "primary", icon=6129732880529628243))
    if nav:
        btns.append(nav)
        
    btns.append([style_btn("🔙 𝐁ᴀᴄᴋ ᴛᴏ 𝐏ʟᴀᴛғᴏʀᴍs", f"smm_srv|{server}", "danger", icon=6129812419028982717)])
    
    total_pages = max(1, (total + limit - 1) // limit)
    icon = PLATFORM_ICONS.get(platform, '🌐')
    msg = (f"<blockquote>{icon} <b>𝐒ᴇʟᴇᴄᴛ 𝐂ᴀᴛᴇɢᴏʀʏ ғᴏʀ {platform}:</b>\n\n"
           f"📄 <b>𝐏ᴀɢᴇ:</b> <code>{page}/{total_pages}</code> (𝐓ᴏᴛᴀʟ: {total} ᴄᴀᴛᴇɢᴏʀɪᴇs)</blockquote>")
           
    try: await event.edit(msg, buttons=btns)
    except MessageNotModifiedError: pass

# ── Step 4: Select Service (under Category) with Pagination ──
async def show_category_services(event, server, platform, cat_idx, page):
    cats = await get_categories_for_platform(platform, server)
    if cat_idx >= len(cats):
        return await event.answer("⚠️ Category not found.", alert=True)
        
    cat_name = cats[cat_idx]['name']
    services = await get_services_for_category(cat_name, server)
    total = len(services)
    
    limit = 6
    offset = (page - 1) * limit
    page_services = services[offset:offset+limit]
    
    btns = []
    for s in page_services:
        s_id = s.get('service')
        s_name = s.get('name', 'Service')
        rate_inr = get_service_inr_rate(s, server)
        short_name = s_name[:26] + '..' if len(s_name) > 28 else s_name
        btns.append([style_btn(f"{short_name} — {P_INR}{rate_inr}/1k", f"smm_srv_info|{server}|{platform}|{cat_idx}|{s_id}", "primary")])
        
    nav = []
    if page > 1:
        nav.append(style_btn("⬅️ 𝐏ʀᴇᴠ", f"smm_cat|{server}|{platform}|{cat_idx}|{page-1}", "primary", icon=6129627894349045589))
    if offset + limit < total:
        nav.append(style_btn("𝐍ᴇxᴛ ➡️", f"smm_cat|{server}|{platform}|{cat_idx}|{page+1}", "primary", icon=6129732880529628243))
    if nav:
        btns.append(nav)
        
    btns.append([style_btn("🔙 𝐁ᴀᴄᴋ ᴛᴏ 𝐂ᴀᴛᴇɢᴏʀɪᴇs", f"smm_plat|{server}|{platform}|1", "danger", icon=6129812419028982717)])
    
    total_pages = max(1, (total + limit - 1) // limit)
    msg = (f"<blockquote>📁 <b>𝐂ᴀᴛᴇɢᴏʀʏ:</b> <code>{html.escape(cat_name)}</code>\n\n"
           f"📄 <b>𝐏ᴀɢᴇ:</b> <code>{page}/{total_pages}</code> (𝐓ᴏᴛᴀʟ: {total} sᴇʀᴠɪᴄᴇs)\n"
           f"👇 <b>𝐒ᴇʟᴇᴄᴛ ᴀ sᴇʀᴠɪᴄᴇ ᴛᴏ ᴠɪᴇᴡ ᴅᴇᴛᴀɪʟs & ᴏʀᴅᴇʀ:</b></blockquote>")
           
    try: await event.edit(msg, buttons=btns)
    except MessageNotModifiedError: pass

# ── Step 5: Service Overview Card ──
async def show_service_card(event, server, platform, cat_idx, service_id):
    s = await get_smm_service_details(service_id, server)
    if not s:
        return await event.answer("❌ Service details unavailable.", alert=True)
        
    s_name = s.get('name', 'Service')
    rate_inr = get_service_inr_rate(s, server)
    min_q = s.get('min', 10)
    max_q = s.get('max', 100000)
    desc = s.get('desc', '') or s.get('description', '')
    desc_text = f"\n📝 <b>𝐃ᴇsᴄʀɪᴘᴛɪᴏɴ:</b>\n<i>{html.escape(desc[:200])}</i>\n" if desc else ""
    
    msg = (f"<blockquote>🚀 <b>𝐒𝐌𝐌 𝐒ᴇʀᴠɪᴄᴇ 𝐃ᴇᴛᴀɪʟs</b>\n\n"
           f"🏷️ <b>𝐒ᴇʀᴠɪᴄᴇ:</b> <code>{html.escape(s_name)}</code>\n"
           f"🆔 <b>𝐒ᴇʀᴠɪᴄᴇ 𝐈𝐃:</b> <code>{service_id}</code>\n"
           f"💰 <b>𝐑ᴀᴛᴇ / 1,000:</b> <code>{P_INR}{rate_inr}</code>\n"
           f"📊 <b>𝐌ɪɴ / 𝐌ᴀx:</b> <code>{min_q} - {max_q}</code>{desc_text}</blockquote>")
           
    btns = [
        [style_btn("🛒 𝐎ʀᴅᴇʀ 𝐍ᴏᴡ", f"smm_ord_start|{server}|{platform}|{cat_idx}|{service_id}", "success", icon=5408995930416362034)],
        [style_btn("🔙 𝐁ᴀᴄᴋ ᴛᴏ 𝐒ᴇʀᴠɪᴄᴇs", f"smm_cat|{server}|{platform}|{cat_idx}|1", "danger", icon=6129812419028982717)]
    ]
    
    try: await event.edit(msg, buttons=btns)
    except MessageNotModifiedError: pass

def register_smm(bot):
    @bot.on(events.CallbackQuery(pattern=b"^smm_menu_main$"))
    async def cb_smm_main(e):
        await show_smm_servers(e)
        
    @bot.on(events.CallbackQuery(pattern=r"^smm_srv\|(\d+)$"))
    async def cb_smm_srv(e):
        srv_id = int(e.pattern_match.group(1).decode())
        await show_smm_platforms_menu(e, server=srv_id)
        
    @bot.on(events.CallbackQuery(pattern=r"^smm_plat\|(\d+)\|([^|]+)\|(\d+)$"))
    async def cb_smm_plat(e):
        p = e.pattern_match
        server = int(p.group(1).decode())
        platform = p.group(2).decode()
        page = int(p.group(3).decode())
        await show_platform_categories(e, server, platform, page)
        
    @bot.on(events.CallbackQuery(pattern=r"^smm_cat\|(\d+)\|([^|]+)\|(\d+)\|(\d+)$"))
    async def cb_smm_cat(e):
        p = e.pattern_match
        server = int(p.group(1).decode())
        platform = p.group(2).decode()
        cat_idx = int(p.group(3).decode())
        page = int(p.group(4).decode())
        await show_category_services(e, server, platform, cat_idx, page)
        
    @bot.on(events.CallbackQuery(pattern=r"^smm_srv_info\|(\d+)\|([^|]+)\|(\d+)\|(\d+)$"))
    async def cb_smm_srv_info(e):
        p = e.pattern_match
        server = int(p.group(1).decode())
        platform = p.group(2).decode()
        cat_idx = int(p.group(3).decode())
        service_id = int(p.group(4).decode())
        await show_service_card(e, server, platform, cat_idx, service_id)
        
    @bot.on(events.CallbackQuery(pattern=r"^smm_ord_start\|(\d+)\|([^|]+)\|(\d+)\|(\d+)$"))
    async def cb_smm_ord_start(e):
        p = e.pattern_match
        uid = e.sender_id
        server = int(p.group(1).decode())
        platform = p.group(2).decode()
        cat_idx = int(p.group(3).decode())
        service_id = int(p.group(4).decode())
        
        s = await get_smm_service_details(service_id, server)
        if not s:
            return await e.answer("❌ Service details unavailable.", alert=True)
            
        smm_order_state[uid] = {
            'stage': 'await_link',
            'server': server,
            'platform': platform,
            'cat_idx': cat_idx,
            'service_id': service_id,
            'service': s,
            'msg_id': e.message_id
        }
        
        msg = (f"<blockquote>🔗 <b>𝐏ʟᴇᴀsᴇ sᴇɴᴅ ᴛʜᴇ ᴛᴀʀɢᴇᴛ 𝐋ɪɴᴋ:</b>\n"
               f"<i>(ᴇ.ɢ., 𝐏ʀᴏғɪʟᴇ 𝐔𝐑𝐋, 𝐏ᴏsᴛ 𝐔𝐑𝐋, 𝐂ʜᴀɴɴᴇʟ 𝐋ɪɴᴋ)</i></blockquote>")
        btns = [[style_btn("❌ 𝐂ᴀɴᴄᴇʟ", "smm_cancel", "danger", icon=6129888444245089008)]]
        try: await e.edit(msg, buttons=btns)
        except MessageNotModifiedError: pass

    @bot.on(events.CallbackQuery(pattern=b"^smm_cancel$"))
    async def cb_smm_cancel(e):
        uid = e.sender_id
        state = smm_order_state.pop(uid, None)
        if state:
            server = state.get('server', 1)
            platform = state.get('platform', 'Telegram')
            cat_idx = state.get('cat_idx', 0)
            service_id = state.get('service_id')
            await show_service_card(e, server, platform, cat_idx, service_id)
        else:
            await show_smm_servers(e)

    @bot.on(events.NewMessage(func=lambda e: e.sender_id in smm_order_state and not e.text.startswith('/')))
    async def msg_smm_order_inputs(e):
        uid = e.sender_id
        state = smm_order_state.get(uid)
        if not state: return
        
        stage = state.get('stage')
        text = (e.text or "").strip()
        
        if stage == 'await_link':
            if len(text) < 3 or (" " in text and not text.startswith("http") and not text.startswith("@") and not text.startswith("t.me")):
                return await e.reply(f"{P_NO} <b>Invalid link!</b> Please send a valid link or @username.")
                
            state['link'] = text
            state['stage'] = 'await_qty'
            s = state['service']
            min_q = s.get('min', 10)
            max_q = s.get('max', 100000)
            
            msg = (f"<blockquote>🔢 <b>𝐄ɴᴛᴇʀ 𝐐ᴜᴀɴᴛɪᴛʏ:</b>\n"
                   f"<i>(𝐌ɪɴ: <code>{min_q}</code> | 𝐌ᴀx: <code>{max_q}</code>)</i></blockquote>")
            btns = [[style_btn("❌ 𝐂ᴀɴᴄᴇʟ", "smm_cancel", "danger", icon=6129888444245089008)]]
            await e.reply(msg, buttons=btns)
            
        elif stage == 'await_qty':
            if not text.isdigit():
                return await e.reply(f"{P_NO} <b>Invalid quantity!</b> Please send numeric digits only.")
                
            qty = int(text)
            s = state['service']
            min_q = int(s.get('min', 10))
            max_q = int(s.get('max', 100000))
            
            if qty < min_q or qty > max_q:
                return await e.reply(f"{P_NO} <b>Quantity out of range!</b>\nMust be between <code>{min_q}</code> and <code>{max_q}</code>.")
                
            server = state['server']
            rate_inr = get_service_inr_rate(s, server)
            total_price = max(1.0, round((rate_inr * qty) / 1000, 2))
            
            state['qty'] = qty
            state['total_price'] = total_price
            state['stage'] = 'confirm'
            
            msg = (f"<blockquote>🧾 <b>𝐂ᴏɴғɪʀᴍ 𝐒𝐌𝐌 𝐎ʀᴅᴇʀ</b>\n\n"
                   f"🚀 <b>𝐒ᴇʀᴠɪᴄᴇ:</b> <code>{html.escape(s.get('name', ''))}</code>\n"
                   f"🔗 <b>𝐋ɪɴᴋ:</b> <code>{html.escape(state['link'])}</code>\n"
                   f"🔢 <b>𝐐ᴜᴀɴᴛɪᴛʏ:</b> <code>{qty}</code>\n"
                   f"💰 <b>𝐓ᴏᴛᴀʟ 𝐏ʀɪᴄᴇ:</b> <code>{P_INR}{total_price}</code>\n\n"
                   f"<b>𝐀ʀᴇ ʏᴏᴜ sᴜʀᴇ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ ᴘʟᴀᴄᴇ ᴛʜɪs ᴏʀᴅᴇʀ?</b></blockquote>")
                   
            btns = [
                [style_btn("✅ 𝐂ᴏɴғɪʀᴍ & 𝐏ᴀʏ", "smm_ord_confirm", "success", icon=5409320020058584473)],
                [style_btn("❌ 𝐂ᴀɴᴄᴇʟ", "smm_cancel", "danger", icon=6129888444245089008)]
            ]
            await e.reply(msg, buttons=btns)

    @bot.on(events.CallbackQuery(pattern=b"^smm_ord_confirm$"))
    async def cb_smm_ord_confirm(e):
        uid = e.sender_id
        state = smm_order_state.pop(uid, None)
        if not state or 'qty' not in state:
            return await e.answer("⚠️ Session expired. Please start over.", alert=True)
            
        total_price = state['total_price']
        service_id = state['service_id']
        link = state['link']
        qty = state['qty']
        server = state['server']
        s = state['service']
        
        async with get_user_lock(uid):
            bal_row = cur.execute("SELECT balance FROM users WHERE user_id=?", (uid,)).fetchone()
            if not bal_row or bal_row[0] < total_price:
                return await e.answer(f"❌ Insufficient Balance! Required: ₹{total_price}, Balance: ₹{bal_row[0] if bal_row else 0}", alert=True)
                
            cur.execute("UPDATE users SET balance = balance - ? WHERE user_id=? AND balance >= ?", (total_price, uid, total_price))
            db.commit()
            
        loading = await e.reply("⏳ <i>Submitting order to SMM Server...</i>")
        api_res = await create_smm_order(service_id, link, qty, server)
        
        if api_res and 'order' in api_res:
            smm_order_id = str(api_res['order'])
            cur.execute("INSERT INTO smm_orders (user_id, server, service_id, service_name, target_link, quantity, price, smm_order_id, status) VALUES (?,?,?,?,?,?,?,?,?)",
                        (uid, server, service_id, s.get('name', ''), link, qty, total_price, smm_order_id, 'Processing'))
            db.commit()
            
            from database import get_log_channels_db
            for ch in get_log_channels_db():
                try:
                    admin_log = (f"<blockquote><b>🚀 𝐍ᴇᴡ 𝐒𝐌𝐌 𝐎ʀᴅᴇʀ</b>\n\n"
                                 f"👤 <b>𝐔sᴇʀ:</b> <code>{uid}</code>\n"
                                 f"🆔 <b>𝐒𝐌𝐌 𝐎ʀᴅᴇʀ 𝐈𝐃:</b> <code>#{smm_order_id}</code>\n"
                                 f"🏷️ <b>𝐒ᴇʀᴠɪᴄᴇ:</b> {html.escape(s.get('name', ''))}\n"
                                 f"🔗 <b>𝐋ɪɴᴋ:</b> <code>{html.escape(link)}</code>\n"
                                 f"🔢 <b>𝐐ᴜᴀɴᴛɪᴛʏ:</b> <code>{qty}</code>\n"
                                 f"💰 <b>𝐏ʀɪᴄᴇ:</b> {P_INR}{total_price}</blockquote>")
                    await bot.send_message(ch, admin_log)
                except: pass
                
            msg = (f"<blockquote>{PE_CHECK} <b>🎉 𝐒𝐌𝐌 𝐎ʀᴅᴇʀ 𝐏ʟᴀᴄᴇᴅ 𝐒ᴜᴄᴄᴇssғᴜʟʟʏ!</b>\n\n"
                   f"🆔 <b>𝐎ʀᴅᴇʀ 𝐈𝐃:</b> <code>#{smm_order_id}</code>\n"
                   f"🚀 <b>𝐒ᴇʀᴠɪᴄᴇ:</b> <code>{html.escape(s.get('name', ''))}</code>\n"
                   f"🔗 <b>𝐋ɪɴᴋ:</b> <code>{html.escape(link)}</code>\n"
                   f"🔢 <b>𝐐ᴜᴀɴᴛɪᴛʏ:</b> <code>{qty}</code>\n"
                   f"💰 <b>𝐀ᴍᴏᴜɴᴛ 𝐃ᴇᴅᴜᴄᴛᴇᴅ:</b> <code>{P_INR}{total_price}</code>\n"
                   f"📊 <b>𝐒ᴛᴀᴛᴜs:</b> <code>Processing</code></blockquote>")
                   
            btns = [
                [style_btn("🚀 𝐁ᴜʏ 𝐌ᴏʀᴇ 𝐒ᴇʀᴠɪᴄᴇs", b"smm_menu_main", "primary", icon=5408995930416362034)],
                [style_btn("🔙 𝐌ᴀɪɴ 𝐌ᴇɴᴜ", b"dashboard_main", "danger", icon=6129812419028982717)]
            ]
            await loading.edit(msg, buttons=btns)
        else:
            # SMM Order failed -> refund user
            err_msg = api_res.get('error', 'API submission failed')
            cur.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (total_price, uid))
            db.commit()
            await loading.edit(f"<blockquote>{P_NO} <b>❌ 𝐎ʀᴅᴇʀ 𝐅ᴀɪʟᴇᴅ!</b>\n\n{html.escape(str(err_msg))}\n\n𝐘ᴏᴜʀ ᴍᴏɴᴇʏ (<b>{P_INR}{total_price}</b>) ʜᴀs ʙᴇᴇɴ <b>ʀᴇғᴜɴᴅᴇᴅ</b>.</blockquote>", buttons=[[style_btn("🔙 𝐁ᴀᴄᴋ ᴛᴏ 𝐒𝐌𝐌", b"smm_menu_main", "primary")]])
