import os
from telethon import events
from telethon.errors import MessageNotModifiedError
from database import cur, db
from config import P_NO
from utils.states import session_buy_state, deposit_input, active_orders
from plugins.start import send_main_menu
from utils.helpers import check_channel_joined
from database import is_admin

def register_callbacks(bot):
    @bot.on(events.CallbackQuery(pattern=b"^tc_accept$"))
    async def cb_tc_accept(e):
        uid = e.sender_id
        cur.execute("UPDATE users SET terms_accepted=1 WHERE user_id=?", (uid,))
        db.commit()
        await e.answer("✅ Terms Accepted!", alert=True)
        # Cannot easily edit from text to media without risking error in some clients if we don't supply file correctly
        # So we just delete the terms message and send the main menu
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
        try: await e.edit(f"{P_NO} <b>Cancelled.</b>")
        except MessageNotModifiedError: pass

    @bot.on(events.CallbackQuery(pattern=b"^verify_join$"))
    async def cb_verify_join(e):
        uid = e.sender_id
        is_joined = await check_channel_joined(bot, uid, is_admin)
        if is_joined:
            await e.answer("✅ Verification successful!", alert=True)
            # Re-run start logic (will prompt for terms if not accepted)
            # A simple approach is just to delete the join message and call start again by sending main menu
            # But we must check terms first. We can just import and call handle_start logic or send_main_menu
            row = cur.execute("SELECT terms_accepted FROM users WHERE user_id=?", (uid,)).fetchone()
            terms_acc = row[0] if row else 0
            if not terms_acc:
                from utils.keyboards import get_terms_buttons
                from config import PE_FLOWER
                msg = f"<blockquote>{PE_FLOWER} <b>𝐓ᴇʀᴍs & 𝐂ᴏɴᴅɪᴛɪᴏɴs</b></blockquote>\n<blockquote>𝐏ʟᴇᴀsᴇ ʀᴇᴀᴅ ᴀɴᴅ ᴀᴄᴄᴇᴘᴛ ᴏᴜʀ 𝐓ᴇʀᴍs & 𝐂ᴏɴᴅɪᴛɪᴏɴs ʙᴇғᴏʀᴇ ᴜsɪɴɢ ᴛʜᴇ ʙᴏᴛ.</blockquote>"
                try: await e.edit(msg, buttons=get_terms_buttons())
                except MessageNotModifiedError: pass
            else:
                await e.delete()
                await send_main_menu(bot, e, uid)
        else:
            await e.answer("❌ You haven't joined all channels yet!", alert=True)
