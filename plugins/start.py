import html
from telethon import events, types, Button
from telethon.errors import MessageNotModifiedError
from database import cur, db, ensure_user, is_user_banned, is_bot_online, is_admin, get_support_url, get_start_image_url
from utils.keyboards import get_persistent_menu, get_terms_buttons, get_join_buttons, style_btn, style_url
from utils.helpers import check_channel_joined, to_small_caps, send_preview_on_top
from config import PE_FLOWER, PE_LOCATION, P_OFF, P_INR, JOIN_URLS, TERMS_URL
from utils.states import session_buy_state, deposit_input

async def send_main_menu(bot, event, uid):
    me = await bot.get_me()
    bot_name = me.first_name or "Store Bot"
    
    bal_row = cur.execute("SELECT balance FROM users WHERE user_id=?", (uid,)).fetchone()
    bal = float(bal_row[0]) if bal_row and bal_row[0] is not None else 0.0
    
    try:
        user_entity = await bot.get_entity(uid)
        first_name = user_entity.first_name or "User"
        username = f"@{user_entity.username}" if user_entity.username else "None"
    except Exception:
        first_name = "User"
        username = "None"
        
    start_img = get_start_image_url()
    support_url = get_support_url()
    support_handle = f"@{support_url.split('/')[-1]}" if support_url.startswith("https://t.me/") else support_url
    
    update_link = JOIN_URLS[0] if JOIN_URLS else support_url
    feedback_link = support_url
    
    styled_name = to_small_caps(bot_name)
    
    msg = (f"<a href='{start_img}'>&#8203;</a><blockquote>💬 <b>{html.escape(styled_name)}</b></blockquote>\n\n"
           f"<blockquote expandable>"
           f"👥 <b>𝐍ᴀᴍᴇ:</b> {html.escape(first_name)}\n"
           f"🪪 <b>𝐔sᴇʀ 𝐈𝐃:</b> <code>{uid}</code>\n"
           f"🎯 <b>𝐔sᴇʀɴᴀᴍᴇ:</b> {username}\n"
           f"💳 <b>𝐁ᴀʟᴀɴᴄᴇ:</b> <code>₹{bal:.2f}</code>"
           f"</blockquote>\n\n"
           f"<blockquote>✈️ <b>𝐒ᴜᴘᴘᴏʀᴛ :</b> <a href='{support_url}'>{support_handle}</a></blockquote>")
           
    buttons = [
        [style_btn("📲 𝐁ᴜʏ 𝐀ᴄᴄᴏᴜɴᴛ", b"buy_menu_main", "success", icon=5440627033111557670)],
        [style_btn("🚀 𝐒ᴏᴄɪᴀʟ ᴍᴇᴅɪᴀ sᴇʀᴠɪᴄᴇs", b"smm_menu_main", "success", icon=5408995930416362034)],
        [style_btn("🛒 𝐁ᴜʏ 𝐒ᴏᴜʀᴄᴇ 𝐂ᴏᴅᴇs", b"src_code_menu", "success", icon=5409320020058584473)],
        [style_btn("🛒 𝐁ᴜʏ 𝐏ᴀɴᴇʟs", b"panels_menu", "success", icon=5409098988156629257)],
        [style_url("💬 𝐎ᴛʜᴇʀ 𝐂ᴏɴᴛᴇɴᴛ ↗️", update_link, "danger", icon=6129812419028982717)],
        [style_btn("💳 𝐑ᴇᴄʜᴀʀɢᴇ", b"depm_upi", "primary", icon=5409271925014801629), style_btn("🧙 𝐏ʀᴏғɪʟᴇ", b"profile_stats", "primary", icon=6203982793379154737)],
        [style_btn("💬 𝐌ᴏʀᴇ", b"more_menu", "primary", icon=6129627894349045589), style_url("📑 𝐅ᴇᴇᴅʙᴀᴄᴋ ↗️", feedback_link, "primary", icon=6129732880529628243)]
    ]
    
    edit_id = event.message_id if isinstance(event, events.CallbackQuery.Event) else None
    await send_preview_on_top(bot, uid, msg, start_img, buttons=buttons, edit_msg_id=edit_id)


def register_start(bot):
    @bot.on(events.NewMessage(pattern=r"(?i)^(/start|🏠 𝐒ᴛᴀʀᴛ)"))
    async def handle_start(e):
        try:
            uid = e.sender_id
            if not uid: return
            
            is_new = cur.execute("SELECT 1 FROM users WHERE user_id=?", (uid,)).fetchone() is None
            
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
                    if ref.isdigit() and int(ref) != uid and is_new:
                        cur.execute("UPDATE users SET referred_by=? WHERE user_id=? AND referred_by IS NULL", (int(ref), uid))
                        db.commit()

            PFP_URL = "assets/image.jpg"
            is_joined = await check_channel_joined(bot, uid, is_admin)
            if not is_joined:
                from utils.helpers import get_unjoined_channels
                from telethon import Button
                from utils.keyboards import style_btn
                
                unjoined = await get_unjoined_channels(bot, uid)
                remaining = len(unjoined)
                msg = f"<blockquote>{PE_FLOWER} <b>𝐘ᴏᴜ ᴍᴜsᴛ ᴊᴏɪɴ ᴏᴜʀ ᴄʜᴀɴɴᴇʟs & ɢʀᴏᴜᴘ ғɪʀsᴛ!</b></blockquote>\n<blockquote>{PE_LOCATION} {remaining} ᴄʜᴀɴɴᴇʟ(s)/ɢʀᴏᴜᴘ(s) ʀᴇᴍᴀɪɴɪɴɢ. 𝐉ᴏɪɴ ᴀɴᴅ ᴛᴀᴘ <b>𝐕ᴇʀɪғʏ 𝐉ᴏɪɴᴇᴅ</b>.</blockquote>"
                
                buttons = []
                for url, idx in unjoined:
                    btn_label = "💬 𝐉ᴏɪɴ 𝐆ʀᴏᴜᴘ" if ("+" in url or "joinchat" in url or idx == 2) else "📢 𝐉ᴏɪɴ 𝐂ʜᴀɴɴᴇʟ"
                    buttons.append([Button.url(btn_label, url)])
                buttons.append([style_btn("𝐕ᴇʀɪғʏ 𝐉ᴏɪɴᴇᴅ", b"verify_join", "success", icon=6129627894349045589)])
                
                f = await bot.upload_file(PFP_URL)
                media = types.InputMediaUploadedPhoto(file=f, spoiler=True)
                return await bot.send_file(e.chat_id, media, caption=msg, buttons=buttons)

            row = cur.execute("SELECT terms_accepted FROM users WHERE user_id=?", (uid,)).fetchone()
            terms_acc = row[0] if row else 0
            if not terms_acc:
                msg = f"<blockquote>{PE_FLOWER} <b>𝐓ᴇʀᴍs & 𝐂ᴏɴᴅɪᴛɪᴏɴs</b></blockquote>\n<blockquote>𝐏ʟᴇᴀsᴇ ʀᴇᴀᴅ ᴀɴᴅ ᴀᴄᴄᴇᴘᴛ ᴏᴜʀ 𝐓ᴇʀᴍs & 𝐂ᴏɴᴅɪᴛɪᴏɴs ʙᴇғᴏʀᴇ ᴜsɪɴɢ ᴛʜᴇ ʙᴏᴛ.</blockquote>"
                return await e.respond(msg, buttons=get_terms_buttons())

            await send_main_menu(bot, e, uid)
        except Exception as ex: 
            print(f"Start Error: {ex}")
