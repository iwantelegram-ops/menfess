"""
database_manager.py
────────────────────
Sistem database otomatis: MongoDB (cloud) ↔ Lokal JSON (Termux)

LOGIKA STARTUP:
  1. Coba koneksi MongoDB (MONGO_URI di .env)
  2. Jika BERHASIL → migrasi data lokal ke Mongo (merge, duplikat dihapus, sisa 1)
               → hapus file lokal yang sudah dimigrasikan
               → semua read/write pakai Mongo
  3. Jika GAGAL/kosong → semua read/write pakai file JSON lokal

LOGIKA JIKA MONGO AKTIF LAIN HARI:
  - Saat bot restart dan Mongo kembali tersedia,
    data lokal yang tersisa (hasil save saat offline) otomatis dimigrasikan kembali.
  - Duplikat: data lokal selalu menang (lebih baru) → merge dengan local_data.update(mongo_data)
    kemudian simpan hasil merge, file lokal dihapus.

FILE YANG TIDAK PERNAH DIHAPUS/DIMIGRASIKAN:
  - *.session  (Pyrogram session, bukan JSON)
  - Semua *.json DIMIGRASI termasuk permanent_clones dan bot_config

TIPE DATA PER FILE:
  - all_users*.json, banned_users*.json, permanent_clones.json → LIST
  - sisanya → DICT
"""

import os
import json
import logging
from pathlib import Path

# ── Nama file yang tidak boleh dimigrasikan / dihapus ─────────────────────────
# Semua file JSON dimigrasi ke Mongo termasuk permanent_clones dan bot_config
_NO_MIGRATE = set()
_NO_MIGRATE_PREFIX = ()

# ── Tipe data per nama file ────────────────────────────────────────────────────
_LIST_KEYWORDS = ("all_users", "clones", "permanent", "banned")

def _is_list_file(filename: str) -> bool:
    return any(kw in filename for kw in _LIST_KEYWORDS)

def _default_for(filename: str):
    return [] if _is_list_file(filename) else {}

def _should_skip(filename: str) -> bool:
    """True jika file ini tidak boleh dimigrasikan ke Mongo."""
    if filename in _NO_MIGRATE:
        return True
    if any(filename.startswith(p) for p in _NO_MIGRATE_PREFIX):
        return True
    return False

# ── Fix DNS Termux ─────────────────────────────────────────────────────────────
try:
    import dns.resolver
    dns.resolver.default_resolver = dns.resolver.Resolver(configure=False)
    dns.resolver.default_resolver.nameservers = ["8.8.8.8", "8.8.4.4"]
except Exception:
    pass

try:
    from pymongo import MongoClient as _MongoClient
except ImportError:
    _MongoClient = None


