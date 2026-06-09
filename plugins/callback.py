import os, signal, html, logging, shutil, sys
from pyrogram import Client, enums
from pyrogram.types import (
    CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
)
from config import *
from utils import (
    load_json, save_json, get_ud, clear_ud,
    get_channels, get_active_channel,
    build_channel_list_kb, CLONE_ADMIN_KB, ADMIN_KB,
)


@Client.on_callback_query()
async def handle_callback(client: Client, query: CallbackQuery):
    user_id = query.from_user.id
    data    = query.data

    # ── BAN / UNBAN ────────────────────────────────────────────────────────────
    if data.startswith("ban_") or data.startswith("unban_"):
        if user_id != OWNER_ID:
            return await query.answer("Akses Ditolak!", show_alert=True)
        parts_ban = data.split("_", 1)
        if len(parts_ban) < 2 or not parts_ban[1]:
            return await query.answer("Data tombol tidak valid.", show_alert=True)
        uid    = parts_ban[1]
        banned = load_json(BAN_FILE)
        if not isinstance(banned, list):
            banned = []
        if data.startswith("ban_") and uid not in banned:
            banned.append(uid)
            save_json(BAN_FILE, banned)
            status_text = "\n\n🚫 <b>STATUS: BANNED</b>"
        elif data.startswith("unban_") and uid in banned:
            banned.remove(uid)
            save_json(BAN_FILE, banned)
            status_text = "\n\n✅ <b>STATUS: AKTIF</b>"
        else:
            return await query.answer("Status sudah ter-update!")
        try:
            orig = query.message.text or query.message.caption or ""
            orig = orig.replace("\n\n🚫 <b>STATUS: BANNED</b>", "").replace("\n\n✅ <b>STATUS: AKTIF</b>", "")
            if query.message.photo or query.message.video:
                await query.message.edit_caption(
                    caption=orig + status_text,
                    parse_mode=enums.ParseMode.HTML,
                    reply_markup=query.message.reply_markup,
                )
            else:
                await query.message.edit_text(
                    text=orig + status_text,
                    parse_mode=enums.ParseMode.HTML,
                    reply_markup=query.message.reply_markup,
                )
            await query.answer("Status User Diperbarui!")
        except Exception as e:
            await query.answer(f"Gagal mengubah log: {e}", show_alert=True)
        return

    # ── Restart clone ─────────────────────────────────────────────────────────
    if data.startswith("restartclone_"):
        idx    = int(data.split("_", 1)[1])
        clones = load_json(CLONE_DB)
        if not isinstance(clones, list): clones = []
        if not (0 <= idx < len(clones)):
            return await query.answer("Index clone tidak valid.", show_alert=True)
        target = clones[idx]
        if user_id != MAIN_OWNER_ID and target.get("owner") != user_id:
            return await query.answer("❌ Bukan clone Anda!", show_alert=True)

        token   = target.get("token", "")
        owner   = target.get("owner", OWNER_ID)
        bot_id  = token.split(":")[0] if ":" in token else "?"
        old_pid = target.get("pid")

        # Matikan proses lama jika masih ada
        if old_pid:
            try: os.kill(int(old_pid), signal.SIGTERM)
            except Exception: pass

        base_dir  = os.path.dirname(os.path.abspath(sys.argv[0]))
        clone_dir = os.path.join(base_dir, f"clone_{owner}_{bot_id}")
        os.makedirs(clone_dir, exist_ok=True)
        for item in ["main.py", "config.py", "utils.py", "plugins", "requirements.txt", "database_manager.py"]:
            src = os.path.join(base_dir, item)
            dst = os.path.join(clone_dir, item)
            if os.path.isdir(src):
                if os.path.exists(dst): shutil.rmtree(dst)
                shutil.copytree(src, dst)
            elif os.path.isfile(src):
                shutil.copy2(src, dst)

        import subprocess
        env = os.environ.copy()
        env["BOT_TOKEN"] = token
        env["IS_CLONE"]  = "True"
        env["OWN_ID"]    = str(owner)
        env.pop("CH_ID", None)
        try:
            proc = subprocess.Popen(
                [sys.executable, os.path.join(clone_dir, "main.py")],
                env=env, cwd=clone_dir,
            )
            clones[idx]["pid"] = proc.pid
            save_json(CLONE_DB, clones)
            await query.message.edit_text(
                f"🔄 <b>Clone #{idx+1} Di-restart!</b>\n\n"
                f"🆔 Bot ID: <code>{bot_id}</code>\n"
                f"⚙️ PID Baru: <code>{proc.pid}</code>\n"
                f"📡 Status: 🟢 Berjalan",
                parse_mode=enums.ParseMode.HTML,
                reply_markup=query.message.reply_markup,
            )
            await query.answer("✅ Restart berhasil!")
        except Exception as e:
            await query.answer(f"❌ Gagal restart: {e}", show_alert=True)
        return

    # ── Hapus clone ────────────────────────────────────────────────────────────
    if data.startswith("delclone_"):
        idx    = int(data.split("_", 1)[1])
        clones = load_json(CLONE_DB)
        if not isinstance(clones, list):
            clones = []
        if not (0 <= idx < len(clones)):
            return await query.answer("Gagal: Index clone tidak valid.", show_alert=True)
        target_clone = clones[idx]
        if user_id != MAIN_OWNER_ID and target_clone.get("owner") != user_id:
            return await query.answer("❌ Anda tidak berhak menghapus clone ini!", show_alert=True)
        removed = clones.pop(idx)
        save_json(CLONE_DB, clones)
        pid_target  = removed.get("pid")
        kill_status = "Data dihapus dari database."
        if pid_target:
            try:
                os.kill(int(pid_target), signal.SIGTERM)
                kill_status = f"Proses PID {pid_target} berhasil dimatikan."
            except ProcessLookupError:
                kill_status = f"Proses PID {pid_target} sudah tidak berjalan."
            except Exception as e:
                kill_status = f"Gagal menghentikan proses: {e}"
        await query.message.edit_text(
            f"✅ <b>Bot Clone Berhasil Dihapus!</b>\n\n"
            f"🤖 Token: <code>{removed.get('token','')[:10]}...</code>\n"
            f"⚡ Status: {kill_status}",
            parse_mode=enums.ParseMode.HTML,
        )
        return

    # ── Ubah jumlah kuota (tombol +/−) — FIX: batasi min=1 di kedua arah ──────
    if data.startswith("count_"):
        if user_id != OWNER_ID:
            return
        parts = data.split("_", 2)
        if len(parts) < 3:
            return await query.answer("Data tombol tidak valid.", show_alert=True)
        tid   = parts[1]
        try:
            val = int(parts[2])
        except (ValueError, IndexError):
            return await query.answer("Data tombol tidak valid.", show_alert=True)

        # Tombol ➖ tidak boleh membuat val turun ke 0
        val_minus = max(1, val - 1)
        val_plus  = val + 1

        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("➖", callback_data=f"count_{tid}_{val_minus}"),
            InlineKeyboardButton(f"💎 {val}", callback_data="n"),
            InlineKeyboardButton("➕", callback_data=f"count_{tid}_{val_plus}"),
        ], [
            InlineKeyboardButton("✅ KONFIRMASI KUOTA", callback_data=f"acc_{tid}_{val}"),
        ]])
        await query.message.edit_reply_markup(reply_markup=kb)
        return

    # ── Konfirmasi kuota ───────────────────────────────────────────────────────
    if data.startswith("acc_"):
        if user_id != OWNER_ID:
            return
        parts = data.split("_", 2)
        if len(parts) < 3:
            return await query.answer("Data tombol tidak valid.", show_alert=True)
        tid, val = parts[1], parts[2]
        user_db  = load_json(USER_DATA_FILE)
        if tid not in user_db:
            user_db[tid] = {"kuota": 0}
        user_db[tid]["kuota"] += int(val)
        save_json(USER_DATA_FILE, user_db)
        try:
            orig   = query.message.text or query.message.caption or ""
            append = f"\n\n✅ <b>BERHASIL DITAMBAHKAN +{val} KUOTA</b>"
            if query.message.photo or query.message.video:
                await query.message.edit_caption(caption=orig + append, parse_mode=enums.ParseMode.HTML)
            else:
                await query.message.edit_text(text=orig + append, parse_mode=enums.ParseMode.HTML)
        except Exception as e:
            logging.warning(f"Gagal edit pesan konfirmasi kuota: {e}")
        try:
            await client.send_message(
                int(tid),
                f"🎉 <b>Pembayaran Berhasil!</b>\n+{val} kuota telah ditambahkan.",
                parse_mode=enums.ParseMode.HTML,
            )
        except Exception:
            pass
        return

    # ── Edit template ──────────────────────────────────────────────────────────
    if data == "cp_tpl":
        if user_id != OWNER_ID:
            return await query.answer("Akses Ditolak!", show_alert=True)
        await query.answer()
        get_ud(user_id)["state"] = "edit_template"
        await query.message.reply_text(
            "📝 <b>Kirim template postingan baru.</b>\n"
            "Gunakan <code>{TEXT}</code> untuk isi menfess dan <code>{SENDER}</code> untuk nama pengirim.",
            parse_mode=enums.ParseMode.HTML,
        )
        return

    # ── Edit QRIS ──────────────────────────────────────────────────────────────
    if data == "cp_qris":
        if user_id != OWNER_ID:
            return await query.answer("Akses Ditolak!", show_alert=True)
        await query.answer()
        get_ud(user_id)["state"] = "edit_qris"
        await query.message.reply_text(
            "🖼️ <b>Kirimkan link gambar QRIS baru.</b>\nContoh: <code>https://telegra.ph/file/xxx.jpg</code>",
            parse_mode=enums.ParseMode.HTML,
        )
        return

    # ── Panduan tambah channel ─────────────────────────────────────────────────
    if data == "ch_add_guide":
        await query.answer()
        await query.message.reply_text(
            "📋 <b>Cara Menambahkan Channel:</b>\n\n"
            "1. Buka channel Telegram Anda.\n"
            "2. Masuk ke <b>Pengaturan Channel → Admin</b>.\n"
            "3. Tambahkan username bot ini sebagai admin dengan hak <b>Posting Pesan</b>.\n"
            "4. Bot akan otomatis mendeteksi dan mengirim konfirmasi ke sini.\n\n"
            "⚠️ Pastikan Anda yang menambahkan (bukan orang lain).",
            parse_mode=enums.ParseMode.HTML,
        )
        return

    # ── Cek apakah bot sudah ada di channel (dari flow /start) ────────────────
    if data == "ch_start_check":
        if user_id != OWNER_ID:
            return await query.answer("Akses Ditolak!", show_alert=True)
        await query.answer()
        cfg      = load_json(CONFIG_FILE)
        channels = get_channels(cfg)
        if channels:
            active_ch   = get_active_channel(cfg)
            active_name = next((c["name"] for c in channels if c.get("id") == active_ch), "-")
            await query.message.edit_text(
                f"✅ <b>Channel terdeteksi!</b>\n\n"
                f"📌 Channel aktif: <b>{html.escape(active_name)}</b>\n\n"
                "Bot siap digunakan. Kembali ke menu admin:",
                parse_mode=enums.ParseMode.HTML,
            )
            await client.send_message(
                user_id,
                "✅ Setup selesai! Selamat menggunakan bot menfess Anda.",
                reply_markup=CLONE_ADMIN_KB,
            )
        else:
            await query.message.edit_text(
                "⚠️ <b>Bot belum terdeteksi di channel manapun.</b>\n\n"
                "Pastikan Anda sudah menambahkan bot sebagai <b>Admin</b> di channel Anda.\n"
                "Setelah itu, tekan /start lagi.",
                parse_mode=enums.ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("📋 Panduan Lengkap", callback_data="ch_add_guide"),
                ]]),
            )
        return

    # ── Konfirmasi channel saat pertama kali ditambahkan ──────────────────────
    if data.startswith("ch_confirm_"):
        if user_id != OWNER_ID:
            return await query.answer("Akses Ditolak!", show_alert=True)
        if data == "ch_confirm_no":
            await query.message.edit_text(
                "✅ Channel disimpan tapi belum dijadikan tujuan menfess.\n"
                "Atur kapan saja di <b>⚙️ Pengaturan Bot → 📢 Kelola Channel</b>.",
                parse_mode=enums.ParseMode.HTML,
            )
            return await query.answer()
        idx      = int(data.split("_", 2)[2])
        cfg      = load_json(CONFIG_FILE)
        channels = get_channels(cfg)
        if not (0 <= idx < len(channels)):
            return await query.answer("Index channel tidak valid.", show_alert=True)
        for i, c in enumerate(channels):
            c["active"] = (i == idx)
        cfg["channels"]       = channels
        cfg["target_channel"] = channels[idx]["id"]
        save_json(CONFIG_FILE, cfg)
        ch_name = channels[idx].get("name", channels[idx]["id"])
        await query.message.edit_text(
            f"🎉 <b>Channel Menfess Aktif:</b>\n📌 {html.escape(ch_name)}\n\nMenu admin siap digunakan!",
            parse_mode=enums.ParseMode.HTML,
        )
        await client.send_message(
            OWNER_ID,
            "✅ Setup selesai! Selamat menggunakan bot menfess Anda.",
            reply_markup=CLONE_ADMIN_KB,
        )
        return

    # ── Aktifkan channel dari daftar ───────────────────────────────────────────
    if data.startswith("ch_set_"):
        if user_id != OWNER_ID:
            return await query.answer("Akses Ditolak!", show_alert=True)
        idx      = int(data.split("_", 2)[2])
        cfg      = load_json(CONFIG_FILE)
        channels = get_channels(cfg)
        if not (0 <= idx < len(channels)):
            return await query.answer("Index channel tidak valid.", show_alert=True)
        for i, c in enumerate(channels):
            c["active"] = (i == idx)
        cfg["channels"]       = channels
        cfg["target_channel"] = channels[idx]["id"]
        save_json(CONFIG_FILE, cfg)
        await query.answer(f"✅ {channels[idx].get('name','Channel')} dijadikan channel aktif!")
        await query.message.edit_reply_markup(reply_markup=build_channel_list_kb(channels))
        return

    # ── Hapus channel dari daftar ─────────────────────────────────────────────
    if data.startswith("ch_del_"):
        if user_id != OWNER_ID:
            return await query.answer("Akses Ditolak!", show_alert=True)
        idx      = int(data.split("_", 2)[2])
        cfg      = load_json(CONFIG_FILE)
        channels = get_channels(cfg)
        if not (0 <= idx < len(channels)):
            return await query.answer("Index channel tidak valid.", show_alert=True)
        removed_ch = channels.pop(idx)
        if cfg.get("target_channel") == removed_ch.get("id"):
            cfg.pop("target_channel", None)
            if channels:
                channels[0]["active"]  = True
                cfg["target_channel"]  = channels[0]["id"]
        cfg["channels"] = channels
        save_json(CONFIG_FILE, cfg)
        ch_name = removed_ch.get("name", removed_ch.get("id", "?"))
        if not channels:
            await query.message.edit_text(
                f"🗑 <b>{html.escape(ch_name)}</b> dihapus.\n\n"
                "⚠️ <b>Tidak ada channel tersisa.</b>\n"
                "Tambahkan bot ke channel baru sebagai admin untuk mendaftarkan channel.",
                parse_mode=enums.ParseMode.HTML,
            )
        else:
            await query.answer(f"🗑 {ch_name} dihapus.")
            await query.message.edit_reply_markup(reply_markup=build_channel_list_kb(channels))
        return

    # ── Buka panel kelola channel ──────────────────────────────────────────────
    if data == "cp_ch":
        if user_id != OWNER_ID:
            return await query.answer("Akses Ditolak!", show_alert=True)
        await query.answer()
        cfg      = load_json(CONFIG_FILE)
        channels = get_channels(cfg)
        active_ch = get_active_channel(cfg)
        if not channels:
            await query.message.reply_text(
                "📢 <b>Daftar Channel Kosong</b>\n\n"
                "Tambahkan bot ini sebagai admin di channel Anda, bot akan otomatis mendeteksinya.",
                parse_mode=enums.ParseMode.HTML,
            )
        else:
            active_name = next((c["name"] for c in channels if c.get("id") == active_ch), "-")
            await query.message.reply_text(
                f"📢 <b>Kelola Channel Menfess</b>\n\n"
                f"Channel aktif: <b>{html.escape(active_name)}</b>\n\n"
                "Pilih channel untuk diaktifkan atau hapus:",
                reply_markup=build_channel_list_kb(channels),
                parse_mode=enums.ParseMode.HTML,
            )
        return

    # ── Fallback ───────────────────────────────────────────────────────────────
    try:
        await query.answer()
    except Exception:
        pass
