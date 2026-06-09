import html
from pyrogram import Client, filters, enums
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from config import *
from utils import (
    load_json, save_json, clear_ud,
    get_channels, get_active_channel,
    ADMIN_KB, CLONE_ADMIN_KB, USER_KB,
)

_WELCOME_USER = (
    "📮 <b>Selamat Datang di Bot Menfess!</b>\n\n"
    "Kirim curahan hati, pesan rahasia, atau apapun secara <b>anonim</b>\n"
    "langsung ke channel — tanpa diketahui siapapun.\n\n"
    "✨ <b>Fitur unggulan:</b>\n"
    "┣ 👤 Mode anonim atau tampilkan nama\n"
    "┣ 🔗 Link sosmed terdeteksi otomatis\n"
    "┣ 📸 Support foto & video\n"
    "┗ 💬 Dapat notifikasi saat ada komentar\n\n"
    "<i>Gunakan tombol menu di bawah untuk mulai.</i>"
)

_WELCOME_ADMIN = (
    "🛠 <b>Panel Admin Bot Menfess</b>\n\n"
    "Selamat datang kembali, <b>{name}</b>!\n\n"
    "Gunakan menu di bawah untuk mengelola bot Anda."
)


@Client.on_message(filters.command("start") & filters.private)
async def cmd_start(client: Client, message: Message):
    uid_int    = message.from_user.id
    first_name = message.from_user.first_name or "User"

    # Daftarkan user ke database
    users = load_json(USERS_LIST_FILE)
    if str(uid_int) not in users:
        users.append(str(uid_int))
        save_json(USERS_LIST_FILE, users)

    user_db = load_json(USER_DATA_FILE)
    if str(uid_int) not in user_db:
        user_db[str(uid_int)] = {"kuota": 0}
        save_json(USER_DATA_FILE, user_db)

    clear_ud(uid_int)

    # ── Clone owner: setup wizard ──────────────────────────────────────────────
    if IS_CLONE and uid_int == OWNER_ID:
        cfg      = load_json(CONFIG_FILE)
        channels = get_channels(cfg)

        if not channels:
            await message.reply_text(
                "👋 <b>Selamat Datang di Bot Clone Anda!</b>\n\n"
                "Sebelum mulai, Anda perlu menghubungkan bot ke channel Anda.\n\n"
                "📌 <b>Langkah 1:</b> Tambahkan bot ini sebagai <b>Admin</b> di channel Anda.\n"
                "📌 <b>Langkah 2:</b> Tekan tombol <b>Sudah, cek sekarang</b> di bawah.",
                parse_mode=enums.ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("✅ Sudah, cek sekarang",      callback_data="ch_start_check"),
                    InlineKeyboardButton("📋 Panduan lengkap",          callback_data="ch_add_guide"),
                ]]),
            )
            return

        active_ch   = get_active_channel(cfg)
        active_name = next((c["name"] for c in channels if c.get("id") == active_ch), "-")
        await message.reply_text(
            f"👋 <b>Selamat Datang kembali, {html.escape(first_name)}!</b>\n\n"
            f"📌 Channel aktif: <b>{html.escape(active_name)}</b>",
            reply_markup=CLONE_ADMIN_KB,
            parse_mode=enums.ParseMode.HTML,
        )
        return

    # ── Master owner ───────────────────────────────────────────────────────────
    if uid_int == MAIN_OWNER_ID and not IS_CLONE:
        await message.reply_text(
            _WELCOME_ADMIN.format(name=html.escape(first_name)),
            reply_markup=ADMIN_KB,
            parse_mode=enums.ParseMode.HTML,
        )
        return

    # ── User biasa ─────────────────────────────────────────────────────────────
    await message.reply_text(
        _WELCOME_USER,
        reply_markup=USER_KB,
        parse_mode=enums.ParseMode.HTML,
    )


@Client.on_message(filters.command("batal") & filters.private)
async def cmd_batal(client: Client, message: Message):
    uid_int = message.from_user.id
    clear_ud(uid_int)
    is_main_owner = uid_int == MAIN_OWNER_ID and not IS_CLONE
    kb = ADMIN_KB if is_main_owner else (CLONE_ADMIN_KB if uid_int == OWNER_ID else USER_KB)
    await message.reply_text("✅ Aksi dibatalkan. Kembali ke menu utama.", reply_markup=kb)
