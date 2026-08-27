import os
import re
import html
import urllib.parse
import io
from telethon import events, Button
from telethon.errors import MessageNotModifiedError
from database import cur, db, get_usdt_rate, update_balance, to_usd, get_log_channels_db, is_admin
from config import PE_GIFT, PE_LIGHTNING, P_MONEY, P_CARD, P_UPI, P_CW, P_NO, P_YES, P_WARN, P_INR, P_USDT, P_KEY, PE_CHECK, P_ACC, P_ID, LOG_CHANNEL_ID, LOG_CHANNELS, ADMIN_ID, CWALLET_QR, CWALLET_ID, UPI_ID, bot, logger
from utils.keyboards import style_btn
from utils.states import deposit_input, waiting_proof, admin_dep_state, custom_dep_amt, get_user_lock

async def deposit_menu(event):
    btns = [
        [style_btn("⚡ 𝐀ᴜᴛᴏ 𝐔𝐏𝐈 (𝐈ɴsᴛᴀɴᴛ 𝐐𝐑 & 𝐔𝐓𝐑)", "dep_choose_AutoUPI", "success", icon=5409271925014801629)],
        [style_btn("✍️ 𝐌ᴀɴᴜᴀʟ 𝐔𝐏𝐈 (𝐒ᴄʀᴇᴇɴsʜᴏᴛ 𝐏ʀᴏᴏғ)", "dep_choose_ManualUPI", "primary", icon=5409098988156629257)],
        [style_btn("💎 𝐂ᴡᴀʟʟᴇᴛ (5% 𝐁𝐎𝐍𝐔𝐒)", "dep_choose_Cwallet", "primary", icon=5440627033111557670)]
    ]
    
    customs = cur.execute("SELECT name FROM custom_payments").fetchall()
    for c in customs:
        btns.append([style_btn(f"{c[0]}", f"dep_choose_{c[0]}", "primary", icon=5408832111773757273)])
        
    btns.append([style_btn("🔙 𝐁ᴀᴄᴋ ᴛᴏ 𝐃ᴀsʜʙᴏᴀʀᴅ", b"dashboard_main", "danger", icon=6129812419028982717)])
    
    msg = (f"<blockquote>💳 <b>𝐑ᴇᴄʜᴀʀɢᴇ / 𝐀ᴅᴅ 𝐅ᴜɴᴅs</b>\n\n"
           f"⚡ <b>𝐀ᴜᴛᴏ 𝐔𝐏𝐈:</b> 𝐈ɴsᴛᴀɴᴛ ᴀᴜᴛᴏ-ᴄʀᴇᴅɪᴛ ᴠɪᴀ 12-ᴅɪɢɪᴛ 𝐔𝐓𝐑.\n"
           f"✍️ <b>𝐌ᴀɴᴜᴀʟ 𝐔𝐏𝐈:</b> 𝐔ᴘʟᴏᴀᴅ ᴘᴀʏᴍᴇɴᴛ sᴄʀᴇᴇɴsʜᴏᴛ ғᴏʀ ᴀᴅᴍɪɴ ᴀᴘᴘʀᴏᴠᴀʟ.\n"
           f"💎 <b>𝐂ᴡᴀʟʟᴇᴛ:</b> 𝐂ʀʏᴘᴛᴏ ᴘᴀʏᴍᴇɴᴛ ᴡɪᴛʜ 5% ᴇxᴛʀᴀ ʙᴏɴᴜs.\n\n"
           f"<i>👇 𝐏ʟᴇᴀsᴇ sᴇʟᴇᴄᴛ ʏᴏᴜʀ ᴘʀᴇғᴇʀʀᴇᴅ ᴍᴇᴛʜᴏᴅ:</i></blockquote>")
           
    if isinstance(event, events.CallbackQuery.Event):
        try: await event.edit(msg, buttons=btns)
        except MessageNotModifiedError: pass
    else: await event.respond(msg, buttons=btns)

async def manual_deposit_init(event, method):
    uid = event.sender_id
    deposit_input[uid] = {'step': 'wait_amt', 'method': method}
    await event.edit(f"{P_MONEY} <b>𝐄ɴᴛᴇʀ 𝐃ᴇᴘᴏsɪᴛ 𝐀ᴍᴏᴜɴᴛ (ɪɴ {P_INR}):</b>\n\n<i>𝐌ɪɴɪᴍᴜᴍ ᴅᴇᴘᴏsɪᴛ ɪs {P_INR}10.</i>", buttons=[[Button.inline("❌ 𝐂ᴀɴᴄᴇʟ", "cancel_action")]])

async def process_referral_bonus(user_id, amt):
    try:
        row = cur.execute("SELECT referred_by FROM users WHERE user_id=?", (user_id,)).fetchone()
        if not row or not row[0]: return
        ref_id = row[0]
        
        pct_row = cur.execute("SELECT value FROM settings WHERE key='ref_percent'").fetchone()
        pct = int(pct_row[0]) if pct_row else 3
        
        bonus = int(amt * (pct / 100))
        if bonus <= 0: return
        
        async with get_user_lock(ref_id):
            update_balance(ref_id, bonus)
            db.commit()
            
        try: await bot.send_message(int(ref_id), f"{PE_GIFT} <b>Referral Bonus!</b>\nYour friend deposited {P_INR}{amt}. You received <b>{P_INR}{bonus}</b> ({pct}%) in your balance!")
        except: pass
    except Exception as e: logger.error(f"Ref bonus error: {e}")

