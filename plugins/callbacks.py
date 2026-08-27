import os
from telethon import events, Button
from telethon.errors import MessageNotModifiedError
from database import cur, db, get_support_url, to_usd, get_flag_by_country_name, is_admin, get_bot_mode
from config import P_NO, P_MONEY, P_INR, P_GIFT, P_USERS, PE_LOCATION, PE_GIFT, PE_CROWN
from utils.states import session_buy_state, deposit_input, active_orders, waiting_proof
from plugins.start import send_main_menu
from utils.helpers import check_channel_joined
from utils.keyboards import style_btn
from utils.lzt import COUNTRY_TO_LZT

async def send_stock_page(event, page=1):
    bot_mode = get_bot_mode()
    limit = 10
    offset = (page - 1) * limit

    if bot_mode == 'manual':
        rows = cur.execute("SELECT country_name, COUNT(*) FROM stock WHERE available=1 GROUP BY country_name ORDER BY country_name").fetchall()
        if not rows:
            msg = f"<blockquote>{PE_LOCATION} <b>𝐒ᴛᴏᴄᴋ</b></blockquote>\n\n<blockquote>𝐍ᴏ sᴛᴏᴄᴋ ᴀᴠᴀɪʟᴀʙʟᴇ ʀɪɢʜᴛ ɴᴏᴡ.</blockquote>"
            if isinstance(event, events.CallbackQuery.Event):
                try: return await event.edit(msg)
                except MessageNotModifiedError: return
            return await event.respond(msg)
        
        total_countries = len(rows)
        total_stock = sum(c for _, c in rows)
        page_items = rows[offset:offset+limit]
        total_pages = (total_countries + limit - 1) // limit

        msg = f"<blockquote>{PE_LOCATION} <b>𝐀ᴠᴀɪʟᴀʙʟᴇ 𝐒ᴛᴏᴄᴋ</b> ({total_stock} ᴛᴏᴛᴀʟ) — 𝐏ᴀɢᴇ {page}/{total_pages}</blockquote>\n\n"
        for cn, cnt in page_items:
            flag = get_flag_by_country_name(cn)
            msg += f"<blockquote>{flag} <b>{cn}</b> — {cnt} ᴀᴄᴄᴏᴜɴᴛs</blockquote>\n"

    elif bot_mode == 'panel':
        all_c = sorted(list(COUNTRY_TO_LZT.keys()))
        try:
            customs = cur.execute("SELECT name FROM custom_countries").fetchall()
            for (c,) in customs:
                if c not in all_c: all_c.append(c)
        except: pass
        all_c.sort()

        total_countries = len(all_c)
        page_items = all_c[offset:offset+limit]
        total_pages = (total_countries + limit - 1) // limit

        msg = f"<blockquote>{PE_LOCATION} <b>𝐀ᴠᴀɪʟᴀʙʟᴇ 𝐒ᴛᴏᴄᴋ</b> (2,000+ ᴛᴏᴛᴀʟ) — 𝐏ᴀɢᴇ {page}/{total_pages}</blockquote>\n\n"
        for cn in page_items:
            flag = get_flag_by_country_name(cn)
            msg += f"<blockquote>{flag} <b>{cn}</b> — 40+ ᴀᴄᴄᴏᴜɴᴛs</blockquote>\n"

    else: # Hybrid mode
        all_c = sorted(list(COUNTRY_TO_LZT.keys()))
        try:
            customs = cur.execute("SELECT name FROM custom_countries").fetchall()
            for (c,) in customs:
                if c not in all_c: all_c.append(c)
        except: pass
        all_c.sort()

        local_counts = dict(cur.execute("SELECT country_name, COUNT(*) FROM stock WHERE available=1 GROUP BY country_name").fetchall())
        total_countries = len(all_c)
        page_items = all_c[offset:offset+limit]
        total_pages = (total_countries + limit - 1) // limit

        msg = f"<blockquote>{PE_LOCATION} <b>𝐀ᴠᴀɪʟᴀʙʟᴇ 𝐒ᴛᴏᴄᴋ</b> (2,000+ ᴛᴏᴛᴀʟ) — 𝐏ᴀɢᴇ {page}/{total_pages}</blockquote>\n\n"
        for cn in page_items:
            flag = get_flag_by_country_name(cn)
            if cn in local_counts and local_counts[cn] > 0:
                msg += f"<blockquote>{flag} <b>{cn}</b> — {local_counts[cn]} ᴀᴄᴄᴏᴜɴᴛs</blockquote>\n"
            else:
                msg += f"<blockquote>{flag} <b>{cn}</b> — 40+ ᴀᴄᴄᴏᴜɴᴛs</blockquote>\n"

    nav = []
    if page > 1:
        nav.append(style_btn("⬅️ 𝐏ʀᴇᴠ", f"stk_pg|{page-1}", "primary", icon=6129627894349045589))
    if offset + limit < total_countries:
        nav.append(style_btn("𝐍ᴇxᴛ ➡️", f"stk_pg|{page+1}", "primary", icon=6129732880529628243))

    btns = [nav] if nav else None

    if isinstance(event, events.CallbackQuery.Event):
        try: await event.edit(msg, buttons=btns)
        except MessageNotModifiedError: pass
    else:
        await event.respond(msg, buttons=btns)

