import random
import asyncio
from telethon import Button
from telethon.errors import UserNotParticipantError, ChatAdminRequiredError
from telethon.tl.functions.channels import GetParticipantRequest
from telethon.tl import types, functions
from database import get_fsub_channels, get_fsub_urls, get_fsub_status
from config import logger

async def check_channel_joined(bot, uid, is_admin_func):
    """Returns True if all joined, False otherwise."""
    if is_admin_func(uid): return True
    if get_fsub_status() == 'off': return True
    
    check_channels = get_fsub_channels()
    if not check_channels: return True
    
    for ch in check_channels:
        try:
            ch_str = str(ch).strip()
            ch_id = int(ch_str) if (ch_str.startswith('-') and ch_str[1:].isdigit()) or ch_str.isdigit() else ch_str
            try:
                await bot(GetParticipantRequest(channel=ch_id, participant=uid))
            except ValueError:
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

async def get_unjoined_channels(bot, uid):
    """Returns list of (url, index) for channels the user has NOT joined."""
    unjoined = []
    if get_fsub_status() == 'off': return []
    
    check_channels = get_fsub_channels()
    join_urls = get_fsub_urls()
    
    for i, ch in enumerate(check_channels):
        try:
            ch_str = str(ch).strip()
            ch_id = int(ch_str) if (ch_str.startswith('-') and ch_str[1:].isdigit()) or ch_str.isdigit() else ch_str
            try:
                await bot(GetParticipantRequest(channel=ch_id, participant=uid))
            except ValueError:
                entity = await bot.get_entity(ch_id)
                await bot(GetParticipantRequest(channel=entity, participant=uid))
        except UserNotParticipantError:
            if i < len(join_urls):
                unjoined.append((join_urls[i], i + 1))
        except Exception:
            if i < len(join_urls):
                unjoined.append((join_urls[i], i + 1))
    return unjoined

SMALL_CAPS_MAP = {
    'A': '𝐀', 'B': '𝐁', 'C': '𝐂', 'D': '𝐃', 'E': '𝐄', 'F': '𝐅', 'G': '𝐆', 'H': '𝐇', 'I': '𝐈', 'J': '𝐉', 'K': '𝐊', 'L': '𝐋', 'M': '𝐌', 'N': '𝐍', 'O': '𝐎', 'P': '𝐏', 'Q': '𝐐', 'R': '𝐑', 'S': '𝐒', 'T': '𝐓', 'U': '𝐔', 'V': '𝐕', 'W': '𝐖', 'X': '𝐗', 'Y': '𝐘', 'Z': '𝐙',
    'a': 'ᴀ', 'b': 'ʙ', 'c': 'ᴄ', 'd': 'ᴅ', 'e': 'ᴇ', 'f': 'ғ', 'g': 'ɢ', 'h': 'ʜ', 'i': 'ɪ', 'j': 'ᴊ', 'k': 'ᴋ', 'l': 'ʟ', 'm': 'ᴍ', 'n': 'ɴ', 'o': 'ᴏ', 'p': 'ᴘ', 'q': 'ǫ', 'r': 'ʀ', 's': 's', 't': 'ᴛ', 'u': 'ᴜ', 'v': 'ᴠ', 'w': 'ᴡ', 'x': 'x', 'y': 'ʏ', 'z': 'ᴢ'
}

def to_small_caps(text):
    if not text: return ""
    return "".join(SMALL_CAPS_MAP.get(c, c) for c in str(text))

async def send_preview_on_top(bot, peer, message, url, buttons=None, edit_msg_id=None):
    """Sends or edits a message with WebPage link preview inverted ON TOP."""
    try:
        text, entities = await bot._parse_message_text(message, 'html')
        markup = bot.build_reply_markup(buttons) if buttons else None
        peer_obj = await bot.get_input_entity(peer)
        media_obj = types.InputMediaWebPage(url=url, force_large_media=True)
        
        if edit_msg_id:
            try:
                return await bot(functions.messages.EditMessageRequest(
                    peer=peer_obj,
                    id=edit_msg_id,
                    message=text,
                    entities=entities,
                    media=media_obj,
                    invert_media=True,
                    reply_markup=markup
                ))
            except Exception as e:
                logger.error(f"Edit invert_media error: {e}")
                
        return await bot(functions.messages.SendMediaRequest(
            peer=peer_obj,
            media=media_obj,
            message=text,
            entities=entities,
            invert_media=True,
            reply_markup=markup,
            random_id=random.randint(0, 2**63 - 1)
        ))
    except Exception as ex:
        logger.error(f"send_preview_on_top fallback: {ex}")
        if edit_msg_id:
            try: return await bot.edit_message(peer, edit_msg_id, message, buttons=buttons, parse_mode='html', link_preview=True)
            except: pass
        return await bot.send_message(peer, message, buttons=buttons, parse_mode='html', link_preview=True)


