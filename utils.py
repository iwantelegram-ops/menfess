import json, os, re, html
from pyrogram import enums
from pyrogram.types import ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from config import BAN_FILE, CONFIG_FILE, MENFESS_TRACK

# ── Keyboards ──────────────────────────────────────────────────────────────────
USER_KB = ReplyKeyboardMarkup(
    [['📝 Tulis Menfess', '🤖 Buat/Kelola Clone'],
     ['💳 Isi Kuota',     '📊 Info Akun']],
    resize_keyboard=True,
)
ADMIN_KB = ReplyKeyboardMarkup(
    [['⚙️ Pengaturan Bot', '📢 Broadcast'],
     ['🔓 Mode Gratis',    '🔒 Mode Bayar'],
     ['🤖 Buat/Kelola Clone', '👤 Mode User']],
    resize_keyboard=True,
)
CLONE_ADMIN_KB = ReplyKeyboardMarkup(
    [['⚙️ Pengaturan Bot', '📢 Broadcast'],
     ['🔓 Mode Gratis',    '🔒 Mode Bayar'],
     ['🤖 Buat/Kelola Clone', '👤 Mode User']],
    resize_keyboard=True,
)
MODE_MENFESS_KB = ReplyKeyboardMarkup(
    [['👤 Kirim Anonim', '👁️ Tampilkan Nama'],
     ['❌ Batal']],
    resize_keyboard=True,
)
OWNER_USER_MODE_KB = ReplyKeyboardMarkup(
    [['📝 Tulis Menfess', '🤖 Buat/Kelola Clone'],
     ['🔙 Admin Menu',    '📊 Info Akun']],
    resize_keyboard=True,
)

# ── In-memory user state ───────────────────────────────────────────────────────
USER_STATES: dict = {}

def get_ud(uid: int) -> dict:
    if uid not in USER_STATES:
        USER_STATES[uid] = {}
    return USER_STATES[uid]

def clear_ud(uid: int) -> None:
    USER_STATES.pop(uid, None)

# ── JSON helpers ───────────────────────────────────────────────────────────────
def load_json(file_name: str):
    is_list_file = any(x in file_name for x in ["all_users", "clones", "permanent", "banned"])
    default = [] if is_list_file else {}
    if not os.path.exists(file_name):
        with open(file_name, "w") as f:
            json.dump(default, f)
        return default
    with open(file_name, "r") as f:
        try:
            data = json.load(f)
            return data if data is not None else default
        except Exception:
            return default

def save_json(file_name: str, data) -> None:
    with open(file_name, "w") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

# ── User helpers ───────────────────────────────────────────────────────────────
def is_banned(uid) -> bool:
    return str(uid) in load_json(BAN_FILE)

def get_channels(cfg: dict) -> list:
    return cfg.get("channels", [])

def get_active_channel(cfg: dict) -> str | None:
    # Coba target_channel dulu; kalau kosong, ambil channel pertama yang aktif dari list
    target = cfg.get("target_channel") or None
    if target:
        return target
    channels = cfg.get("channels", [])
    for ch in channels:
        if ch.get("active"):
            return ch.get("id") or None
    # Terakhir: pakai channel pertama di list walau belum di-set aktif
    if channels:
        return channels[0].get("id") or None
    return None

def clone_has_channel(cfg: dict) -> bool:
    return bool(get_channels(cfg))

# ── Channel list keyboard ──────────────────────────────────────────────────────
def build_channel_list_kb(channels: list, show_delete: bool = True) -> InlineKeyboardMarkup:
    rows = []
    for i, ch in enumerate(channels):
        ch_name   = ch.get("name", ch.get("id", ""))
        is_active = ch.get("active", False)
        label_act = "✅ Aktif" if is_active else "▶ Aktifkan"
        row = [
            InlineKeyboardButton(f"{'📌 ' if is_active else ''}{ch_name}", callback_data="n"),
            InlineKeyboardButton(label_act, callback_data=f"ch_set_{i}"),
        ]
        if show_delete:
            row.append(InlineKeyboardButton("🗑", callback_data=f"ch_del_{i}"))
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)

