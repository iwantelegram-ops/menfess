import html, logging
from pyrogram import Client, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.handlers import ChatMemberUpdatedHandler
from config import *
from utils import load_json, save_json, get_channels

@Client.on_chat_member_updated()
async def handle_my_chat_member(client, update):
    bot_me = await client.get_me()
    if not update.new_chat_member or update.new_chat_member.user.id != bot_me.id: return

    chat, new_status = update.chat, update.new_chat_member
    if chat.type != enums.ChatType.CHANNEL: return
    if new_status.status not in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]: return

    added_by = update.from_user
    if not added_by or added_by.id != OWNER_ID: return

    ch_id, ch_name = str(chat.id), chat.title or str(chat.id)
    cfg = load_json(CONFIG_FILE)
    channels = get_channels(cfg)

    existing_ids = [c.get("id") for c in channels]
    if ch_id in existing_ids:
        try: await client.send_message(OWNER_ID, f"ℹ️ Channel <b>{html.escape(ch_name)}</b> sudah terdaftar sebelumnya.", parse_mode=enums.ParseMode.HTML)
        except: pass
        return

    channels.append({"id": ch_id, "name": ch_name, "active": False})
    cfg["channels"] = channels
    save_json(CONFIG_FILE, cfg)

    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Ya, Jadikan Channel Menfess", callback_data=f"ch_confirm_{len(channels)-1}"),
        InlineKeyboardButton("❌ Tidak", callback_data="ch_confirm_no")
    ]])
    try:
        await client.send_message(
            OWNER_ID,
            f"📢 <b>1 Channel Ditambahkan!</b>\n\n📌 Nama: <b>{html.escape(ch_name)}</b>\n🆔 ID: <code>{ch_id}</code>\n\nApakah ingin menjadikan channel ini sebagai tujuan menfess?",
            reply_markup=kb, parse_mode=enums.ParseMode.HTML
        )
    except Exception as e:
        logging.error(f"Gagal kirim notif channel baru ke owner: {e}")