async def show_more_menu(event):
    pct_row = cur.execute("SELECT value FROM settings WHERE key='ref_percent'").fetchone()
    pct = pct_row[0] if pct_row else "3"
    
    from config import TERMS_URL
    from database import get_support_url
    
    msg = (f"<blockquote>💬 <b>𝐌ᴏʀᴇ 𝐎ᴘᴛɪᴏɴs & 𝐓ᴏᴏʟs</b>\n\n"
           f"🎁 <b>𝐑ᴇғᴇʀ & 𝐄ᴀʀɴ:</b> 𝐄ᴀʀɴ {pct}% ᴏғ ᴀʟʟ ғʀɪᴇɴᴅ ᴅᴇᴘᴏsɪᴛs!\n"
           f"📊 <b>𝐋ɪᴠᴇ 𝐒ᴛᴏᴄᴋ:</b> 𝐕ɪᴇᴡ ᴀᴠᴀɪʟᴀʙʟᴇ ᴀᴄᴄᴏᴜɴᴛs ᴀᴄʀᴏss ᴀʟʟ ᴄᴏᴜɴᴛʀɪᴇs.\n"
           f"📜 <b>𝐓ᴇʀᴍs & 𝐑ᴜʟᴇs:</b> 𝐑ᴇᴀᴅ ᴏᴜʀ sᴇʀᴠɪᴄᴇ ᴛᴇʀᴍs.</blockquote>")
           
    btns = [
        [style_btn("🎁 Refer & Earn", b"view_referrals", "success", icon=5354889508674360491)],
        [style_btn("📊 Live Stock", b"stk_pg|1", "primary", icon=6129627894349045589)],
        [Button.url("📜 Terms & Conditions", TERMS_URL)],
        [Button.url("📩 Support", get_support_url())],
        [style_btn("🔙 𝐁ᴀᴄᴋ ᴛᴏ 𝐌ᴇɴᴜ", b"buy_menu_main", "danger", icon=6129812419028982717)]
    ]
    try: await event.edit(msg, buttons=btns)
    except MessageNotModifiedError: pass

