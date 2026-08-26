import asyncio
from telethon import Button
from telethon.errors import UserNotParticipantError, ChatAdminRequiredError
from telethon.tl.functions.channels import GetParticipantRequest
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