def get_admin_custom_keypad(dep_id):
    return [
        [style_btn("1", f"dkp|{dep_id}|1", "primary", icon=5375125990118793401), style_btn("2", f"dkp|{dep_id}|2", "primary", icon=5409098988156629257), style_btn("3", f"dkp|{dep_id}|3", "primary", icon=6154249597532248059)],
        [style_btn("4", f"dkp|{dep_id}|4", "primary", icon=5796170975699544141), style_btn("5", f"dkp|{dep_id}|5", "primary", icon=5409320020058584473), style_btn("6", f"dkp|{dep_id}|6", "primary", icon=5409098988156629257)],
        [style_btn("7", f"dkp|{dep_id}|7", "primary", icon=6129779562529168023), style_btn("8", f"dkp|{dep_id}|8", "primary", icon=5355292788923593967), style_btn("9", f"dkp|{dep_id}|9", "primary", icon=5408832111773757273)],
        [style_btn("Del", f"dkp|{dep_id}|del", "danger", icon=6129732880529628243), style_btn("0", f"dkp|{dep_id}|0", "primary", icon=6154249597532248059), style_btn("Confirm", f"dkp|{dep_id}|conf", "success", 5409098988156629257, icon=5409320020058584473)],
        [style_btn("𝐂ᴀɴᴄᴇʟ", f"dkp|{dep_id}|cancel", "danger", icon=6129888444245089008)]
    ]

# We will skip the automated UPI part in this script to save space if needed, 
# or I can port it directly. The user had a keypad logic for UPI amounts.
def get_keypad():
    return [
        [style_btn("1", b"kp_1", style_type="primary", icon=5408832111773757273), style_btn("2", b"kp_2", style_type="primary", icon=5408832111773757273), style_btn("3", b"kp_3", style_type="primary", icon=6129888444245089008)],
        [style_btn("4", b"kp_4", style_type="primary", icon=6064275556008989746), style_btn("5", b"kp_5", style_type="primary", icon=6129627894349045589), style_btn("6", b"kp_6", style_type="primary", icon=5409320020058584473)],
        [style_btn("7", b"kp_7", style_type="primary", icon=5375125990118793401), style_btn("8", b"kp_8", style_type="primary", icon=6129731974291527294), style_btn("9", b"kp_9", style_type="primary", icon=6170048080679801421)],
        [style_btn("Del", b"kp_del", style_type="danger", icon=6203982793379154737), style_btn("0", b"kp_0", style_type="primary", icon=5408832111773757273), style_btn("Confirm", b"kp_done", style_type="success", icon=6064310143380625195)],
        [style_btn("𝐂ᴀɴᴄᴇʟ", b"cancel_action", style_type="danger", icon=5796170975699544141)]
    ]