# ── Social media link extractor ────────────────────────────────────────────────
def parse_and_extract_links(raw_text: str) -> tuple[str, str]:
    url_pattern = (
        r'((?:https?://|www\.)[^\s]+'
        r'|(?:instagram\.com|facebook\.com|fb\.com|fb\.watch|fb\.gg'
        r'|twitter\.com|x\.com|tiktok\.com|vt\.tiktok\.com'
        r'|youtube\.com|youtu\.be|threads\.net|linkedin\.com'
        r'|pinterest\.com|pin\.it|snapchat\.com|twitch\.tv'
        r'|discord\.gg|discord\.com|reddit\.com|t\.me|telegram\.me'
        r'|wa\.me|spotify\.com|soundcloud\.com|github\.com|medium\.com)[^\s]*)'
    )
    urls       = re.findall(url_pattern, raw_text, re.IGNORECASE)
    clean_text = raw_text
    for u in urls:
        clean_text = clean_text.replace(u, "")
    clean_text = re.sub(r"\s+", " ", clean_text).strip()

    categories = {
        "facebook":   r"facebook\.com|fb\.com|fb\.watch|fb\.gg",
        "instagram":  r"instagram\.com|ig\.me",
        "x (twitter)":r"twitter\.com|x\.com",
        "tiktok":     r"tiktok\.com|vt\.tiktok\.com",
        "youtube":    r"youtube\.com|youtu\.be",
        "threads":    r"threads\.net",
        "linkedin":   r"linkedin\.com",
        "pinterest":  r"pinterest\.com|pin\.it",
        "snapchat":   r"snapchat\.com",
        "twitch":     r"twitch\.tv",
        "discord":    r"discord\.gg|discord\.com",
        "reddit":     r"reddit\.com",
        "telegram":   r"t\.me|telegram\.me",
        "whatsapp":   r"wa\.me|api\.whatsapp\.com",
        "spotify":    r"spotify\.com",
        "soundcloud": r"soundcloud\.com",
        "github":     r"github\.com",
        "medium":     r"medium\.com",
    }

    grouped: dict[str, list[str]] = {}
    for url in urls:
        href    = url if url.startswith("http") else "https://" + url
        matched = False
        for cat, pattern in categories.items():
            if re.search(pattern, url, re.IGNORECASE):
                grouped.setdefault(cat, []).append(href)
                matched = True
                break
        if not matched:
            grouped.setdefault("link", []).append(href)

    sosmed_text = ""
    if grouped:
        sosmed_text += "\n\n"
        links_list = []
        for cat, links in grouped.items():
            for i, href in enumerate(links):
                label = cat if len(links) == 1 else f"{cat} {i + 1}"
                links_list.append(f"🔗 <a href='{href}'>{label}</a>")
        sosmed_text += "\n".join(links_list)

    return clean_text, sosmed_text

# ── Post link builder ──────────────────────────────────────────────────────────
def build_post_link(target_id: str, post_id: int) -> str:
    """
    Bangun link langsung ke postingan channel.
    Mendukung channel private (-100...) dan public (@username).
    """
    tid = target_id.strip()
    if tid.startswith("-100"):
        # Private channel: t.me/c/{channel_id_tanpa_-100}/{post_id}
        return f"https://t.me/c/{tid[4:]}/{post_id}"
    elif tid.startswith("@"):
        # Public channel dengan username
        return f"https://t.me/{tid.lstrip('@')}/{post_id}"
    else:
        # Numerik tanpa prefix — pakai format /c/
        return f"https://t.me/c/{tid.lstrip('-')}/{post_id}"

# ── Menfess tracking (untuk notifikasi komentar) ───────────────────────────────
def save_menfess_track(channel_id: str, post_id: int, sender_id: int,
                       sender_name: str, post_link: str) -> None:
    """Simpan pemetaan channel_id+post_id → pengirim menfess."""
    tracking = load_json(MENFESS_TRACK)
    key = f"{channel_id}_{post_id}"
    tracking[key] = {
        "sender_id":   sender_id,
        "sender_name": sender_name,
        "post_link":   post_link,
    }
    # Batasi maksimal 5000 entri (cegah file tumbuh tak terbatas)
    if len(tracking) > 5000:
        keys_sorted = list(tracking.keys())
        for old_key in keys_sorted[:len(tracking) - 4000]:
            tracking.pop(old_key, None)
    save_json(MENFESS_TRACK, tracking)

def get_menfess_track(channel_id: str, post_id: int) -> dict | None:
    """Ambil data pengirim menfess berdasarkan channel_id dan post_id."""
    tracking = load_json(MENFESS_TRACK)
    return tracking.get(f"{channel_id}_{post_id}")

# ── Channel setup guide ────────────────────────────────────────────────────────
async def ask_channel_setup(client, chat_id: int, first_name: str) -> None:
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("➕ Tambahkan Channel", callback_data="ch_add_guide")
    ]])
    await client.send_message(
        chat_id,
        (
            f"👋 <b>Halo, {html.escape(first_name)}!</b>\n\n"
            "Bot clone Anda belum dikaitkan ke channel manapun.\n\n"
            "<b>Cara menambahkan channel:</b>\n"
            "1. Tambahkan bot ini sebagai <b>Admin</b> di channel Anda.\n"
            "2. Bot akan otomatis mendeteksi dan menanyakan konfirmasi.\n\n"
            "Atau klik tombol di bawah untuk panduan lengkap:"
        ),
        reply_markup=kb,
        parse_mode=enums.ParseMode.HTML,
    )
