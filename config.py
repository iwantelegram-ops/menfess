import os
import logging
from pathlib import Path

# ── Load .env file (support Termux & semua environment) ───────────────────────
try:
    import dns.resolver
    dns.resolver.default_resolver = dns.resolver.Resolver(configure=False)
    dns.resolver.default_resolver.nameservers = ['8.8.8.8', '8.8.4.4']
        
    from dotenv import load_dotenv
    # Cari .env di folder yang sama dengan file ini
    _env_path = Path(__file__).parent / ".env"
    if _env_path.exists():
        load_dotenv(dotenv_path=_env_path)
        logging.info(f"[Config] .env berhasil dimuat dari {_env_path}")
    else:
        load_dotenv()  # fallback: cari .env di CWD
except ImportError:
    logging.warning("[Config] python-dotenv tidak terinstall. Variabel lingkungan dibaca dari sistem.")

# ── Pyrogram MTProto credentials ──────────────────────────────────────────────
API_ID   = int(os.getenv("API_ID", "0") or "0")
API_HASH = os.getenv("API_HASH", "")

# ── Bot credentials ────────────────────────────────────────────────────────────
TOKEN = os.getenv("BOT_TOKEN", "")

# ── Owner & channel defaults ───────────────────────────────────────────────────
DEFAULT_CHANNEL = os.getenv("CH_ID", "")
MAIN_OWNER_ID   = int(os.getenv("MAIN_OWNER_ID", "8562224386"))
OWNER_ID        = int(os.getenv("OWN_ID", str(MAIN_OWNER_ID)))

# ── Clone system ───────────────────────────────────────────────────────────────
IS_CLONE = os.getenv("IS_CLONE", "False") == "True"
suffix   = f"_{OWNER_ID}" if IS_CLONE else ""

# ── Persistent data files ──────────────────────────────────────────────────────
USER_DATA_FILE   = f"user_stats{suffix}.json"
CONFIG_FILE      = f"bot_config{suffix}.json"
USERS_LIST_FILE  = f"all_users{suffix}.json"
BAN_FILE         = f"banned_users{suffix}.json"
CLONE_DB         = "permanent_clones.json"
MENFESS_TRACK    = f"menfess_track{suffix}.json"

# ── Default template (modern channel card) ────────────────────────────────────
DEFAULT_TEMPLATE = (
    "━━━━━━━━━━━━━━━━━━━━━━━━\n"
    "📮  <b>M E N F E S S</b>\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    "{TEXT}\n\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━\n"
    "✍️ <i>Dikirim oleh</i> {SENDER}"
)

# ── Validasi konfigurasi wajib ─────────────────────────────────────────────────
def validate_config():
    errors = []
    if not TOKEN:
        errors.append("BOT_TOKEN belum diset di .env!")
    if API_ID == 0:
        errors.append("API_ID belum diset di .env!")
    if not API_HASH:
        errors.append("API_HASH belum diset di .env!")
    if errors:
        for e in errors:
            logging.error(f"[Config] ❌ {e}")
        raise SystemExit(
            "\n\n❌ Konfigurasi tidak lengkap!\n"
            + "\n".join(f"  • {e}" for e in errors)
            + "\n\nEdit file .env lalu jalankan ulang bot."
        )

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