# ══════════════════════════════════════════════════════════════════════════════
class DatabaseManager:
# ══════════════════════════════════════════════════════════════════════════════

    def __init__(self):
        self.local_dir    = Path(".")
        self.mongo_client = None
        self.db           = None

        uri = os.getenv("MONGO_URI", "").strip()

        if uri and _MongoClient:
            try:
                client = _MongoClient(uri, serverSelectionTimeoutMS=4000)
                client.admin.command("ping")          # tes koneksi nyata
                db_name   = uri.split("/")[-1].split("?")[0].strip() or "menfess_bot"
                self.mongo_client = client
                self.db           = client[db_name]
                print(f"[DB] ✅ MongoDB aktif  →  database: {db_name}")
                self._migrate_local_to_mongo()        # sinkronisasi saat startup
                self._hijack_utils()
            except Exception as exc:
                logging.error(f"[DB] ❌ MongoDB gagal ({exc}) → pakai lokal JSON.")
                self.mongo_client = None
                self.db           = None
        else:
            if not uri:
                print("[DB] ℹ️  MONGO_URI tidak diset → pakai lokal JSON.")
            elif not _MongoClient:
                print("[DB] ⚠️  pymongo tidak terinstall → pakai lokal JSON.")

    # ── Property ───────────────────────────────────────────────────────────────
    @property
    def mode(self) -> str:
        return "mongodb" if self.db is not None else "local"

    # ── Migrasi lokal → Mongo ──────────────────────────────────────────────────
    def _migrate_local_to_mongo(self):
        """
        Saat bot start dan Mongo tersedia:
        - Cari semua *.json di folder bot
        - Skip file yang masuk daftar _NO_MIGRATE
        - Merge: data lokal menang atas data Mongo (lokal lebih baru)
          • DICT  : mongo_data.update(local_data)   → key lokal timpa key Mongo
          • LIST  : gabung + deduplikat, urutan lokal di depan
        - Simpan hasil merge ke Mongo
        - Hapus file lokal (sudah aman di cloud)
        """
        local_files = [f for f in self.local_dir.glob("*.json")
                       if not _should_skip(f.name)]

        if not local_files:
            print("[DB] ℹ️  Tidak ada data lokal yang perlu dimigrasikan.")
            return

        print(f"[DB] 🔄 Memulai migrasi {len(local_files)} file lokal → MongoDB...")
        migrated = 0

        for filepath in local_files:
            fname = filepath.name
            try:
                # --- Baca data lokal ---
                with open(filepath, "r", encoding="utf-8") as fh:
                    local_raw = json.load(fh)
            except Exception as exc:
                logging.warning(f"[DB] Gagal baca {fname}: {exc} — dilewati.")
                continue

            # Pastikan tipe konsisten
            if _is_list_file(fname):
                local_data = local_raw if isinstance(local_raw, list) else []
            else:
                local_data = local_raw if isinstance(local_raw, dict) else {}

            col_name = fname.replace(".json", "")
            col      = self.db[col_name]

            try:
                # --- Ambil data Mongo yang sudah ada ---
                doc = col.find_one({"_id": "main_data"})
                mongo_raw = doc.get("data") if doc else None

                # --- Merge sesuai tipe ---
                if _is_list_file(fname):
                    mongo_list  = mongo_raw if isinstance(mongo_raw, list) else []
                    # Gabung, data lokal di depan, duplikat dihapus (pertahankan yg lokal)
                    seen   = []
                    merged = []
                    for item in local_data + mongo_list:
                        # Serialisasi ke string untuk deduplikat universal
                        key = json.dumps(item, sort_keys=True, ensure_ascii=False)
                        if key not in seen:
                            seen.append(key)
                            merged.append(item)
                else:
                    mongo_dict = mongo_raw if isinstance(mongo_raw, dict) else {}
                    merged     = {**mongo_dict, **local_data}   # lokal menang

                # --- Simpan ke Mongo ---
                col.update_one(
                    {"_id": "main_data"},
                    {"$set": {"data": merged}},
                    upsert=True,
                )

                # --- Hapus file lokal (sudah aman) ---
                filepath.unlink()
                migrated += 1
                print(f"[DB] ✅ {fname} → MongoDB  (lokal dihapus)")

            except Exception as exc:
                logging.error(f"[DB] Gagal migrasi {fname}: {exc} — file lokal dipertahankan.")

        if migrated:
            print(f"[DB] 🎉 Migrasi selesai: {migrated}/{len(local_files)} file berhasil.")
        else:
            print("[DB] ⚠️  Tidak ada file yang berhasil dimigrasikan.")

    # ── CRUD ──────────────────────────────────────────────────────────────────
    def save_data(self, filename: str, data) -> bool:
        """
        Simpan data.
        - Mode Mongo  : tulis ke collection Mongo, TIDAK menulis ke lokal.
        - Mode lokal  : tulis ke file JSON.
        - Jika Mongo gagal saat write: fallback tulis lokal sebagai backup,
          sehingga saat Mongo kembali online data bisa dimigrasikan ulang.
        """
        if self.mode == "mongodb":
            try:
                col_name = filename.replace(".json", "")
                self.db[col_name].update_one(
                    {"_id": "main_data"},
                    {"$set": {"data": data}},
                    upsert=True,
                )
                return True
            except Exception as exc:
                logging.error(f"[DB] Mongo write gagal ({exc}) → fallback lokal.")
                # Jatuh ke write lokal sebagai backup

        # Lokal (mode lokal ATAU fallback dari Mongo gagal)
        try:
            filepath = self.local_dir / filename
            with open(filepath, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=4, ensure_ascii=False)
            return True
        except Exception as exc:
            logging.error(f"[DB] Gagal tulis lokal {filename}: {exc}")
            return False

    def load_data(self, filename: str, default_factory=dict):
        """
        Baca data.
        - Mode Mongo  : baca dari Mongo.
        - Mode lokal  : baca dari file JSON.
        - Jika Mongo gagal baca: coba fallback ke file lokal jika ada.
        """
        if self.mode == "mongodb":
            try:
                col_name = filename.replace(".json", "")
                doc = self.db[col_name].find_one({"_id": "main_data"})
                if doc and "data" in doc:
                    val = doc["data"]
                    return val if val is not None else default_factory()
            except Exception as exc:
                logging.warning(f"[DB] Mongo read gagal ({exc}) → fallback lokal.")
                # Jatuh ke baca lokal

        filepath = self.local_dir / filename
        if filepath.exists():
            try:
                with open(filepath, "r", encoding="utf-8") as fh:
                    val = json.load(fh)
                    return val if val is not None else default_factory()
            except Exception:
                return default_factory()
        return default_factory()

    # ── Inject ke utils ────────────────────────────────────────────────────────
    def _hijack_utils(self):
        """
        Override utils.load_json / utils.save_json dengan versi DB-aware.
        Deteksi tipe default (list vs dict) otomatis dari nama file,
        sama persis dengan perilaku asli load_json di utils.py.
        """
        try:
            import utils
            _load = self.load_data
            _save = self.save_data

            def _compat_load(file_name: str):
                factory = list if _is_list_file(file_name) else dict
                result = _load(file_name, default_factory=factory)
                # Jika Mongo mengembalikan default kosong, coba fallback ke file lokal
                # (bisa terjadi saat collection belum ada atau data kosong)
                empty = factory()
                if result == empty:
                    filepath = self.local_dir / file_name
                    if filepath.exists():
                        try:
                            with open(filepath, "r", encoding="utf-8") as fh:
                                local_val = json.load(fh)
                            if local_val:
                                logging.info(f"[DB] Fallback lokal untuk {file_name}")
                                return local_val
                        except Exception:
                            pass
                return result

            utils.load_json = _compat_load
            utils.save_json = _save
            print("[DB] 🛡️  utils.load_json & save_json → MongoDB aktif.")
        except Exception as exc:
            logging.error(f"[DB] _hijack_utils gagal: {exc}")


# ── Inisialisasi singleton ─────────────────────────────────────────────────────
DB = DatabaseManager()