def register_callbacks(bot):
    @bot.on(events.CallbackQuery(pattern=b"^more_menu$"))
    async def cb_more_menu(e):
        await show_more_menu(e)

    @bot.on(events.CallbackQuery(pattern=r"^stk_pg\|(\d+)$"))
    async def cb_stk_pg(e):
        page = int(e.pattern_match.group(1).decode())
        await send_stock_page(e, page)

    @bot.on(events.NewMessage(pattern=r"(?i)^(📊 𝐒ᴛᴏᴄᴋ|📊 Stock)$"))
    async def msg_stock(e):
        await send_stock_page(e, 1)

    @bot.on(events.CallbackQuery(pattern=b"^tc_accept$"))
    async def cb_tc_accept(e):
        uid = e.sender_id
        cur.execute("UPDATE users SET terms_accepted=1 WHERE user_id=?", (uid,))
        db.commit()
        await e.answer("✅ Terms Accepted!", alert=True)
        await e.delete()
        await send_main_menu(bot, e, uid)

    @bot.on(events.CallbackQuery(pattern=b"^tc_reject$"))
    async def cb_tc_reject(e):
        try: await e.edit(f"{P_NO} You cannot use the bot without accepting the terms.")
        except MessageNotModifiedError: pass

    @bot.on(events.CallbackQuery(pattern=b"^cancel_action$"))
    async def cb_cancel_action(e):
        uid = e.sender_id
        deposit_input.pop(uid, None)
        session_buy_state.pop(uid, None)
        waiting_proof.pop(uid, None)
        try: await e.delete()
        except Exception: pass
        await e.answer("Cancelled", alert=False)

    @bot.on(events.CallbackQuery(pattern=b"^verify_join$"))
    async def cb_verify_join(e):
        uid = e.sender_id
        from utils.helpers import get_unjoined_channels
        from utils.keyboards import style_btn
        from config import PE_FLOWER, PE_LOCATION

        unjoined = await get_unjoined_channels(bot, uid)
        
        if not unjoined:
            # All channels joined!
            await e.answer("✅ Verification successful!", alert=True)
            row = cur.execute("SELECT terms_accepted FROM users WHERE user_id=?", (uid,)).fetchone()
            terms_acc = row[0] if row else 0
            if not terms_acc:
                from utils.keyboards import get_terms_buttons
                msg = f"<blockquote>{PE_FLOWER} <b>𝐓ᴇʀᴍs & 𝐂ᴏɴᴅɪᴛɪᴏɴs</b></blockquote>\n<blockquote>𝐏ʟᴇᴀsᴇ ʀᴇᴀᴅ ᴀɴᴅ ᴀᴄᴄᴇᴘᴛ ᴏᴜʀ 𝐓ᴇʀᴍs & 𝐂ᴏɴᴅɪᴛɪᴏɴs ʙᴇғᴏʀᴇ ᴜsɪɴɢ ᴛʜᴇ ʙᴏᴛ.</blockquote>"
                try: await e.edit(msg, buttons=get_terms_buttons())
                except MessageNotModifiedError: pass
            else:
                await e.delete()
                await send_main_menu(bot, e, uid)
        else:
            # Show only unjoined channels
            remaining = len(unjoined)
            await e.answer(f"❌ {remaining} channel(s)/group(s) not joined yet!", alert=True)
            buttons = []
            for url, idx in unjoined:
                btn_label = "💬 𝐉ᴏɪɴ 𝐆ʀᴏᴜᴘ" if ("+" in url or "joinchat" in url or idx == 2) else "📢 𝐉ᴏɪɴ 𝐂ʜᴀɴɴᴇʟ"
                buttons.append([Button.url(btn_label, url)])
            buttons.append([style_btn("𝐕ᴇʀɪғʏ 𝐉ᴏɪɴᴇᴅ", b"verify_join", "success", icon=6129627894349045589)])
            msg = f"<blockquote>{PE_FLOWER} <b>𝐘ᴏᴜ ᴍᴜsᴛ ᴊᴏɪɴ ᴏᴜʀ ᴄʜᴀɴɴᴇʟs & ɢʀᴏᴜᴘ ғɪʀsᴛ!</b></blockquote>\n<blockquote>{PE_LOCATION} {remaining} ᴄʜᴀɴɴᴇʟ(s)/ɢʀᴏᴜᴘ(s) ʀᴇᴍᴀɪɴɪɴɢ. 𝐉ᴏɪɴ ᴀɴᴅ ᴛᴀᴘ <b>𝐕ᴇʀɪғʏ 𝐉ᴏɪɴᴇᴅ</b>.</blockquote>"
            try: await e.edit(msg, buttons=buttons)
            except MessageNotModifiedError: pass

    # ── Keyboard Button Handlers ──

    @bot.on(events.NewMessage(pattern=r"(?i)^(📦 𝐌ʏ 𝐎ʀᴅᴇʀs|📦 My Orders)$"))
    async def msg_my_orders(e):
        uid = e.sender_id
        rows = cur.execute("SELECT phone, country, price, date FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 10", (uid,)).fetchall()
        if not rows:
            return await e.respond(f"<blockquote>{PE_GIFT} <b>𝐌ʏ 𝐎ʀᴅᴇʀs</b></blockquote>\n\n<blockquote>𝐍ᴏ ᴏʀᴅᴇʀs ʏᴇᴛ. 𝐁ᴜʏ ʏᴏᴜʀ ғɪʀsᴛ ᴀᴄᴄᴏᴜɴᴛ!</blockquote>")
        msg = f"<blockquote>{PE_GIFT} <b>𝐌ʏ 𝐎ʀᴅᴇʀs</b> (𝐋ᴀsᴛ 10)</blockquote>\n\n"
        for ph, cn, pr, dt in rows:
            flag = get_flag_by_country_name(cn)
            msg += f"<blockquote>{flag} {cn} | <code>{ph}</code>\n{P_MONEY} {P_INR}{pr} | 📅 {dt[:10]}</blockquote>\n"
        await e.respond(msg)

    @bot.on(events.NewMessage(pattern=r"(?i)^(💰 𝐁ᴀʟᴀɴᴄᴇ|💰 Balance)$"))
    async def msg_balance(e):
        uid = e.sender_id
        row = cur.execute("SELECT balance FROM users WHERE user_id=?", (uid,)).fetchone()
        bal = row[0] if row else 0
        msg = (f"<blockquote>{PE_CROWN} <b>𝐘ᴏᴜʀ 𝐁ᴀʟᴀɴᴄᴇ</b></blockquote>\n\n"
               f"<blockquote>{P_MONEY} <b>𝐁ᴀʟᴀɴᴄᴇ:</b> <code>{P_INR}{bal}</code>\n"
               f"💲 <b>𝐔𝐒𝐃:</b> <code>${to_usd(bal):.2f}</code></blockquote>")
        await e.respond(msg)


    @bot.on(events.NewMessage(pattern=r"(?i)^(🎁 𝐑ᴇғᴇʀ|🎁 Refer)$"))
    async def msg_refer(e):
        uid = e.sender_id
        me = await bot.get_me()
        bot_username = me.username or ""
        ref_link = f"https://t.me/{bot_username}?start=ref_{uid}"
        ref_count = cur.execute("SELECT COUNT(*) FROM users WHERE referred_by=?", (uid,)).fetchone()[0]
        pct_row = cur.execute("SELECT value FROM settings WHERE key='referral_pct'").fetchone()
        pct = pct_row[0] if pct_row else 3
        msg = (f"<blockquote>{P_GIFT} <b>𝐑ᴇғᴇʀ & 𝐄ᴀʀɴ</b></blockquote>\n\n"
               f"<blockquote>{P_USERS} <b>𝐘ᴏᴜʀ 𝐑ᴇғᴇʀʀᴀʟs:</b> {ref_count}\n"
               f"💲 <b>𝐁ᴏɴᴜs:</b> {pct}% ᴏғ ᴇᴠᴇʀʏ ᴅᴇᴘᴏsɪᴛ</blockquote>\n\n"
               f"<blockquote>🔗 <b>𝐘ᴏᴜʀ 𝐋ɪɴᴋ:</b>\n<code>{ref_link}</code></blockquote>\n\n"
               f"<blockquote><i>𝐒ʜᴀʀᴇ ᴛʜɪs ʟɪɴᴋ ᴡɪᴛʜ ғʀɪᴇɴᴅs. 𝐖ʜᴇɴ ᴛʜᴇʏ ᴅᴇᴘᴏsɪᴛ, ʏᴏᴜ ᴇᴀʀɴ {pct}%!</i></blockquote>")
        await e.respond(msg)

    @bot.on(events.NewMessage(pattern=r"(?i)^(📩 𝐒ᴜᴘᴘᴏʀᴛ|📩 Support)$"))
    async def msg_support(e):
        url = get_support_url()
        msg = f"<blockquote>📩 <b>𝐒ᴜᴘᴘᴏʀᴛ</b></blockquote>\n\n<blockquote>𝐅ᴏʀ ᴀɴʏ ɪssᴜᴇs ᴏʀ ǫᴜᴇsᴛɪᴏɴs, ᴄᴏɴᴛᴀᴄᴛ ᴏᴜʀ sᴜᴘᴘᴏʀᴛ:</blockquote>"
        btns = [[Button.url("📩 𝐂ᴏɴᴛᴀᴄᴛ 𝐒ᴜᴘᴘᴏʀᴛ", url)]]
        await e.respond(msg, buttons=btns)
