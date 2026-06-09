"""
plugins/notifications.py
─────────────────────────
Notifikasi komentar ke pengirim menfess.

Cara kerja:
  1. Saat menfess dikirim, sender_id disimpan di menfess_track{suffix}.json
     dengan key = "{channel_id}_{post_id}".

  2. Handler ini mendengarkan pesan di semua grup (termasuk grup diskusi privat).

  3. Saat ada komentar baru:
     a. Cek apakah pesan adalah reply ke forwarded channel post
        (message.reply_to_message.forward_from_chat).
     b. Ambil channel_id + post_id dari forwarded message.
     c. Cari pengirim asli menfess via get_menfess_track().
     d. Kirim notifikasi ke pengirim + tombol link ke postingan.

  Catatan:
  - Bot HARUS menjadi anggota/admin di linked discussion group agar dapat
    menerima update komentar dari sana.
  - Untuk grup diskusi privat, link yang dikirim tetap menggunakan format
    t.me/c/{channel_id}/{post_id} (bukan link ke grup diskusi).
  - Pengirim asli tidak akan mendapat notifikasi jika dia sendiri yang berkomentar.
  - Pengirim anonim juga tetap mendapat notifikasi (via sender_id tersimpan).
"""

import html
import logging
from pyrogram import Client, filters, enums
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from utils import get_menfess_track


@Client.on_message(filters.group & ~filters.service)
async def handle_comment_notification(client: Client, message: Message):
    """
    Deteksi komentar baru di postingan channel dan kirim notifikasi
    ke pengirim menfess aslinya.
    """
    # Hanya proses pesan yang merupakan reply
    if not message.reply_to_message:
        return

    reply = message.reply_to_message

    # Pesan yang di-reply harus merupakan forward dari channel
    if not getattr(reply, "forward_from_chat", None):
        return

    # Abaikan pesan dari bot/channel itu sendiri
    if not message.from_user:
        return

    forward_chat = reply.forward_from_chat
    if not forward_chat:
        return

    channel_id = str(forward_chat.id)
    post_id    = getattr(reply, "forward_from_message_id", None)
    if not post_id:
        return

    # Cari data pengirim menfess
    track = get_menfess_track(channel_id, post_id)
    if not track:
        return

    sender_id   = track.get("sender_id")
    sender_name = track.get("sender_name", "Anda")
    post_link   = track.get("post_link", "")
    if not sender_id:
        return

    # Jangan notif jika pengirim asli yang berkomentar sendiri
    if message.from_user.id == sender_id:
        return

    # Informasi komentator
    commenter      = message.from_user
    commenter_name = html.escape(commenter.first_name or "Seseorang")
    comment_preview = (message.text or message.caption or "📎 <i>Media</i>")[:200]

    # Bangun link ke postingan (bukan link ke grup diskusi)
    if not post_link:
        # Fallback jika post_link tidak tersimpan
        if channel_id.startswith("-100"):
            post_link = f"https://t.me/c/{channel_id[4:]}/{post_id}"
        else:
            post_link = f"https://t.me/c/{channel_id.lstrip('-')}/{post_id}"

    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("💬 Lihat Postingan ↗️", url=post_link)
    ]])

    notif_text = (
        "💬 <b>Ada komentar baru di menfess Anda!</b>\n\n"
        f"👤 <b>{commenter_name}</b> baru saja berkomentar:\n"
        f"<i>{html.escape(str(comment_preview))}</i>\n\n"
        "🔗 Klik tombol di bawah untuk melihat postingan dan semua komentar:"
    )

    try:
        await client.send_message(
            sender_id,
            notif_text,
            reply_markup=kb,
            parse_mode=enums.ParseMode.HTML,
        )
    except Exception as e:
        logging.warning(f"[NotifKomentar] Gagal kirim notif ke {sender_id}: {e}")
