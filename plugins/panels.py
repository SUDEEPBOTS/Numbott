import html
from telethon import events, Button
from telethon.errors import MessageNotModifiedError
from database import cur, db, get_panels, is_admin
from utils.states import get_user_lock
from config import P_INR, P_NO, PE_CHECK, PE_GIFT, logger
from utils.keyboards import style_btn

async def show_panels_menu(event):
    pnls = get_panels()
    btns = []
    for p_id, title, desc, price, panel_link, avail in pnls:
        btns.append([style_btn(f"{title} - {P_INR}{price}", f"pnl_info|{p_id}", "primary")])
        
    btns.append([style_btn("🔙 𝐁ᴀᴄᴋ", b"buy_menu_main", "danger", icon=6129812419028982717)])
    
    msg = ("<blockquote>🌌 <b>𝐏ᴀɴᴇʟ 𝐒ᴛᴏʀᴇ</b>\n"
           "───────────────────────────────\n"
           "• 𝐂ʜᴇᴀᴘᴇsᴛ ᴀɴᴅ 𝐓ʀᴜsᴛᴇᴅ ᴘᴀɴᴇʟs\n"
           "• 𝐓ʜᴇsᴇ ᴘᴀɴᴇʟs ᴀʀᴇ ᴜsᴇᴅ ʙʏ ᴜs ᴀʟsᴏ\n\n"
           "<i>𝐒ᴇʟᴇᴄᴛ ᴛʜᴇ ᴘᴀɴᴇʟ ʏᴏᴜ ᴡᴀɴɴᴀ ʙᴜʏ:</i></blockquote>")
           
    if isinstance(event, events.CallbackQuery.Event):
        try: await event.edit(msg, buttons=btns)
        except MessageNotModifiedError: pass
    else:
        await event.respond(msg, buttons=btns)

async def show_panel_info(event, panel_id):
    row = cur.execute("SELECT id, title, description, price, panel_content FROM panels WHERE id=?", (panel_id,)).fetchone()
    if not row:
        return await event.answer("❌ Panel not found.", alert=True)
        
    p_id, title, desc, price, panel_link = row
    msg = (f"<blockquote>🌌 <b>{html.escape(title)}</b>\n\n"
           f"📝 <b>𝐃ᴇsᴄʀɪᴘᴛɪᴏɴ:</b>\n{html.escape(desc)}\n\n"
           f"💰 <b>𝐏ʀɪᴄᴇ:</b> <code>{P_INR}{price}</code>\n"
           f"⚡ <b>𝐃ᴇʟɪᴠᴇʀʏ:</b> <code>Instant Access & Setup Guide</code>\n\n"
           f"<b>𝐀ʀᴇ ʏᴏᴜ sᴜʀᴇ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ ʙᴜʏ?</b></blockquote>")
           
    btns = [
        [style_btn("✅ 𝐂ᴏɴғɪʀᴍ 𝐁ᴜʏ", f"pnl_cf|{p_id}", "success", icon=5409320020058584473)],
        [style_btn("🔙 𝐁ᴀᴄᴋ", b"panels_menu", "danger", icon=6129812419028982717)]
    ]
    try: await event.edit(msg, buttons=btns)
    except MessageNotModifiedError: pass

def register_panels(bot):
    @bot.on(events.CallbackQuery(pattern=b"^panels_menu$"))
    async def cb_pnl_main(e):
        await show_panels_menu(e)
        
    @bot.on(events.CallbackQuery(pattern=r"^pnl_info\|(\d+)$"))
    async def cb_pnl_info(e):
        panel_id = int(e.pattern_match.group(1).decode())
        await show_panel_info(e, panel_id)
        
    @bot.on(events.CallbackQuery(pattern=r"^pnl_cf\|(\d+)$"))
    async def cb_pnl_cf(e):
        uid = e.sender_id
        panel_id = int(e.pattern_match.group(1).decode())
        
        row = cur.execute("SELECT id, title, description, price, panel_content FROM panels WHERE id=?", (panel_id,)).fetchone()
        if not row:
            return await e.answer("❌ Panel not found.", alert=True)
            
        p_id, title, desc, price, panel_link = row
        
        async with get_user_lock(uid):
            bal_row = cur.execute("SELECT balance FROM users WHERE user_id=?", (uid,)).fetchone()
            if not bal_row or bal_row[0] < price:
                return await e.answer(f"❌ Insufficient Balance! Price: ₹{price}, Your Balance: ₹{bal_row[0] if bal_row else 0}", alert=True)
                
            cur.execute("UPDATE users SET balance = balance - ? WHERE user_id=? AND balance >= ?", (price, uid, price))
            db.commit()
            
        from config import LOG_CHANNELS
        for ch in LOG_CHANNELS:
            try:
                admin_log = (f"<blockquote><b>🌌 𝐍ᴇᴡ 𝐏ᴀɴᴇʟ 𝐏ᴜʀᴄʜᴀsᴇ</b>\n\n"
                             f"👤 <b>𝐔sᴇʀ:</b> <code>{uid}</code>\n"
                             f"🏷️ <b>𝐏ᴀɴᴇʟ:</b> {html.escape(title)}\n"
                             f"💰 <b>𝐏ʀɪᴄᴇ:</b> {P_INR}{price}</blockquote>")
                await bot.send_message(ch, admin_log)
            except: pass
            
        msg = (f"<blockquote>{PE_CHECK} <b>🎉 𝐏ᴜʀᴄʜᴀsᴇ 𝐒ᴜᴄᴄᴇssғᴜʟ!</b>\n\n"
               f"🌌 <b>𝐏ᴀɴᴇʟ:</b> <b>{html.escape(title)}</b>\n"
               f"💰 <b>𝐀ᴍᴏᴜɴᴛ 𝐏ᴀɪᴅ:</b> <code>{P_INR}{price}</code>\n\n"
               f"🔗 <b>𝐏ᴀɴᴇʟ 𝐖ᴇʙsɪᴛᴇ 𝐔𝐑𝐋:</b>\n"
               f"<code>{html.escape(panel_link)}</code>\n\n"
               f"<i>𝐕ɪsɪᴛ ᴛʜᴇ ᴘᴀɴᴇʟ ᴜʀʟ ᴛᴏ ʀᴇɢɪsᴛᴇʀ ᴀɴᴅ ᴜsᴇ ʏᴏᴜʀ ᴘᴀɴᴇʟ!</i></blockquote>")
               
        btns = [
            [Button.url("🌐 𝐎ᴘᴇɴ 𝐏ᴀɴᴇʟ 𝐖ᴇʙsɪᴛᴇ ↗️", panel_link)],
            [style_btn("🔙 𝐁ᴀᴄᴋ ᴛᴏ 𝐒ᴛᴏʀᴇ", b"panels_menu", "primary")]
        ]
        try: await e.edit(msg, buttons=btns)
        except MessageNotModifiedError: pass
