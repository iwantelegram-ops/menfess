import html, os, sys, subprocess, asyncio, logging
from datetime import datetime
from pyrogram import Client, filters, enums
from pyrogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup
)
from config import *
from utils import (
    USER_STATES, USER_KB, ADMIN_KB, CLONE_ADMIN_KB, MODE_MENFESS_KB,
    OWNER_USER_MODE_KB, get_ud, clear_ud, load_json, save_json,
    is_banned, get_channels, get_active_channel, ask_channel_setup,
    parse_and_extract_links, build_post_link, save_menfess_track,
    build_channel_list_kb,
)

# Cache get_me() — dipanggil sekali, disimpan per-instance
_bot_me_cache: dict = {}

async def _get_me(client):
    if "me" not in _bot_me_cache:
        _bot_me_cache["me"] = await client.get_me()
    return _bot_me_cache["me"]


@Client.on_message(
    (filters.text | filters.photo | filters.video)
    & ~filters.command(["start", "batal"])
    & filters.private
)
async def handle_message(client: Client, message: Message):
    uid_int      = message.from_user.id
    uid          = str(uid_int)
    raw_text_input = message.text or message.caption or ""

    if is_banned(uid_int):
        return

    all_buttons = [
        '📝 Tulis Menfess', '🤖 Buat/Kelola Clone', '💳 Isi Kuota', '📊 Info Akun',
        '⚙️ Pengaturan Bot', '📢 Broadcast', '🔓 Mode Gratis', '🔒 Mode Bayar',
        '👤 Mode User', '👤 Kirim Anonim', '👁️ Tampilkan Nama', '❌ Batal', '🔙 Admin Menu',
    ]
    ud = get_ud(uid_int)

    if raw_text_input in all_buttons:
        ud.pop("state", None)
        if raw_text_input == "❌ Batal":
            is_main_owner = uid_int == MAIN_OWNER_ID and not IS_CLONE
            kb = ADMIN_KB if is_main_owner else (CLONE_ADMIN_KB if uid_int == OWNER_ID else USER_KB)
            return await message.reply_text(
                "✅ Aksi dibatalkan. Kembali ke menu utama.",
                reply_markup=kb,
            )

    state = ud.get("state")

    # ── Bukti pembayaran (foto dari user bukan owner & bukan sedang tulis menfess) ──
    if message.photo and uid_int != OWNER_ID and state != "tulis_menfess":
        caption_owner = (
            f"💳 <b>BUKTI PEMBAYARAN BARU</b>\n\n"
            f"👤 Dari: {html.escape(message.from_user.first_name or 'User')}\n"
            f"🆔 ID: <code>{uid}</code>"
        )
        kb_owner = InlineKeyboardMarkup([[
            InlineKeyboardButton("➖", callback_data=f"count_{uid}_4"),
            InlineKeyboardButton("💎 5",  callback_data="n"),
            InlineKeyboardButton("➕", callback_data=f"count_{uid}_6"),
        ], [
            InlineKeyboardButton("✅ KONFIRMASI", callback_data=f"acc_{uid}_5"),
        ]])
        await client.send_photo(
            OWNER_ID, photo=message.photo.file_id,
            caption=caption_owner, reply_markup=kb_owner,
            parse_mode=enums.ParseMode.HTML,
        )
        return await message.reply_text(
            "✅ <b>Bukti pembayaran terkirim!</b>\nMohon tunggu admin mengonfirmasi.",
            parse_mode=enums.ParseMode.HTML,
        )

    # ── Waiting: token clone baru ──────────────────────────────────────────────
    if state == "waiting_clone":
        token_clean = raw_text_input.strip()
        if ":" not in token_clean or len(token_clean) < 30:
            return await message.reply_text(
                "❌ <b>Format Token salah!</b>\nKirim ulang token valid dari @BotFather atau klik ❌ Batal.",
                parse_mode=enums.ParseMode.HTML,
            )
        clear_ud(uid_int)
        kb_back = ADMIN_KB if (uid_int == MAIN_OWNER_ID and not IS_CLONE) else (
            CLONE_ADMIN_KB if uid_int == OWNER_ID else USER_KB
        )

        clones = load_json(CLONE_DB)
        if not isinstance(clones, list):
            clones = []

        # Cek token duplikat — cegah clone token yang sama dua kali
        existing_tokens = [c.get("token", "") for c in clones]
        if token_clean in existing_tokens:
            return await message.reply_text(
                "⚠️ <b>Token ini sudah digunakan di clone yang aktif!</b>\n"
                "Gunakan token bot yang berbeda dari @BotFather.",
                reply_markup=kb_back,
                parse_mode=enums.ParseMode.HTML,
            )

        # Owner bot (OWNER_ID) bebas unlimited clone di bot manapun
        # User biasa hanya boleh 1 clone
        is_owner = (uid_int == MAIN_OWNER_ID) or (uid_int == OWNER_ID)
        if not is_owner:
            user_clone_count = sum(1 for c in clones if c.get("owner") == uid_int)
            if user_clone_count >= 1:
                return await message.reply_text(
                    "❌ <b>Anda sudah memiliki 1 bot clone aktif.</b>\n\n"
                    "Matikan clone lama terlebih dahulu sebelum membuat yang baru.\n"
                    "Gunakan tombol <b>🤖 Buat/Kelola Clone</b> untuk melihat daftar clone Anda.",
                    reply_markup=kb_back,
                    parse_mode=enums.ParseMode.HTML,
                )

        await message.reply_text("⏳ Menghidupkan core server clone...")
        try:
            script_path = os.path.abspath(sys.argv[0])
            # Tiap clone pakai subfolder sendiri agar session SQLite tidak bentrok
            clone_dir = os.path.join(os.path.dirname(script_path), f"clone_{uid_int}_{token_clean.split(':')[0]}")
            os.makedirs(clone_dir, exist_ok=True)
            # Salin main.py, config.py, utils.py, plugins ke clone_dir jika belum ada
            import shutil
            base = os.path.dirname(script_path)
            for item in ["main.py", "config.py", "utils.py", "plugins", "requirements.txt"]:
                src = os.path.join(base, item)
                dst = os.path.join(clone_dir, item)
                if os.path.isdir(src):
                    if not os.path.exists(dst):
                        shutil.copytree(src, dst)
                elif os.path.isfile(src) and not os.path.exists(dst):
                    shutil.copy2(src, dst)
            env = os.environ.copy()
            env["BOT_TOKEN"] = token_clean
            env["IS_CLONE"]  = "True"
            env["OWN_ID"]    = str(uid_int)
            env.pop("CH_ID", None)
            proc = subprocess.Popen(
                [sys.executable, os.path.join(clone_dir, "main.py")],
                env=env,
                cwd=clone_dir,
            )
            clones.append({"token": token_clean, "owner": uid_int, "pid": proc.pid,
                           "added_at": datetime.now().strftime("%d/%m/%Y %H:%M")})
            save_json(CLONE_DB, clones)
            return await message.reply_text(
                f"✅ <b>Bot Clone Berhasil Diaktifkan!</b>\n\n"
                f"👤 <b>Owner:</b> <a href='tg://user?id={uid_int}'>"
                f"{html.escape(message.from_user.first_name or 'User')}</a>\n"
                f"⚙️ <b>PID:</b> <code>{proc.pid}</code>\n\n"
                "Silakan buka bot clone baru Anda lalu tekan /start.",
                reply_markup=kb_back,
                parse_mode=enums.ParseMode.HTML,
            )
        except Exception as e:
            logging.error(f"[Clone] Gagal launch: {e}")
            return await message.reply_text(
                f"❌ <b>Gagal meluncurkan clone!</b>\n\n<code>{html.escape(str(e))}</code>\n\n"
                "Pastikan Termux memiliki izin menjalankan proses baru.",
                reply_markup=kb_back,
                parse_mode=enums.ParseMode.HTML,
            )

    # ── Waiting: broadcast ────────────────────────────────────────────────────
    if uid_int == OWNER_ID and state == "waiting_bc":
        clear_ud(uid_int)
        all_users = load_json(USERS_LIST_FILE)
        count = 0
        await message.reply_text("⏳ Sedang mengirim broadcast...")
        for u in all_users:
            try:
                if message.photo:
                    await client.send_photo(
                        int(u), message.photo.file_id,
                        caption=f"📢 <b>INFO ADMIN</b>\n\n{html.escape(raw_text_input)}",
                        parse_mode=enums.ParseMode.HTML,
                    )
                else:
                    await client.send_message(
                        int(u),
                        f"📢 <b>INFO ADMIN</b>\n\n{html.escape(raw_text_input)}",
                        parse_mode=enums.ParseMode.HTML,
                        disable_web_page_preview=True,
                    )
                count += 1
                await asyncio.sleep(0.05)
            except Exception:
                continue
        return await message.reply_text(
            f"✅ <b>Broadcast Selesai!</b> Pesan terkirim ke <b>{count}</b> user.",
            parse_mode=enums.ParseMode.HTML,
        )

    # ── Waiting: edit template / edit QRIS ────────────────────────────────────
    if uid_int == OWNER_ID and state in ["edit_template", "edit_qris"]:
        clear_ud(uid_int)
        cfg = load_json(CONFIG_FILE)
        if state == "edit_template":
            cfg["post_template"] = raw_text_input
            await message.reply_text(
                "✅ <b>Template berhasil diperbarui!</b>\n\n"
                "<i>Kirim menfess untuk melihat tampilan barunya.</i>",
                parse_mode=enums.ParseMode.HTML,
            )
        else:
            cfg["qris_link"] = raw_text_input.strip()
            await message.reply_text(
                "✅ Link QRIS/Gambar Isi Kuota berhasil diperbarui!",
                parse_mode=enums.ParseMode.HTML,
            )
        save_json(CONFIG_FILE, cfg)
        return

    # ── Kirim Menfess ─────────────────────────────────────────────────────────
    if state == "tulis_menfess":
        user_db = load_json(USER_DATA_FILE)
        cfg     = load_json(CONFIG_FILE)

        # Cek kuota
        if uid_int != OWNER_ID and not cfg.get("gratis", False):
            kuota = user_db.get(uid, {}).get("kuota", 0)
            if kuota <= 0:
                clear_ud(uid_int)
                return await message.reply_text(
                    "❌ <b>Kuota Anda habis!</b>\nSilakan isi ulang kuota.",
                    reply_markup=USER_KB,
                    parse_mode=enums.ParseMode.HTML,
                )

        # Cek channel aktif (clone)
        if IS_CLONE and not get_active_channel(cfg):
            clear_ud(uid_int)
            await message.reply_text(
                "⚠️ Bot belum dikaitkan ke channel menfess.\n"
                "Silakan tambahkan bot ke channel terlebih dahulu.",
                parse_mode=enums.ParseMode.HTML,
            )
            return await ask_channel_setup(client, OWNER_ID, message.from_user.first_name or "Owner")

        # Parse teks + link sosmed
        clean_text, sosmed_text = parse_and_extract_links(raw_text_input)
        mode_kirim = ud.get("menfess_mode", "anonim")
        first_name = message.from_user.first_name or "User"
        sender     = (
            "anonim" if mode_kirim == "anonim"
            else f"<a href='tg://user?id={uid_int}'>{html.escape(first_name)}</a>"
        )

        text_with_sosmed = (
            (f"<i>{html.escape(clean_text)}</i>" if clean_text else "")
            + sosmed_text
        )
        template   = cfg.get("post_template", DEFAULT_TEMPLATE)
        base_text  = template.replace("{TEXT}", text_with_sosmed).replace("{SENDER}", sender)

        bot_me     = await _get_me(client)
        final_text = (
            base_text
            + f"\n🤖 <i>via</i> <a href='https://t.me/{bot_me.username}?start=help'>"
            f"{html.escape(bot_me.first_name)}</a>"
        )

        # Tentukan target channel
        if IS_CLONE:
            target_id = str(get_active_channel(cfg)).strip()
        else:
            target_id = str(cfg.get("target_channel", DEFAULT_CHANNEL)).strip()

        try:
            if message.photo:
                snt = await client.send_photo(
                    target_id, photo=message.photo.file_id,
                    caption=final_text, parse_mode=enums.ParseMode.HTML,
                )
            elif message.video:
                snt = await client.send_video(
                    target_id, video=message.video.file_id,
                    caption=final_text, parse_mode=enums.ParseMode.HTML,
                )
            else:
                snt = await client.send_message(
                    target_id, final_text,
                    parse_mode=enums.ParseMode.HTML,
                    disable_web_page_preview=True,
                )

            # Kurangi kuota
            if uid_int != OWNER_ID and not cfg.get("gratis", False):
                if uid in user_db and "kuota" in user_db[uid]:
                    user_db[uid]["kuota"] = max(0, user_db[uid]["kuota"] - 1)
                    save_json(USER_DATA_FILE, user_db)

            # Link langsung ke postingan (mendukung private & public channel)
            post_link = build_post_link(target_id, snt.id)

            # ── Simpan tracking untuk notifikasi komentar ──────────────────
            # Normalisasi channel_id untuk key: selalu gunakan numeric ID
            channel_id_for_track = target_id
            if not target_id.startswith("-100") and not target_id.startswith("-"):
                # Coba dapatkan numeric ID dari objek pesan yang terkirim
                if snt.chat and snt.chat.id:
                    channel_id_for_track = str(snt.chat.id)
            save_menfess_track(
                channel_id=channel_id_for_track,
                post_id=snt.id,
                sender_id=uid_int,
                sender_name=first_name,
                post_link=post_link,
            )

            # Log ke owner
            log_text = (
                f"📩 <b>LOG MENFESS MASUK</b>\n\n"
                f"<b>Sender:</b> {html.escape(first_name)} (<code>{uid}</code>)\n"
                f"<b>Tipe:</b> {mode_kirim.upper()}\n"
                f"<b>Isi Asli:</b>\n{html.escape(raw_text_input[:300])}"
            )
            log_kb = InlineKeyboardMarkup([[
                InlineKeyboardButton("🚫 BAN USER",  callback_data=f"ban_{uid}"),
                InlineKeyboardButton("✅ UNBAN",      callback_data=f"unban_{uid}"),
            ]])
            if message.photo:
                await client.send_photo(
                    OWNER_ID, photo=message.photo.file_id,
                    caption=log_text, reply_markup=log_kb,
                    parse_mode=enums.ParseMode.HTML,
                )
            elif message.video:
                await client.send_video(
                    OWNER_ID, video=message.video.file_id,
                    caption=log_text, reply_markup=log_kb,
                    parse_mode=enums.ParseMode.HTML,
                )
            else:
                await client.send_message(
                    OWNER_ID, log_text, reply_markup=log_kb,
                    parse_mode=enums.ParseMode.HTML,
                    disable_web_page_preview=True,
                )

            clear_ud(uid_int)
            is_main_owner = uid_int == MAIN_OWNER_ID and not IS_CLONE
            kb_back = ADMIN_KB if is_main_owner else (
                CLONE_ADMIN_KB if uid_int == OWNER_ID else USER_KB
            )

            await message.reply_text(
                "🎉 <b>Menfess Berhasil Terkirim!</b>",
                reply_markup=kb_back,
                parse_mode=enums.ParseMode.HTML,
            )
            return await message.reply_text(
                "Lihat hasil kiriman Anda:",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("Lihat Postingan ↗️", url=post_link)
                ]]),
            )

        except Exception as e:
            clear_ud(uid_int)
            logging.error(f"[Menfess] Gagal kirim ke {target_id}: {e}")
            return await message.reply_text(
                f"❌ Gagal mengirim menfess.\nPastikan bot sudah menjadi admin di channel.\n\n<code>{e}</code>",
                parse_mode=enums.ParseMode.HTML,
            )

    # ── Routing tombol menu utama ─────────────────────────────────────────────

    if raw_text_input == "🤖 Buat/Kelola Clone":
        ud["state"] = "waiting_clone"
        clones = load_json(CLONE_DB)
        if not isinstance(clones, list):
            clones = []

        # Filter clone yang relevan untuk user ini
        visible = [
            (i, c) for i, c in enumerate(clones)
            if uid_int == MAIN_OWNER_ID or c.get("owner") == uid_int
        ]

        if visible:
            clones_updated = False
            for i, c in visible:
                token_raw  = c.get("token", "")
                bot_id     = token_raw.split(":")[0] if ":" in token_raw else "?"
                token_show = f"{token_raw[:10]}...{token_raw[-5:]}" if len(token_raw) > 15 else token_raw
                owner_id   = c.get("owner", "?")
                pid        = c.get("pid", "?")
                added_at   = c.get("added_at", "-")

                # Ambil nama bot — dari cache dulu, kalau belum ada fetch via API
                bot_name = c.get("bot_name", "")
                bot_username = c.get("bot_username", "")
                if not bot_name and bot_id.isdigit():
                    try:
                        bot_user = await client.get_users(int(bot_id))
                        bot_name     = bot_user.first_name or ""
                        bot_username = f"@{bot_user.username}" if bot_user.username else ""
                        # Simpan ke cache agar tidak fetch ulang
                        clones[i]["bot_name"]     = bot_name
                        clones[i]["bot_username"] = bot_username
                        clones_updated = True
                    except Exception:
                        bot_name     = "?"
                        bot_username = ""

                bot_label = html.escape(bot_name)
                if bot_username:
                    bot_label += f" ({html.escape(bot_username)})"

                # Cek status proses (masih jalan atau sudah mati)
                status = "❓ Unknown"
                if pid and pid != "?":
                    try:
                        os.kill(int(pid), 0)
                        status = "🟢 Berjalan"
                    except ProcessLookupError:
                        status = "🔴 Mati / Crashed"
                    except PermissionError:
                        status = "🟡 Berjalan (no-perm)"

                # Cek apakah folder clone masih ada
                base_dir   = os.path.dirname(os.path.abspath(sys.argv[0]))
                clone_dir  = os.path.join(base_dir, f"clone_{owner_id}_{bot_id}")
                dir_status = "✅ Ada" if os.path.isdir(clone_dir) else "⚠️ Tidak ada"

                detail = (
                    f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"🤖 <b>Clone #{i+1}</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"🏷️ <b>Nama Bot:</b> {bot_label}\n"
                    f"🆔 <b>Bot ID:</b> <code>{bot_id}</code>\n"
                    f"🔑 <b>Token:</b> <code>{token_show}</code>\n"
                    f"👤 <b>Owner ID:</b> <code>{owner_id}</code>\n"
                    f"⚙️ <b>PID:</b> <code>{pid}</code>\n"
                    f"📡 <b>Status:</b> {status}\n"
                    f"📁 <b>Folder:</b> {dir_status}\n"
                    f"🕐 <b>Dibuat:</b> {added_at}"
                )
                kb_detail = InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔄 Restart", callback_data=f"restartclone_{i}"),
                    InlineKeyboardButton("🛑 Matikan", callback_data=f"delclone_{i}"),
                ]])
                await message.reply_text(
                    detail,
                    reply_markup=kb_detail,
                    parse_mode=enums.ParseMode.HTML,
                )
            if clones_updated:
                save_json(CLONE_DB, clones)
        else:
            await message.reply_text(
                "📋 Anda belum memiliki bot clone aktif.",
                parse_mode=enums.ParseMode.HTML,
            )

        return await message.reply_text(
            "🤖 <b>PANEL CLONING SYSTEM MENFESS</b>\n\n"
            "<b>Cara Mengkloning:</b>\n"
            "1. Ambil token bot baru dari @BotFather.\n"
            "2. <b>Paste token</b> tersebut di sini sekarang.\n",
            reply_markup=ReplyKeyboardMarkup([["❌ Batal"]], resize_keyboard=True),
            parse_mode=enums.ParseMode.HTML,
        )

    if uid_int == OWNER_ID:
        if raw_text_input == "⚙️ Pengaturan Bot":
            cfg      = load_json(CONFIG_FILE)
            channels = get_channels(cfg)
            active_ch   = get_active_channel(cfg)
            active_name = next((c["name"] for c in channels if c.get("id") == active_ch), "Belum diset")
            ch_btn = [InlineKeyboardButton("📢 Kelola Channel", callback_data="cp_ch")]
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("📝 Edit Template", callback_data="cp_tpl"), *ch_btn],
                [InlineKeyboardButton("🖼️ Edit QRIS/Gambar", callback_data="cp_qris")],
            ])
            if IS_CLONE:
                ch_info = (
                    f"<b>Channel Terdaftar:</b> {len(channels)}\n"
                    f"<b>Channel Aktif:</b> {html.escape(active_name)}"
                )
            else:
                ch_info = f"<b>Target Channel ID:</b> <code>{cfg.get('target_channel', DEFAULT_CHANNEL)}</code>"
            return await message.reply_text(
                f"⚙️ <b>PENGATURAN BOT</b>\n\n{ch_info}\n"
                f"<b>Link QRIS:</b> <code>{cfg.get('qris_link', 'Belum disetel')}</code>\n\n"
                f"<b>Contoh template:</b>\n"
                f"<code>━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📮  M E N F E S S\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"{{{{TEXT}}}}\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"✍️ Dikirim oleh {{{{SENDER}}}}</code>",
                reply_markup=kb,
                parse_mode=enums.ParseMode.HTML,
            )

        if raw_text_input == "📢 Broadcast":
            ud["state"] = "waiting_bc"
            return await message.reply_text(
                "📢 <b>Kirim pesan broadcast Anda sekarang.</b>",
                reply_markup=ReplyKeyboardMarkup([["❌ Batal"]], resize_keyboard=True),
                parse_mode=enums.ParseMode.HTML,
            )

        if raw_text_input == "🔓 Mode Gratis":
            cfg = load_json(CONFIG_FILE)
            cfg["gratis"] = True
            save_json(CONFIG_FILE, cfg)
            return await message.reply_text("✅ <b>Mode GRATIS diaktifkan!</b>", parse_mode=enums.ParseMode.HTML)

        if raw_text_input == "🔒 Mode Bayar":
            cfg = load_json(CONFIG_FILE)
            cfg["gratis"] = False
            save_json(CONFIG_FILE, cfg)
            return await message.reply_text("✅ <b>Mode BERBAYAR diaktifkan!</b>", parse_mode=enums.ParseMode.HTML)

        if raw_text_input == "👤 Mode User":
            return await message.reply_text("Berpindah ke tampilan User.", reply_markup=OWNER_USER_MODE_KB)

        if raw_text_input == "🔙 Admin Menu":
            clear_ud(uid_int)
            return await message.reply_text(
                "✅ Kembali ke menu Admin.",
                reply_markup=CLONE_ADMIN_KB if IS_CLONE else ADMIN_KB,
            )

    if raw_text_input == "📝 Tulis Menfess":
        return await message.reply_text("Pilih mode pengiriman Anda:", reply_markup=MODE_MENFESS_KB)

    if raw_text_input in ["👤 Kirim Anonim", "👁️ Tampilkan Nama"]:
        ud["state"]        = "tulis_menfess"
        ud["menfess_mode"] = "anonim" if raw_text_input == "👤 Kirim Anonim" else "nama"
        return await message.reply_text(
            "✍️ <b>Silakan ketik atau kirim menfess Anda.</b>\n"
            "<i>Link sosial media akan dideteksi otomatis.</i>",
            reply_markup=ReplyKeyboardMarkup([["❌ Batal"]], resize_keyboard=True),
            parse_mode=enums.ParseMode.HTML,
        )

    if raw_text_input == "💳 Isi Kuota":
        cfg      = load_json(CONFIG_FILE)
        img_qris = cfg.get("qris_link", "").strip()
        if img_qris and img_qris != "Belum disetel":
            try:
                return await client.send_photo(
                    uid_int, photo=img_qris,
                    caption="💳 Kirim bukti transfer kuota Anda langsung ke chat bot ini.",
                    parse_mode=enums.ParseMode.HTML,
                )
            except Exception as e:
                logging.error(f"Gagal memuat gambar QRIS: {e}")
        return await message.reply_text(
            "💳 Kirim bukti transfer kuota Anda langsung ke chat bot ini.",
            parse_mode=enums.ParseMode.HTML,
        )

    if raw_text_input == "📊 Info Akun":
        user_db   = load_json(USER_DATA_FILE)
        cfg       = load_json(CONFIG_FILE)
        kuota_now = user_db.get(uid, {}).get("kuota", 0)
        mode_now  = "Gratis ✅" if cfg.get("gratis", False) else "Berbayar 💎"
        return await message.reply_text(
            f"📊 <b>INFO AKUN</b>\n\n"
            f"🆔 ID: <code>{uid}</code>\n"
            f"💎 Sisa Kuota: <b>{kuota_now}</b>\n"
            f"⚙️ Mode Bot: <b>{mode_now}</b>",
            parse_mode=enums.ParseMode.HTML,
        )

    # Fallback untuk input tidak dikenal
    if not raw_text_input.startswith("/"):
        is_main_owner = uid_int == MAIN_OWNER_ID and not IS_CLONE
        kb = ADMIN_KB if is_main_owner else (CLONE_ADMIN_KB if uid_int == OWNER_ID else USER_KB)
        await message.reply_text("💡 Gunakan tombol menu untuk berinteraksi.", reply_markup=kb)