def register_deposit(bot):
    @bot.on(events.NewMessage(pattern=r"(?i)^(💳 𝐃ᴇᴘᴏsɪᴛ|💳 Deposit)$"))
    async def msg_deposit(e):
        await deposit_menu(e)

    @bot.on(events.CallbackQuery(pattern=r"^(open_deposit_menu|deposit_menu|depm_menu_main|depm_upi)$"))
    async def cb_deposit_menu_main(e):
        await deposit_menu(e)

    @bot.on(events.CallbackQuery(pattern=r"^dep_choose_(.+)$"))
    async def cb_choose_dep_method(e):
        method = e.pattern_match.group(1).decode()
        await manual_deposit_init(e, method)

    @bot.on(events.NewMessage(func=lambda e: e.sender_id in deposit_input and deposit_input[e.sender_id]['step'] == 'wait_amt'))
    async def msg_wait_amt(e):
        uid = e.sender_id
        text = (e.text or "").strip()
        
        # Check if user sent photo/document/link/letters instead of pure numbers
        if e.photo or e.document or e.media or not text.isdigit():
            return await e.reply(f"<blockquote>{P_NO} <b>❌ 𝐈ɴᴠᴀʟɪᴅ 𝐀ᴍᴏᴜɴᴛ!</b>\n\n"
                                 f"𝐏ʟᴇᴀsᴇ ᴇɴᴛᴇʀ a valid <b>numeric amount</b> (digits only, e.g. <code>50</code>, <code>100</code>, <code>500</code>).\n"
                                 f"<i>𝐋ɪɴᴋs, sᴄʀᴇᴇɴsʜᴏᴛs, ʟᴇᴛᴛᴇʀs ᴏʀ sᴘᴇᴄɪᴀʟ ᴄʜᴀʀᴀᴄᴛᴇʀs ᴀʀᴇ ɴᴏᴛ ᴀʟʟᴏᴡᴇᴅ.</i></blockquote>",
                                 buttons=[[Button.inline("❌ 𝐂ᴀɴᴄᴇʟ", "cancel_action")]])
        try:
            amt = int(text)
            if amt < 10: 
                return await e.reply(f"<blockquote>{P_WARN} <b>Minimum Deposit is {P_INR}10.</b>\n𝐏ʟᴇᴀsᴇ ᴇɴᴛᴇʀ {P_INR}10 ᴏʀ ᴍᴏʀᴇ:</blockquote>",
                                     buttons=[[Button.inline("❌ 𝐂ᴀɴᴄᴇʟ", "cancel_action")]])
            if amt > 50000:
                return await e.reply(f"<blockquote>{P_WARN} <b>Maximum Deposit is {P_INR}50,000.</b>\n𝐏ʟᴇᴀsᴇ ᴇɴᴛᴇʀ a smaller amount:</blockquote>",
                                     buttons=[[Button.inline("❌ 𝐂ᴀɴᴄᴇʟ", "cancel_action")]])
                
            method = deposit_input[uid]['method']
            waiting_proof[uid] = {'amount': amt, 'method': method}
            deposit_input.pop(uid)
            
            rate = get_usdt_rate()
            usdt_amt = round(amt / rate, 2)
            rate_text = f"<blockquote>{P_MONEY} <b>𝐀ᴍᴏᴜɴᴛ ᴛᴏ 𝐏ᴀʏ:</b> {P_INR}{amt} (~{P_USDT}{usdt_amt} USDT)\n💱 <i>𝐄xᴄʜᴀɴɢᴇ 𝐑ᴀᴛᴇ: {P_INR}{rate} = $1</i></blockquote>"
            
            if method == "Cwallet":
                msg = (f"<blockquote>{P_CARD} <b>𝐌ᴇᴛʜᴏᴅ:</b> {method}\n\n🚀 <b>𝐀ᴅᴅʀᴇss / 𝐈𝐃:</b>\n<code>{CWALLET_ID}</code></blockquote>\n"
                       f"{rate_text}\n"
                       f"<blockquote>👉 <b>𝐒ᴇɴᴅ 𝐏ʀᴏᴏғ:</b>\n𝐏ʟᴇᴀsᴇ sᴇɴᴅ ᴛʜᴇ 𝐓ʀᴀɴsᴀᴄᴛɪᴏɴ 𝐇ᴀsʜ (𝐋ɪɴᴋ) ᴏʀ ᴀ 𝐒ᴄʀᴇᴇɴsʜᴏᴛ ᴏғ ᴛʜᴇ ᴘᴀʏᴍᴇɴᴛ ɴᴏᴡ.</blockquote>")
                try: await bot.send_file(uid, CWALLET_QR, caption=msg, buttons=[[Button.inline("❌ 𝐂ᴀɴᴄᴇʟ", "cancel_action")]])
                except Exception: await bot.send_message(uid, msg + f"\n\n🔗 QR Link: {CWALLET_QR}", buttons=[[Button.inline("❌ 𝐂ᴀɴᴄᴇʟ", "cancel_action")]])
            elif method in ("AutoUPI", "UPI"):
                upi_res = cur.execute("SELECT value FROM settings WHERE key='upi_id'").fetchone()
                active_upi = upi_res[0] if upi_res and upi_res[0] else UPI_ID
                
                upi_url = f"upi://pay?pa={active_upi}&am={amt}&cu=INR"
                instruction = "👉 <b>𝐀ғᴛᴇʀ 𝐏ᴀʏɪɴɢ:</b>\n𝐏ʟᴇᴀsᴇ ᴇɴᴛᴇʀ ʏᴏᴜʀ <b>12-ᴅɪɢɪᴛ 𝐔𝐓𝐑 / 𝐑ᴇғ 𝐍ᴏ.</b> (ᴏʀ 𝐓ʀᴀɴsᴀᴄᴛɪᴏɴ 𝐈𝐃) ʙᴇʟᴏᴡ:"
                    
                msg = (f"<blockquote>⚡ <b>𝐀ᴜᴛᴏ 𝐔𝐏𝐈 𝐃ᴇᴘᴏsɪᴛ (𝐈ɴsᴛᴀɴᴛ)</b>\n\n🆔 <b>UPI ID:</b>\n<code>{active_upi}</code></blockquote>\n"
                       f"{rate_text}\n"
                       f"<blockquote>{instruction}</blockquote>")
                try: 
                    import qrcode
                    qr = qrcode.QRCode(version=1, box_size=10, border=4)
                    qr.add_data(upi_url)
                    qr.make(fit=True)
                    img = qr.make_image(fill_color="black", back_color="white")
                    
                    qr_file = io.BytesIO()
                    qr_file.name = "upi_qr.png"
                    img.save(qr_file, "PNG")
                    qr_file.seek(0)
                    
                    await bot.send_file(uid, qr_file, caption=msg, buttons=[[Button.inline("❌ 𝐂ᴀɴᴄᴇʟ", "cancel_action")]])
                except Exception as e: 
                    logger.error(f"Failed to send UPI QR: {e}")
                    await bot.send_message(uid, msg, buttons=[[Button.inline("❌ 𝐂ᴀɴᴄᴇʟ", "cancel_action")]])
            elif method == "ManualUPI":
                upi_res = cur.execute("SELECT value FROM settings WHERE key='upi_id'").fetchone()
                active_upi = upi_res[0] if upi_res and upi_res[0] else UPI_ID
                
                upi_url = f"upi://pay?pa={active_upi}&am={amt}&cu=INR"
                instruction = "👉 <b>𝐒ᴇɴᴅ 𝐏ʀᴏᴏғ:</b>\n𝐏ʟᴇᴀsᴇ sᴇɴᴅ ᴀ ᴄʟᴇᴀʀ <b>𝐒ᴄʀᴇᴇɴsʜᴏᴛ</b> ᴏғ ᴛʜᴇ ᴘᴀʏᴍᴇɴᴛ ɴᴏᴡ. 𝐎ᴜʀ ᴀᴅᴍɪɴ ᴡɪʟʟ ᴠᴇʀɪғʏ ᴀɴᴅ ᴀᴘᴘʀᴏᴠᴇ ɪɴsᴛᴀɴᴛʟʏ."
                    
                msg = (f"<blockquote>✍️ <b>𝐌ᴀɴᴜᴀʟ 𝐔𝐏𝐈 𝐃ᴇᴘᴏsɪᴛ</b>\n\n🆔 <b>UPI ID:</b>\n<code>{active_upi}</code></blockquote>\n"
                       f"{rate_text}\n"
                       f"<blockquote>{instruction}</blockquote>")
                try: 
                    import qrcode
                    qr = qrcode.QRCode(version=1, box_size=10, border=4)
                    qr.add_data(upi_url)
                    qr.make(fit=True)
                    img = qr.make_image(fill_color="black", back_color="white")
                    
                    qr_file = io.BytesIO()
                    qr_file.name = "upi_qr.png"
                    img.save(qr_file, "PNG")
                    qr_file.seek(0)
                    
                    await bot.send_file(uid, qr_file, caption=msg, buttons=[[Button.inline("❌ 𝐂ᴀɴᴄᴇʟ", "cancel_action")]])
                except Exception as e: 
                    logger.error(f"Failed to send UPI QR: {e}")
                    await bot.send_message(uid, msg, buttons=[[Button.inline("❌ 𝐂ᴀɴᴄᴇʟ", "cancel_action")]])
            else:
                row = cur.execute("SELECT caption, qr_file_id FROM custom_payments WHERE name=?", (method,)).fetchone()
                if row:
                    cap = f"<blockquote>{row[0]}</blockquote>\n{rate_text}\n<blockquote>👇 <b>𝐀ғᴛᴇʀ ᴘᴀʏɪɴɢ, sᴇɴᴅ ᴀ ᴄʟᴇᴀʀ 𝐒ᴄʀᴇᴇɴsʜᴏᴛ ʜᴇʀᴇ:</b></blockquote>"
                    btns = [[Button.inline("❌ 𝐂ᴀɴᴄᴇʟ", "cancel_action")]]
                    if row[1] and os.path.exists(row[1]): 
                        try: await bot.send_file(e.chat_id, row[1], caption=cap, buttons=btns)
                        except: await e.reply(cap, buttons=btns)
                    else: await e.reply(cap, buttons=btns)
                else: await e.reply(f"{P_CARD} <b>{method} Deposit</b>{rate_text}\n\n👇 Send Screenshot here:", buttons=[[Button.inline("❌ 𝐂ᴀɴᴄᴇʟ", "cancel_action")]])
            raise events.StopPropagation
        except ValueError: 
            await e.respond(f"{P_NO} Please enter a valid number in {P_INR} (INR).")
            raise events.StopPropagation
        except events.StopPropagation:
            raise
        except Exception as e_amt:
            logger.error(f"Error in msg_wait_amt: {e_amt}")

    @bot.on(events.NewMessage(func=lambda e: e.sender_id in waiting_proof and (e.photo or e.document or e.media or (e.text and not e.text.startswith('/')))))
    async def msg_wait_proof(e):
        uid = e.sender_id
        info = waiting_proof.pop(uid)
        final_amt = info['amount']
        if info['method'] == "Cwallet": final_amt = int(final_amt * 1.05)
        
        # 1. AUTO-UPI / IMAP UTR FLOW
        if info['method'] in ("AutoUPI", "UPI") and e.text and not (e.photo or e.document or e.media):
            utr_input = re.sub(r'[^0-9A-Za-z]', '', e.text.strip())
            if len(utr_input) < 6:
                waiting_proof[uid] = info
                return await e.reply(f"<blockquote>{P_WARN} <b>Invalid UTR!</b>\n\n𝐏ʟᴇᴀsᴇ ᴇɴᴛᴇʀ ʏᴏᴜʀ valid <b>12-ᴅɪɢɪᴛ 𝐔𝐓𝐑 / 𝐑ᴇғᴇʀᴇɴᴄᴇ 𝐍ᴏ.</b> (ᴏʀ 𝐓ʀᴀɴsᴀᴄᴛɪᴏɴ 𝐈𝐃).</blockquote>")
            
            # Anti-Duplicate UTR Check
            dup_check = cur.execute("SELECT id, user_id FROM deposits WHERE utr=? AND status='approved'", (utr_input,)).fetchone()
            if dup_check:
                waiting_proof[uid] = info  # keep active
                return await e.reply(f"<blockquote>{P_NO} <b>❌ 𝐔𝐓𝐑 𝐀ʟʀᴇᴀᴅʏ 𝐔sᴇᴅ!</b>\n\n𝐓ʜɪs 𝐔𝐓𝐑 / 𝐓ʀᴀɴsᴀᴄᴛɪᴏɴ 𝐈𝐃 (<code>{utr_input}</code>) ʜᴀs ᴀʟʀᴇᴀᴅʏ ʙᴇᴇɴ ʀᴇᴅᴇᴇᴍᴇᴅ!\n<i>𝐃ᴜᴘʟɪᴄᴀᴛᴇ ᴏʀ ғᴀᴋᴇ 𝐔𝐓𝐑s ᴀʀᴇ sᴛʀɪᴄᴛʟʏ ᴘʀᴏʜɪʙɪᴛᴇᴅ.</i></blockquote>")
            
            dep_mode_res = cur.execute("SELECT value FROM settings WHERE key='deposit_mode'").fetchone()
            dep_mode = dep_mode_res[0] if dep_mode_res and dep_mode_res[0] else "auto"
            
            if dep_mode in ("auto", "hybrid"):
                status_msg = await e.reply(f"<blockquote>⏳ <b>𝐕ᴇʀɪғʏɪɴɢ ʏᴏᴜʀ ᴘᴀʏᴍᴇɴᴛ...</b>\n𝐂ʜᴇᴄᴋɪɴɢ 𝐔𝐓𝐑 <code>{utr_input}</code> ᴡɪᴛʜ ʙᴀɴᴋ sᴇʀᴠᴇʀs. 𝐏ʟᴇᴀsᴇ ᴡᴀɪᴛ...</blockquote>")
                from utils.imap_verifier import verify_payment_utr
                ok, v_res = await verify_payment_utr(utr_input)
                
                if ok:
                    credited_amt = v_res.get('amount') or final_amt
                    async with get_user_lock(uid):
                        prev_row = cur.execute("SELECT balance FROM users WHERE user_id=?", (uid,)).fetchone()
                        prev_bal = prev_row[0] if prev_row else 0
                        update_balance(uid, credited_amt)
                        cur.execute("INSERT INTO deposits (user_id, amount, method_name, status, utr) VALUES (?, ?, 'UPI (Auto)', 'approved', ?)",
                                    (uid, credited_amt, utr_input))
                        cur.execute("UPDATE users SET total_deposited = total_deposited + ? WHERE user_id=?", (credited_amt, uid))
                        db.commit()
                        
                    await process_referral_bonus(uid, credited_amt)
                    
                    new_bal = prev_bal + credited_amt
                    success_text = (f"<blockquote>{PE_CHECK} <b>🎉 𝐏ᴀʏᴍᴇɴᴛ 𝐕ᴇʀɪғɪᴇᴅ & 𝐂ʀᴇᴅɪᴛᴇᴅ!</b>\n\n"
                                    f"{P_MONEY} <b>𝐀ᴍᴏᴜɴᴛ 𝐀ᴅᴅᴇᴅ:</b> <b>{P_INR}{credited_amt}</b> (${to_usd(credited_amt):.2f})\n"
                                    f"🔑 <b>𝐔𝐓𝐑:</b> <code>{utr_input}</code>\n"
                                    f"👤 <b>𝐒ᴇɴᴅᴇʀ:</b> <code>{v_res.get('sender', 'User')}</code>\n"
                                    f"📈 <b>𝐍ᴇᴡ 𝐁ᴀʟᴀɴᴄᴇ:</b> <b>{P_INR}{new_bal}</b> (${to_usd(new_bal):.2f})</blockquote>")
                    btns = [
                        [style_btn("📲 𝐁ᴜʏ 𝐀ᴄᴄᴏᴜɴᴛ", "open_buy_categories", "success", icon=5440627033111557670)],
                        [style_btn("🔙 𝐁ᴀᴄᴋ ᴛᴏ 𝐃ᴀsʜʙᴏᴀʀᴅ", "dashboard_main", "danger", icon=6129812419028982717)]
                    ]
                    try: await status_msg.edit(success_text, buttons=btns)
                    except: await e.reply(success_text, buttons=btns)
                    
                    for log_ch in get_log_channels_db():
                        try:
                            await bot.send_message(log_ch, f"<blockquote>⚡ <b>✅ 𝐀𝐔𝐓𝐎-𝐔𝐏𝐈 𝐃𝐄𝐏𝐎𝐒𝐈𝐓 𝐕𝐄𝐑𝐈𝐅𝐈𝐄𝐃</b>\n\n👤 <b>User:</b> <code>{uid}</code>\n💰 <b>Amount:</b> <b>{P_INR}{credited_amt}</b>\n🔑 <b>UTR:</b> <code>{utr_input}</code>\n💳 <b>Sender:</b> {v_res.get('sender')}</blockquote>")
                        except Exception as log_ex:
                            logger.error(f"Failed to log auto deposit to {log_ch}: {log_ex}")
                    return
                else:
                    if dep_mode == "hybrid":
                        waiting_proof[uid] = info
                        fail_text = (f"<blockquote>⚠️ <b>𝐏ᴀʏᴍᴇɴᴛ ɴᴏᴛ ᴅᴇᴛᴇᴄᴛᴇᴅ ʏᴇᴛ ғᴏʀ 𝐔𝐓𝐑:</b> <code>{utr_input}</code>\n\n"
                                     f"𝐈ғ ʏᴏᴜ ᴀʟʀᴇᴀᴅʏ ᴘᴀɪᴅ ᴀɴᴅ ᴛʜᴇ ᴇᴍᴀɪʟ ɪs ᴅᴇʟᴀʏᴇᴅ, ʏᴏᴜ ᴄᴀɴ <b>sᴇɴᴅ ᴀ 𝐒ᴄʀᴇᴇɴsʜᴏᴛ</b> ʜᴇʀᴇ ɴᴏᴡ ғᴏʀ ᴍᴀɴᴜᴀʟ ᴀᴅᴍɪɴ ᴀᴘᴘʀᴏᴠᴀʟ, ᴏʀ ᴛʀʏ ᴇɴᴛᴇʀɪɴɢ ᴛʜᴇ 𝐔𝐓𝐑 ᴀɢᴀɪɴ ɪɴ 1 ᴍɪɴᴜᴛᴇ.</blockquote>")
                        try: await status_msg.edit(fail_text, buttons=[[Button.inline("❌ 𝐂ᴀɴᴄᴇʟ", "cancel_action")]])
                        except: await e.reply(fail_text)
                        return
                    else:
                        waiting_proof[uid] = info
                        fail_text = (f"<blockquote>❌ <b>𝐏ᴀʏᴍᴇɴᴛ 𝐍ᴏᴛ 𝐅ᴏᴜɴᴅ</b>\n\n"
                                     f"𝐍ᴏ ᴘᴀʏᴍᴇɴᴛ ᴡᴀs ғᴏᴜɴᴅ ғᴏʀ 𝐔𝐓𝐑 <code>{utr_input}</code> ʏᴇᴛ.\n"
                                     f"𝐏ʟᴇᴀsᴇ ᴍᴀᴋᴇ sᴜʀᴇ ʏᴏᴜ ʜᴀᴠᴇ ᴘᴀɪᴅ ᴛᴏ <code>vinit-godara@fam</code> ᴀɴᴅ ᴛʀʏ ᴀɢᴀɪɴ ɪɴ 1-2 ᴍɪɴᴜᴛᴇs.</blockquote>")
                        try: await status_msg.edit(fail_text, buttons=[[Button.inline("❌ 𝐂ᴀɴᴄᴇʟ", "cancel_action")]])
                        except: await e.reply(fail_text)
                        return

        # 2. MANUAL SCREENSHOT / PROOF FLOW
        cur.execute("INSERT INTO deposits (user_id, amount, method_name, status) VALUES (?,?,?,?)", (uid, final_amt, info['method'], "pending"))
        db.commit()
        dep_id = cur.lastrowid
        
        await e.reply(f"<blockquote>{PE_GIFT} <b>𝐃ᴇᴘᴏsɪᴛ ʀᴇǫᴜᴇsᴛ sᴜʙᴍɪᴛᴛᴇᴅ!</b>\n\n⏳ 𝐏ʟᴇᴀsᴇ ᴡᴀɪᴛ ᴡʜɪʟᴇ ᴀɴ ᴀᴅᴍɪɴ ᴠᴇʀɪғɪᴇs ʏᴏᴜʀ ᴘᴀʏᴍᴇɴᴛ. 𝐘ᴏᴜʀ ʙᴀʟᴀɴᴄᴇ ᴡɪʟʟ ʙᴇ ᴄʀᴇᴅɪᴛᴇᴅ ᴀᴜᴛᴏᴍᴀᴛɪᴄᴀʟʟʏ!</blockquote>")
        
        rate = get_usdt_rate()
        usdt_val = round(final_amt / rate, 2)
        proof_text = f"\n📝 <b>Details / Note:</b> <code>{html.escape(e.text[:200])}</code>" if (e.text and not e.photo and not e.document) else ""
        cap = (f"<blockquote>{PE_LIGHTNING} <b>𝐍ᴇᴡ 𝐃ᴇᴘᴏsɪᴛ 𝐑ᴇǫᴜᴇsᴛ</b>\n\n"
               f"{P_ACC} <b>𝐔sᴇʀ:</b> <code>{uid}</code>\n"
               f"{P_MONEY} <b>𝐀ᴍᴏᴜɴᴛ:</b> <b>{P_INR}{final_amt}</b> (~${usdt_val})\n"
               f"{P_CARD} <b>𝐌ᴇᴛʜᴏᴅ:</b> <code>{info['method']}</code>\n"
               f"{P_ID} <b>𝐃ᴇᴘᴏsɪᴛ 𝐈𝐃:</b> <code>#{dep_id}</code>{proof_text}</blockquote>")
        
        btns = [
            [style_btn(f"✅ 𝐀ᴄᴄᴇᴘᴛ (₹{final_amt})", f"dep_acc|{dep_id}|{uid}|{info['method']}|exact|{final_amt}", "success", icon=5409098988156629257), 
             style_btn("❌ 𝐑ᴇᴊᴇᴄᴛ", f"dep_rej|{dep_id}|{uid}", "danger", icon=5409119256107297715)],
            [style_btn("✏️ 𝐂ᴜsᴛᴏᴍ 𝐀ᴍᴏᴜɴᴛ", f"dep_acc|{dep_id}|{uid}|{info['method']}|custom|0", "primary", icon=5409098988156629257)]
        ]
        
        # Deliver to Primary Channel -> Fallback Channel -> Admin DM
        delivered = False
        target_channels = get_log_channels_db()
        
        # 1. Try Log Channels in priority order
        for log_ch in target_channels:
            try:
                if e.media:
                    await bot.send_file(log_ch, e.media, caption=cap, buttons=btns)
                else:
                    await bot.send_message(log_ch, cap, buttons=btns)
                delivered = True
                break  # Successfully delivered to primary channel!
            except Exception as ex:
                logger.error(f"Failed to send deposit to channel {log_ch}: {ex}, trying fallback...")
        
        # 2. If all channels failed or no channels configured -> Fallback to Admin PM
        if not delivered:
            try:
                admin_rows = cur.execute("SELECT user_id FROM admins").fetchall()
                admin_ids = [r[0] for r in admin_rows]
                if ADMIN_ID and ADMIN_ID not in admin_ids:
                    admin_ids.append(ADMIN_ID)
                
                for a_id in admin_ids:
                    try:
                        if e.media:
                            await bot.send_file(a_id, e.media, caption=f"🔔 <b>[FALLBACK PAYMENT APPROVAL]</b>\n{cap}", buttons=btns)
                        else:
                            await bot.send_message(a_id, f"🔔 <b>[FALLBACK PAYMENT APPROVAL]</b>\n{cap}", buttons=btns)
                        break  # Delivered to admin PM
                    except Exception:
                        pass
            except Exception as e_adm:
                logger.error(f"Error sending fallback deposit to admin DM: {e_adm}")

    @bot.on(events.CallbackQuery(pattern=r"^dep_acc\|"))
    async def cb_dep_acc(e):
        admin_uid = e.sender_id
        if not is_admin(admin_uid):
            return await e.answer("🚫 Access Denied! Only Bot Admins can approve deposits.", alert=True)
            
        p = e.data.decode().split("|")
        dep_id, t_uid, method, a_type = p[1], int(p[2]), p[3], p[4]
        
        row = cur.execute("SELECT status, amount FROM deposits WHERE id=?", (dep_id,)).fetchone()
        if not row or row[0] != 'pending': 
            return await e.answer("⚠️ This deposit request has already been processed!", alert=True)
        
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
            
            user_msg = (f"<blockquote>{PE_CHECK} <b>🎉 𝐃ᴇᴘᴏsɪᴛ 𝐀ᴘᴘʀᴏᴠᴇᴅ!</b>\n\n"
                        f"{P_MONEY} <b>𝐀ᴍᴏᴜɴᴛ 𝐀ᴅᴅᴇᴅ:</b> <b>{P_INR}{amt}</b> (${to_usd(amt):.2f})\n"
                        f"📉 <b>𝐏ʀᴇᴠɪᴏᴜs 𝐁ᴀʟᴀɴᴄᴇ:</b> {P_INR}{prev_bal}\n"
                        f"📈 <b>𝐍ᴇᴡ 𝐁ᴀʟᴀɴᴄᴇ:</b> <b>{P_INR}{prev_bal+amt}</b> (${to_usd(prev_bal+amt):.2f})</blockquote>")
            try: await bot.send_message(int(t_uid), user_msg)
            except: pass
            
            approved_text = (f"<blockquote>{PE_CHECK} <b>✅ 𝐃ᴇᴘᴏsɪᴛ 𝐀ᴘᴘʀᴏᴠᴇᴅ!</b>\n\n"
                             f"{P_ACC} <b>𝐔sᴇʀ:</b> <code>{t_uid}</code>\n"
                             f"{P_MONEY} <b>𝐀ᴍᴏᴜɴᴛ 𝐂ʀᴇᴅɪᴛᴇᴅ:</b> <b>{P_INR}{amt}</b>\n"
                             f"{P_CARD} <b>𝐌ᴇᴛʜᴏᴅ:</b> <code>{method}</code>\n"
                             f"👨‍💻 <b>𝐀ᴘᴘʀᴏᴠᴇᴅ 𝐁ʏ:</b> <code>{admin_uid}</code></blockquote>")
            try: await e.edit(approved_text)
            except MessageNotModifiedError: pass
            await e.answer(f"✅ Approved! ₹{amt} credited to user {t_uid}.", alert=True)
            
        elif a_type == "custom":
            custom_dep_amt[int(dep_id)] = "0"
            await e.edit(f"<blockquote>{P_KEY} <b>Enter 𝐂ᴜsᴛᴏᴍ 𝐀ᴍᴏᴜɴᴛ for User <code>{t_uid}</code>:</b>\n\n{P_MONEY} <b>{P_INR}0</b></blockquote>", buttons=get_admin_custom_keypad(int(dep_id)))
            
    @bot.on(events.CallbackQuery(pattern=r"^dep_rej\|"))
    async def cb_dep_rej(e):
        admin_uid = e.sender_id
        if not is_admin(admin_uid):
            return await e.answer("🚫 Access Denied! Only Bot Admins can reject deposits.", alert=True)
            
        p = e.data.decode().split("|")
        dep_id, t_uid = p[1], int(p[2])
        
        row = cur.execute("SELECT status, amount, method_name FROM deposits WHERE id=?", (dep_id,)).fetchone()
        if not row or row[0] != 'pending': 
            return await e.answer("⚠️ This deposit request has already been processed!", alert=True)
        
        cur.execute("UPDATE deposits SET status='rejected' WHERE id=?", (dep_id,))
        db.commit()
        
        try:
            await bot.send_message(int(t_uid), f"<blockquote>{P_NO} <b>❌ 𝐃ᴇᴘᴏsɪᴛ 𝐑ᴇᴊᴇᴄᴛᴇᴅ!</b>\n\n𝐘ᴏᴜʀ ᴅᴇᴘᴏsɪᴛ ʀᴇǫᴜᴇsᴛ ᴏғ <b>{P_INR}{row[1]}</b> ᴡᴀs ʀᴇᴊᴇᴄᴛᴇᴅ ʙʏ ᴀᴅᴍɪɴ.\n𝐈ғ ʏᴏᴜ ᴀʟʀᴇᴀᴅʏ ᴘᴀɪᴅ, ᴘʟᴇᴀsᴇ ᴄᴏɴᴛᴀᴄᴛ <b>𝐒ᴜᴘᴘᴏʀᴛ</b> ᴡɪᴛʜ ʏᴏᴜʀ ᴘᴀʏᴍᴇɴᴛ ᴘʀᴏᴏғ.</blockquote>")
        except: pass
        
        rej_text = (f"<blockquote>{P_NO} <b>❌ 𝐃ᴇᴘᴏsɪᴛ 𝐑ᴇᴊᴇᴄᴛᴇᴅ!</b>\n\n"
                    f"{P_ACC} <b>𝐔sᴇʀ:</b> <code>{t_uid}</code>\n"
                    f"{P_MONEY} <b>𝐀ᴍᴏᴜɴᴛ:</b> {P_INR}{row[1]}\n"
                    f"👨‍💻 <b>𝐑ᴇᴊᴇᴄᴛᴇᴅ 𝐁ʏ:</b> <code>{admin_uid}</code></blockquote>")
        try: await e.edit(rej_text)
        except MessageNotModifiedError: pass
        await e.answer(f"❌ Deposit #{dep_id} rejected.", alert=True)

    @bot.on(events.CallbackQuery(pattern=r"^dkp\|"))
    async def cb_dkp(e):
        uid = e.sender_id
        if not is_admin(uid):
            return await e.answer("🚫 Access Denied! Only Bot Admins can set deposit amounts.", alert=True)
            
        _, dep_id, action = e.data.decode().split("|")
        dep_id = int(dep_id)
        row = cur.execute("SELECT user_id, method_name, status, amount FROM deposits WHERE id=?", (dep_id,)).fetchone()
        if not row or row[2] != 'pending': 
            return await e.answer("⚠️ Already processed.", alert=True)
        t_uid, method, orig_amt = row[0], row[1], row[3]
        
        curr = custom_dep_amt.get(dep_id, "0")
        
        if action.isdigit():
            if curr == "0": curr = action
            else: curr += action
            if len(curr) > 7: curr = curr[:7]
        elif action == "del": 
            curr = curr[:-1] or "0"
        elif action == "cancel":
            btns = [
                [style_btn(f"✅ 𝐀ᴄᴄᴇᴘᴛ (₹{orig_amt})", f"dep_acc|{dep_id}|{t_uid}|{method}|exact|{orig_amt}", "success", icon=5409098988156629257), 
                 style_btn("❌ 𝐑ᴇᴊᴇᴄᴛ", f"dep_rej|{dep_id}|{t_uid}", "danger", icon=5409119256107297715)],
                [style_btn("✏️ 𝐂ᴜsᴛᴏᴍ 𝐀ᴍᴏᴜɴᴛ", f"dep_acc|{dep_id}|{t_uid}|{method}|custom|0", "primary", icon=5409098988156629257)]
            ]
            return await e.edit(f"<blockquote>{PE_LIGHTNING} <b>𝐍ᴇᴡ 𝐃ᴇᴘᴏsɪᴛ 𝐑ᴇǫᴜᴇsᴛ</b>\n\n{P_ACC} 𝐔sᴇʀ: <code>{t_uid}</code>\n{P_MONEY} 𝐑ᴇǫᴜᴇsᴛ: <b>{P_INR}{orig_amt}</b>\n{P_CARD} 𝐌ᴇᴛʜᴏᴅ: <code>{method}</code>\n{P_ID} 𝐑ᴇғ: <code>#{dep_id}</code></blockquote>", buttons=btns)
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
            conf_text = (f"<blockquote>{PE_CHECK} <b>✅ 𝐃ᴇᴘᴏsɪᴛ 𝐀ᴘᴘʀᴏᴠᴇᴅ (𝐂ᴜsᴛᴏᴍ)!</b>\n\n"
                         f"{P_ACC} <b>𝐔sᴇʀ:</b> <code>{t_uid}</code>\n"
                         f"{P_MONEY} <b>𝐀ᴍᴏᴜɴᴛ 𝐂ʀᴇᴅɪᴛᴇᴅ:</b> <b>{P_INR}{amt}</b>\n"
                         f"👨‍💻 <b>𝐀ᴘᴘʀᴏᴠᴇᴅ 𝐁ʏ:</b> <code>{uid}</code></blockquote>")
            await e.edit(conf_text)
            try:
                await bot.send_message(int(t_uid), f"<blockquote>{PE_CHECK} <b>🎉 𝐃ᴇᴘᴏsɪᴛ 𝐀ᴘᴘʀᴏᴠᴇᴅ!</b>\n\n{P_MONEY} <b>𝐀ᴍᴏᴜɴᴛ 𝐀ᴅᴅᴇᴅ:</b> <b>{P_INR}{amt}</b>\n📉 <b>𝐎ʟᴅ:</b> {P_INR}{prev_bal} | 📈 <b>𝐍ᴇᴡ:</b> <b>{P_INR}{prev_bal+amt}</b></blockquote>")
            except: pass
            await e.answer(f"✅ Approved ₹{amt} for user {t_uid}.", alert=True)
            return

        custom_dep_amt[dep_id] = curr
        await e.edit(f"<blockquote>{P_KEY} <b>Enter 𝐂ᴜsᴛᴏᴍ 𝐀ᴍᴏᴜɴᴛ for User <code>{t_uid}</code>:</b>\n\n{P_MONEY} <b>{P_INR}{curr}</b></blockquote>", buttons=get_admin_custom_keypad(dep_id))
