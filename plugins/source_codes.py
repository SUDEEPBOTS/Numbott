import html
from telethon import events, Button
from telethon.errors import MessageNotModifiedError
from database import cur, db, get_source_codes, is_admin
from utils.states import get_user_lock
from config import P_INR, P_NO, PE_CHECK, PE_GIFT, logger
from utils.keyboards import style_btn

async def show_source_codes_menu(event):
    codes = get_source_codes()
    btns = []
    for c_id, title, desc, price, file_link, avail in codes:
        btns.append([style_btn(f"{title} - {P_INR}{price}", f"src_info|{c_id}", "primary")])
        
    btns.append([style_btn("🔙 𝐁ᴀᴄᴋ", b"buy_menu_main", "danger", icon=6129812419028982717)])
    
    msg = ("<blockquote>💻 <b>𝐒ᴏᴜʀᴄᴇ 𝐂ᴏᴅᴇ 𝐒ᴛᴏʀᴇ</b>\n"
           "───────────────────────────────\n"
           "• 𝐑ᴇᴀᴅʏᴍᴀᴅᴇ ᴄᴏᴅᴇs, 𝐂ʀᴇᴀᴛᴇ ʏᴏᴜʀ ᴏᴡɴ ʙᴏᴛs\n"
           "• 𝐀ʟʟ ᴛʜɪɴɢs ᴀʀᴇ ᴅᴏɴᴇ ᴀʟʀᴇᴀᴅʏ ʏᴏᴜ ᴊᴜsᴛ ʜᴀᴠᴇ ᴛᴏ ᴇᴅɪᴛ ᴛʜᴇ ᴅᴇᴛᴀɪʟs\n\n"
           "<i>𝐒ᴇʟᴇᴄᴛ ᴛʜᴇ sᴏᴜʀᴄᴇ ᴄᴏᴅᴇ ʏᴏᴜ ᴡᴀɴɴᴀ ʙᴜʏ:</i></blockquote>")
           
    if isinstance(event, events.CallbackQuery.Event):
        try: await event.edit(msg, buttons=btns)
        except MessageNotModifiedError: pass
    else:
        await event.respond(msg, buttons=btns)

async def show_source_code_info(event, code_id):
    row = cur.execute("SELECT id, title, description, price, file_content FROM source_codes WHERE id=?", (code_id,)).fetchone()
    if not row:
        return await event.answer("❌ Source code not found.", alert=True)
        
    c_id, title, desc, price, file_link = row
    msg = (f"<blockquote>💻 <b>{html.escape(title)}</b>\n\n"
           f"📝 <b>𝐃ᴇsᴄʀɪᴘᴛɪᴏɴ:</b>\n{html.escape(desc)}\n\n"
           f"💰 <b>𝐏ʀɪᴄᴇ:</b> <code>{P_INR}{price}</code>\n"
           f"⚡ <b>𝐃ᴇʟɪᴠᴇʀʏ:</b> <code>Instant Download Link</code>\n\n"
           f"<b>𝐀ʀᴇ ʏᴏᴜ sᴜʀᴇ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ ʙᴜʏ?</b></blockquote>")
           
    btns = [
        [style_btn("✅ 𝐂ᴏɴғɪʀᴍ 𝐁ᴜʏ", f"src_cf|{c_id}", "success", icon=5409320020058584473)],
        [style_btn("🔙 𝐁ᴀᴄᴋ", b"src_code_menu", "danger", icon=6129812419028982717)]
    ]
    try: await event.edit(msg, buttons=btns)
    except MessageNotModifiedError: pass

def register_source_codes(bot):
    @bot.on(events.CallbackQuery(pattern=b"^src_code_menu$"))
    async def cb_src_main(e):
        await show_source_codes_menu(e)
        
    @bot.on(events.CallbackQuery(pattern=r"^src_info\|(\d+)$"))
    async def cb_src_info(e):
        code_id = int(e.pattern_match.group(1).decode())
        await show_source_code_info(e, code_id)
        
    @bot.on(events.CallbackQuery(pattern=r"^src_cf\|(\d+)$"))
    async def cb_src_cf(e):
        uid = e.sender_id
        code_id = int(e.pattern_match.group(1).decode())
        
        row = cur.execute("SELECT id, title, description, price, file_content FROM source_codes WHERE id=?", (code_id,)).fetchone()
        if not row:
            return await e.answer("❌ Source code not found.", alert=True)
            
        c_id, title, desc, price, file_link = row
        
        async with get_user_lock(uid):
            bal_row = cur.execute("SELECT balance FROM users WHERE user_id=?", (uid,)).fetchone()
            if not bal_row or bal_row[0] < price:
                return await e.answer(f"❌ Insufficient Balance! Price: ₹{price}, Your Balance: ₹{bal_row[0] if bal_row else 0}", alert=True)
                
            cur.execute("UPDATE users SET balance = balance - ? WHERE user_id=? AND balance >= ?", (price, uid, price))
            db.commit()
            
        from config import LOG_CHANNELS
        for ch in LOG_CHANNELS:
            try:
                admin_log = (f"<blockquote><b>💻 𝐍ᴇᴡ 𝐒ᴏᴜʀᴄᴇ 𝐂ᴏᴅᴇ 𝐏ᴜʀᴄʜᴀsᴇ</b>\n\n"
                             f"👤 <b>𝐔sᴇʀ:</b> <code>{uid}</code>\n"
                             f"🏷️ <b>𝐈ᴛᴇᴍ:</b> {html.escape(title)}\n"
                             f"💰 <b>𝐏ʀɪᴄᴇ:</b> {P_INR}{price}</blockquote>")
                await bot.send_message(ch, admin_log)
            except: pass
            
        msg = (f"<blockquote>{PE_CHECK} <b>🎉 𝐏ᴜʀᴄʜᴀsᴇ 𝐒ᴜᴄᴄᴇssғᴜʟ!</b>\n\n"
               f"💻 <b>𝐈ᴛᴇᴍ:</b> <b>{html.escape(title)}</b>\n"
               f"💰 <b>𝐀ᴍᴏᴜɴᴛ 𝐏ᴀɪᴅ:</b> <code>{P_INR}{price}</code>\n\n"
               f"🔗 <b>𝐃ᴏᴡɴʟᴏᴀᴅ / 𝐀ᴄᴄᴇss 𝐋ɪɴᴋ:</b>\n"
               f"<code>{html.escape(file_link)}</code>\n\n"
               f"<i>𝐓ʜᴀɴᴋ ʏᴏᴜ ғᴏʀ ʏᴏᴜʀ ᴘᴜʀᴄʜᴀsᴇ!</i></blockquote>")
               
        btns = [
            [Button.url("📥 𝐎ᴘᴇɴ 𝐆ɪᴛ𝐇ᴜʙ 𝐑ᴇᴘᴏ ↗️", file_link)],
            [style_btn("🔙 𝐁ᴀᴄᴋ ᴛᴏ 𝐒ᴛᴏʀᴇ", b"src_code_menu", "primary")]
        ]
        try: await e.edit(msg, buttons=btns)
        except MessageNotModifiedError: pass
