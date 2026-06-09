# 📮 Bot Menfess Telegram

Bot Telegram untuk mengirim pesan anonim (menfess) ke channel, dengan fitur clone, kuota, notifikasi komentar, dan banyak lagi.

---

## 🚀 Cara Install di Termux (HP Android)

### 1. Install dependensi sistem
```bash
pkg update && pkg upgrade -y
pkg install python git -y
```

### 2. Clone / download project
```bash
# Jika dari git:
git clone <repo_url>
cd bot_project

# Atau ekstrak ZIP:
unzip bot_project.zip
cd bot_project-main
```

### 3. Setup konfigurasi
```bash
cp .env.example .env
nano .env
```
Isi nilai berikut di `.env`:
- `API_ID` dan `API_HASH` — dari https://my.telegram.org/apps
- `BOT_TOKEN` — dari @BotFather
- `OWN_ID` — ID Telegram Anda (cek via @userinfobot)

### 4. Install Python packages
```bash
pip install -r requirements.txt
```

### 5. Jalankan bot
```bash
bash start.sh
```
Atau langsung:
```bash
python3 main.py
```

---

## ⚙️ Variabel .env

| Variabel | Wajib | Keterangan |
|---|---|---|
| `API_ID` | ✅ | Dari my.telegram.org |
| `API_HASH` | ✅ | Dari my.telegram.org |
| `BOT_TOKEN` | ✅ | Dari @BotFather |
| `OWN_ID` | ✅ | ID Telegram owner bot |
| `CH_ID` | ❌ | Channel default (bisa diset via bot) |
| `MAIN_OWNER_ID` | ❌ | ID developer utama |

---

## 📁 Struktur File

```
bot_project/
├── main.py          — Entry point utama
├── config.py        — Konfigurasi & load .env
├── utils.py         — Helper functions & keyboard
├── .env             — Konfigurasi rahasia (buat dari .env.example)
├── .env.example     — Template konfigurasi
├── requirements.txt — Daftar dependencies Python
├── start.sh         — Script start untuk Termux
└── plugins/
    ├── start.py         — Handler /start
    ├── channels.py      — Deteksi channel otomatis
    ├── messages.py      — Handler pesan & menfess
    ├── callback.py      — Handler tombol inline
    └── notifications.py — Notifikasi komentar
```

---

## 🔧 Fitur

- ✅ Kirim menfess anonim / tampilkan nama
- ✅ Support foto & video
- ✅ Deteksi link sosial media otomatis
- ✅ Sistem kuota (gratis / berbayar)
- ✅ Notifikasi komentar ke pengirim
- ✅ Clone bot untuk multi-channel
- ✅ Broadcast ke semua user
- ✅ Ban/unban user
- ✅ Edit template post & QRIS

---

## ❓ Troubleshooting

**Bot tidak jalan / error `.env`**
→ Pastikan file `.env` sudah ada dan terisi lengkap.

**"API_ID invalid"**
→ Periksa nilai `API_ID` di `.env`, harus angka (contoh: `12345678`).

**Bot tidak bisa post ke channel**
→ Pastikan bot sudah dijadikan **Admin** di channel dengan hak **Post Messages**.

**Error `ModuleNotFoundError: pyrogram`**
→ Jalankan: `pip install -r requirements.txt`
