import os, sys, subprocess, logging, shutil
from pyrogram import Client
from config import validate_config, API_ID, API_HASH, TOKEN, IS_CLONE, OWNER_ID, CLONE_DB, suffix
from utils import load_json, save_json

if __name__ == '__main__':
    validate_config()

    if not IS_CLONE:
        clones = load_json(CLONE_DB)
        if not isinstance(clones, list):
            clones = []
        updated_clones = []
        base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))

        for c in clones:
            try:
                token = c.get('token', '')
                owner = c.get('owner', OWNER_ID)
                if not token:
                    continue

                # Tiap clone punya subfolder sendiri → hindari SQLite database locked
                clone_dir = os.path.join(base_dir, f"clone_{owner}_{token.split(':')[0]}")
                os.makedirs(clone_dir, exist_ok=True)
                for item in ["main.py", "config.py", "utils.py", "plugins", "requirements.txt", "database_manager.py"]:
                    src = os.path.join(base_dir, item)
                    dst = os.path.join(clone_dir, item)
                    if os.path.isdir(src):
                        if not os.path.exists(dst):
                            shutil.copytree(src, dst)
                    elif os.path.isfile(src) and not os.path.exists(dst):
                        shutil.copy2(src, dst)

                env = os.environ.copy()
                env["BOT_TOKEN"] = token
                env["OWN_ID"]    = str(owner)
                env["IS_CLONE"]  = "True"
                env.pop("CH_ID", None)

                proc = subprocess.Popen(
                    [sys.executable, os.path.join(clone_dir, "main.py")],
                    env=env,
                    cwd=clone_dir,
                )
                c['pid'] = proc.pid
                updated_clones.append(c)
                logging.info(f"Auto-Boot Clone {token[:10]}... PID: {proc.pid} dir: {clone_dir}")
            except Exception as e:
                logging.error(f"Gagal memuat boot-clone: {e}")
        save_json(CLONE_DB, updated_clones)

    # ── Memicu Pengecekan Database Saat Inisialisasi Logger Siap ────────────────
    try:
        from database_manager import DB
        print(f"\n[DATABASE STATUS] -> Mode database saat ini: {DB.mode.upper()}\n")
        logging.info(f"[Database] Mode database yang aktif saat ini: {DB.mode.upper()}")
    except ImportError:
        print("\n[DATABASE ERROR] -> Gagal memuat database_manager.py!\n")

    app = Client(
        f"menfess_session{suffix}",
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=TOKEN,
        plugins=dict(root="plugins"),
    )

    app.run()
